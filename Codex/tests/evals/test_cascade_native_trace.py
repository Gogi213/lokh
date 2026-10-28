"""Synthetic native JSONL traces: only records, never model prose, count."""
from datetime import datetime, timedelta, timezone
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from tools.Codex.Skills import CascadeNativeTrace as native


class NativeTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.sessions = base / 'sessions'
        self.fixture = base / 'fixture'
        self.artifacts = base / 'artifacts'
        self.fixture.mkdir()
        self.artifacts.mkdir()
        self.start = datetime.now(timezone.utc) - timedelta(minutes=2)
        self.directory = self.sessions / datetime.fromtimestamp(self.start.timestamp()).strftime('%Y/%m/%d')
        self.directory.mkdir(parents=True)
        self.ids = {name: str(uuid.uuid4()) for name in native.EXPECTED}
        self.events = {name: [] for name in native.EXPECTED}
        self.policy = {
            'primary': {'model': 'gpt-6.1-sol', 'effort': 'high'},
            'defaultWorker': {'model': 'gpt-6.1-sol', 'effort': 'high'},
            'routes': {'research': {'model': 'gpt-6.1-sol', 'effort': 'high'},
                       'design': {'model': 'gpt-6.1-sol', 'effort': 'xhigh'},
                       'review': {'model': 'gpt-6.1-sol', 'effort': 'xhigh'},
                       'patch': {'model': 'gpt-6.1-sol', 'effort': 'high'},
                       'mechanical': {'model': 'gpt-6.1-terra', 'effort': 'high'}},
        }
        timings = {
            '/root': (1, 1.5, 80), '/root/research': (3, 4, 9),
            '/root/design': (12, 13, 22), '/root/lead': (25, 26, 53),
            '/root/lead/calc': (34, 35, 50), '/root/lead/display': (34, 35, 51),
            '/root/review': (55, 56, 65),
        }
        for name, (route, parent) in native.EXPECTED.items():
            source = 'cli' if parent is None else {'subagent': {'thread_spawn': {
                'parent_thread_id': self.ids[parent], 'depth': name.count('/') - 1,
                'agent_path': name, 'agent_role': {'/root/research': 'researcher_sol', '/root/design': 'planner_sol'}.get(name, 'default')}}}
            meta_at, context_at, complete_at = timings[name]
            self.add(name, meta_at, 'session_meta', {'id': self.ids[name], 'source': source, 'cwd': str(self.fixture)})
            setting = self.policy['primary'] if route == 'primary' else self.policy['defaultWorker'] if route == 'lead' else self.policy['routes'][route]
            self.add(name, context_at, 'turn_context', {'turn_id': 'turn', 'model': setting['model'], 'effort': setting['effort']})
            self.add(name, complete_at, 'event_msg', {'type': 'task_complete', 'turn_id': 'turn'})
        self.spawn('/root', 'research', 2)
        self.read('/root/research', 'calc.py', 5)
        self.message('/root/research', '/root', 'research_result', 7, summary='Research', files=['calc.py'])
        self.spawn('/root', 'design', 11)
        self.message('/root', '/root/design', 'design_handoff', 14,
                     research_summary='Research', files=['calc.py'])
        self.read('/root/design', 'calc.py', 16)
        self.read('/root/design', 'display.py', 18)
        self.message('/root/design', '/root', 'design_result', 20, summary='Design', files=['calc.py', 'display.py'])
        self.spawn('/root', 'lead', 24)
        self.message('/root', '/root/lead', 'design_context', 25.2,
                     design_summary='Design', files=['calc.py', 'display.py'])
        self.message('/root/lead', '/root', 'proposal', 27, children=native.CHILDREN)
        self.message('/root', '/root/lead', 'approval', 29, children=native.CHILDREN)
        for child in ('calc', 'display'):
            self.spawn('/root/lead', child, 32)
        self.message('/root/lead', '/root/lead/calc', 'worker_context', 34.1,
                     design_summary='Design', files=['calc.py'],
                     spec={'operation': 'sum', 'empty': 0, 'reject_boolean': True})
        self.message('/root/lead', '/root/lead/display', 'worker_context', 34.2,
                     design_summary='Design', files=['display.py'], spec={'format': 'total: <value>'})
        self.read('/root/lead/calc', 'calc.py', 36)
        self.message('/root/lead/calc', '/root/lead', 'defect', 38, id='bool-accepted')
        self.message('/root/lead', '/root', 'defect', 40, id='bool-accepted')
        self.message('/root/lead', '/root', 'question', 42, question_id='bool-empty')
        self.message('/root', '/root/lead', 'clarification', 44, question_id='bool-empty', answer=native.ANSWER)
        for child in ('calc', 'display'):
            self.message('/root/lead', '/root/lead/' + child, 'clarification', 46, question_id='bool-empty', answer=native.ANSWER)
            self.patch('/root/lead/' + child, child + '.py', 48)
        self.call('/root', 52, 'exec_command', {'cmd': 'python3 -B -m unittest -v test_app'},
                  json.dumps({'exit_code': 0, 'output': 'OK'}), namespace='functions')
        self.spawn('/root', 'review', 54)
        for second, path in ((57, 'app.py'), (59, 'calc.py'), (61, 'display.py')):
            self.read('/root/review', path, second)
        self.message('/root/review', '/root', 'review_result', 63, summary='Reviewed', files=['app.py', 'calc.py', 'display.py'])

    def add(self, name, second, typ, payload):
        self.events[name].append({'timestamp': (self.start + timedelta(seconds=second)).isoformat(), 'type': typ, 'payload': payload})

    def call(self, name, second, tool, arguments, output, namespace='collaboration', custom=False):
        cid = str(uuid.uuid4())
        call = {'type': 'custom_tool_call' if custom else 'function_call', 'name': tool,
                'call_id': cid, 'status': 'completed'}
        if custom:
            call['input'] = arguments
        else:
            call.update(namespace=namespace, arguments=json.dumps(arguments))
        self.add(name, second, 'response_item', call)
        self.add(name, second + 1, 'response_item', {'type': 'custom_tool_call_output' if custom else 'function_call_output', 'call_id': cid, 'output': output})

    def spawn(self, parent, child, second):
        name = parent + '/' + child
        args = {'task_name': child, 'fork_turns': 'none'}
        if native.EXPECTED.get(name, (None,))[0] == 'mechanical':
            setting = self.policy['routes']['mechanical']
            args.update(model=setting['model'], reasoning_effort=setting['effort'])
        self.call(parent, second, 'spawn_agent', args, json.dumps({'task_name': name}))

    def message(self, sender, target, event, second, **fields):
        body = {'cascade_event': event, **fields}
        self.call(sender, second, 'send_message', {'target': target, 'message': json.dumps(body)}, '')

    def patch(self, name, file, second):
        self.call(name, second, 'apply_patch', '*** Begin Patch\n*** Update File: ' + file + '\n@@\n-old\n+new\n*** End Patch\n',
                  'Success. Updated the following files:\nM ' + file, custom=True)

    def read(self, name, file, second):
        self.call(name, second, 'exec_command', {'cmd': 'cat ' + file},
                  json.dumps({'exit_code': 0, 'output': 'fixture contents\n'}), namespace='functions')

    def observed_item(self, name, second, kind='read'):
        cid = str(uuid.uuid4())
        item_id = str(uuid.uuid4())  # Native item identity is distinct from the enclosing call_id.
        self.add(name, second, 'response_item', {'type': 'custom_tool_call', 'name': 'exec',
                 'call_id': cid, 'status': 'completed', 'input': 'opaque javascript'})
        if kind == 'change':
            item = {'type': 'FileChange', 'id': item_id, 'status': 'completed',
                    'changes': {str(self.fixture / 'app.py'): {'type': 'update', 'unified_diff': '<diff>', 'move_path': None}}}
        else:
            command = 'python3 -B -m unittest -v test_app' if kind == 'test' else 'cat calc.py'
            item = {'type': 'CommandExecution', 'id': item_id, 'status': 'completed',
                    'source': 'unified_exec_startup', 'cwd': self.fixture.as_uri(),
                    'command': ['/bin/bash', '-lc', command], 'exit_code': 0, 'aggregated_output': '<output>'}
        payload = {'type': 'item_completed', 'thread_id': self.ids[name], 'turn_id': 'turn',
                   'started_at_ms': int((self.start.timestamp() + second + 0.2) * 1000),
                   'completed_at_ms': int((self.start.timestamp() + second + 0.4) * 1000), 'item': item}
        self.add(name, second + 0.6, 'event_msg', payload)
        self.add(name, second + 1, 'response_item', {'type': 'custom_tool_call_output',
                 'call_id': cid, 'output': [{'type': 'input_text', 'text': 'completed'}]})
        return cid, payload

    def remove_calls(self, name, predicate):
        ids = {event['payload']['call_id'] for event in self.events[name]
               if event['payload'].get('type') in {'function_call', 'custom_tool_call'} and predicate(event['payload'])}
        self.events[name] = [event for event in self.events[name] if event['payload'].get('call_id') not in ids]

    def save(self):
        for name, events in self.events.items():
            path = self.directory / ('rollout-example-' + self.ids[name] + '.jsonl')
            # Native record order, with metadata always first.
            ordered = [events[0], *sorted(events[1:], key=lambda e: e['timestamp'])]
            path.write_text(''.join(json.dumps(event) + '\n' for event in ordered), encoding='utf-8')

    def assess(self):
        self.save()
        return native.collect_and_assess(self.ids['/root'], self.sessions, self.artifacts,
                                         self.fixture, self.policy, self.start.timestamp())

    def test_complete_native_tree(self):
        failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertEqual([], gaps)
        self.assertEqual(7, len(observed['sessions']))
        actual = {session['agent_path']: (session['turns'][0]['model'], session['turns'][0]['effort'])
                  for session in observed['sessions']}
        self.assertEqual({
            '/root': ('gpt-6.1-sol', 'high'), '/root/lead': ('gpt-6.1-sol', 'high'),
            '/root/research': ('gpt-6.1-sol', 'high'), '/root/design': ('gpt-6.1-sol', 'xhigh'),
            '/root/review': ('gpt-6.1-sol', 'xhigh'),
            '/root/lead/calc': ('gpt-6.1-terra', 'high'),
            '/root/lead/display': ('gpt-6.1-terra', 'high'),
        }, actual)
        self.assertEqual({'calc.py', 'display.py'}, {x['path'] for x in observed['writes']})
        self.assertEqual(7, len(list((self.artifacts / 'native-traces').iterdir())))

    def test_structured_exec_observations_do_not_authorize_unknown_js(self):
        cid, read = self.observed_item('/root', 66)
        self.observed_item('/root', 68, 'change')
        self.observed_item('/root', 70, 'test')
        self.assertNotEqual(cid, read['item']['id'])
        failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertTrue(any('unclassified native tool: /root: exec' in x for x in gaps))
        self.assertEqual(['read', 'file_change', 'test'], [x['kind'] for x in observed['native_observed_actions']])
        self.assertEqual('calc.py', observed['native_observed_actions'][0]['path'])
        self.assertEqual(['app.py'], observed['native_observed_actions'][1]['paths'])
        self.assertEqual(0, observed['native_observed_actions'][2]['exit_code'])
        for entry in observed['native_observed_actions'][:2]:
            self.assertTrue(entry['path_check_at_collection'])
            self.assertTrue(entry['symlink_history_unverified'])
        self.assertNotIn('output', observed['native_observed_actions'][2])

    def test_context_budget_exhaustion_is_incomplete(self):
        for number in range(4):
            self.add('/root', 60 + number, 'turn_context', {'turn_id': 'extra-' + str(number),
                     'model': 'gpt-6.1-sol', 'effort': 'high'})
        with patch.object(native, 'MAX_CONTEXTS', 3):
            failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertTrue(any('context count exceeded' in gap for gap in gaps))
        self.assertEqual([], observed['sessions'])

    def test_tool_call_budget_exhaustion_is_incomplete(self):
        with patch.object(native, 'MAX_CALLS', 4):
            failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertTrue(any('tool call count exceeded' in gap or 'tool record count exceeded' in gap for gap in gaps))
        self.assertEqual([], observed['native_observed_actions'])

    def test_deadline_exhaustion_during_assessment_returns_gap(self):
        calls = 0
        def ticking_clock():
            nonlocal calls
            calls += 1
            return 0.0 if calls < 120 else 6.0
        with patch.object(native.time, 'monotonic', side_effect=ticking_clock):
            failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertTrue(any('time budget exceeded' in gap for gap in gaps))
        self.assertEqual([], observed['sessions'])

    def test_structured_observation_rejects_foreign_thread_and_turn(self):
        _, first = self.observed_item('/root', 66)
        _, second = self.observed_item('/root', 68)
        first['thread_id'] = self.ids['/root/review']
        second['turn_id'] = 'foreign-turn'
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('session or turn binding' in x for x in gaps))

    def test_structured_observation_requires_canonical_fixture_uri(self):
        new_fixture = self.fixture.with_name('fixture with space # and ?')
        self.fixture.rename(new_fixture)
        self.fixture = new_fixture
        for events in self.events.values():
            events[0]['payload']['cwd'] = str(new_fixture)
        _, canonical = self.observed_item('/root', 66)
        _, raw = self.observed_item('/root', 68)
        raw['item']['cwd'] = 'file://' + str(new_fixture)
        self.assertIn('%20', canonical['item']['cwd'])
        self.assertIn('%23', canonical['item']['cwd'])
        self.assertIn('%3F', canonical['item']['cwd'])
        _, gaps, observed = self.assess()
        self.assertEqual(1, len(observed['native_observed_actions']))
        self.assertTrue(any('unsupported command cwd' in x for x in gaps))

    def test_structured_observation_rejects_cwd_paths_and_change_types(self):
        _, cwd = self.observed_item('/root', 66)
        cwd['item']['cwd'] = 'file://other-host' + str(self.fixture)
        _, shell = self.observed_item('/root', 68)
        shell['item']['command'][2] = 'cat calc.py; cat app.py'
        _, outside = self.observed_item('/root', 70, 'change')
        outside['item']['changes'] = {'/tmp/outside.py': {'type': 'update', 'unified_diff': '<diff>', 'move_path': None}}
        _, moved = self.observed_item('/root', 72, 'change')
        next(iter(moved['item']['changes'].values()))['move_path'] = 'calc.py'
        _, deleted = self.observed_item('/root', 74, 'change')
        next(iter(deleted['item']['changes'].values()))['type'] = 'delete'
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('unsupported command cwd' in x for x in gaps))
        self.assertTrue(any('unsupported observed command' in x for x in gaps))
        self.assertTrue(any('unsupported file change' in x for x in gaps))

    def test_structured_observation_rejects_symlink(self):
        self.observed_item('/root', 66)
        (self.fixture / 'calc.py').symlink_to(self.fixture / 'elsewhere')
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('symlink in path' in x for x in gaps))

    def test_structured_observation_rejects_failed_exit_and_bad_time(self):
        _, failed = self.observed_item('/root', 66, 'test')
        failed['item']['exit_code'] = 1
        _, timed = self.observed_item('/root', 68)
        timed['completed_at_ms'] = timed['started_at_ms'] - 1
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('successful exit' in x for x in gaps))
        self.assertTrue(any('invalid item timestamps' in x for x in gaps))

    def test_structured_observation_rejects_missing_exec_output(self):
        missing_id, _ = self.observed_item('/root', 66)
        self.events['/root'] = [event for event in self.events['/root'] if not
                                (event['payload'].get('type') == 'custom_tool_call_output' and event['payload'].get('call_id') == missing_id)]
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('exec envelope' in x for x in gaps))

    def test_structured_observation_rejects_overlapping_exec(self):
        self.observed_item('/root', 68)
        self.observed_item('/root', 68.25)
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('exec envelope missing or ambiguous' in x for x in gaps))

    def test_structured_observation_rejects_overlapping_other_tool(self):
        self.observed_item('/root', 66)
        cid = str(uuid.uuid4())
        self.add('/root', 66.25, 'response_item', {'type': 'function_call', 'name': 'wait_agent',
                 'namespace': 'collaboration', 'call_id': cid, 'status': 'completed',
                 'arguments': json.dumps({'timeout_ms': 10})})
        self.add('/root', 66.35, 'response_item', {'type': 'function_call_output', 'call_id': cid, 'output': ''})
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('overlapping native tool envelope' in x for x in gaps))

    def test_structured_observation_rejects_duplicate_item_identity(self):
        _, first = self.observed_item('/root', 66)
        _, second = self.observed_item('/root', 68)
        second['item']['id'] = first['item']['id']
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('item identity missing or duplicated' in x for x in gaps))

    def test_structured_observation_rejects_id_shared_with_other_item_type(self):
        _, observed_item = self.observed_item('/root', 66)
        self.add('/root', 67.5, 'event_msg', {'type': 'item_completed',
                 'item': {'type': 'Reasoning', 'id': observed_item['item']['id']}})
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('item identity missing or duplicated' in x for x in gaps))

    def test_observations_cannot_prove_encrypted_protocol(self):
        self.observed_item('/root', 66)
        for events in self.events.values():
            for event in events:
                payload = event['payload']
                if payload.get('type') == 'function_call' and payload.get('name') == 'send_message':
                    args = json.loads(payload['arguments'])
                    args['message'] = 'gAAAAA-opaque-ciphertext'
                    payload['arguments'] = json.dumps(args)
        failures, gaps, observed = self.assess()
        self.assertEqual([], failures)
        self.assertEqual(1, len(observed['native_observed_actions']))
        self.assertTrue(any('unclassified native tool: /root: exec' in x for x in gaps))
        self.assertTrue(any('protocol message missing' in x for x in gaps))

    def test_matching_item_id_does_not_replace_enclosing_exec(self):
        cid, payload = self.observed_item('/root', 66)
        payload['item']['id'] = cid
        for event in self.events['/root']:
            if event['payload'] is payload:
                event['timestamp'] = (self.start + timedelta(seconds=68.6)).isoformat()
        payload['started_at_ms'] = int((self.start.timestamp() + 68.2) * 1000)
        payload['completed_at_ms'] = int((self.start.timestamp() + 68.4) * 1000)
        _, gaps, observed = self.assess()
        self.assertEqual([], observed['native_observed_actions'])
        self.assertTrue(any('exec envelope' in x for x in gaps))

    def test_exec_source_root_is_accepted(self):
        self.events['/root'][0]['payload']['source'] = 'exec'
        failures, gaps, observed = self.assess()
        self.assertEqual(([], []), (failures, gaps))
        self.assertEqual(7, len(observed['sessions']))

    @unittest.skipUnless(hasattr(time, 'tzset'), 'local TZ selection needs tzset')
    def test_exec_discovery_uses_local_date_across_utc_midnight(self):
        previous_tz = os.environ.get('TZ')
        os.environ['TZ'] = 'Etc/GMT-3'
        time.tzset()
        try:
            start = datetime(2026, 10, 26, 22, 14, 36, tzinfo=timezone.utc)
            for events in self.events.values():
                for event in events:
                    offset = datetime.fromisoformat(event['timestamp']) - self.start
                    event['timestamp'] = (start + offset).isoformat()
            self.start = start
            self.events['/root'][0]['payload']['source'] = 'exec'
            self.directory = self.sessions / '2026/10/27'
            self.directory.mkdir(parents=True, exist_ok=True)
            fake_now = (start + timedelta(minutes=2)).timestamp()

            class Clock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return datetime.fromtimestamp(fake_now, tz)

            with patch.object(native, 'datetime', Clock):
                failures, gaps, observed = self.assess()
            self.assertEqual(([], []), (failures, gaps))
            self.assertEqual(7, len(observed['sessions']))
        finally:
            if previous_tz is None:
                os.environ.pop('TZ', None)
            else:
                os.environ['TZ'] = previous_tz
            time.tzset()

    def test_idle_research_has_no_success_evidence(self):
        self.remove_calls('/root/research', lambda p: True)
        _, gaps, _ = self.assess()
        self.assertTrue(any('research_result' in x for x in gaps))

    def test_idle_reviewer_has_no_success_evidence(self):
        self.remove_calls('/root/review', lambda p: True)
        _, gaps, _ = self.assess()
        self.assertTrue(any('review_result' in x for x in gaps))

    def test_read_without_report_is_not_evidence_of_result(self):
        self.remove_calls('/root/design', lambda p: p.get('name') == 'send_message')
        _, gaps, _ = self.assess()
        self.assertTrue(any('design_result' in x for x in gaps))

    def test_review_before_final_change_is_incomplete(self):
        self.patch('/root', 'app.py', 70)
        failures, gaps, _ = self.assess()
        self.assertTrue(any('precedes final patch' in x for x in failures))
        self.assertTrue(any('report lacks timely successful file read: /root/review' in x for x in gaps))

    def test_successful_test_before_late_patch_fails_even_when_review_is_after(self):
        # Root test completes at 53; this patch completes at 56.1, before the
        # reviewer's first read at 57. Only the test ordering is violated.
        self.patch('/root', 'app.py', 55.1)
        failures, gaps, observed = self.assess()
        self.assertEqual(['native fixture test precedes final patch'], failures)
        self.assertEqual([], gaps)
        self.assertEqual(3, sum(item['agent_path'] == '/root/review' for item in observed['reads']))

    def test_worker_defect_must_precede_lead_return(self):
        self.remove_calls('/root/lead/calc', lambda p: p.get('name') == 'send_message')
        _, gaps, _ = self.assess()
        self.assertTrue(any('defect /root/lead/calc' in x for x in gaps))

    def test_unrecognized_spawn_output_identity_is_incomplete(self):
        for event in self.events['/root']:
            p = event['payload']
            if p.get('type') == 'function_call_output' and 'task_name' in p.get('output', ''):
                obj = json.loads(p['output'])
                obj['agent_id'] = str(uuid.uuid4())
                p['output'] = json.dumps(obj)
                break
        _, gaps, _ = self.assess()
        self.assertTrue(any('unrecognized spawn output fields' in x for x in gaps))

    def test_unknown_command_output_does_not_prove_test_success(self):
        for event in self.events['/root']:
            p = event['payload']
            if p.get('type') == 'function_call_output' and p.get('output') == json.dumps({'exit_code': 0, 'output': 'OK'}):
                p['output'] = 'Process exited with code 0'
                break
        _, gaps, observed = self.assess()
        self.assertTrue(any('unrecognized completed command output' in x for x in gaps))
        self.assertEqual([], observed['tests'])

    def test_wrong_effective_model(self):
        self.events['/root/research'][1]['payload']['model'] = 'gpt-6.1-terra'
        failures, _, _ = self.assess()
        self.assertTrue(any('model or effort mismatch' in x for x in failures))

    def test_mechanical_request_does_not_replace_effective_model_evidence(self):
        self.events['/root/lead/calc'][1]['payload']['model'] = 'gpt-6.1-sol'
        failures, _, _ = self.assess()
        self.assertIn('effective model or effort mismatch: /root/lead/calc', failures)

    def test_mechanical_request_does_not_replace_effective_effort_evidence(self):
        self.events['/root/lead/display'][1]['payload']['effort'] = 'xhigh'
        failures, _, _ = self.assess()
        self.assertIn('effective model or effort mismatch: /root/lead/display', failures)

    def test_mechanical_spawns_require_explicit_model_and_effort(self):
        for event in self.events['/root/lead']:
            payload = event['payload']
            if payload.get('name') == 'spawn_agent':
                args = json.loads(payload['arguments'])
                args.pop('model' if args['task_name'] == 'calc' else 'reasoning_effort')
                payload['arguments'] = json.dumps(args)
        failures, _, _ = self.assess()
        for child in ('calc', 'display'):
            self.assertIn('explicit mechanical spawn model or effort mismatch: /root/lead/' + child, failures)

    def test_mechanical_spawns_reject_wrong_requested_route(self):
        for event in self.events['/root/lead']:
            payload = event['payload']
            if payload.get('name') == 'spawn_agent':
                args = json.loads(payload['arguments'])
                args.update(model='gpt-6.1-sol', reasoning_effort='xhigh')
                payload['arguments'] = json.dumps(args)
        failures, _, _ = self.assess()
        for child in ('calc', 'display'):
            self.assertIn('explicit mechanical spawn model or effort mismatch: /root/lead/' + child, failures)

    def test_inherited_parent_history_is_incomplete_not_wrong_model(self):
        parent_meta = dict(self.events['/root'][0]['payload'])
        self.add('/root/research', 3.1, 'session_meta', parent_meta)
        self.add('/root/research', 3.2, 'turn_context',
                 {'turn_id': 'inherited-parent-turn', 'model': 'gpt-6.1-sol', 'effort': 'high'})
        self.spawn('/root/research', 'unapproved', 3.3)
        failures, gaps, observed = self.assess()
        self.assertFalse(any('model or effort mismatch' in x for x in failures))
        self.assertFalse(any('unexpected native spawn' in x for x in failures))
        self.assertTrue(any('mixed-session history unsupported: /root/research' in x for x in gaps))
        session = next(x for x in observed['sessions'] if x['agent_path'] == '/root/research')
        self.assertEqual([], session['turns'])
        self.assertFalse(any(x['agent_path'] == '/root/research' for x in observed['reads']))

    def test_inherited_early_spawn_is_not_attributed_to_lead(self):
        self.add('/root/lead', 25.1, 'session_meta', dict(self.events['/root'][0]['payload']))
        self.spawn('/root/lead', 'calc', 28)
        failures, gaps, _ = self.assess()
        self.assertFalse(any('child spawned before approval' in x for x in failures))
        self.assertTrue(any('mixed-session history unsupported: /root/lead' in x for x in gaps))

    def test_missing_named_role(self):
        self.events['/root/design'][0]['payload']['source']['subagent']['thread_spawn']['agent_role'] = None
        _, gaps, _ = self.assess()
        self.assertTrue(any('named native role' in x for x in gaps))

    def test_wrong_parent_does_not_satisfy_tree(self):
        self.events['/root/lead/calc'][0]['payload']['source']['subagent']['thread_spawn']['parent_thread_id'] = self.ids['/root']
        failures, _, _ = self.assess()
        self.assertTrue(any('wrong parent' in x for x in failures))

    def test_observed_approval_after_spawn_is_failure(self):
        for event in self.events['/root']:
            payload = event['payload']
            if payload.get('name') == 'send_message':
                arguments = json.loads(payload['arguments'])
                if json.loads(arguments['message']).get('cascade_event') == 'approval':
                    cid = payload['call_id']
                    event['timestamp'] = (self.start + timedelta(seconds=33)).isoformat()
                    break
        for event in self.events['/root']:
            if event['payload'].get('type') == 'function_call_output' and event['payload'].get('call_id') == cid:
                event['timestamp'] = (self.start + timedelta(seconds=34)).isoformat()
        failures, _, _ = self.assess()
        self.assertTrue(any('before approval' in x for x in failures))

    def test_encrypted_messages_are_incomplete_not_early_spawn(self):
        for events in self.events.values():
            for event in events:
                payload = event['payload']
                if payload.get('type') == 'function_call' and payload.get('name') == 'send_message':
                    arguments = json.loads(payload['arguments'])
                    arguments['message'] = 'gAAAAA-opaque-ciphertext'
                    payload['arguments'] = json.dumps(arguments)
        failures, gaps, _ = self.assess()
        self.assertEqual([], failures)
        self.assertTrue(any('approval' in x for x in gaps))
        self.assertTrue(any('clarification' in x for x in gaps))

    def test_equal_approval_and_spawn_times_are_ambiguous(self):
        for event in self.events['/root']:
            payload = event['payload']
            if payload.get('name') == 'send_message':
                arguments = json.loads(payload['arguments'])
                if json.loads(arguments['message']).get('cascade_event') == 'approval':
                    cid = payload['call_id']
                    break
        for event in self.events['/root']:
            if event['payload'].get('type') == 'function_call_output' and event['payload'].get('call_id') == cid:
                event['timestamp'] = (self.start + timedelta(seconds=32)).isoformat()
        failures, gaps, _ = self.assess()
        self.assertFalse(any('before approval' in x for x in failures))
        self.assertTrue(any('native ordering ambiguous: child spawned before approval' in x for x in gaps))

    def test_missing_patches_do_not_prove_test_was_early(self):
        for worker in ('/root/lead/calc', '/root/lead/display'):
            self.remove_calls(worker, lambda p: p.get('name') == 'apply_patch')
        failures, gaps, _ = self.assess()
        self.assertFalse(any('test precedes final patch' in x for x in failures))
        self.assertIn('native final patch timing unavailable', gaps)

    def test_input_text_output_wrapper_is_recognized(self):
        for events in self.events.values():
            for event in events:
                payload = event['payload']
                if payload.get('type') == 'custom_tool_call_output':
                    payload['output'] = [{'type': 'input_text', 'text': payload['output']}]
        failures, gaps, observed = self.assess()
        self.assertEqual(([], []), (failures, gaps))
        self.assertEqual({'calc.py', 'display.py'}, {item['path'] for item in observed['writes']})

    def test_lead_spawn_before_design_result_fails(self):
        lead_call = next(event for event in self.events['/root']
                         if event['payload'].get('name') == 'spawn_agent'
                         and json.loads(event['payload']['arguments'])['task_name'] == 'lead')
        cid = lead_call['payload']['call_id']
        lead_call['timestamp'] = (self.start + timedelta(seconds=19)).isoformat()
        for event in self.events['/root']:
            if event['payload'].get('type') == 'function_call_output' and event['payload'].get('call_id') == cid:
                event['timestamp'] = (self.start + timedelta(seconds=20)).isoformat()
        failures, _, _ = self.assess()
        self.assertTrue(any('lead spawned before design result' in x for x in failures))

    def move_design_spawn(self, second):
        call = next(event for event in self.events['/root']
                    if event['payload'].get('name') == 'spawn_agent'
                    and json.loads(event['payload']['arguments'])['task_name'] == 'design')
        cid = call['payload']['call_id']
        call['timestamp'] = (self.start + timedelta(seconds=second)).isoformat()
        for event in self.events['/root']:
            if event['payload'].get('type') == 'function_call_output' and event['payload'].get('call_id') == cid:
                event['timestamp'] = (self.start + timedelta(seconds=second + 1)).isoformat()

    def move_tool_call(self, name, tool, predicate, second):
        call = next(event for event in self.events[name]
                    if event['payload'].get('name') == tool
                    and predicate(json.loads(event['payload']['arguments'])
                                  if 'arguments' in event['payload'] else {}))
        cid = call['payload']['call_id']
        call['timestamp'] = (self.start + timedelta(seconds=second)).isoformat()
        for event in self.events[name]:
            if event['payload'].get('type') in ('function_call_output', 'custom_tool_call_output') and event['payload'].get('call_id') == cid:
                event['timestamp'] = (self.start + timedelta(seconds=second + 1)).isoformat()

    def edit_protocol(self, name, event_kind, target, change):
        for event in self.events[name]:
            payload = event['payload']
            if payload.get('name') != 'send_message':
                continue
            args = json.loads(payload['arguments'])
            body = json.loads(args['message'])
            if body.get('cascade_event') == event_kind and args.get('target') == target:
                change(body)
                args['message'] = json.dumps(body)
                payload['arguments'] = json.dumps(args)
                return
        self.fail('protocol message not found')

    def test_missing_each_content_handoff_is_incomplete(self):
        original_events = copy.deepcopy(self.events)
        cases = [('/root', 'design_handoff', '/root/design'),
                 ('/root', 'design_context', '/root/lead'),
                 ('/root/lead', 'worker_context', '/root/lead/calc'),
                 ('/root/lead', 'worker_context', '/root/lead/display')]
        for sender, event_kind, target in cases:
            with self.subTest(event=event_kind, target=target), tempfile.TemporaryDirectory() as folder:
                self.events = copy.deepcopy(original_events)
                self.artifacts = Path(folder)
                self.remove_calls(sender, lambda p: p.get('name') == 'send_message'
                                  and json.loads(p['arguments']).get('target') == target
                                  and json.loads(json.loads(p['arguments'])['message']).get('cascade_event') == event_kind)
                failures, gaps, _ = self.assess()
                self.assertEqual([], failures)
                self.assertTrue(any('protocol message missing or ambiguous: ' + event_kind in gap for gap in gaps))

    def test_content_handoff_summary_scope_and_spec_are_checked(self):
        original_events = copy.deepcopy(self.events)
        cases = [
            ('/root', 'design_handoff', '/root/design', 'invalid design handoff summary',
             lambda b: b.update(research_summary='other')),
            ('/root', 'design_handoff', '/root/design', 'invalid design handoff scope',
             lambda b: b.update(files=['display.py'])),
            ('/root', 'design_context', '/root/lead', 'invalid design context summary',
             lambda b: b.update(design_summary='other')),
            ('/root', 'design_context', '/root/lead', 'invalid design context scope',
             lambda b: b.update(files=['calc.py'])),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py summary',
             lambda b: b.update(design_summary='other')),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py scope',
             lambda b: b.update(files=['display.py'])),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py spec',
             lambda b: b['spec'].update(empty=False)),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py spec',
             lambda b: b['spec'].update(reject_boolean=1)),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py spec',
             lambda b: b['spec'].pop('empty')),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py spec',
             lambda b: b['spec'].update(extra=True)),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'invalid worker context calc.py spec',
             lambda b: b.update(spec='sum')),
            ('/root/lead', 'worker_context', '/root/lead/display', 'invalid worker context display.py spec',
             lambda b: b.update(spec={})),
            ('/root/lead', 'worker_context', '/root/lead/display', 'invalid worker context display.py spec',
             lambda b: b.pop('spec')),
        ]
        for sender, kind, target, failure, change in cases:
            with self.subTest(kind=kind, failure=failure, change=change), tempfile.TemporaryDirectory() as folder:
                self.events = copy.deepcopy(original_events)
                self.artifacts = Path(folder)
                self.edit_protocol(sender, kind, target, change)
                failures, _, _ = self.assess()
                self.assertIn(failure, failures)

    def test_missing_source_summary_is_gap_not_false_mismatch(self):
        self.edit_protocol('/root/research', 'research_result', '/root', lambda body: body.update(summary=''))
        failures, gaps, _ = self.assess()
        self.assertNotIn('invalid design handoff summary', failures)
        self.assertIn('design handoff source summary unavailable', gaps)

    def test_missing_design_summary_is_gap_not_false_mismatch(self):
        self.edit_protocol('/root/design', 'design_result', '/root', lambda body: body.update(summary=''))
        failures, gaps, _ = self.assess()
        self.assertFalse(any('context summary' in failure for failure in failures))
        self.assertIn('design context source summary unavailable', gaps)

    def test_display_patch_before_its_worker_context_fails(self):
        self.move_tool_call('/root/lead', 'send_message',
                            lambda a: a.get('target') == '/root/lead/display'
                            and json.loads(a['message']).get('cascade_event') == 'worker_context', 48.5)
        failures, _, _ = self.assess()
        self.assertIn('worker patched before worker context: /root/lead/display', failures)

    def test_assigned_direct_read_requires_worker_context(self):
        original_events = copy.deepcopy(self.events)
        violation = 'worker read before worker context: /root/lead/calc'
        for second, position in ((36.5, 'early'), (35.5, 'overlap'), (35, 'equal'), (34.1, 'after')):
            with self.subTest(position=position), tempfile.TemporaryDirectory() as folder:
                self.events = copy.deepcopy(original_events)
                self.artifacts = Path(folder)
                self.move_tool_call('/root/lead', 'send_message',
                                    lambda a: a.get('target') == '/root/lead/calc'
                                    and json.loads(a['message']).get('cascade_event') == 'worker_context', second)
                failures, gaps, _ = self.assess()
                ambiguous = 'native ordering ambiguous: ' + violation
                if position == 'early':
                    self.assertIn(violation, failures)
                elif position in ('overlap', 'equal'):
                    self.assertNotIn(violation, failures)
                    self.assertIn(ambiguous, gaps)
                else:
                    self.assertNotIn(violation, failures)
                    self.assertNotIn(ambiguous, gaps)

    def test_js_observation_is_not_worker_read_gate_evidence(self):
        self.observed_item('/root/lead/calc', 35.1)
        self.move_tool_call('/root/lead', 'send_message',
                            lambda a: a.get('target') == '/root/lead/calc'
                            and json.loads(a['message']).get('cascade_event') == 'worker_context', 36.5)
        self.move_tool_call('/root/lead/calc', 'exec_command', lambda a: a.get('cmd') == 'cat calc.py', 37.7)
        failures, gaps, observed = self.assess()
        self.assertFalse(any('worker read before worker context' in value for value in failures + gaps))
        self.assertTrue(any('unclassified native tool' in gap for gap in gaps))
        self.assertEqual(1, len(observed['native_observed_actions']))

    def test_context_order_early_overlap_and_after(self):
        original_events = copy.deepcopy(self.events)
        cases = [
            ('/root', 'design_context', '/root/lead', 'proposal precedes design context',
             ((27.5, 'early'), (26.5, 'overlap'), (26, 'equal'), (25.2, 'after'))),
            ('/root/lead', 'worker_context', '/root/lead/calc', 'worker defect precedes worker context: /root/lead/calc',
             ((38.5, 'early'), (37.5, 'overlap'), (37, 'equal'), (34.1, 'after'))),
        ]
        for sender, kind, target, violation, timings in cases:
            for second, position in timings:
                with self.subTest(edge=violation, position=position), tempfile.TemporaryDirectory() as folder:
                    self.events = copy.deepcopy(original_events)
                    self.artifacts = Path(folder)
                    self.move_tool_call(sender, 'send_message',
                                        lambda a: a.get('target') == target
                                        and json.loads(a['message']).get('cascade_event') == kind, second)
                    failures, gaps, _ = self.assess()
                    ambiguous = 'native ordering ambiguous: ' + violation
                    if position == 'early':
                        self.assertIn(violation, failures)
                    elif position in ('overlap', 'equal'):
                        self.assertNotIn(violation, failures)
                        self.assertIn(ambiguous, gaps)
                    else:
                        self.assertNotIn(violation, failures)
                        self.assertNotIn(ambiguous, gaps)

    def test_any_worker_direct_read_or_list_requires_own_context(self):
        original_events = copy.deepcopy(self.events)
        for child in ('calc', 'display'):
            worker = '/root/lead/' + child
            for operation, command in (('read', 'cat test_app.py'), ('list', 'ls'), ('list', 'ls -l')):
                violation = 'worker ' + operation + ' before worker context: ' + worker
                for context_at, position in ((36.5, 'early'), (35.5, 'overlap'), (35, 'equal'),
                                             (34.1 if child == 'calc' else 34.2, 'after')):
                    with self.subTest(worker=worker, command=command, position=position), tempfile.TemporaryDirectory() as folder:
                        self.events = copy.deepcopy(original_events)
                        self.artifacts = Path(folder)
                        if child == 'calc':
                            self.remove_calls(worker, lambda p: p.get('name') == 'exec_command'
                                              and json.loads(p['arguments']).get('cmd') == 'cat calc.py')
                        self.call(worker, 36, 'exec_command', {'cmd': command},
                                  json.dumps({'exit_code': 0, 'output': 'fixture data'}), namespace='functions')
                        self.move_tool_call('/root/lead', 'send_message',
                                            lambda a: a.get('target') == worker
                                            and json.loads(a['message']).get('cascade_event') == 'worker_context', context_at)
                        failures, gaps, _ = self.assess()
                        ambiguous = 'native ordering ambiguous: ' + violation
                        if position == 'early':
                            self.assertIn(violation, failures)
                        elif position in ('overlap', 'equal'):
                            self.assertNotIn(violation, failures)
                            self.assertIn(ambiguous, gaps)
                        else:
                            self.assertNotIn(violation, failures)
                            self.assertNotIn(ambiguous, gaps)

    def test_every_design_read_is_checked_even_if_later_read_succeeds(self):
        original_events = copy.deepcopy(self.events)
        violation = 'design read before handoff: calc.py'
        for second, position in ((13.5, 'early'), (14.5, 'overlap'), (15, 'equal'), (15.5, 'after')):
            with self.subTest(position=position), tempfile.TemporaryDirectory() as folder:
                self.events = copy.deepcopy(original_events)
                self.artifacts = Path(folder)
                self.read('/root/design', 'calc.py', second)
                failures, gaps, _ = self.assess()
                ambiguous = 'native ordering ambiguous: ' + violation
                if position == 'early':
                    self.assertIn(violation, failures)
                elif position in ('overlap', 'equal'):
                    self.assertNotIn(violation, failures)
                    self.assertIn(ambiguous, gaps)
                else:
                    self.assertNotIn(violation, failures)
                    self.assertNotIn(ambiguous, gaps)

    def test_other_worker_direct_actions_require_own_context(self):
        original_events = copy.deepcopy(self.events)
        for child in ('calc', 'display'):
            worker = '/root/lead/' + child
            for kind, label in (('send_message', 'message'), ('followup_task', 'followup'),
                                ('spawn_agent', 'spawned'), ('exec_command', 'test')):
                with self.subTest(worker=worker, kind=kind), tempfile.TemporaryDirectory() as folder:
                    self.events = copy.deepcopy(original_events)
                    self.artifacts = Path(folder)
                    self.move_tool_call('/root/lead', 'send_message',
                                        lambda a: a.get('target') == worker
                                        and json.loads(a['message']).get('cascade_event') == 'worker_context', 36.5)
                    if kind == 'spawn_agent':
                        args, output, namespace = {'task_name': 'extra'}, json.dumps({'task_name': worker + '/extra'}), 'collaboration'
                    elif kind == 'exec_command':
                        args, output, namespace = {'cmd': 'python3 -B -m unittest -v test_app'}, json.dumps({'exit_code': 0, 'output': 'OK'}), 'functions'
                    else:
                        args, output, namespace = {'target': '/root/lead', 'message': 'ordinary work'}, '', 'collaboration'
                    self.call(worker, 36, kind, args, output, namespace=namespace)
                    failures, _, _ = self.assess()
                    self.assertIn('worker ' + label + ' before worker context: ' + worker, failures)

    def test_encrypted_worker_context_does_not_prove_early_list(self):
        for event in self.events['/root/lead']:
            payload = event['payload']
            if payload.get('name') == 'send_message':
                args = json.loads(payload['arguments'])
                if args.get('target') == '/root/lead/calc' and json.loads(args['message']).get('cascade_event') == 'worker_context':
                    args['message'] = 'gAAAAA-opaque-ciphertext'
                    payload['arguments'] = json.dumps(args)
                    break
        self.call('/root/lead/calc', 36, 'exec_command', {'cmd': 'ls'},
                  json.dumps({'exit_code': 0, 'output': 'fixture files'}), namespace='functions')
        failures, gaps, _ = self.assess()
        self.assertNotIn('worker list before worker context: /root/lead/calc', failures)
        self.assertTrue(any('protocol message missing or ambiguous: worker_context' in gap for gap in gaps))

    def test_design_spawn_and_defect_question_order_intervals(self):
        original_events = copy.deepcopy(self.events)
        cases = [
            ('/root', 'design_handoff', '/root/design', 'design handoff precedes design spawn',
             ((10.5, 'early'), (11.5, 'overlap'), (12, 'equal'), (14, 'after'))),
            ('/root/lead', 'question', '/root', 'question precedes defect return',
             ((39.5, 'early'), (40.5, 'overlap'), (41, 'equal'), (42, 'after'))),
        ]
        for sender, event_kind, target, violation, timings in cases:
            for second, position in timings:
                with self.subTest(edge=violation, position=position), tempfile.TemporaryDirectory() as folder:
                    self.events = copy.deepcopy(original_events)
                    self.artifacts = Path(folder)
                    self.move_tool_call(sender, 'send_message',
                                        lambda a: a.get('target') == target
                                        and json.loads(a['message']).get('cascade_event') == event_kind, second)
                    failures, gaps, _ = self.assess()
                    ambiguous = 'native ordering ambiguous: ' + violation
                    if position == 'early':
                        self.assertIn(violation, failures)
                    elif position in ('overlap', 'equal'):
                        self.assertNotIn(violation, failures)
                        self.assertIn(ambiguous, gaps)
                    else:
                        self.assertNotIn(violation, failures)
                        self.assertNotIn(ambiguous, gaps)

    def test_causal_order_intervals(self):
        original_events = copy.deepcopy(self.events)
        scenarios = [
            ('/root', 'spawn_agent', lambda args: args.get('task_name') == 'lead',
             'lead spawned before design result', (19, 20.5, 21, 22)),
            ('/root', 'send_message', lambda args: json.loads(args['message']).get('cascade_event') == 'approval',
             'approval does not follow proposal', (26.5, 27.5, 28, 29)),
            ('/root/lead/calc', 'apply_patch', lambda args: True,
             'worker patched before clarification: /root/lead/calc', (45.5, 46.5, 47, 48)),
            ('/root', 'exec_command', lambda args: args.get('cmd') == 'python3 -B -m unittest -v test_app',
             'native fixture test precedes final patch', (47.5, 48.5, 49, 50)),
        ]
        for name, tool, predicate, violation, times in scenarios:
            for position, second in zip(('early', 'overlap', 'equal', 'after'), times):
                with self.subTest(edge=violation, position=position), tempfile.TemporaryDirectory() as folder:
                    self.events = copy.deepcopy(original_events)
                    self.artifacts = Path(folder)
                    self.move_tool_call(name, tool, predicate, second)
                    failures, gaps, _ = self.assess()
                    ambiguous = 'native ordering ambiguous: ' + violation
                    if position == 'early':
                        self.assertIn(violation, failures)
                    elif position in ('overlap', 'equal'):
                        self.assertNotIn(violation, failures)
                        self.assertIn(ambiguous, gaps)
                    else:
                        self.assertNotIn(violation, failures)
                        self.assertNotIn(ambiguous, gaps)

    def test_each_patch_is_compared_to_test_independently(self):
        self.patch('/root', 'app.py', 40)
        root_patch = next(event for event in self.events['/root']
                          if event['payload'].get('name') == 'apply_patch')
        for event in self.events['/root']:
            if event['payload'].get('type') == 'custom_tool_call_output' and event['payload'].get('call_id') == root_patch['payload']['call_id']:
                event['timestamp'] = (self.start + timedelta(seconds=60)).isoformat()
        self.move_tool_call('/root', 'exec_command',
                            lambda args: args.get('cmd') == 'python3 -B -m unittest -v test_app', 47.5)
        failures, gaps, _ = self.assess()
        self.assertIn('native fixture test precedes final patch', failures)
        self.assertIn('native ordering ambiguous: native fixture test precedes final patch', gaps)

    def test_worker_patch_requires_both_clarification_forwards(self):
        original_events = copy.deepcopy(self.events)
        violation = 'worker patched before clarification: /root/lead/calc'
        for position, second in (('early', 49), ('overlap', 47.5), ('equal', 47), ('after', 46)):
            with self.subTest(position=position), tempfile.TemporaryDirectory() as folder:
                self.events = copy.deepcopy(original_events)
                self.artifacts = Path(folder)
                self.move_tool_call('/root/lead', 'send_message',
                                    lambda args: args.get('target') == '/root/lead/display'
                                    and json.loads(args['message']).get('cascade_event') == 'clarification', second)
                failures, gaps, _ = self.assess()
                ambiguous = 'native ordering ambiguous: ' + violation
                if position == 'early':
                    self.assertIn(violation, failures)
                elif position in ('overlap', 'equal'):
                    self.assertNotIn(violation, failures)
                    self.assertIn(ambiguous, gaps)
                else:
                    self.assertNotIn(violation, failures)
                    self.assertNotIn(ambiguous, gaps)

    def test_design_spawn_before_research_result_fails(self):
        self.move_design_spawn(6.5)
        failures, _, _ = self.assess()
        self.assertIn('design spawned before research result', failures)

    def test_design_spawn_at_research_result_time_is_ambiguous(self):
        self.move_design_spawn(8)
        failures, gaps, _ = self.assess()
        self.assertNotIn('design spawned before research result', failures)
        self.assertIn('native ordering ambiguous: design spawned before research result', gaps)

    def test_design_spawn_during_research_send_is_ambiguous(self):
        self.move_design_spawn(7.5)
        failures, gaps, _ = self.assess()
        self.assertNotIn('design spawned before research result', failures)
        self.assertIn('native ordering ambiguous: design spawned before research result', gaps)

    def test_design_spawn_at_research_send_start_is_ambiguous(self):
        self.move_design_spawn(7)
        failures, gaps, _ = self.assess()
        self.assertNotIn('design spawned before research result', failures)
        self.assertIn('native ordering ambiguous: design spawned before research result', gaps)

    def test_missing_research_result_does_not_prove_early_design_spawn(self):
        self.move_design_spawn(6.5)
        self.remove_calls('/root/research', lambda p: p.get('name') == 'send_message')
        failures, gaps, _ = self.assess()
        self.assertNotIn('design spawned before research result', failures)
        self.assertTrue(any('research_result' in gap for gap in gaps))

    def test_approval_substitutes_child_scope(self):
        for event in self.events['/root']:
            payload = event['payload']
            if payload.get('name') == 'send_message':
                args = json.loads(payload['arguments'])
                body = json.loads(args['message'])
                if body['cascade_event'] == 'approval':
                    body['children'][0]['files'] = ['display.py']
                    args['message'] = json.dumps(body)
                    payload['arguments'] = json.dumps(args)
        failures, _, _ = self.assess()
        self.assertTrue(any('child scopes' in x for x in failures))

    def test_missing_output_and_context(self):
        self.events['/root/lead/calc'] = [e for e in self.events['/root/lead/calc'] if e['type'] != 'turn_context' and e['payload'].get('type') != 'custom_tool_call_output']
        _, gaps, _ = self.assess()
        self.assertTrue(any('turns missing' in x for x in gaps))
        self.assertTrue(any('paired outputs' in x for x in gaps))

    def test_malformed_types_are_incomplete(self):
        self.add('/root', 60, 'response_item', {'type': [], 'name': 'apply_patch'})
        _, gaps, _ = self.assess()
        self.assertTrue(any('invalid native record' in x for x in gaps))

    def test_duplicate_root_and_unrelated_log(self):
        self.save()
        unrelated = self.directory / ('rollout-unrelated-' + str(uuid.uuid4()) + '.jsonl')
        unrelated.write_text('{"type":"session_meta","payload":{}}\n', encoding='utf-8')
        duplicate = self.directory / ('rollout-other-' + self.ids['/root'] + '.jsonl')
        duplicate.write_text('ignored\n', encoding='utf-8')
        _, gaps, _ = native.collect_and_assess(self.ids['/root'], self.sessions, self.artifacts,
                                                self.fixture, self.policy, self.start.timestamp())
        self.assertIn('native root trace missing or ambiguous', gaps)
        self.assertFalse((self.artifacts / 'native-traces').exists())

    def test_unrelated_trace_ignored(self):
        unrelated = self.directory / ('rollout-unrelated-' + str(uuid.uuid4()) + '.jsonl')
        unrelated.write_text('{"type":"session_meta","payload":{}}\n', encoding='utf-8')
        failures, gaps, observed = self.assess()
        self.assertEqual(([], []), (failures, gaps))
        self.assertEqual(7, len(observed['sessions']))

    def test_patch_scope_escape(self):
        self.patch('/root/lead/calc', '../outside.py', 49)
        _, gaps, _ = self.assess()
        self.assertTrue(any('unsafe patch path' in x for x in gaps))

    def test_wrong_worker_patch(self):
        self.patch('/root/lead/calc', 'display.py', 49)
        failures, _, _ = self.assess()
        self.assertTrue(any('unauthorized native write' in x for x in failures))

    def test_fabricated_agent_message_does_not_approve(self):
        self.events['/root'] = [e for e in self.events['/root'] if e['payload'].get('name') != 'send_message' and not (e['payload'].get('type') == 'function_call_output' and e['payload'].get('output') == '')]
        self.add('/root', 12, 'response_item', {'type': 'agent_message', 'content': json.dumps({'cascade_event': 'approval', 'children': native.CHILDREN})})
        failures, gaps, _ = self.assess()
        self.assertTrue(any('protocol message missing' in x for x in gaps))
        self.assertFalse(any('before approval' in x for x in failures))

    def test_unknown_write_capability_is_incomplete(self):
        self.call('/root', 60, 'exec', 'arbitrary javascript', '', custom=True)
        _, gaps, _ = self.assess()
        self.assertTrue(any('unclassified native tool' in x for x in gaps))

    def test_duplicate_test_attempt_is_failure(self):
        self.call('/root/lead/calc', 46, 'exec_command', {'cmd': 'python3 -B -m unittest -v test_app'},
                  json.dumps({'exit_code': 0, 'output': 'OK'}), namespace='functions')
        failures, _, _ = self.assess()
        self.assertTrue(any('more than once' in x for x in failures))

    def test_symlink_candidate_rejected(self):
        (self.directory / 'rollout-link.jsonl').symlink_to(self.directory / 'missing')
        _, gaps, _ = self.assess()
        self.assertTrue(any('symlink' in x for x in gaps))

    def test_no_time_budget_does_not_scan(self):
        _, gaps, observed = native.collect_and_assess(self.ids['/root'], self.sessions, self.artifacts,
                                                       self.fixture, self.policy, self.start.timestamp(), budget_seconds=0)
        self.assertTrue(any('budget unavailable' in x for x in gaps))
        self.assertEqual([], observed['sessions'])
        self.assertFalse((self.artifacts / 'native-traces').exists())


if __name__ == '__main__':
    unittest.main()
