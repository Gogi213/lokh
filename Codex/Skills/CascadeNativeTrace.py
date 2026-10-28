"""Bounded assessment of the selected Codex native rollout tree.

Only records belonging to the identified fixture run are retained. Model prose,
agent messages and requested settings are not evidence of execution.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import uuid

from . import CascadeEval

MAX_LINE = 1024 * 1024
MAX_HEADER = 256 * 1024
MAX_TRACE = 8 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
MAX_HEADER_TOTAL = 16 * 1024 * 1024
MAX_CANDIDATES = 4096
MAX_SESSIONS = 8
MAX_PROCESS_SECONDS = 5
MAX_OBS_ITEMS = 512
MAX_RECORDS = 4096
MAX_CONTEXTS = 128
MAX_CALLS = 512
MAX_PATH_PARTS = 128
MAX_PATCH_LINES = 8192
EXPECTED = {
    '/root': ('primary', None), '/root/research': ('research', '/root'),
    '/root/design': ('design', '/root'), '/root/lead': ('lead', '/root'),
    '/root/lead/calc': ('mechanical', '/root/lead'),
    '/root/lead/display': ('mechanical', '/root/lead'),
    '/root/review': ('review', '/root'),
}
CHILDREN = [{'task_name': 'calc', 'files': ['calc.py']},
            {'task_name': 'display', 'files': ['display.py']}]
ANSWER = 'Empty input produces total 0; bool values are rejected.'
WORKER_SPECS = ({'operation': 'sum', 'empty': 0, 'reject_boolean': True},
                {'format': 'total: <value>'})


class _BudgetExceeded(Exception):
    pass


def _check_budget(deadline):
    if time.monotonic() > deadline:
        raise _BudgetExceeded('native assessment time budget exceeded')


def _checked(values, deadline):
    for value in values:
        _check_budget(deadline)
        yield value


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp missing')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timestamp lacks timezone')
    return result.timestamp()


def _json_object(value):
    if not isinstance(value, str):
        raise ValueError('JSON argument is not text')
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ValueError('JSON argument is not an object')
    return result


def _no_symlinks(path, deadline):
    path = Path(os.path.abspath(path))
    if len(path.parents) > MAX_PATH_PARTS:
        raise _BudgetExceeded('native path depth budget exceeded')
    for item in (path, *path.parents):
        _check_budget(deadline)
        if item.is_symlink():
            raise ValueError('symlink in path')
    return path


def _read(path, limit):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError('not a regular file')
        data = f.read(limit + 1)
    if len(data) > limit:
        raise _BudgetExceeded('native trace size limit exceeded')
    return data


def _first(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError('not a regular file')
        line = f.readline(MAX_HEADER + 1)
    return line


def _metadata(line):
    if len(line) > MAX_HEADER:
        raise _BudgetExceeded('native metadata size limit exceeded')
    event = json.loads(line)
    if not isinstance(event, dict) or event.get('type') != 'session_meta' or not isinstance(event.get('payload'), dict):
        raise ValueError('missing session metadata')
    return event


def _output_text(value, deadline):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        if len(value) > MAX_RECORDS:
            raise _BudgetExceeded('native output item budget exceeded')
        pieces = []
        for item in value:
            _check_budget(deadline)
            if not isinstance(item, dict) or item.get('type') not in ('text', 'input_text') or not isinstance(item.get('text'), str):
                raise ValueError('unsupported tool output')
            pieces.append(item['text'])
        return ''.join(pieces)
    raise ValueError('unsupported tool output')


def _command_output(value):
    """Accept structured CLI tool results or the supported completed text envelope."""
    try:
        obj = json.loads(value)
    except (ValueError, TypeError):
        obj = None
    if isinstance(obj, dict) and type(obj.get('exit_code')) is int and isinstance(obj.get('output'), str) and not obj.get('session_id'):
        return obj['exit_code'], obj['output']
    match = re.fullmatch(r'(?:Chunk ID: [^\n]*\n)?Wall time: [^\n]*\nProcess exited with code (-?\d+)\n(?:Final )?Output:\n([\s\S]*)', value)
    if match:
        return int(match.group(1)), match.group(2)
    raise ValueError('unrecognized completed command output')


def _patch_paths(value, fixture, deadline):
    if not isinstance(value, str) or not value.startswith('*** Begin Patch\n') or not value.rstrip().endswith('*** End Patch'):
        raise ValueError('unsupported patch')
    names = []
    lines = value.splitlines()
    if len(lines) > MAX_PATCH_LINES:
        raise _BudgetExceeded('native patch line budget exceeded')
    for line in lines:
        _check_budget(deadline)
        match = re.fullmatch(r'\*\*\* (?:Add|Update|Delete) File: (.+)', line)
        move = re.fullmatch(r'\*\*\* Move to: (.+)', line)
        if not match and not move:
            continue
        name = (match or move).group(1)
        path = PurePosixPath(name)
        if not name or '\\' in name or '..' in path.parts:
            raise ValueError('unsafe patch path')
        if path.is_absolute():
            try:
                path = path.relative_to(PurePosixPath(str(fixture)))
            except ValueError as exc:
                raise ValueError('patch outside fixture') from exc
        if len(path.parts) != 1 or str(path) not in {'app.py', 'calc.py', 'display.py'}:
            raise ValueError('patch outside allowed files')
        _no_symlinks(fixture / str(path), deadline)
        names.append(str(path))
    if not names:
        raise ValueError('patch lacks literal file headers')
    return names


def _observe_items(name, ident, fixture, contexts, finished, invalid_turns, records, items, item_ids, deadline, observations, gaps):
    """Collect selected structured events without treating exec as fully observable."""
    if len(records) > MAX_OBS_ITEMS * 2 or len(items) > MAX_OBS_ITEMS or len(item_ids) > MAX_OBS_ITEMS:
        raise _BudgetExceeded('native observation item budget exceeded')
    calls, outputs = [], {}
    for index, stamp, payload in records:
        _check_budget(deadline)
        kind = payload.get('type')
        if kind in ('custom_tool_call', 'function_call'):
            calls.append((index, stamp, payload))
        elif kind in ('custom_tool_call_output', 'function_call_output'):
            cid = payload.get('call_id')
            if isinstance(cid, str):
                outputs.setdefault(cid, []).append((index, stamp, payload))
    item_counts = {}
    for item_id in item_ids:
        _check_budget(deadline)
        if not isinstance(item_id, str) or not item_id:
            gaps.append('native observation item identity unavailable: ' + name)
            return
        item_counts[item_id] = item_counts.get(item_id, 0) + 1
    for index, stamp, payload in items:
        _check_budget(deadline)
        try:
            item = payload.get('item')
            if not isinstance(item, dict):
                raise ValueError('item is not an object')
            item_id = item.get('id')
            if not isinstance(item_id, str) or not item_id or item_counts.get(item_id) != 1:
                raise ValueError('item identity missing or duplicated')
            turn = payload.get('turn_id')
            if payload.get('thread_id') != ident or not isinstance(turn, str) or turn not in contexts or turn not in finished or turn in invalid_turns:
                raise ValueError('session or turn binding unavailable')
            started, ended = payload.get('started_at_ms'), payload.get('completed_at_ms')
            if type(started) is not int or type(ended) is not int or started < 0 or started > ended:
                raise ValueError('invalid item timestamps')
            lo, hi = started / 1000, ended / 1000
            if not contexts[turn][2] <= lo <= hi <= stamp <= finished[turn]:
                raise ValueError('item outside completed turn')
            active = []
            for call_index, call_stamp, call in calls:
                _check_budget(deadline)
                if call_index >= index:
                    continue
                cid = call.get('call_id')
                matching = outputs.get(cid, []) if isinstance(cid, str) else []
                if len(matching) != 1 or matching[0][0] <= call_index or matching[0][0] > index:
                    active.append((call_index, call_stamp, call, matching))
            if len(active) != 1:
                raise ValueError('exec envelope missing or ambiguous')
            call_index, call_stamp, call, matching = active[0]
            if (len(matching) != 1 or call.get('status') != 'completed' or
                    call.get('type') != 'custom_tool_call' or call.get('name') != 'exec'):
                raise ValueError('exec envelope lacks completed output')
            output_index, output_stamp, output = matching[0]
            if output.get('type') != 'custom_tool_call_output':
                raise ValueError('exec output type mismatch')
            if not isinstance(call.get('call_id'), str) or not call['call_id'] or not call_index < index < output_index:
                raise ValueError('invalid exec call identity or order')
            matching_calls = 0
            for _, _, other in calls:
                _check_budget(deadline)
                if other.get('call_id') == call['call_id']:
                    matching_calls += 1
            if matching_calls != 1:
                raise ValueError('duplicate exec call identity')
            _output_text(output.get('output'), deadline)
            if not contexts[turn][2] <= call_stamp <= lo <= hi <= stamp <= output_stamp <= finished[turn]:
                raise ValueError('item timestamps outside exec envelope')
            for other_index, other_stamp, other in calls:
                _check_budget(deadline)
                if other_index == call_index:
                    continue
                other_id = other.get('call_id')
                other_outputs = outputs.get(other_id, []) if isinstance(other_id, str) else []
                if len(other_outputs) != 1 or other_outputs[0][0] <= other_index:
                    if other_index <= output_index or other_stamp <= output_stamp:
                        raise ValueError('other tool envelope unavailable or ambiguous')
                    continue
                other_end_index, other_end_stamp, _ = other_outputs[0]
                if (other_index <= output_index and other_end_index >= call_index or
                        other_stamp <= output_stamp and other_end_stamp >= call_stamp):
                    raise ValueError('overlapping native tool envelope')
            if item.get('status') != 'completed':
                raise ValueError('item lacks completed status')
            entry = {'agent_path': name, 'kind': None, 'started_at_ms': started,
                     'completed_at_ms': ended, 'exec_started_at': call_stamp,
                     'exec_completed_at': output_stamp}
            if item.get('type') == 'CommandExecution':
                if item.get('cwd') != fixture.as_uri() or item.get('source') != 'unified_exec_startup':
                    raise ValueError('unsupported command cwd or source')
                command = item.get('command')
                if not isinstance(command, list) or len(command) != 3 or command[:2] != ['/bin/bash', '-lc'] or not isinstance(command[2], str):
                    raise ValueError('unsupported command argv')
                if type(item.get('exit_code')) is not int or item['exit_code'] != 0 or not isinstance(item.get('aggregated_output'), str):
                    raise ValueError('command lacks successful exit or output')
                cmd = command[2]
                files = set(CascadeEval.FILES) | set(CascadeEval.SHIPPED_INPUTS.values())
                if cmd == 'python3 -B -m unittest -v test_app':
                    entry.update(kind='test', exit_code=0)
                elif cmd.startswith('cat ') and cmd[4:] in files:
                    path = cmd[4:]
                    _no_symlinks(fixture / path, deadline)
                    entry.update(kind='read', path=path, exit_code=0,
                                 path_check_at_collection=True, symlink_history_unverified=True)
                else:
                    raise ValueError('unsupported observed command')
            elif item.get('type') == 'FileChange':
                changes = item.get('changes')
                if not isinstance(changes, dict) or not changes or len(changes) > 3:
                    raise ValueError('invalid file changes')
                allowed = {str(fixture / path): path for path in ('app.py', 'calc.py', 'display.py')}
                paths = []
                for raw_path, change in changes.items():
                    _check_budget(deadline)
                    if raw_path not in allowed or not isinstance(change, dict) or change.get('type') != 'update' or 'move_path' not in change or change['move_path'] is not None or not isinstance(change.get('unified_diff'), str):
                        raise ValueError('unsupported file change')
                    path = allowed[raw_path]
                    _no_symlinks(fixture / path, deadline)
                    paths.append(path)
                entry.update(kind='file_change', paths=sorted(paths),
                             path_check_at_collection=True, symlink_history_unverified=True)
            else:
                raise ValueError('unsupported item type')
            observations['native_observed_actions'].append(entry)
        except (ValueError, TypeError, OSError, UnicodeError) as exc:
            gaps.append('native observation incomplete: ' + name + ': ' + str(exc)[:100])


def _collect_and_assess(root_thread_id, sessions_root: Path, artifacts: Path,
                        fixture: Path, policy: dict, started_at: float, *, budget_seconds=5.0):
    failures, gaps = [], []
    observations = {'sessions': [], 'messages': [], 'writes': [], 'reads': [], 'tests': [], 'native_observed_actions': []}
    try:
        if isinstance(budget_seconds, bool) or not isinstance(budget_seconds, (int, float)) or not 0 < budget_seconds <= MAX_PROCESS_SECONDS:
            raise ValueError('native processing budget unavailable')
        deadline = time.monotonic() + budget_seconds
        if not isinstance(root_thread_id, str) or str(uuid.UUID(root_thread_id)) != root_thread_id:
            raise ValueError('invalid root thread ID')
        if isinstance(started_at, bool) or not isinstance(started_at, (float, int)):
            raise ValueError('invalid start time')
        # Codex names its session directories using the inherited local TZ,
        # while timestamps inside the JSONL records are UTC.
        start = datetime.fromtimestamp(started_at).date()
        today = datetime.now().date()
        end = min(today, start + timedelta(days=1))
        if start > end or (today - start).days > 1:
            raise ValueError('run date range outside bound')
        sessions_root = _no_symlinks(sessions_root, deadline)
        fixture = _no_symlinks(fixture, deadline)
        artifacts = _no_symlinks(artifacts, deadline)
        if not sessions_root.is_dir() or not fixture.is_dir() or not artifacts.is_dir():
            raise ValueError('run directories unavailable')
    except (ValueError, TypeError, OSError, OverflowError) as exc:
        return [], ['native trace unavailable: ' + str(exc)], observations

    candidates = []
    try:
        for offset in range((end - start).days + 1):
            _check_budget(deadline)
            day = start + timedelta(days=offset)
            directory = sessions_root / day.strftime('%Y/%m/%d')
            _no_symlinks(directory, deadline)
            if not directory.exists():
                continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    _check_budget(deadline)
                    if not entry.name.startswith('rollout-') or not entry.name.endswith('.jsonl'):
                        continue
                    if entry.is_symlink():
                        gaps.append('symlink rollout candidate rejected')
                        continue
                    if entry.is_file(follow_symlinks=False):
                        candidates.append(Path(entry.path))
                        if len(candidates) > MAX_CANDIDATES:
                            raise _BudgetExceeded('rollout candidate count exceeded')
    except (OSError, ValueError) as exc:
        return [], ['native discovery incomplete: ' + str(exc)], observations
    roots = [p for p in _checked(candidates, deadline) if p.name.endswith('-' + root_thread_id + '.jsonl')]
    if len(roots) != 1:
        return [], ['native root trace missing or ambiguous'], observations

    # Read only first-line metadata of candidates, and full bytes only for selected tree.
    metadata = {}
    try:
        root_line = _first(roots[0])
        metadata_bytes = len(root_line)
        root = _metadata(root_line)
        rp = root['payload']
        if rp.get('id') != root_thread_id or rp.get('source') not in ('cli', 'exec') or rp.get('cwd') != str(fixture) or _timestamp(root.get('timestamp')) < started_at:
            raise ValueError('root metadata does not identify this fixture run')
        metadata[root_thread_id] = (roots[0], root, None, '/root')
        remaining = [p for p in _checked(candidates, deadline) if p != roots[0]]
        # Metadata cannot establish relevance if malformed. Ignore unrelated files;
        # a referenced child without usable metadata remains a missing-tree gap.
        for path in remaining:
            try:
                _check_budget(deadline)
                line = _first(path)
                metadata_bytes += len(line)
                if metadata_bytes > MAX_HEADER_TOTAL:
                    raise RuntimeError('native metadata byte budget exceeded')
                event = _metadata(line)
                p = event['payload']
                source = p.get('source')
                sub = source.get('subagent') if isinstance(source, dict) else None
                spawn = sub.get('thread_spawn') if isinstance(sub, dict) else None
                ident = p.get('id')
                if not isinstance(spawn, dict) or not isinstance(ident, str):
                    continue
                if p.get('cwd') != str(fixture) or not started_at <= _timestamp(event.get('timestamp')) <= started_at + 900:
                    continue
                parent = spawn.get('parent_thread_id')
                agent_path = spawn.get('agent_path')
                if not isinstance(parent, str) or not isinstance(agent_path, str):
                    continue
                # Verify file identity, preventing one log from impersonating another.
                if str(uuid.UUID(ident)) != ident or not path.name.endswith('-' + ident + '.jsonl'):
                    continue
                if ident == root_thread_id:
                    raise RuntimeError('duplicate root session identity')
                metadata.setdefault(ident, []).append((path, event, parent, agent_path))
            except (ValueError, TypeError, OSError, UnicodeError):
                continue
    except (ValueError, TypeError, OSError, UnicodeError, RuntimeError) as exc:
        return [], ['native metadata incomplete: ' + str(exc)], observations

    selected = {root_thread_id: metadata.pop(root_thread_id)}
    while True:
        _check_budget(deadline)
        new = {}
        for ident, items in metadata.items():
            _check_budget(deadline)
            relevant = [item for item in _checked(items, deadline) if item[2] in selected]
            if relevant:
                if len(items) != 1:
                    return [], ['duplicate native session identity'], observations
                new[ident] = relevant[0]
        if not new:
            break
        selected.update(new)
        for ident in new:
            _check_budget(deadline)
            del metadata[ident]
        if len(selected) > MAX_SESSIONS:
            raise _BudgetExceeded('native session count exceeded')
    names = {}
    for ident, item in selected.items():
        _check_budget(deadline)
        path, event, parent, name = item
        if name in names:
            gaps.append('duplicate agent path: ' + name)
        names[name] = ident
        if name not in EXPECTED:
            failures.append('unexpected descendant: ' + name[:100])
        elif EXPECTED[name][1] is not None and selected[parent][3] != EXPECTED[name][1]:
            failures.append('wrong parent for ' + name)
        spawn = event['payload'].get('source')
        if parent is not None:
            depth = spawn['subagent']['thread_spawn'].get('depth')
            if type(depth) is not int or depth != name.count('/') - 1:
                gaps.append('invalid depth for ' + name)
            role = spawn['subagent']['thread_spawn'].get('agent_role')
            required_role = {'/root/research': 'researcher_sol', '/root/design': 'planner_sol'}.get(name)
            if required_role and role != required_role:
                gaps.append('named native role unavailable or mismatched: ' + name)
    for name in _checked(EXPECTED.keys() - names.keys(), deadline):
        gaps.append('native session missing: ' + name)

    traces = {}
    try:
        total = 0
        for ident, (path, first, _, _) in selected.items():
            _check_budget(deadline)
            data = _read(path, MAX_TRACE)
            total += len(data)
            if total > MAX_TOTAL:
                raise _BudgetExceeded('native trace byte budget exceeded')
            if not data.endswith(b'\n') or json.loads(data.splitlines()[0]) != first:
                raise ValueError('trace changed or incomplete')
            traces[ident] = data
        dest = artifacts / 'native-traces'
        if dest.exists() or dest.is_symlink():
            raise ValueError('native trace destination already exists')
        dest.mkdir(mode=0o700)
        for ident, data in traces.items():
            _check_budget(deadline)
            fd = os.open(dest / (ident + '.jsonl'), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as out:
                out.write(data)
    except (ValueError, TypeError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        return failures, sorted(set(gaps + ['native capture incomplete: ' + str(exc)])), observations

    actions, test_calls = [], 0
    for ident, data in traces.items():
        _check_budget(deadline)
        name = selected[ident][3]
        source = selected[ident][1]['payload']['source']
        role = source['subagent']['thread_spawn'].get('agent_role') if isinstance(source, dict) else None
        session = {'thread_id': ident, 'agent_path': name, 'parent_thread_id': selected[ident][2], 'agent_role': role, 'turns': []}
        observations['sessions'].append(session)
        # A forked rollout may prepend copied parent history after the child's
        # own session_meta. Its records cannot safely be attributed to the child.
        # Do not guess where its own execution resumes.
        metadata_count = 0
        for line_number, raw in enumerate(data.splitlines(), 1):
            _check_budget(deadline)
            if line_number > MAX_RECORDS:
                raise _BudgetExceeded('native record count exceeded')
            if len(raw) > MAX_LINE:
                raise _BudgetExceeded('native event line size limit exceeded')
            try:
                record = json.loads(raw)
            except (ValueError, UnicodeError):
                continue  # The normal parser will record the malformed line.
            if isinstance(record, dict) and record.get('type') == 'session_meta':
                metadata_count += 1
                if metadata_count > 1:
                    break
        if metadata_count > 1:
            session['history'] = 'mixed-unsupported'
            gaps.append('inherited or mixed-session history unsupported: ' + name)
            continue
        calls, outputs, contexts, finished = {}, {}, {}, {}
        invalid_turns = set()
        observation_records, observation_items, observation_item_ids = [], [], []
        for index, raw in enumerate(data.splitlines()):
            _check_budget(deadline)
            try:
                if len(raw) > MAX_LINE:
                    raise ValueError('oversized line')
                event = json.loads(raw)
                if not isinstance(event, dict) or not isinstance(event.get('payload'), dict):
                    raise ValueError('malformed record')
                stamp = _timestamp(event.get('timestamp'))
                if not started_at <= stamp <= started_at + 900:
                    raise ValueError('record outside run time window')
                kind, p = event.get('type'), event['payload']
                if not isinstance(kind, str):
                    raise ValueError('record type missing')
                if kind == 'turn_context':
                    turn = p.get('turn_id')
                    if not isinstance(turn, str) or not isinstance(p.get('model'), str) or not isinstance(p.get('effort'), str) or turn in contexts:
                        if isinstance(turn, str):
                            invalid_turns.add(turn)
                        raise ValueError('invalid turn context')
                    contexts[turn] = (p['model'], p['effort'], stamp)
                    if len(contexts) > MAX_CONTEXTS:
                        raise _BudgetExceeded('native context count exceeded')
                elif kind == 'event_msg' and p.get('type') == 'task_complete':
                    if not isinstance(p.get('turn_id'), str):
                        raise ValueError('completion lacks turn id')
                    if p['turn_id'] in finished:
                        invalid_turns.add(p['turn_id'])
                        raise ValueError('duplicate turn completion')
                    finished[p['turn_id']] = stamp
                    if len(finished) > MAX_CONTEXTS:
                        raise _BudgetExceeded('native completion count exceeded')
                elif kind == 'event_msg' and p.get('type') == 'item_completed':
                    item = p.get('item')
                    observation_item_ids.append(item.get('id') if isinstance(item, dict) else None)
                    if len(observation_item_ids) > MAX_OBS_ITEMS:
                        raise _BudgetExceeded('native observation item budget exceeded')
                    if isinstance(item, dict) and item.get('type') in ('CommandExecution', 'FileChange'):
                        observation_items.append((index, stamp, p))
                elif kind == 'response_item':
                    typ = p.get('type')
                    if not isinstance(typ, str):
                        raise ValueError('response type missing')
                    if typ in ('custom_tool_call', 'custom_tool_call_output', 'function_call', 'function_call_output'):
                        observation_records.append((index, stamp, p))
                        if len(observation_records) > MAX_CALLS * 2:
                            raise _BudgetExceeded('native tool record count exceeded')
                    if typ in {'function_call', 'custom_tool_call'}:
                        cid = p.get('call_id')
                        if not isinstance(cid, str) or not cid or cid in calls or not isinstance(p.get('name'), str) or p.get('status') != 'completed':
                            raise ValueError('invalid tool call')
                        calls[cid] = (stamp, p)
                        if len(calls) > MAX_CALLS:
                            raise _BudgetExceeded('native tool call count exceeded')
                    elif typ in {'function_call_output', 'custom_tool_call_output'}:
                        cid = p.get('call_id')
                        if not isinstance(cid, str) or cid in outputs:
                            raise ValueError('invalid tool output identity')
                        outputs[cid] = (stamp, _output_text(p.get('output'), deadline))
                        if len(outputs) > MAX_CALLS:
                            raise _BudgetExceeded('native tool output count exceeded')
                    elif typ == 'web_search_call':
                        failures.append('forbidden native web search: ' + name)
                    elif typ not in {'message', 'agent_message', 'reasoning', 'additional_tools'}:
                        gaps.append('unclassified native response: ' + name + ': ' + typ[:100])
            except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                gaps.append('invalid native record for ' + name + ': ' + str(exc)[:100])
        if not contexts or set(contexts) != set(finished):
            gaps.append('native turns missing context or completion: ' + name)
        elif any(contexts[turn][2] >= finished[turn] for turn in _checked(contexts, deadline)):
            gaps.append('native turn completion order invalid: ' + name)
        session['turns'] = [{'turn_id': turn, 'model': model, 'effort': effort, 'completed': turn in finished}
                            for turn, (model, effort, _) in _checked(contexts.items(), deadline)]
        _observe_items(name, ident, fixture, contexts, finished, invalid_turns, observation_records,
                       observation_items, observation_item_ids, deadline, observations, gaps)
        route = EXPECTED.get(name, (None,))[0]
        try:
            expected = policy['primary'] if route == 'primary' else policy['defaultWorker'] if route == 'lead' else policy['routes'][route]
            allowed = expected.get('allowedEfforts', [expected['effort']])
            for model, effort, _ in contexts.values():
                _check_budget(deadline)
                if model != expected['model'] or effort not in allowed:
                    failures.append('effective model or effort mismatch: ' + name)
        except (KeyError, TypeError):
            gaps.append('routing policy unavailable for ' + name)
        if calls.keys() != outputs.keys():
            gaps.append('native tool calls lack paired outputs: ' + name)
        for cid, (stamp, p) in calls.items():
            _check_budget(deadline)
            if cid not in outputs:
                continue
            endstamp, output = outputs[cid]
            if endstamp < stamp:
                gaps.append('tool output precedes call: ' + name)
                continue
            if not any(turn in finished and context[2] <= stamp <= endstamp <= finished[turn]
                       for turn, context in _checked(contexts.items(), deadline)):
                gaps.append('native action outside completed turn: ' + name)
                continue
            tool, ns, typ = p['name'], p.get('namespace'), p['type']
            try:
                if ns == 'collaboration' and tool in {'spawn_agent', 'send_message', 'followup_task'}:
                    args = _json_object(p.get('arguments'))
                    if tool == 'spawn_agent':
                        result = _json_object(output)
                        if set(result) != {'task_name'}:
                            raise ValueError('unrecognized spawn output fields')
                        child = result.get('task_name')
                        if not isinstance(child, str) or not child.startswith(name + '/') or args.get('task_name') != child.rsplit('/', 1)[-1]:
                            raise ValueError('spawn output binding invalid')
                        actions.append((stamp, endstamp, name, tool, child, args))
                    else:
                        if output.strip():
                            raise ValueError('message output not confirmed')
                        actions.append((stamp, endstamp, name, tool, args.get('target'), args))
                elif ns == 'collaboration' and tool in {'wait_agent', 'list_agents'}:
                    pass
                elif tool == 'apply_patch' and ns in (None, 'functions'):
                    patch = p.get('input') if typ == 'custom_tool_call' else _json_object(p.get('arguments')).get('input')
                    paths = _patch_paths(patch, fixture, deadline)
                    if not output.startswith('Success. Updated the following files:'):
                        raise ValueError('patch lacks successful output')
                    allowed = {'/root': {'app.py'}, '/root/lead/calc': {'calc.py'}, '/root/lead/display': {'display.py'}}.get(name, set())
                    for path in paths:
                        _check_budget(deadline)
                        if path not in allowed:
                            failures.append('unauthorized native write: ' + name + ' -> ' + path)
                        observations['writes'].append({'agent_path': name, 'path': path, 'completed_at': endstamp})
                    actions.append((stamp, endstamp, name, 'patch', paths, {}))
                elif tool == 'exec_command' and ns in (None, 'functions'):
                    args = _json_object(p.get('arguments'))
                    if set(args) - {'cmd', 'workdir', 'yield_time_ms', 'max_output_tokens', 'tty', 'shell', 'login'}:
                        raise ValueError('unrecognized command options')
                    workdir = args.get('workdir')
                    if workdir is not None and workdir not in ('.', str(fixture)):
                        raise ValueError('command working directory is not fixture')
                    shell = args.get('shell')
                    if shell is not None and shell not in ('bash', '/bin/bash', '/usr/bin/bash', 'sh', '/bin/sh', '/usr/bin/sh'):
                        raise ValueError('unrecognized command shell')
                    command = args.get('cmd')
                    argv = CascadeEval.command_argv(command) if isinstance(command, str) else None
                    if argv is None:
                        failures.append('forbidden native command: ' + name)
                    else:
                        is_test = argv == ['python3', '-B', '-m', 'unittest', '-v', 'test_app']
                        if is_test:
                            test_calls += 1
                        code, command_output = _command_output(output)
                        if code != 0:
                            failures.append('native command failed: ' + name)
                        elif is_test:
                            observations['tests'].append({'agent_path': name, 'started_at': stamp, 'completed_at': endstamp})
                            actions.append((stamp, endstamp, name, 'test', None, {}))
                        elif argv in (['ls'], ['ls', '-l']):
                            actions.append((stamp, endstamp, name, 'list', None, {}))
                        elif argv and argv[0] in {'cat', '/bin/cat', '/usr/bin/cat'} and len(argv) == 2:
                            if not command_output:
                                raise ValueError('file read has empty output')
                            observations['reads'].append({'agent_path': name, 'path': argv[1], 'completed_at': endstamp, 'kind': 'successful_cat_tool_call'})
                            actions.append((stamp, endstamp, name, 'read', argv[1], {}))
                        else:
                            gaps.append('unclassified allowed native command: ' + name)
                else:
                    gaps.append('unclassified native tool: ' + name + ': ' + tool[:100])
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                gaps.append('native action incomplete: ' + name + ': ' + str(exc)[:100])

    if test_calls == 0:
        gaps.append('native fixture test attempt unavailable')
    elif test_calls > 1:
        failures.append('native fixture test attempted more than once')
    spawns = [a for a in _checked(actions, deadline) if a[3] == 'spawn_agent']
    for name, (_, parent) in EXPECTED.items():
        _check_budget(deadline)
        if parent is None or name not in names:
            continue
        matches = [a for a in _checked(spawns, deadline) if a[2] == parent and a[4] == name]
        if len(matches) != 1:
            gaps.append('native spawn binding missing or ambiguous: ' + name)
        elif matches[0][0] > _timestamp(selected[names[name]][1].get('timestamp')):
            gaps.append('child session predates spawn: ' + name)
        if len(matches) == 1 and EXPECTED[name][0] == 'mechanical':
            try:
                expected = policy['routes']['mechanical']
                args = matches[0][5]
                if args.get('model') != expected['model'] or args.get('reasoning_effort') != expected['effort']:
                    failures.append('explicit mechanical spawn model or effort mismatch: ' + name)
            except (KeyError, TypeError):
                gaps.append('mechanical spawn routing policy unavailable: ' + name)
    for action in spawns:
        _check_budget(deadline)
        if action[4] not in EXPECTED or EXPECTED[action[4]][1] != action[2]:
            failures.append('unexpected native spawn: ' + str(action[4])[:100])

    messages = []
    for a in actions:
        _check_budget(deadline)
        if a[3] != 'send_message':
            continue
        try:
            body = _json_object(a[5].get('message'))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        messages.append((a, body))
        observations['messages'].append({'sender': a[2], 'target': a[4], 'event': body.get('cascade_event')})
    def find(sender, target, event):
        targets = {target}
        if target.rsplit('/', 1)[0] == sender:
            targets.add(target.rsplit('/', 1)[-1])
        return [(a, b) for a, b in _checked(messages, deadline) if a[2] == sender and isinstance(a[4], str) and a[4] in targets and b.get('cascade_event') == event]
    def one(sender, target, event):
        found = find(sender, target, event)
        if len(found) != 1:
            gaps.append('protocol message missing or ambiguous: ' + event + ' ' + sender + ' -> ' + target)
            return None
        return found[0]
    def ordered(earlier_start, earlier_end, later_start, violation):
        if later_start < earlier_start:
            failures.append(violation)
        elif later_start <= earlier_end:
            gaps.append('native ordering ambiguous: ' + violation)
    proposal = one('/root/lead', '/root', 'proposal')
    approval = one('/root', '/root/lead', 'approval')
    question = one('/root/lead', '/root', 'question')
    worker_defect = one('/root/lead/calc', '/root/lead', 'defect')
    defect = one('/root/lead', '/root', 'defect')
    research = one('/root/research', '/root', 'research_result')
    handoff = one('/root', '/root/design', 'design_handoff')
    design = one('/root/design', '/root', 'design_result')
    design_context = one('/root', '/root/lead', 'design_context')
    worker_contexts = [one('/root/lead', '/root/lead/' + child, 'worker_context')
                       for child in ('calc', 'display')]
    review = one('/root/review', '/root', 'review_result')
    clarification = one('/root', '/root/lead', 'clarification')
    forwards = [one('/root/lead', '/root/lead/' + child, 'clarification') for child in ('calc', 'display')]
    patches = [a for a in _checked(actions, deadline) if a[3] == 'patch']
    last_patch = max((a[1] for a in _checked(patches, deadline)), default=None)
    reads = [a for a in _checked(actions, deadline) if a[3] == 'read']
    def bind_summary(source, target, key, files, label, expected_spec=None):
        if not target:
            return
        body = target[1]
        if body.get('files') != files:
            failures.append('invalid ' + label + ' scope')
        if expected_spec is not None:
            spec = body.get('spec')
            if (not isinstance(spec, dict) or set(spec) != set(expected_spec) or
                    any(type(spec[key]) is not type(value) or spec[key] != value
                        for key, value in expected_spec.items())):
                failures.append('invalid ' + label + ' spec')
        summary = source[1].get('summary') if source else None
        if not isinstance(summary, str) or not summary.strip():
            gaps.append(label + ' source summary unavailable')
        elif body.get(key) != summary:
            failures.append('invalid ' + label + ' summary')
    bind_summary(research, handoff, 'research_summary', ['calc.py'], 'design handoff')
    bind_summary(design, design_context, 'design_summary', ['calc.py', 'display.py'], 'design context')
    for context, path, spec in zip(worker_contexts, ('calc.py', 'display.py'), WORKER_SPECS):
        bind_summary(design, context, 'design_summary', [path], 'worker context ' + path, expected_spec=spec)
    for item, sender, required in ((research, '/root/research', ['calc.py']),
                                    (design, '/root/design', ['calc.py', 'display.py']),
                                    (review, '/root/review', ['app.py', 'calc.py', 'display.py'])):
        if not item:
            continue
        body = item[1]
        if not isinstance(body.get('summary'), str) or not body['summary'].strip() or body.get('files') != required:
            gaps.append('report lacks expected summary or file references: ' + sender)
            continue
        for path in required:
            _check_budget(deadline)
            relevant = [a for a in _checked(reads, deadline) if a[2] == sender and a[4] == path and a[1] < item[0][0]]
            if sender == '/root/design':
                relevant = [a for a in _checked(relevant, deadline) if handoff and handoff[0][1] < a[0]]
            if sender == '/root/review':
                relevant = [a for a in _checked(relevant, deadline) if last_patch is not None and last_patch < a[0]]
            if not relevant:
                gaps.append('report lacks timely successful file read: ' + sender + ' -> ' + path)
    if research and handoff:
        ordered(research[0][0], research[0][1], handoff[0][0], 'design handoff precedes research result')
    if handoff:
        for read in _checked(reads, deadline):
            if read[2] == '/root/design' and read[4] in ('calc.py', 'display.py'):
                ordered(handoff[0][0], handoff[0][1], read[0], 'design read before handoff: ' + read[4])
    if design and design_context:
        ordered(design[0][0], design[0][1], design_context[0][0], 'design context precedes design result')
    if design_context and proposal:
        ordered(design_context[0][0], design_context[0][1], proposal[0][0], 'proposal precedes design context')
    if design and approval:
        ordered(design[0][0], design[0][1], approval[0][0], 'approval precedes design result')
    for spawn in spawns:
        _check_budget(deadline)
        if spawn[2] == '/root' and spawn[4] == '/root/design' and research:
            ordered(research[0][0], research[0][1], spawn[0], 'design spawned before research result')
        if spawn[2] == '/root' and spawn[4] == '/root/design' and handoff:
            ordered(spawn[0], spawn[1], handoff[0][0], 'design handoff precedes design spawn')
        if spawn[2] == '/root' and spawn[4] == '/root/lead' and design:
            ordered(design[0][0], design[0][1], spawn[0], 'lead spawned before design result')
        if spawn[2] == '/root' and spawn[4] == '/root/lead' and design_context:
            ordered(spawn[0], spawn[1], design_context[0][0], 'design context precedes lead spawn')
        for context, worker in zip(worker_contexts, ('/root/lead/calc', '/root/lead/display')):
            if context and spawn[2] == '/root/lead' and spawn[4] == worker:
                ordered(spawn[0], spawn[1], context[0][0], 'worker context precedes spawn: ' + worker)
    for test in [a for a in _checked(actions, deadline) if a[3] == 'test']:
        _check_budget(deadline)
        if test[2] != '/root':
            failures.append('native fixture test not run by root')
        if not patches:
            gaps.append('native final patch timing unavailable')
        else:
            for patch in _checked(patches, deadline):
                ordered(patch[0], patch[1], test[0], 'native fixture test precedes final patch')
    for item in (proposal, approval):
        if item and item[1].get('children') != CHILDREN:
            failures.append('invalid protocol child scopes')
    if proposal and approval:
        ordered(proposal[0][0], proposal[0][1], approval[0][0], 'approval does not follow proposal')
    for context, worker in zip(worker_contexts, ('/root/lead/calc', '/root/lead/display')):
        if context and approval:
            ordered(approval[0][0], approval[0][1], context[0][0], 'worker context precedes approval: ' + worker)
    work_labels = {'read': 'read', 'list': 'list', 'test': 'test', 'patch': 'patched',
                   'spawn_agent': 'spawned', 'send_message': 'message', 'followup_task': 'followup'}
    for action in _checked(actions, deadline):
        if action[2] in ('/root/lead/calc', '/root/lead/display') and action[3] in work_labels:
            context = worker_contexts[0 if action[2].endswith('/calc') else 1]
            if context:
                ordered(context[0][0], context[0][1], action[0],
                        'worker ' + work_labels[action[3]] + ' before worker context: ' + action[2])
    if worker_contexts[0] and worker_defect:
        ordered(worker_contexts[0][0][0], worker_contexts[0][0][1], worker_defect[0][0],
                'worker defect precedes worker context: /root/lead/calc')
    for a in spawns:
        _check_budget(deadline)
        if a[4] in {'/root/lead/calc', '/root/lead/display'} and approval:
            ordered(approval[0][0], approval[0][1], a[0], 'child spawned before approval: ' + a[4])
    if question and question[1].get('question_id') != 'bool-empty':
        failures.append('invalid protocol question')
    if defect and defect[1].get('id') != 'bool-accepted':
        failures.append('invalid protocol defect')
    if worker_defect and worker_defect[1].get('id') != 'bool-accepted':
        failures.append('invalid worker defect')
    if worker_defect and not any(a[2] == '/root/lead/calc' and a[4] == 'calc.py' and a[1] < worker_defect[0][0] for a in _checked(reads, deadline)):
        gaps.append('worker defect lacks prior successful calc.py read')
    if worker_defect and defect:
        ordered(worker_defect[0][0], worker_defect[0][1], defect[0][0], 'defect return does not follow worker message')
    if defect and clarification:
        ordered(defect[0][0], defect[0][1], clarification[0][0], 'clarification precedes defect return')
    if defect and question:
        ordered(defect[0][0], defect[0][1], question[0][0], 'question precedes defect return')
    for item in [clarification, *forwards]:
        if item and (item[1].get('question_id') != 'bool-empty' or item[1].get('answer') != ANSWER):
            failures.append('invalid protocol clarification')
    if question and clarification:
        ordered(question[0][0], question[0][1], clarification[0][0], 'clarification does not follow question')
    for item in forwards:
        if item and clarification:
            ordered(clarification[0][0], clarification[0][1], item[0][0], 'forward does not follow clarification')
    for a in actions:
        _check_budget(deadline)
        if a[3] == 'patch' and a[2] in {'/root/lead/calc', '/root/lead/display'}:
            for forward in forwards:
                if forward:
                    ordered(forward[0][0], forward[0][1], a[0], 'worker patched before clarification: ' + a[2])
    for worker, path in (('/root/lead/calc', 'calc.py'), ('/root/lead/display', 'display.py')):
        if not any(item['agent_path'] == worker and item['path'] == path for item in _checked(observations['writes'], deadline)):
            gaps.append('native worker patch unavailable: ' + worker)
    _check_budget(deadline)
    return sorted(set(failures)), sorted(set(gaps)), observations


def collect_and_assess(root_thread_id, sessions_root: Path, artifacts: Path,
                       fixture: Path, policy: dict, started_at: float, *, budget_seconds=5.0):
    try:
        return _collect_and_assess(root_thread_id, sessions_root, artifacts, fixture,
                                   policy, started_at, budget_seconds=budget_seconds)
    except _BudgetExceeded as exc:
        return [], [str(exc)], {'sessions': [], 'messages': [], 'writes': [], 'reads': [],
                                'tests': [], 'native_observed_actions': []}
