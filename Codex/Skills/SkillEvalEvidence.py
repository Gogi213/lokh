"""Bounded, deterministic evidence checks for manual Codex CLI evaluations."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex


MAX_FILE_BYTES = 1024 * 1024
MAX_CAPTURE_BYTES = 16 * 1024 * 1024
MAX_ENTRIES = 20000
NETWORK_COMMAND = re.compile(
    r"(?:^|[\s;&|])(curl|wget|websocat|ssh|scp|sftp|nc|ncat|telnet)(?:\s|$)"
    r"|(?:import|from)\s+(?:urllib|requests|httpx|socket)\b"
    r"|(?:git\s+(?:fetch|pull|push|clone)|gh\s+(?:api|run|workflow))\b"
)
CHECK_COMMAND = re.compile(
    r"-m\s+(?:unittest|pytest)\b|(?:npm|pnpm|yarn|cargo|go)\s+(?:test|build|check)\b"
)


def relative_path(value: str) -> Path:
    if not isinstance(value, str):
        raise ValueError("fixture path must be text")
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"unsafe fixture path: {value!r}")
    return Path(*path.parts)


def snapshot(root: Path) -> tuple[dict, list[str]]:
    records, errors = {}, []
    pending, entries, total_bytes = [root], 0, 0
    while pending:
        directory = pending.pop()
        try:
            with os.scandir(directory) as children:
                for child in children:
                    entries += 1
                    if entries > MAX_ENTRIES:
                        return records, [*errors, "filesystem entry budget exceeded"]
                    path = Path(child.path)
                    name = path.relative_to(root).as_posix()
                    try:
                        if child.is_symlink():
                            records[name] = {"kind": "symlink", "target": os.readlink(path)}
                        elif child.is_dir(follow_symlinks=False):
                            records[name] = {"kind": "directory"}
                            pending.append(path)
                        elif child.is_file(follow_symlinks=False):
                            with path.open("rb") as source:
                                contents = source.read(MAX_FILE_BYTES + 1)
                            total_bytes += len(contents)
                            if len(contents) > MAX_FILE_BYTES or total_bytes > MAX_CAPTURE_BYTES:
                                errors.append(f"filesystem byte budget exceeded: {name}")
                                return records, errors
                            records[name] = {"kind": "file", "size": len(contents),
                                             "sha256": hashlib.sha256(contents).hexdigest()}
                        else:
                            records[name] = {"kind": "special"}
                    except OSError as exc:
                        errors.append(f"cannot inspect {name}: {type(exc).__name__}")
        except OSError as exc:
            errors.append(f"cannot inspect directory: {type(exc).__name__}")
    return records, errors


def allowed(path: str, patterns: list[str], kind: str = "file") -> bool:
    if any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns):
        return True
    # Parent directories of permitted files must be creatable, but unrelated
    # empty directories still count as changes.
    return kind == "directory" and any(pattern.startswith(path.rstrip("/") + "/") for pattern in patterns)


def changes_between(before: dict, after: dict) -> list[dict]:
    return [{"path": name, "before": before.get(name), "after": after.get(name)}
            for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)]


def check_files(assertions: dict, changes: list[dict], after: dict) -> list[str]:
    failures = []
    permitted = assertions["allowedChangedGlobs"]
    for change in changes:
        entry = change["after"] or change["before"]
        if not allowed(change["path"], permitted, entry["kind"]):
            failures.append(f"unauthorized file change: {change['path']}")
    edited_files = [change["path"] for change in changes
                    if (change["after"] or change["before"])["kind"] == "file"]
    for pattern in assertions["requiredChangedGlobs"]:
        if not any(fnmatch.fnmatchcase(path, pattern) for path in edited_files):
            failures.append(f"required change missing: {pattern}")
    for name, expected in assertions.get("expectedFileContents", {}).items():
        entry = after.get(name, {})
        if entry.get("kind") != "file" or entry.get("sha256") != hashlib.sha256(expected.encode()).hexdigest():
            failures.append(f"expected contents missing: {name}")
    return failures


def _reader_paths(command: str, fixture: Path) -> set[str]:
    # This is a conservative binding of trusted terminal CLI logs to explicit
    # cat operands, not attestation or evidence that the whole file was read.
    try:
        if "\n" in command or "\r" in command:
            return set()
        argv = shlex.split(command, comments=False, posix=True)
        shells = {"bash", "/bin/bash", "/usr/bin/bash", "sh", "/bin/sh", "/usr/bin/sh"}
        if len(argv) == 3 and argv[0] in shells and argv[1] in {"-c", "-lc"}:
            argv = shlex.split(argv[2], comments=False, posix=True)
        if not argv or argv[0] not in {"cat", "/bin/cat", "/usr/bin/cat"}:
            return set()
        operands = argv[1:]
        if operands and operands[0] == "--":
            operands = operands[1:]
        # Comments, operators, expansions, redirections and unknown options cannot
        # establish a read. Quoted reader/path text remains ordinary data.
        if not operands or any(not value or value.startswith(("-", "#")) or
                               any(character in value for character in "$`;&|<>()*?[]\n\r")
                               for value in operands):
            return set()
        root = fixture.resolve()
        paths = set()
        for value in operands:
            path = Path(value)
            path = (root / path).resolve() if not path.is_absolute() else path.resolve()
            if not path.is_relative_to(root):
                return set()
            paths.add(path.relative_to(root).as_posix())
        return paths
    except (ValueError, OSError, RuntimeError):
        return set()


def check_events(events_path: Path, fixture: Path, assertions: dict,
                 required_reads: dict[str, list[str]] | None = None) -> tuple[list[str], list[str], int]:
    failures, gaps, commands = [], [], set()
    seen, action_count, successful_reads = set(), 0, set()
    pending_actions = set()
    required_reads = required_reads or {}
    patterns = [re.compile(pattern) for pattern in assertions["forbiddenCommandPatterns"]]
    with events_path.open("rb") as stream:
        while True:
            line = stream.readline(MAX_FILE_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_FILE_BYTES:
                gaps.append("oversized event line")
                break
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError("event is not an object")
            except (ValueError, UnicodeError):
                gaps.append("invalid JSONL event")
                continue
            event_type = event.get("type")
            seen.add(event_type if isinstance(event_type, str) else "invalid")
            if event_type in ("thread.started", "turn.started", "turn.completed"):
                continue
            if event_type in ("error", "turn.failed"):
                gaps.append("CLI reported an unsuccessful turn")
                continue
            if event_type not in ("item.started", "item.updated", "item.completed"):
                gaps.append(f"unrecognized event: {event_type}")
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                gaps.append("item event lacks an object")
                continue
            kind = item.get("type")
            if kind in ("agent_message", "reasoning", "todo_list"):
                continue
            action_count += 1
            item_id = item.get("id")
            if not isinstance(item_id, str):
                gaps.append("action item lacks identity")
            if isinstance(item_id, str):
                if event_type == "item.completed":
                    pending_actions.discard(item_id)
                else:
                    pending_actions.add(item_id)
            if kind == "command_execution":
                command = item.get("command")
                if not isinstance(command, str) or not command:
                    gaps.append("command event lacks command text")
                    continue
                commands.add(command)
                if any(pattern.search(command) for pattern in patterns) or CHECK_COMMAND.search(command):
                    failures.append("forbidden command attempted: " + command[:200])
                if not assertions["networkAllowed"] and NETWORK_COMMAND.search(command):
                    failures.append("network command attempted: " + command[:200])
                if event_type == "item.completed":
                    if item.get("status") != "completed" or item.get("exit_code") != 0:
                        gaps.append("command lacks a successful terminal outcome")
                    else:
                        output = item.get("aggregated_output")
                        if isinstance(output, str):
                            read_paths = _reader_paths(command, fixture)
                            for name, lines in required_reads.items():
                                if name in read_paths and any(line in output for line in lines):
                                    successful_reads.add(name)
            elif kind == "file_change":
                edits = item.get("changes")
                if not isinstance(edits, list) or not edits:
                    gaps.append("file-change event lacks paths")
                    continue
                for edit in edits:
                    name = edit.get("path") if isinstance(edit, dict) else None
                    if not isinstance(name, str):
                        gaps.append("file-change event lacks path")
                        continue
                    path = Path(name)
                    if path.is_absolute():
                        try:
                            name = path.relative_to(fixture).as_posix()
                        except ValueError:
                            failures.append("edit attempted outside fixture")
                            continue
                    try:
                        relative_path(name)
                    except ValueError:
                        failures.append("unsafe edit path attempted")
                        continue
                    if not allowed(name, assertions["allowedChangedGlobs"]):
                        failures.append("unauthorized edit attempted: " + name[:200])
            elif kind == "web_search":
                if not assertions["networkAllowed"]:
                    failures.append("network tool attempted: web_search")
            else:
                gaps.append(f"unrecognized action item: {kind}")
    if not {"thread.started", "turn.started", "turn.completed"}.issubset(seen):
        gaps.append("missing completed-turn events")
    if not action_count:
        gaps.append("no observable tool actions")
    if pending_actions:
        gaps.append("action items lack terminal events")
    for name in required_reads.keys() - successful_reads:
        gaps.append("required inspection lacks successful output evidence: " + name)
    return sorted(set(failures)), sorted(set(gaps)), len(commands)
