#!/usr/bin/env python3
"""Run explicitly authorized manual evals via the existing authenticated CLI.

Routine CI imports/tests this runner with a fake process. Real model calls
require --run and separate task-scoped permission; no API key is requested.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

try:
    from tools.Codex.Skills import SkillEvalEvidence as evidence
    from tools.Codex import PlanWorkflow as workflow
    from tools.Codex import AgentRouting as routing
    from tools.Codex.Skills import CascadeEval as cascade
    from tools.Codex.Skills import CascadeNativeTrace as native_trace
except ModuleNotFoundError:
    from Skills import SkillEvalEvidence as evidence
    import PlanWorkflow as workflow
    import AgentRouting as routing
    from Skills import CascadeEval as cascade
    from Skills import CascadeNativeTrace as native_trace


MODEL = "gpt-6.1-sol"
REASONING = "high"
FINAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "outcome": {"type": "string", "enum": ["completed", "needs_permission", "needs_decision"]},
        "evidence_types": {"type": "array", "items": {"type": "string", "enum": ["static-only"]}},
        "summary": {"type": "string"},
    },
    "required": ["outcome", "evidence_types", "summary"],
}


def load_suite(path: Path) -> dict:
    suite = json.loads(path.read_text())  # Repository YAML intentionally uses JSON syntax.
    if not isinstance(suite, dict) or set(suite) != {"model", "reasoningEffort", "scenarios"}:
        raise ValueError("invalid eval suite fields")
    if suite.get("model") != MODEL or suite.get("reasoningEffort") != REASONING:
        raise ValueError("unsupported eval model routing")
    scenarios = suite.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios or len(scenarios) > 32:
        raise ValueError("eval suite requires 1..32 scenarios")
    ids = set()
    for scenario in scenarios:
        if not isinstance(scenario, dict) or set(scenario) != {"id", "hardPermission", "prompt", "fixtureFiles", "assertions"}:
            raise ValueError("invalid eval scenario fields")
        if type(scenario["hardPermission"]) is not bool:
            raise ValueError("hardPermission must be a boolean")
        name = scenario.get("id", "")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]+", name) or name in ids:
            raise ValueError("invalid or duplicate scenario id")
        ids.add(name)
        if not isinstance(scenario.get("prompt"), str) or not scenario["prompt"]:
            raise ValueError("scenario requires a prompt")
        if not isinstance(scenario.get("fixtureFiles"), dict):
            raise ValueError("scenario requires fixtureFiles")
        for name, text in scenario["fixtureFiles"].items():
            evidence.relative_path(name)
            if not isinstance(text, str) or len(text.encode()) > evidence.MAX_FILE_BYTES:
                raise ValueError("invalid fixture file contents")
        assertions = scenario.get("assertions", {})
        required = {"allowedChangedGlobs", "requiredChangedGlobs", "forbiddenCommandPatterns", "outcomes", "evidenceTypes", "networkAllowed"}
        optional = {"expectedFileContents", "requiredReadPaths", "validPlanDirectories"}
        if not isinstance(assertions, dict) or not required.issubset(assertions) or set(assertions) - required - optional:
            raise ValueError("invalid eval assertion fields")
        for field in ("allowedChangedGlobs", "requiredChangedGlobs", "forbiddenCommandPatterns", "outcomes", "evidenceTypes"):
            if not isinstance(assertions.get(field), list) or not all(isinstance(v, str) for v in assertions[field]):
                raise ValueError("invalid assertion: " + field)
        if assertions.get("networkAllowed") is not False:
            raise ValueError("these evals prohibit agent network access")
        for pattern in assertions["forbiddenCommandPatterns"]:
            re.compile(pattern)
        expected = assertions.get("expectedFileContents", {})
        if not isinstance(expected, dict):
            raise ValueError("expectedFileContents must be an object")
        for name, text in expected.items():
            evidence.relative_path(name)
            if not isinstance(text, str):
                raise ValueError("expected contents must be text")
        for field in ("requiredReadPaths", "validPlanDirectories"):
            values = assertions.get(field, [])
            if not isinstance(values, list):
                raise ValueError("invalid assertion: " + field)
            for name in values:
                evidence.relative_path(name)
    return suite


def prepare_fixture(root: Path, fixture: Path, scenario: dict) -> None:
    # Instructions and the durable-plan helper suffice; no source tree, auth,
    # user config, services, Git repository, or external MCP is copied.
    candidates = [root / "AGENTS.md", root / "tools/Codex/PlanWorkflow.py"]
    candidates += list((root / "docs/Agents").glob("*.md"))
    candidates += list((root / "docs/Agents").glob("*.json"))
    candidates += list((root / ".agents/skills").glob("*/SKILL.md"))
    candidates += list((root / ".codex/agents").glob("*.toml"))
    for source in candidates:
        if source.is_file():
            destination = fixture / source.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    for name, text in scenario["fixtureFiles"].items():
        destination = fixture / evidence.relative_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")


def cli_command(codex: list[str], scenario: dict, fixture: Path, artifacts: Path) -> list[str]:
    sandbox = "workspace-write" if scenario["assertions"]["allowedChangedGlobs"] else "read-only"
    return [*codex, "--ask-for-approval", "never", "exec",
            "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
            "--model", MODEL, "--sandbox", sandbox, "--cd", str(fixture),
            "-c", 'model_reasoning_effort="high"', "-c", 'service_tier="default"',
            "-c", "features.fast_mode=true", "-c", "agents.enabled=false",
            "-c", 'web_search="disabled"', "-c", "sandbox_workspace_write.network_access=false",
            "--json", "--output-schema", str(artifacts / "final-schema.json"),
            "--output-last-message", str(artifacts / "final.json"), "-"]


def stop_process(process: subprocess.Popen) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def capture_process(command: list[str], fixture: Path, prompt: str, artifacts: Path, timeout: float, monitor=None, environment=None) -> dict:
    started = time.monotonic()
    if os.name != "posix":
        return {"returncode": None, "error": "bounded CLI capture requires POSIX", "duration_seconds": 0}
    environment = dict(os.environ if environment is None else environment)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        process = subprocess.Popen(command, cwd=fixture, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=os.name == "posix", env=environment)
    except OSError as exc:
        return {"returncode": None, "error": f"CLI unavailable: {type(exc).__name__}", "duration_seconds": 0}
    error = None
    violation = None
    deadline = started + timeout
    try:
        with ExitStack() as files, selectors.DefaultSelector() as selector:
            for stream, name, limit in ((process.stdout, "events.jsonl", evidence.MAX_CAPTURE_BYTES),
                                        (process.stderr, "stderr.log", 65536)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ,
                                  [files.enter_context((artifacts / name).open("wb")), limit, 0])
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, None)
            pending_input = memoryview(prompt.encode("utf-8"))
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                for key, _ in selector.select(min(remaining, 0.1)):
                    if key.fileobj is process.stdin:
                        if pending_input:
                            count = os.write(key.fd, pending_input[:8192])
                            pending_input = pending_input[count:]
                        if not pending_input:
                            selector.unregister(process.stdin)
                            process.stdin.close()
                        continue
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    destination, limit, total = key.data
                    destination.write(chunk[:max(0, limit - total)])
                    key.data[2] += len(chunk)
                    if key.data[2] > limit:
                        raise ValueError("CLI output capture budget exceeded")
                    if monitor is not None and key.fileobj is process.stdout:
                        violation = monitor.feed(chunk)
                        if violation:
                            raise RuntimeError("observed forbidden attempt")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            process.wait(timeout=remaining)
    except RuntimeError:
        stop_process(process)
    except subprocess.TimeoutExpired:
        error = "CLI timeout"
        stop_process(process)
    except (OSError, BrokenPipeError):
        error = "CLI input/output failure"
        stop_process(process)
    except ValueError as exc:
        error = str(exc)
        stop_process(process)
    finally:
        stop_process(process)  # Stop the original owned group; detached descendants may escape.
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            error = "CLI failed to terminate after deadline"
    result = {"returncode": process.returncode, "error": error,
              "duration_seconds": round(time.monotonic() - started, 3)}
    if violation:
        result["observed_violation"] = violation
    return result


def run_scenario(root: Path, scenario: dict, artifacts: Path, codex: list[str], timeout: float = 300) -> dict:
    if not 0 < timeout <= 300:
        raise ValueError("timeout must be within (0, 300] seconds")
    artifacts = artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "final-schema.json").write_text(json.dumps(FINAL_SCHEMA), encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="fixture-", dir=artifacts) as folder:
        fixture = Path(folder)
        prepare_fixture(root.resolve(), fixture, scenario)
        before, before_errors = evidence.snapshot(fixture)
        if before_errors:
            raise ValueError("fixture cannot be completely captured: " + "; ".join(before_errors))
        required_reads = {}
        for name in scenario["assertions"].get("requiredReadPaths", []):
            path = fixture / evidence.relative_path(name)
            if before.get(name, {}).get("kind") != "file":
                raise ValueError("required inspection file missing from fixture: " + name)
            lines = path.read_text(encoding="utf-8").splitlines()
            required_reads[name] = [line.strip() for line in lines if len(line.strip()) >= 4][:20]
        prompt = scenario["prompt"] + "\n\nReturn the requested JSON outcome; evidence_types describes only evidence actually obtained."
        process = capture_process(cli_command(codex, scenario, fixture, artifacts), fixture, prompt, artifacts, timeout)
        after, after_errors = evidence.snapshot(fixture)
        changes = evidence.changes_between(before, after)
        failures = evidence.check_files(scenario["assertions"], changes, after) if not after_errors else []
        for name in scenario["assertions"].get("validPlanDirectories", []):
            directory = fixture / evidence.relative_path(name)
            if any(after.get(name + "/" + file, {}).get("kind") != "file" for file in ("state.json", "plan.md")):
                failures.append("required plan files unavailable: " + name)
                continue
            try:
                state = workflow.validate_plan_dir(directory)
                if not state["tasks"]:
                    raise workflow.PlanError("decision-complete plan requires tasks")
                if re.search(r"(?m)^\s*-\s*TODO\s*$", (directory / "plan.md").read_text()):
                    raise workflow.PlanError("unresolved plan placeholder")
            except (workflow.PlanError, OSError, ValueError, TypeError, KeyError) as exc:
                failures.append("invalid plan: " + name + ": " + str(exc)[:200])
        events_path = artifacts / "events.jsonl"
        if events_path.exists():
            event_failures, gaps, commands = evidence.check_events(events_path, fixture, scenario["assertions"], required_reads)
            failures += event_failures
        else:
            gaps, commands = ["CLI events unavailable"], 0
        gaps += after_errors
        final = None
        try:
            final_path = artifacts / "final.json"
            if final_path.stat().st_size > 65536:
                raise ValueError("oversized final response")
            final = json.loads(final_path.read_text(encoding="utf-8"))
            if not isinstance(final, dict) or set(final) != set(FINAL_SCHEMA["required"]):
                raise ValueError("invalid final response shape")
            if not isinstance(final["summary"], str) or not isinstance(final["evidence_types"], list):
                raise ValueError("invalid final response types")
            if final["outcome"] not in scenario["assertions"]["outcomes"]:
                failures.append("declared outcome outside scenario expectations")
            if not final["evidence_types"] or any(kind not in scenario["assertions"]["evidenceTypes"] for kind in final["evidence_types"]):
                failures.append("declared evidence outside scenario expectations")
        except (OSError, ValueError, UnicodeError):
            gaps.append("final structured response unavailable or invalid")
        status = "passed"
        if gaps:
            status = "incomplete"
        if failures:
            status = "failed"
        if process["error"] or process["returncode"] != 0:
            status = "error"
        result = {"scenario": scenario["id"], "status": status, **process,
                  "failures": sorted(set(failures)), "evidence_gaps": sorted(set(gaps)),
                  "changes": changes, "observed_commands": commands,
                  "events_path": str(events_path), "declared_result": final,
                  "observed_evidence": ["filesystem", "cli-events"],
                  "model": MODEL, "reasoning_effort": REASONING}
        (artifacts / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result


def validate_primary_selection(model: str, effort: str) -> dict:
    """Validate representation only; available models and efforts are not hardcoded."""
    for value in (model, effort):
        if (not isinstance(value, str) or not value or value != value.strip()
                or any(ord(character) < 32 or ord(character) == 127
                       or 0xD800 <= ord(character) <= 0xDFFF for character in value)):
            raise ValueError("primary model and effort must be nonempty valid strings")
    return {"model": model, "effort": effort}


def select_cascade_policy(policy: dict, primary_override: dict | None) -> dict:
    if primary_override is None:
        return policy
    if not isinstance(primary_override, dict) or set(primary_override) != {"model", "effort"}:
        raise ValueError("invalid primary selection")
    primary = validate_primary_selection(primary_override["model"], primary_override["effort"])
    return dict(policy, primary=primary, routes=dict(policy["routes"], integration=dict(primary)))


def run_cascade(root: Path, artifacts: Path, codex: list[str], timeout: float = 900,
                native: bool = False, primary_override: dict | None = None) -> dict:
    """Launch one explicitly authorized isolated cascade; retain observed evidence."""
    if not 0 < timeout <= 900:
        raise ValueError("cascade timeout must be within (0, 900] seconds")
    policy = select_cascade_policy(routing.load_routing(root), primary_override)
    artifacts = artifacts.resolve()
    artifacts.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cascade-fixture-") as folder:
        fixture = Path(folder)
        cascade.prepare(root, fixture)
        before, before_errors = evidence.snapshot(fixture)
        (artifacts / "before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
        if before_errors:
            raise ValueError("fixture snapshot incomplete: " + "; ".join(before_errors))
        primary = policy["primary"]
        command = [*codex, "--ask-for-approval", "never", "exec",
                   "--ignore-user-config", *([] if native else ["--ephemeral"]), "--skip-git-repo-check",
                   "--model", primary["model"], "--sandbox", "workspace-write", "--cd", str(fixture),
                   "-c", "model_reasoning_effort=" + json.dumps(primary["effort"], ensure_ascii=False),
                   "-c", 'service_tier="default"', "-c", "agents.enabled=true",
                   "-c", "agents.max_concurrent_threads_per_session=4",
                   "-c", "agents.researcher_sol.config_file=" + json.dumps(str(fixture / ".codex/agents/researcher-sol.toml")),
                   "-c", 'agents.researcher_sol.description="Read-only researcher for bounded fact-finding and evidence gathering."',
                   "-c", "agents.planner_sol.config_file=" + json.dumps(str(fixture / ".codex/agents/planner-sol.toml")),
                   "-c", 'agents.planner_sol.description="Read-only design helper for a bounded planning question."',
                   "-c", 'web_search="disabled"', "-c", "sandbox_workspace_write.network_access=false",
                   "--json", "--output-last-message", str(artifacts / "final.txt"), "-"]
        prompt = cascade.PROMPT + ("\nThe requested primary selection in the routing data below "
                                   "applies to this eval and supersedes any preferred default.\n"
                                   "If either requested native role is unavailable, "
                                   "report the evaluation incomplete; do not substitute another role.\n") + "\nRouting policy: " + json.dumps({
            "primary": primary, "research": policy["routes"]["research"],
            "design": policy["routes"]["design"], "lead": policy["defaultWorker"],
            "mechanical": policy["routes"]["mechanical"], "review": policy["routes"]["review"],
        }) + "\n"
        (artifacts / "invocation.json").write_text(json.dumps({
            "command": command, "cwd": str(fixture), "timeout_seconds": timeout,
            "prompt": prompt, "clarification_origin": "synthetic fixture; not real UI delivery",
            "native_trace": native, "persistent_codex_session": native,
            "requested_primary": primary,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (artifacts / "fixture-events.jsonl").write_text(json.dumps({
            "type": "synthetic_clarification_declared", "origin": "fixture",
            "text": "Empty input produces total 0; bool values are rejected.",
            "real_user_delivery": False,
        }, ensure_ascii=False) + "\n", encoding="utf-8")
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise ValueError("cascade deadline expired during preparation")
        started_at = time.time()
        process = capture_process(command, fixture, prompt, artifacts, remaining,
                                  cascade.StreamMonitor(fixture), cascade.cli_environment(os.environ))
        after, after_errors = evidence.snapshot(fixture)
        (artifacts / "after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        changes = evidence.changes_between(before, after)
        failures = cascade.check_fixture(changes, after) if not after_errors else []
        event_failures, gaps, observations = cascade.inspect_events(artifacts / "events.jsonl", fixture, policy, native_trace=native)
        failures.extend(event_failures)
        if native:
            try:
                if time.monotonic() - started >= timeout:
                    raise TimeoutError("cascade deadline expired before trace collection")
                root_id = cascade.root_thread_id(artifacts / "events.jsonl")
                codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
                remaining_native = timeout - (time.monotonic() - started)
                if remaining_native <= 0:
                    raise TimeoutError("cascade deadline expired before native trace assessment")
                native_failures, native_gaps, native_observations = native_trace.collect_and_assess(
                    root_id, codex_home / "sessions", artifacts, fixture, policy, started_at,
                    budget_seconds=min(5.0, remaining_native))
                failures.extend(native_failures)
                gaps.extend(native_gaps)
                observations["native_trace"] = native_observations
            except Exception as exc:
                # Malformed or unavailable native evidence must not suppress the report.
                gaps.append("native trace collection unavailable: " + type(exc).__name__)

        if process.get("observed_violation"):
            failures.append(process["observed_violation"])
        gaps.extend(after_errors)
        gaps.extend(cascade.save_fixture_output(fixture, artifacts / "fixture-output", after))
        status = "error" if process["error"] or (process["returncode"] != 0 and not process.get("observed_violation")) else (
            "failed" if failures else "incomplete" if gaps else "passed")
        result = {"scenario": cascade.SCENARIO, "status": status, **process,
                  "failures": sorted(set(failures)), "evidence_gaps": sorted(set(gaps)),
                  "changes": changes, "observations": observations,
                  "events_path": str(artifacts / "events.jsonl"),
                  "synthetic_clarification": True, "real_ui_delivery_observed": False,
                  "limitations": ["default CLI-only adapter cannot grant passed without native trace",
                                  "process-group cleanup cannot guarantee detached descendants stop",
                                  "workspace and network restrictions do not guarantee full read or arbitrary Python syscall isolation",
                                  "observable action restrictions do not prove absence of unobserved imported-code actions"],
                  "requested_routing": {"primary": primary, "routes": policy["routes"]}}
        (artifacts / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--scenario", action="append")
    parser.add_argument("--cascade", action="store_true", help="select the isolated native-agent cascade fixture")
    parser.add_argument("--primary-model", help="override the cascade root model (requires --primary-effort)")
    parser.add_argument("--primary-effort", help="override the cascade root effort (requires --primary-model)")
    parser.add_argument("--native-trace", action="store_true", help="retain and inspect this run's normal Codex session journals; requires --cascade --run")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--run", action="store_true", help="explicit opt-in; real model calls require separate authorization")
    args = parser.parse_args(argv)
    if (args.primary_model is None) != (args.primary_effort is None):
        parser.error("--primary-model and --primary-effort must be provided together")
    primary_override = None
    if args.primary_model is not None:
        if not args.cascade:
            parser.error("--primary-model and --primary-effort require --cascade")
        try:
            primary_override = validate_primary_selection(args.primary_model, args.primary_effort)
        except ValueError as exc:
            parser.error(str(exc))
    if args.native_trace and not (args.cascade and args.run):
        parser.error("--native-trace requires --cascade --run; it retains normal Codex session journals")
    timeout = args.timeout_seconds if args.timeout_seconds is not None else (900 if args.cascade else 300)
    limit = 900 if args.cascade else 300
    if not 0 < timeout <= limit:
        parser.error(f"--timeout-seconds must be within (0, {limit}]")
    root = args.root.resolve()
    if args.cascade:
        policy = select_cascade_policy(routing.load_routing(root), primary_override)
        if args.scenario and set(args.scenario) != {cascade.SCENARIO}:
            parser.error("unknown cascade scenario")
        if not args.run:
            print(json.dumps({"scenario": cascade.SCENARIO, "requested_routing": policy["routes"],
                              "primary": policy["primary"], "model_calls": False,
                              "limits": "CLI adapter cannot produce passed: descendants, effective routing and approval lack native trace evidence; process-group timeout excludes detached descendants; workspace/network restrictions are not full read or syscall isolation; total children and commands are observed, not hard enforced"}))
            return 0
        parent = (args.output_dir or root / "build/skill-evals").resolve()
        if not parent.is_relative_to(root):
            parser.error("--output-dir must stay inside --root")
        parent.mkdir(parents=True, exist_ok=True)
        output = Path(tempfile.mkdtemp(prefix="cascade-run-", dir=parent))
        result = run_cascade(root, output, [args.codex_bin], timeout, native=args.native_trace,
                             primary_override=primary_override)
        print(f"{cascade.SCENARIO}: {result['status']}\nEval report: {output / 'result.json'}")
        return 0 if result["status"] == "passed" else 1
    suite = load_suite(root / "tools/Codex/SkillEvals.yaml")
    scenarios = suite["scenarios"]
    if args.scenario:
        unknown = set(args.scenario) - {case["id"] for case in scenarios}
        if unknown:
            parser.error("unknown scenarios: " + ", ".join(sorted(unknown)))
        scenarios = [case for case in scenarios if case["id"] in args.scenario]
    if not args.run:
        print(json.dumps({"model": MODEL, "reasoning_effort": REASONING,
                          "scenarios": [case["id"] for case in scenarios], "model_calls": False}))
        return 0
    parent = (args.output_dir or root / "build/skill-evals").resolve()
    if not parent.is_relative_to(root):
        parser.error("--output-dir must stay inside --root")
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    results = []
    for scenario in scenarios:
        results.append(run_scenario(root, scenario, output / scenario["id"], [args.codex_bin], timeout))
        print(f"{scenario['id']}: {results[-1]['status']}", flush=True)
    report = {"model": MODEL, "reasoning_effort": REASONING, "results": results,
              "passed": all(result["status"] == "passed" for result in results)}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Eval report: {output / 'report.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
