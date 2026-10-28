#!/usr/bin/env python3
"""Fail-closed state manager for durable CXETCPP implementation plans."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable

try:
    import fcntl
except ImportError:
    fcntl = None


PLAN_STATUSES = {"active", "verification_pending", "clean", "blocked", "archived"}
TASK_STATUSES = {
    "draft",
    "ready",
    "in_progress",
    "done_unverified",
    "verified",
    "blocked",
    "needs_decision",
    "superseded",
}
COMPLEXITIES = {"MECHANICAL", "LOGIC", "COMPLEX"}
EVIDENCE_TYPES = {"static", "schema", "build", "targeted-test", "runtime", "browser", "model", "performance", "live"}
INTEGRATED_STATUSES = {"done_unverified", "verified"}
LEGAL_TRANSITIONS = {
    "draft": {"ready", "blocked", "needs_decision", "superseded"},
    "ready": {"in_progress", "blocked", "needs_decision", "superseded"},
    "in_progress": {"done_unverified", "blocked", "needs_decision"},
    "done_unverified": {"verified", "ready", "blocked", "needs_decision", "superseded"},
    "verified": {"superseded"},
    "blocked": {"ready", "needs_decision", "superseded"},
    "needs_decision": {"ready", "blocked", "superseded"},
    "superseded": set(),
}
TASK_FIELDS = {
    "id",
    "title",
    "complexity",
    "status",
    "dependsOn",
    "ownerRole",
    "ownedPaths",
    "sharedPaths",
    "anchors",
    "acceptanceCriteria",
    "antiCriteria",
    "requiredEvidence",
    "verificationCommands",
    "permissionsRequired",
    "prompt",
    "evidence",
}
PLAN_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)*$")


class PlanError(RuntimeError):
    pass


@contextmanager
def _plan_writer_lock(plan_dir: Path):
    """One nonblocking canonical writer, tied to the directory across rename."""
    if fcntl is None or not hasattr(os, "O_DIRECTORY"):
        raise PlanError("plan directory writer locking is unavailable on this platform")
    try:
        descriptor = os.open(plan_dir, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise PlanError(f"cannot open plan directory for writer lock: {plan_dir}: {exc}") from exc
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PlanError(f"plan directory writer lock is busy: {plan_dir}") from exc
        except OSError as exc:
            raise PlanError(f"cannot acquire plan directory writer lock: {plan_dir}: {exc}") from exc
        yield
    finally:
        os.close(descriptor)


def _plan_mutator(function):
    @wraps(function)
    def locked(plan_dir: Path, *args, **kwargs):
        with _plan_writer_lock(plan_dir):
            return function(plan_dir, *args, **kwargs)
    return locked


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"invalid JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PlanError(f"top-level JSON value must be an object: {path}")
    return value


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _required_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{field} must be a non-empty string")
    return value


def _exact_fields(value: Any, fields: set[str], field: str, *, optional: set[str] | None = None) -> None:
    if not isinstance(value, dict):
        raise PlanError(f"{field} must be an object")
    missing = fields - set(value)
    unexpected = set(value) - fields - (optional or set())
    if missing or unexpected:
        raise PlanError(f"{field} has invalid fields; missing: {sorted(missing)}, unexpected: {sorted(unexpected)}")


def _string_list(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise PlanError(f"{field} must be a list of non-empty strings")
    if non_empty and not value:
        raise PlanError(f"{field} must not be empty")
    if len(value) != len(set(value)):
        raise PlanError(f"{field} must not contain duplicates")
    return value


def _evidence_types(value: Any, field: str, *, non_empty: bool = False) -> list[str]:
    result = _string_list(value, field, non_empty=non_empty)
    unknown = set(result) - EVIDENCE_TYPES
    if unknown:
        raise PlanError(f"{field} contains unknown evidence types: {sorted(unknown)}")
    return result


def _latest_results(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {result["command"]: result for result in evidence["commandResults"]}


def _verification_error(task: dict[str, Any]) -> str | None:
    evidence = task["evidence"]
    if evidence is None:
        return f"verified task {task['id']} has no evidence"
    if not set(task["requiredEvidence"]).issubset(evidence["types"]):
        return f"verified task {task['id']} has insufficient evidence"
    latest = _latest_results(evidence)
    for command in task["verificationCommands"]:
        if command not in latest or latest[command]["exitStatus"] != 0:
            return (f"verified task {task['id']} requires a successful latest result "
                    f"for every declared verification command: {command}")
    proven = {kind for result in latest.values() if result["exitStatus"] == 0 for kind in result["types"]}
    missing = (set(task["requiredEvidence"]) | set(evidence["types"])) - {"static"} - proven
    if missing:
        return f"verified task {task['id']} lacks matching successful command evidence: {sorted(missing)}"
    return None


def _path_root(value: str) -> str:
    normalized = value.replace("\\", "/").strip().rstrip("/")
    for suffix in ("/**", "/*"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    if not normalized or normalized.startswith("/") or normalized.startswith("../"):
        raise PlanError(f"owned path must be repository-relative: {value}")
    return normalized


def _paths_overlap(left: str, right: str) -> bool:
    left_root = _path_root(left)
    right_root = _path_root(right)
    return (
        left_root == right_root
        or left_root.startswith(right_root + "/")
        or right_root.startswith(left_root + "/")
    )


def _task_map(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            raise PlanError("every task must be an object")
        task_id = _required_string(task.get("id"), "task.id")
        if not TASK_ID_RE.fullmatch(task_id):
            raise PlanError(f"invalid task id: {task_id}")
        if task_id in result:
            raise PlanError(f"duplicate task id: {task_id}")
        result[task_id] = task
    return result


def _dependency_closure(task_id: str, tasks: dict[str, dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    pending = list(tasks[task_id]["dependsOn"])
    while pending:
        dependency = pending.pop()
        if dependency in result:
            continue
        result.add(dependency)
        pending.extend(tasks[dependency]["dependsOn"])
    return result


def _validate_task(task: dict[str, Any]) -> None:
    missing = TASK_FIELDS - set(task)
    if missing:
        raise PlanError(f"task {task.get('id', '<unknown>')} missing fields: {sorted(missing)}")
    _exact_fields(task, TASK_FIELDS, f"task {task['id']}")
    _required_string(task["title"], f"{task['id']}.title")
    _required_string(task["ownerRole"], f"{task['id']}.ownerRole")
    _required_string(task["prompt"], f"{task['id']}.prompt")
    if task["complexity"] not in COMPLEXITIES:
        raise PlanError(f"{task['id']}.complexity must be one of {sorted(COMPLEXITIES)}")
    if task["status"] not in TASK_STATUSES:
        raise PlanError(f"{task['id']}.status must be one of {sorted(TASK_STATUSES)}")
    _evidence_types(task["requiredEvidence"], f"{task['id']}.requiredEvidence", non_empty=True)
    _string_list(task["dependsOn"], f"{task['id']}.dependsOn")
    owned = _string_list(task["ownedPaths"], f"{task['id']}.ownedPaths", non_empty=True)
    shared = _string_list(task["sharedPaths"], f"{task['id']}.sharedPaths")
    for item in owned + shared:
        _path_root(item)
    for left in owned:
        if any(_paths_overlap(left, right) for right in shared):
            raise PlanError(f"{task['id']} assigns the same boundary as owned and shared: {left}")
    _string_list(task["anchors"], f"{task['id']}.anchors", non_empty=True)
    _string_list(task["acceptanceCriteria"], f"{task['id']}.acceptanceCriteria", non_empty=True)
    _string_list(task["antiCriteria"], f"{task['id']}.antiCriteria", non_empty=True)
    _string_list(task["verificationCommands"], f"{task['id']}.verificationCommands")
    _string_list(task["permissionsRequired"], f"{task['id']}.permissionsRequired")
    evidence = task["evidence"]
    if evidence is not None:
        if not isinstance(evidence, dict):
            raise PlanError(f"{task['id']}.evidence must be null or an object")
        if "level" in evidence:
            raise PlanError(f"{task['id']}.evidence.level is unsupported; use types")
        _exact_fields(evidence, {"types", "summary", "commandResults"}, f"{task['id']}.evidence")
        _evidence_types(evidence.get("types"), f"{task['id']}.evidence.types")
        _required_string(evidence.get("summary"), f"{task['id']}.evidence.summary")
        command_results = evidence.get("commandResults")
        if not isinstance(command_results, list):
            raise PlanError(f"{task['id']}.evidence.commandResults must be a list")
        for result in command_results:
            if not isinstance(result, dict):
                raise PlanError(f"{task['id']} command result must be an object")
            _exact_fields(result, {"command", "types", "exitStatus", "summary"}, f"{task['id']}.commandResult")
            command = _required_string(result.get("command"), f"{task['id']}.evidence.command")
            if command not in task["verificationCommands"]:
                raise PlanError(f"{task['id']} evidence command was not listed in the plan: {command}")
            if type(result.get("exitStatus")) is not int:
                raise PlanError(f"{task['id']}.evidence.exitStatus must be an integer")
            _evidence_types(result.get("types"), f"{task['id']}.evidence.commandTypes")
            _required_string(result.get("summary"), f"{task['id']}.evidence.commandSummary")
    if task["status"] == "verified":
        error = _verification_error(task)
        if error:
            raise PlanError(error)
    elif evidence is not None:
        latest = _latest_results(evidence)
        proven = {kind for result in latest.values() if result["exitStatus"] == 0 for kind in result["types"]}
        missing_types = set(evidence["types"]) - {"static"} - proven
        if missing_types:
            raise PlanError(f"{task['id']} lacks matching successful command evidence: {sorted(missing_types)}")


def _derived_plan_status(tasks: list[dict[str, Any]]) -> str:
    material = [task for task in tasks if task["status"] != "superseded"]
    if material and all(task["status"] == "verified" for task in material):
        return "clean"
    if any(task["status"] == "done_unverified" for task in material):
        return "verification_pending"
    if material and all(task["status"] in {"blocked", "needs_decision"} for task in material):
        return "blocked"
    return "active"


def validate_state_data(state: dict[str, Any], plan_bytes: bytes) -> None:
    _exact_fields(state, {"planId", "planStatus", "repoOwner", "planSha256", "tasks", "findings"}, "state")
    plan_id = _required_string(state.get("planId"), "planId")
    if not PLAN_ID_RE.fullmatch(plan_id):
        raise PlanError(f"invalid planId: {plan_id}")
    _required_string(state.get("repoOwner"), "repoOwner")
    if state.get("planStatus") not in PLAN_STATUSES:
        raise PlanError(f"invalid planStatus: {state.get('planStatus')}")
    if state.get("planSha256") != _sha256(plan_bytes):
        raise PlanError("planSha256 does not match plan.md")
    tasks_value = state.get("tasks")
    if not isinstance(tasks_value, list):
        raise PlanError("tasks must be a list")
    if not isinstance(state.get("findings"), list):
        raise PlanError("findings must be a list")
    tasks = _task_map(tasks_value)
    for task in tasks.values():
        _validate_task(task)
        for dependency in task["dependsOn"]:
            if dependency == task["id"]:
                raise PlanError(f"task {task['id']} depends on itself")
            if dependency not in tasks:
                raise PlanError(f"task {task['id']} has unknown dependency {dependency}")
    for task_id in tasks:
        if task_id in _dependency_closure(task_id, tasks):
            raise PlanError(f"dependency cycle includes {task_id}")
    finding_task_ids: set[str] = set()
    for finding in state["findings"]:
        if not isinstance(finding, dict):
            raise PlanError("every finding must be an object")
        _exact_fields(finding, {"taskId", "severity", "status"}, "finding")
        task_id = _required_string(finding.get("taskId"), "finding.taskId")
        if task_id not in tasks:
            raise PlanError(f"finding refers to unknown task: {task_id}")
        if task_id in finding_task_ids:
            raise PlanError(f"duplicate finding task: {task_id}")
        finding_task_ids.add(task_id)
        if finding.get("severity") not in {"BLOCKER", "HIGH", "MEDIUM", "LOW", "NOTE"}:
            raise PlanError(f"finding {task_id} has invalid severity")
        if finding.get("status") not in {"open", "closed"}:
            raise PlanError(f"finding {task_id} has invalid status")
        if finding["status"] == "closed" and tasks[task_id]["status"] not in INTEGRATED_STATUSES:
            raise PlanError(f"finding {task_id} is closed without an integrated task")

    executable = [
        task for task in tasks.values()
        if task["status"] in {"ready", "in_progress"}
        and all(tasks[dependency]["status"] in INTEGRATED_STATUSES for dependency in task["dependsOn"])
    ]
    for index, left in enumerate(executable):
        left_dependencies = _dependency_closure(left["id"], tasks)
        for right in executable[index + 1 :]:
            right_dependencies = _dependency_closure(right["id"], tasks)
            if right["id"] in left_dependencies or left["id"] in right_dependencies:
                continue
            for left_path in left["ownedPaths"]:
                for right_path in right["ownedPaths"]:
                    if _paths_overlap(left_path, right_path):
                        raise PlanError(
                            f"concurrently executable tasks {left['id']} and {right['id']} "
                            f"overlap ownership: {left_path} vs {right_path}"
                        )

    material_tasks = [task for task in tasks.values() if task["status"] != "superseded"]
    if state["planStatus"] in {"clean", "archived"}:
        if not material_tasks or any(task["status"] != "verified" for task in material_tasks):
            raise PlanError(f"planStatus {state['planStatus']} requires every active task to be verified")
    if state["planStatus"] != "archived":
        expected_status = _derived_plan_status(state["tasks"])
        if state["planStatus"] != expected_status:
            raise PlanError(
                f"planStatus {state['planStatus']} is inconsistent with tasks; expected {expected_status}"
            )


def validate_plan_dir(plan_dir: Path) -> dict[str, Any]:
    plan_path = plan_dir / "plan.md"
    state_path = plan_dir / "state.json"
    try:
        plan_bytes = plan_path.read_bytes()
    except FileNotFoundError as exc:
        raise PlanError(f"missing file: {plan_path}") from exc
    state = _json(state_path)
    validate_state_data(state, plan_bytes)
    if plan_dir.name != state["planId"]:
        raise PlanError(f"plan directory name must equal planId: {state['planId']}")
    return state


@_plan_mutator
def seal_plan(plan_dir: Path) -> dict[str, Any]:
    plan_path = plan_dir / "plan.md"
    state_path = plan_dir / "state.json"
    try:
        plan_bytes = plan_path.read_bytes()
    except FileNotFoundError as exc:
        raise PlanError(f"missing file: {plan_path}") from exc
    state = _json(state_path)
    state["planSha256"] = _sha256(plan_bytes)
    validate_state_data(state, plan_bytes)
    if plan_dir.name != state["planId"]:
        raise PlanError(f"plan directory name must equal planId: {state['planId']}")
    _atomic_json(state_path, state)
    return state


def _refresh_plan_status(state: dict[str, Any]) -> None:
    if state["planStatus"] == "archived":
        return
    state["planStatus"] = _derived_plan_status(state["tasks"])


def initialize_plan(plan_dir: Path, plan_id: str, repo_owner: str, title: str) -> None:
    if not PLAN_ID_RE.fullmatch(plan_id):
        raise PlanError(f"invalid planId: {plan_id}")
    if fcntl is None or not hasattr(os, "O_DIRECTORY"):
        raise PlanError("plan directory writer locking is unavailable on this platform")
    try:
        plan_dir.mkdir(parents=True)
    except FileExistsError as exc:
        raise PlanError(f"plan directory already exists: {plan_dir}") from exc
    except OSError as exc:
        raise PlanError(f"cannot create plan directory: {plan_dir}: {exc}") from exc
    with _plan_writer_lock(plan_dir):
        _initialize_plan_locked(plan_dir, plan_id, repo_owner, title)


def _initialize_plan_locked(plan_dir: Path, plan_id: str, repo_owner: str, title: str) -> None:
    plan_text = (
        f"# {title}\n\n"
        "## Summary\n\n"
        "- TODO\n\n"
        "## Tasks\n\n"
        "Add decision-complete task sections with stable IDs matching `state.json`.\n\n"
        "## Verification gates\n\n"
        "List exact commands and their required permission; do not record them as run.\n"
    )
    state = {
        "planId": plan_id,
        "planStatus": "active",
        "repoOwner": repo_owner,
        "planSha256": _sha256(plan_text.encode("utf-8")),
        "tasks": [],
        "findings": [],
    }
    validate_state_data(state, plan_text.encode("utf-8"))
    _atomic_text(plan_dir / "plan.md", plan_text)
    _atomic_json(plan_dir / "state.json", state)


def ready_tasks(state: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = _task_map(state["tasks"])
    return [
        task for task in state["tasks"]
        if task["status"] == "ready"
        and all(tasks[dependency]["status"] in INTEGRATED_STATUSES for dependency in task["dependsOn"])
    ]


def _new_task(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "id": args.task_id,
        "title": args.title,
        "complexity": args.complexity,
        "status": "ready",
        "dependsOn": args.depends_on,
        "ownerRole": args.owner_role,
        "ownedPaths": args.owned_path,
        "sharedPaths": args.shared_path,
        "anchors": args.anchor,
        "acceptanceCriteria": args.accept,
        "antiCriteria": args.anti,
        "requiredEvidence": args.required_evidence or ["static"],
        "verificationCommands": args.verification_command,
        "permissionsRequired": args.permission,
        "prompt": args.prompt,
        "evidence": None,
    }


@_plan_mutator
def add_task(plan_dir: Path, args: argparse.Namespace, *, finding: bool) -> None:
    state = validate_plan_dir(plan_dir)
    if state["planStatus"] == "archived":
        raise PlanError("cannot change an archived plan")
    task = _new_task(args)
    if finding:
        task["dependsOn"] = list(dict.fromkeys(task["dependsOn"]))
    state["tasks"].append(task)
    section = (
        f"\n\n## {'Verification finding' if finding else 'Task'} {task['id']}: {task['title']}\n\n"
        f"- Complexity: `{task['complexity']}`\n"
        f"- Owner: `{task['ownerRole']}`\n"
        f"- Depends on: {', '.join(task['dependsOn']) if task['dependsOn'] else 'none'}\n"
        f"- Owned paths: {', '.join(task['ownedPaths'])}\n"
        f"- Shared paths: {', '.join(task['sharedPaths']) if task['sharedPaths'] else 'none'}\n"
        f"- Anchors: {'; '.join(task['anchors'])}\n"
        f"- Required evidence: {', '.join(f'`{kind}`' for kind in task['requiredEvidence'])}\n"
        f"- Prompt: {task['prompt']}\n"
        f"- Acceptance: {'; '.join(task['acceptanceCriteria'])}\n"
        f"- Anti-criteria: {'; '.join(task['antiCriteria'])}\n"
        f"- Permission requirements: {'; '.join(task['permissionsRequired']) if task['permissionsRequired'] else 'none'}\n"
        "- Exact verification commands (not execution evidence):\n"
        + ("\n".join(f"  - `{command}`" for command in task['verificationCommands'])
           if task['verificationCommands'] else "  - none") + "\n"
    )
    if finding:
        section += f"- Severity: `{args.severity}`\n"
        state["findings"].append({"taskId": task["id"], "severity": args.severity, "status": "open"})
    plan_path = plan_dir / "plan.md"
    updated_plan = plan_path.read_text(encoding="utf-8").rstrip() + section
    state["planSha256"] = _sha256(updated_plan.encode("utf-8"))
    _refresh_plan_status(state)
    validate_state_data(state, updated_plan.encode("utf-8"))
    _atomic_text(plan_path, updated_plan)
    _atomic_json(plan_dir / "state.json", state)


@_plan_mutator
def transition_task(
    plan_dir: Path,
    task_id: str,
    target: str,
    evidence_types: list[str] | None,
    evidence_summary: str | None,
    command_results: list[dict[str, Any]],
) -> None:
    state = validate_plan_dir(plan_dir)
    tasks = _task_map(state["tasks"])
    if task_id not in tasks:
        raise PlanError(f"unknown task: {task_id}")
    task = tasks[task_id]
    if target not in LEGAL_TRANSITIONS[task["status"]]:
        raise PlanError(f"illegal transition {task['status']} -> {target} for {task_id}")
    if target == "in_progress":
        missing = [dependency for dependency in task["dependsOn"] if tasks[dependency]["status"] not in INTEGRATED_STATUSES]
        if missing:
            raise PlanError(f"task {task_id} has unintegrated dependencies: {missing}")
    if target == "verified" or evidence_types is not None or evidence_summary is not None or command_results:
        if evidence_types is None or not evidence_summary:
            raise PlanError("recording evidence requires --evidence-type and --evidence-summary")
        _evidence_types(evidence_types, "evidence types")
        previous_results = task["evidence"]["commandResults"] if task["evidence"] is not None else []
        task["evidence"] = {
            "types": evidence_types,
            "summary": evidence_summary,
            "commandResults": previous_results + command_results,
        }
    task["status"] = target
    for finding in state["findings"]:
        if finding.get("taskId") == task_id and target == "verified":
            finding["status"] = "closed"
    _refresh_plan_status(state)
    plan_bytes = (plan_dir / "plan.md").read_bytes()
    validate_state_data(state, plan_bytes)
    _atomic_json(plan_dir / "state.json", state)


def resolve_plan(repo_owner: Path, plan_id: str | None) -> Path:
    active_root = repo_owner / 'docs' / "agent-plans" / "active"
    if plan_id:
        candidate = active_root / plan_id
        validate_plan_dir(candidate)
        return candidate
    candidates = sorted(path for path in active_root.iterdir() if path.is_dir()) if active_root.is_dir() else []
    if len(candidates) != 1:
        raise PlanError(f"expected exactly one active plan, found {len(candidates)}; provide --plan-id")
    validate_plan_dir(candidates[0])
    return candidates[0]


@_plan_mutator
def archive_plan(plan_dir: Path, archive_root: Path) -> Path:
    state = validate_plan_dir(plan_dir)
    if state["planStatus"] != "clean":
        raise PlanError("only a clean plan may be archived")
    destination = archive_root / state["planId"]
    if destination.exists():
        raise PlanError(f"archive destination already exists: {destination}")
    archive_root.mkdir(parents=True, exist_ok=True)
    original_status = state["planStatus"]
    state["planStatus"] = "archived"
    _atomic_json(plan_dir / "state.json", state)
    try:
        os.replace(plan_dir, destination)
    except OSError as exc:
        state["planStatus"] = original_status
        _atomic_json(plan_dir / "state.json", state)
        raise PlanError(f"failed to archive plan: {exc}") from exc
    validate_plan_dir(destination)
    return destination


def validate_rule_index(repo_root: Path) -> dict[str, Any]:
    index_path = repo_root / "docs" / "Agents" / "RuleIndex.json"
    index = _json(index_path)
    _exact_fields(index, {"policyGlobs", "rules"}, "rule-index")
    if not isinstance(index.get("rules"), list):
        raise PlanError("invalid rule-index contract")
    for pattern in _string_list(index.get("policyGlobs"), "rule-index.policyGlobs", non_empty=True):
        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise PlanError(f"unsafe rule-index policy glob: {pattern}")
    seen: set[str] = set()
    for rule in index["rules"]:
        if not isinstance(rule, dict):
            raise PlanError("rule-index entries must be objects")
        _exact_fields(rule, {"id", "path", "triggers"}, "rule-index entry", optional={"requiredText"})
        rule_id = _required_string(rule.get("id"), "rule.id")
        if rule_id in seen:
            raise PlanError(f"duplicate rule id: {rule_id}")
        seen.add(rule_id)
        path = _required_string(rule.get("path"), f"{rule_id}.path")
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise PlanError(f"unsafe rule owner path: {path}")
        _string_list(rule.get("triggers"), f"{rule_id}.triggers", non_empty=True)
        owner_path = repo_root / path
        if not owner_path.is_file():
            raise PlanError(f"rule owner does not exist: {path}")
        required_text = _string_list(rule.get("requiredText", []), f"{rule_id}.requiredText")
        if required_text:
            owner_text = owner_path.read_text(encoding="utf-8")
            missing_text = [anchor for anchor in required_text if anchor not in owner_text]
            if missing_text:
                raise PlanError(f"rule owner {path} is missing preserved anchors: {missing_text}")
    root_text = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    required_pointers = (
        "docs/Agents/GlobalContracts.md",
        "docs/Agents/HotPathFastLane.md",
        "docs/Agents/PlanWorkflow.md",
        "docs/Agents/AwsWorkflow.md",
        "docs/Agents/RoleRouter.md",
        "docs/Agents/ReportFormat.md",
    )
    missing = [pointer for pointer in required_pointers if pointer not in root_text]
    if missing:
        raise PlanError(f"AGENTS.md is missing mandatory routing pointers: {missing}")
    return index


def _task_arguments(parser: argparse.ArgumentParser, *, finding: bool) -> None:
    parser.add_argument("plan_dir", type=Path)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--complexity", choices=sorted(COMPLEXITIES), default="LOGIC")
    parser.add_argument("--owner-role", required=True)
    parser.add_argument("--depends-on", action="append", default=[])
    parser.add_argument("--owned-path", action="append", required=True)
    parser.add_argument("--shared-path", action="append", default=[])
    parser.add_argument("--anchor", action="append", required=True)
    parser.add_argument("--accept", action="append", required=True)
    parser.add_argument("--anti", action="append", required=True)
    parser.add_argument("--required-evidence", choices=sorted(EVIDENCE_TYPES), action="append")
    parser.add_argument("--verification-command", action="append", default=[])
    parser.add_argument("--permission", action="append", default=[])
    parser.add_argument("--prompt", required=True)
    if finding:
        parser.add_argument("--severity", choices=("BLOCKER", "HIGH", "MEDIUM", "LOW", "NOTE"), required=True)


def _command_results(values: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for value in values:
        try:
            result = json.loads(value)
        except json.JSONDecodeError as exc:
            raise PlanError(f"invalid --command-result JSON: {exc}") from exc
        if not isinstance(result, dict):
            raise PlanError("--command-result must encode a JSON object")
        results.append(result)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create an empty plan.md/state.json pair")
    init.add_argument("plan_dir", type=Path)
    init.add_argument("--plan-id", required=True)
    init.add_argument("--repo-owner", required=True)
    init.add_argument("--title", required=True)

    validate = commands.add_parser("validate", help="validate a plan directory")
    validate.add_argument("plan_dir", type=Path)

    seal = commands.add_parser("seal", help="bind state to the current plan.md hash")
    seal.add_argument("plan_dir", type=Path)

    ready = commands.add_parser("ready", help="print executable ready tasks as JSON")
    ready.add_argument("plan_dir", type=Path)

    resolve = commands.add_parser("resolve", help="resolve one active plan")
    resolve.add_argument("repo_owner", type=Path)
    resolve.add_argument("--plan-id")

    add = commands.add_parser("add-task", help="append a task to plan and state")
    _task_arguments(add, finding=False)

    finding = commands.add_parser("add-finding", help="append a verifier finding as a task")
    _task_arguments(finding, finding=True)

    transition = commands.add_parser("transition", help="apply one legal task-state transition")
    transition.add_argument("plan_dir", type=Path)
    transition.add_argument("task_id")
    transition.add_argument("target", choices=sorted(TASK_STATUSES))
    transition.add_argument("--evidence-type", choices=sorted(EVIDENCE_TYPES), action="append")
    transition.add_argument("--evidence-summary")
    transition.add_argument(
        "--command-result",
        action="append",
        default=[],
        help='JSON object with command, types, integer exitStatus, and summary',
    )

    archive = commands.add_parser("archive", help="move a clean plan to its archive root")
    archive.add_argument("plan_dir", type=Path)
    archive.add_argument("archive_root", type=Path)

    rules = commands.add_parser("rules", help="validate the agent rule index")
    rules.add_argument("repo_root", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            initialize_plan(args.plan_dir, args.plan_id, args.repo_owner, args.title)
            print(args.plan_dir)
        elif args.command == "validate":
            state = validate_plan_dir(args.plan_dir)
            print(json.dumps({"planId": state["planId"], "planStatus": state["planStatus"], "valid": True}))
        elif args.command == "seal":
            state = seal_plan(args.plan_dir)
            print(json.dumps({"planId": state["planId"], "sealed": True}))
        elif args.command == "ready":
            state = validate_plan_dir(args.plan_dir)
            print(json.dumps(ready_tasks(state), indent=2, ensure_ascii=False))
        elif args.command == "resolve":
            print(resolve_plan(args.repo_owner, args.plan_id))
        elif args.command == "add-task":
            add_task(args.plan_dir, args, finding=False)
        elif args.command == "add-finding":
            add_task(args.plan_dir, args, finding=True)
        elif args.command == "transition":
            transition_task(
                args.plan_dir,
                args.task_id,
                args.target,
                args.evidence_type,
                args.evidence_summary,
                _command_results(args.command_result),
            )
        elif args.command == "archive":
            print(archive_plan(args.plan_dir, args.archive_root))
        elif args.command == "rules":
            index = validate_rule_index(args.repo_root)
            print(json.dumps({"rules": len(index["rules"]), "valid": True}))
        else:
            raise PlanError(f"unsupported command: {args.command}")
    except PlanError as exc:
        print(f"plan_workflow: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
