"""Isolated native-agent cascade fixture and conservative CLI event assessment.

Only CLI-produced JSONL and filesystem snapshots are evidence. Text from an
agent, including its final response, is never converted into a tool event.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shlex
import stat

from . import SkillEvalEvidence as evidence

SCENARIO = "atomic-cascade"
FILES = {
    "calc.py": "def total(values):\n    return sum(values)\n",
    "display.py": "def describe(value):\n    return str(value)\n",
    "app.py": "from calc import total\nfrom display import describe\n\ndef report(values):\n    return describe(total(values))\n",
    "test_app.py": (
        "import unittest\nfrom app import report\n\n"
        "class ReportTests(unittest.TestCase):\n"
        "    def test_empty(self):\n        self.assertEqual(report([]), 'total: 0')\n"
        "    def test_values(self):\n        self.assertEqual(report([2, -1, 4]), 'total: 5')\n"
        "    def test_reject_bool(self):\n        with self.assertRaises(TypeError):\n            report([True])\n"
    ),
}
# Only these known, non-secret repository inputs are copied, never the project
# config (which may enable MCP servers), auth, the real home, or a product tree.
SHIPPED_INPUTS = {
    "tools/Codex/GlobalAgentInstructions.md": "AGENTS.md",
    "tools/Codex/AgentRouting.json": "policy/AgentRouting.json",
    "docs/Agents/ReportFormat.md": "docs/Agents/ReportFormat.md",
    ".codex/agents/researcher-sol.toml": ".codex/agents/researcher-sol.toml",
    ".codex/agents/planner-sol.toml": ".codex/agents/planner-sol.toml",
}
PROMPT = """Implement the small reporting fixture: total integer values and format the result
as `total: <value>`. This task requests independent research and design, a branch
lead with two disjoint atomic patch workers, root integration, and an independent
generic read-only Sol/xhigh review, following the shipped instructions.
The caller has selected and approved this exact fixture plan: research, design,
two scoped patches, root integration, the one named test and independent review.
That approval permits changes to calc.py, display.py and app.py and the single
named test below; no renewed plan approval is needed. It does not authorize other
plans or actions. This fixture statement and its synthetic protocol/clarification
are not evidence of any real UI user approval.
Use these stable task names: root starts `research` with agent_type `researcher_sol`,
`design` with agent_type `planner_sol`, `lead` and `review`; lead starts `calc`
for calc.py and `display` for display.py. Lead proposes the
children to root and waits for root's approval before starting either child.
Root owns app.py and final integration.
Root follows the selected primary routing; lead uses the Sol/high default-worker
route. The two small calc/display patches
use the mechanical Terra/high route: lead must pass explicit
`model="gpt-6.1-terra"` and `reasoning_effort="high"` in both spawn_agent calls.
The generic reviewer uses Sol/xhigh. Requested settings alone are not execution
evidence; the native trace must show each session's effective model and effort.
Start every child with `fork_turns="none"` and a complete scoped assignment;
do not copy the parent's turn history into a research, design or worker session.

Synthetic clarification supplied in advance by the fixture: empty input must
produce total 0, and bool values must be rejected (bool is a subclass of int).
This is synthetic, not a real UI user message or approval. Relay a discovered
defect through the branch to root and propagate the clarification to workers.

For this evaluation only, use native send_message with these JSON payloads and
wait for delivery before dependent actions. Delivery demonstrates transmission,
not a recipient's understanding or a real UI interaction. Every named read below is a separate
successful direct `cat <file>` via exec_command. Research reads calc.py, then:
research -> root: {"cascade_event":"research_result","summary":"<nonempty finding>","files":["calc.py"]}
Root must wait until it receives research_result before spawning design. After
spawning design, root sends the exact research_result.summary string as
research_summary (replace the placeholder; do not send it literally):
root -> design: {"cascade_event":"design_handoff","research_summary":"<research_result.summary>","files":["calc.py"]}
Design reads calc.py and display.py after the handoff, then:
design -> root: {"cascade_event":"design_result","summary":"<nonempty design>","files":["calc.py","display.py"]}
Root must receive design_result before spawning lead, then send lead the exact
design_result.summary string as design_summary before lead makes its proposal:
root -> lead: {"cascade_event":"design_context","design_summary":"<design_result.summary>","files":["calc.py","display.py"]}
After approval and child starts, lead sends each child its context, carrying that
same exact design_summary and only its own file. Send the spec objects exactly:
lead -> calc: {"cascade_event":"worker_context","design_summary":"<design_result.summary>","files":["calc.py"],"spec":{"operation":"sum","empty":0,"reject_boolean":true}}
lead -> display: {"cascade_event":"worker_context","design_summary":"<design_result.summary>","files":["display.py"],"spec":{"format":"total: <value>"}}
Each worker waits for its own context before any work or patch. Unrelated
independent work may run concurrently only if it respects these fixture
dependencies, limits and permissions. After calc receives its context, calc reads
calc.py using a successful direct cat, identifies the existing bool acceptance and:
calc -> lead: {"cascade_event":"defect","id":"bool-accepted"}
Lead forwards that defect to root, asks the question, waits for the answer and
forwards the clarification to both children before either child patches. No
worker should patch until its clarification arrives.
lead -> root: {"cascade_event":"proposal","children":[{"task_name":"calc","files":["calc.py"]},{"task_name":"display","files":["display.py"]}]}
root -> lead: {"cascade_event":"approval","children":[{"task_name":"calc","files":["calc.py"]},{"task_name":"display","files":["display.py"]}]}
lead -> root: {"cascade_event":"defect","id":"bool-accepted"}
lead -> root: {"cascade_event":"question","question_id":"bool-empty"}
root -> lead: {"cascade_event":"clarification","question_id":"bool-empty","answer":"Empty input produces total 0; bool values are rejected."}
lead -> each worker: {"cascade_event":"clarification","question_id":"bool-empty","answer":"Empty input produces total 0; bool values are rejected."}
Do not start children before the approval. Use native apply_patch for edits so the
trace can associate each changed path with its author. Root runs the one fixture
test only after all patches. After all patches the reviewer separately reads
app.py, calc.py and display.py using successful direct cat calls, then sends:
review -> root: {"cascade_event":"review_result","summary":"<nonempty review>","files":["app.py","calc.py","display.py"]}

Test-specific permissions and limits: use at most 8 agents total including root,
at most 4 concurrent, and finish within the deadline. Only calc.py, display.py and
app.py may be changed. For each read or listing, use a separate direct
exec_command call with one of these forms:
- `ls` or `ls -l` with no path argument;
- `cat <file>` with exactly one of these paths: calc.py, display.py, app.py,
  test_app.py, AGENTS.md, policy/AgentRouting.json, docs/Agents/ReportFormat.md,
  .codex/agents/researcher-sol.toml, .codex/agents/planner-sol.toml.
The .codex/agents path is a directory; read its two named TOML files directly.
Do not pass a directory or path argument to ls. Do not use compound commands,
shell operators, or read multiple files in one command. The only test permitted
is `python3 -B -m unittest -v test_app`, once. No Git, network, external MCP,
servers, product trees, or other checks.
"""


def cli_environment(environ: dict[str, str]) -> dict[str, str]:
    """Retain CLI essentials and configured proxies without forwarding other credentials."""
    allowed = {"PATH", "HOME", "USER", "LOGNAME", "SHELL", "LANG", "TZ", "TERM", "TMPDIR", "CODEX_HOME",
               "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
               "http_proxy", "https_proxy", "all_proxy", "no_proxy"}
    result = {key: value for key, value in environ.items() if key in allowed or key.startswith("LC_")}
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def prepare(root: Path, fixture: Path) -> None:
    for name, contents in FILES.items():
        (fixture / name).write_text(contents, encoding="utf-8")
    for source, name in SHIPPED_INPUTS.items():
        data = (root / source).read_bytes()
        if len(data) > evidence.MAX_FILE_BYTES:
            raise ValueError("shipped fixture input too large: " + source)
        destination = fixture / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def command_argv(command: str) -> list[str] | None:
    """Allow direct and one explicit shell wrapper around an exact safe argv."""
    try:
        if "\n" in command or "\r" in command:
            return None
        args = shlex.split(command, comments=False)
        shells = {"bash", "/bin/bash", "/usr/bin/bash", "sh", "/bin/sh", "/usr/bin/sh"}
        if len(args) == 3 and args[0] in shells and args[1] in {"-c", "-lc"}:
            command = args[2]
            args = shlex.split(command, comments=False)
        if any(c in command for c in "\n\r;&|`$<>()#*?[]\\"):
            return None
        if args == ["python3", "-B", "-m", "unittest", "-v", "test_app"]:
            return args
        if args in (["ls"], ["ls", "-l"]):
            return args
        readable = set(FILES) | set(SHIPPED_INPUTS.values())
        if len(args) == 2 and args[0] in {"cat", "/bin/cat", "/usr/bin/cat"} and args[1] in readable:
            return args
        return None
    except ValueError:
        return None


def command_allowed(command: str) -> bool:
    return command_argv(command) is not None


def save_fixture_output(fixture: Path, destination: Path, after: dict) -> list[str]:
    """Save fixture output only after a no-follow, bounded hash-checked read."""
    destination.mkdir(parents=True, exist_ok=True)
    gaps = []
    for name in FILES:
        try:
            fd = os.open(fixture / name, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("not a regular file")
                contents = stream.read(evidence.MAX_FILE_BYTES + 1)
            if len(contents) > evidence.MAX_FILE_BYTES:
                raise ValueError("file exceeds output limit")
            if hashlib.sha256(contents).hexdigest() != after.get(name, {}).get("sha256"):
                raise ValueError("file changed after snapshot")
            (destination / name).write_bytes(contents)
        except (OSError, ValueError) as exc:
            gaps.append("fixture output unavailable: " + name + ": " + str(exc)[:100])
    return gaps


class StreamMonitor:
    """Stop the owned process on an observable forbidden attempt, not on prose."""
    def __init__(self, fixture: Path):
        self.fixture = fixture
        self.buffer = b""
        self.spawns = set()

    def feed(self, chunk: bytes) -> str | None:
        self.buffer += chunk
        if len(self.buffer) > evidence.MAX_FILE_BYTES and b"\n" not in self.buffer:
            return None  # The retained parser will mark oversized events incomplete.
        lines = self.buffer.split(b"\n")
        self.buffer = lines.pop()
        for line in lines:
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    continue
                event_type = event.get("type")
                item = event.get("item")
                if not isinstance(event_type, str) or event_type not in {"item.started", "item.updated", "item.completed"} or not isinstance(item, dict):
                    continue
                kind = item.get("type")
                if kind == "command_execution" and isinstance(item.get("command"), str) and not command_allowed(item["command"]):
                    return "forbidden command attempted: " + item["command"][:200]
                if kind == "web_search" or (isinstance(kind, str) and "mcp" in kind):
                    return "forbidden network or MCP tool attempted: " + str(kind)
                if kind == "file_change" and isinstance(item.get("changes"), list):
                    for change in item["changes"]:
                        name = change.get("path") if isinstance(change, dict) else None
                        if not isinstance(name, str):
                            continue
                        path = Path(name)
                        if path.is_absolute():
                            try:
                                name = path.relative_to(self.fixture).as_posix()
                            except ValueError:
                                return "edit attempted outside fixture"
                        try:
                            if evidence.relative_path(name).as_posix() not in {"calc.py", "display.py", "app.py"}:
                                return "unauthorized edit attempted: " + name[:200]
                        except ValueError:
                            return "unsafe edit path attempted"
                if kind == "collab_tool_call" and isinstance(item.get("tool"), str) and item["tool"] in {"spawn_agent", "spawn"}:
                    ident = item.get("id")
                    if isinstance(ident, str):
                        self.spawns.add(ident)
                    if len(self.spawns) > 7:
                        return "more than seven observed spawn attempts"
            except (ValueError, UnicodeError, AttributeError):
                continue
        return None


def root_thread_id(path: Path) -> str:
    """Find one unambiguous root ID in the CLI's own bounded event stream."""
    ids = set()
    with path.open("rb") as stream:
        for line in stream:
            if len(line) > evidence.MAX_FILE_BYTES:
                raise ValueError("oversized CLI event")
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue  # The CLI event assessor records malformed lines.
            if isinstance(event, dict) and event.get("type") == "thread.started":
                ident = event.get("thread_id")
                if not isinstance(ident, str) or not ident:
                    raise ValueError("invalid root thread identifier")
                ids.add(ident)
    if len(ids) != 1:
        raise ValueError("root thread identifier is missing or ambiguous")
    return next(iter(ids))


def inspect_events(path: Path, fixture: Path, policy: dict, native_trace: bool = False) -> tuple[list[str], list[str], dict]:
    """Inspect observed CLI events, never interpret model-authored prose as events.

    The currently supported CLI stream cannot attest the complete descendant
    action stream, model settings, or the root's subtree approval. Do not infer
    these from prompts, config, agent messages, or a self-reported transcript.
    """
    failures, gaps = [], []
    seen, pending, commands, spawns = set(), set(), set(), {}
    test_ids, started_actions = set(), set()
    terminal_test = False
    if not path.is_file():
        return [], ["CLI events unavailable"], {"commands": [], "spawns": []}
    with path.open("rb") as stream:
        for line in stream:
            if len(line) > evidence.MAX_FILE_BYTES:
                gaps.append("oversized event line")
                break
            try:
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError
            except (ValueError, UnicodeError):
                gaps.append("invalid JSONL event")
                continue
            typ = event.get("type")
            if not isinstance(typ, str):
                gaps.append("event type is not text")
                continue
            seen.add(typ)
            if typ in {"thread.started", "turn.started", "turn.completed"}:
                continue
            if typ in {"turn.failed", "error"}:
                gaps.append("CLI reported unsuccessful turn")
                continue
            if typ not in {"item.started", "item.updated", "item.completed"}:
                gaps.append("unrecognized event: " + str(typ)[:100])
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                gaps.append("item event lacks object")
                continue
            kind = item.get("type")
            if not isinstance(kind, str):
                gaps.append("item type is not text")
                continue
            if kind in {"agent_message", "reasoning", "todo_list"}:
                continue
            status = item.get("status")
            if status is not None and not isinstance(status, str):
                gaps.append("action status is not text")
            ident = item.get("id")
            if not isinstance(ident, str) or not ident:
                gaps.append("action lacks identity")
            elif typ == "item.completed":
                if ident not in started_actions:
                    gaps.append("action lacks observed start: " + ident[:100])
                pending.discard(ident)
            else:
                if typ == "item.started":
                    started_actions.add(ident)
                pending.add(ident)
            if kind == "command_execution":
                command = item.get("command")
                if not isinstance(command, str) or not command:
                    gaps.append("command lacks text")
                    continue
                commands.add(command)
                argv = command_argv(command)
                if argv is None:
                    failures.append("forbidden command attempted: " + command[:200])
                elif argv == ["python3", "-B", "-m", "unittest", "-v", "test_app"] and isinstance(ident, str):
                    test_ids.add(ident)
                    if len(test_ids) > 1:
                        failures.append("fixture test attempted more than once")
                if argv == ["python3", "-B", "-m", "unittest", "-v", "test_app"] and typ == "item.completed":
                    code = item.get("exit_code")
                    if status == "completed" and type(code) is int:
                        if code != 0:
                            failures.append("fixture test command failed")
                        elif isinstance(ident, str) and ident in started_actions:
                            terminal_test = True
                        else:
                            gaps.append("fixture test lacks observed start")
                    elif status == "failed":
                        failures.append("fixture test command failed")
                    else:
                        gaps.append("fixture test lacks terminal outcome")
            elif kind == "file_change":
                changes = item.get("changes")
                if not isinstance(changes, list) or not changes:
                    gaps.append("file change lacks paths")
                    continue
                for change in changes:
                    name = change.get("path") if isinstance(change, dict) else None
                    if not isinstance(name, str):
                        gaps.append("file change lacks path")
                        continue
                    path_value = Path(name)
                    if path_value.is_absolute():
                        try:
                            name = path_value.relative_to(fixture).as_posix()
                        except ValueError:
                            failures.append("edit attempted outside fixture")
                            continue
                    try:
                        name = evidence.relative_path(name).as_posix()
                    except ValueError:
                        failures.append("unsafe edit path attempted")
                        continue
                    if name not in {"calc.py", "display.py", "app.py"}:
                        failures.append("unauthorized edit attempted: " + name[:200])
            elif kind == "web_search" or (isinstance(kind, str) and "mcp" in kind):
                failures.append("forbidden network or MCP tool attempted: " + str(kind))
            elif kind == "collab_tool_call":
                # A top-level collab event proves an attempt, not descendant
                # execution, effective model/effort, or nested approval order.
                tool = item.get("tool")
                if not isinstance(tool, str):
                    gaps.append("collaboration tool is not text")
                elif tool in {"spawn_agent", "spawn"}:
                    if isinstance(ident, str):
                        spawns[ident] = {"id": ident, "status": item.get("status"),
                                         "sender_thread_id": item.get("sender_thread_id"),
                                         "receiver_thread_ids": item.get("receiver_thread_ids")}

            else:
                gaps.append("unrecognized action item: " + str(kind)[:100])
    if not {"thread.started", "turn.started", "turn.completed"}.issubset(seen):
        gaps.append("missing completed-turn events")
    if pending:
        gaps.append("action items lack terminal events")
    if not terminal_test:
        gaps.append("successful fixture test event unavailable")
    if len(spawns) > 7:
        failures.append("more than seven observed spawn attempts")
    # CLI JSON does not currently bind the requested facts to observed descendant
    # events. A new verified native event adapter is needed before granting pass.
    if not native_trace:
        gaps.extend(["descendant events and complete parent/child tree unavailable",
                 "effective agent models and efforts unavailable",
                 "shipped role registration and effective profiles unavailable",
                 "root subtree proposal and approval ordering unavailable",
                 "defect return and synthetic clarification propagation unavailable",
                 "independent review and descendant write attribution unavailable"])
    return sorted(set(failures)), sorted(set(gaps)), {"commands": sorted(commands), "spawns": list(spawns.values())}


def check_fixture(changes: list[dict], after: dict) -> list[str]:
    assertions = {"allowedChangedGlobs": ["calc.py", "display.py", "app.py"],
                  "requiredChangedGlobs": ["calc.py", "display.py"]}
    failures = evidence.check_files(assertions, changes, after)
    for name in ("calc.py", "display.py", "app.py", "test_app.py"):
        if after.get(name, {}).get("kind") != "file":
            failures.append("fixture file missing or not regular: " + name)
    return failures
