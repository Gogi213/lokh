"""Offline synthetic CLI event regression tests. No real model is invoked."""
import copy
import io
import json
import os
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.Codex import AgentRouting, RunSkillEvals
from tools.Codex.Skills import CascadeEval, SkillEvalEvidence


class CascadeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.fixture = self.base / "fixture"
        self.fixture.mkdir()
        CascadeEval.prepare(ROOT, self.fixture)
        self.policy = AgentRouting.load_routing(ROOT)
        self.path = self.base / "events.jsonl"
        self.events = [{"type": "thread.started", "thread_id": "root"},
                       {"type": "turn.started"}]

    def assess(self, more):
        self.path.write_text("\n".join(json.dumps(x) for x in [*self.events, *more, {"type": "turn.completed"}]) + "\n")
        return CascadeEval.inspect_events(self.path, self.fixture, self.policy)

    @staticmethod
    def command(text, status="completed", exit_code=0):
        return {"type": "item.completed", "item": {"id": "cmd", "type": "command_execution",
                "command": text, "status": status, "exit_code": exit_code}}

    def test_permitted_test_is_evidence_but_missing_children_are_incomplete(self):
        start = self.command("python3 -B -m unittest -v test_app")
        start["type"] = "item.started"
        fail, gaps, observations = self.assess([start, self.command("python3 -B -m unittest -v test_app")])
        self.assertEqual(fail, [])
        self.assertNotIn("successful fixture test event unavailable", gaps)
        self.assertTrue(any("descendant" in gap for gap in gaps))
        self.assertEqual(len(observations["commands"]), 1)

    def test_fabricated_cascade_and_model_attestation_in_agent_text_is_not_evidence(self):
        message = {"type": "item.completed", "item": {"id": "fake", "type": "agent_message",
                   "text": json.dumps({"approved": True, "models": "correct", "children": "all complete"})}}
        _, gaps, _ = self.assess([message, self.command("python3 -B -m unittest -v test_app")])
        self.assertTrue(any("approval" in gap for gap in gaps))
        self.assertTrue(any("models" in gap for gap in gaps))
        self.assertTrue(any("descendant" in gap for gap in gaps))

    def test_spawn_without_model_or_approval_evidence_cannot_fake_success(self):
        # A spawn event without observed effective configuration cannot attest it.
        spawn = {"type": "item.completed", "item": {"id": "spawn", "type": "collab_tool_call",
                 "tool": "spawn_agent", "status": "completed",
                 "sender_thread_id": "root", "receiver_thread_ids": ["child"]}}
        _, gaps, _ = self.assess([spawn])
        self.assertTrue(any("models" in gap for gap in gaps))
        self.assertTrue(any("approval" in gap for gap in gaps))

    def test_forbidden_attempts_fail_even_if_denied_and_stop_monitor(self):
        for command in ("git status", "cat /etc/passwd", "python3 -B -m unittest -v test_app; true", "curl example.org"):
            with self.subTest(command=command):
                event = self.command(command, status="failed", exit_code=1)
                failures, _, _ = self.assess([event])
                self.assertTrue(any("forbidden command" in failure for failure in failures))
                self.assertIn("forbidden command", CascadeEval.StreamMonitor(self.fixture).feed((json.dumps(event) + "\n").encode()))

    def test_outside_edit_and_scope_change_fail(self):
        edit = {"type": "item.completed", "item": {"type": "file_change", "id": "e", "status": "failed",
                "changes": [{"path": "../escape", "kind": "add"}]}}
        failures, _, _ = self.assess([edit])
        self.assertTrue(failures)
        self.assertTrue(CascadeEval.StreamMonitor(self.fixture).feed((json.dumps(edit) + "\n").encode()))
        before, _ = SkillEvalEvidence.snapshot(self.fixture)
        (self.fixture / "test_app.py").write_text("tampered")
        after, _ = SkillEvalEvidence.snapshot(self.fixture)
        self.assertTrue(any("unauthorized" in failure for failure in CascadeEval.check_fixture(
            SkillEvalEvidence.changes_between(before, after), after)))

    def test_unknown_malformed_and_missing_events_are_incomplete(self):
        self.path.write_text('not json\n{"type":"future.event"}\n')
        _, gaps, _ = CascadeEval.inspect_events(self.path, self.fixture, self.policy)
        self.assertIn("invalid JSONL event", gaps)
        self.assertTrue(any("unrecognized event" in gap for gap in gaps))
        self.assertIn("missing completed-turn events", gaps)

    def test_non_string_event_fields_are_incomplete_and_monitor_survives(self):
        cases = [{"type": []},
                 {"type": "item.completed", "item": {"id": "a", "type": {}}},
                 {"type": "item.completed", "item": {"id": "b", "type": "collab_tool_call", "tool": []}},
                 {"type": "item.completed", "item": {"id": [], "type": "command_execution",
                   "command": "python3 -B -m unittest -v test_app", "status": {}}}]
        for event in cases:
            with self.subTest(event=event):
                _, gaps, _ = self.assess([event])
                self.assertTrue(any("not text" in gap or "lacks identity" in gap for gap in gaps))
                self.assertIsNone(CascadeEval.StreamMonitor(self.fixture).feed((json.dumps(event) + "\n").encode()))

    def test_child_environment_retains_only_configured_proxy_and_cli_essentials(self):
        proxies = {name: "fixture-proxy-value" for name in (
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
            "http_proxy", "https_proxy", "all_proxy", "no_proxy")}
        env = CascadeEval.cli_environment({"PATH": "/bin", "HOME": "/home/u", "LANG": "C",
                                           "LC_ALL": "C", "CODEX_HOME": "/home/u/.codex", **proxies,
                                           "AWS_SECRET_ACCESS_KEY": "secret", "OPENAI_API_KEY": "secret",
                                           "INJECTED_TOKEN": "secret", "OTHER_PROXY": "secret"})
        self.assertEqual(env, {"PATH": "/bin", "HOME": "/home/u", "LANG": "C", "LC_ALL": "C",
                               "CODEX_HOME": "/home/u/.codex", "PYTHONDONTWRITEBYTECODE": "1", **proxies})
        self.assertNotIn("HTTPS_PROXY", CascadeEval.cli_environment({}))

    def test_spawn_limit_counts_unique_attempts_and_terminates_on_eighth(self):
        monitor = CascadeEval.StreamMonitor(self.fixture)
        for i in range(8):
            event = {"type": "item.started", "item": {"type": "collab_tool_call", "id": str(i), "tool": "spawn_agent"}}
            result = monitor.feed((json.dumps(event) + "\n").encode())
            if i < 7:
                self.assertIsNone(result)
            else:
                self.assertIn("seven", result)

    def test_timeout_uses_owned_process_group_and_reports_error(self):
        fake = self.base / "fake.py"
        fake.write_text("import sys, time\nsys.stdin.read()\ntime.sleep(10)\n")
        artifacts = self.base / "artifacts"
        artifacts.mkdir()
        result = RunSkillEvals.capture_process([sys.executable, str(fake)], self.fixture,
                                               "fixture", artifacts, 0.1,
                                               CascadeEval.StreamMonitor(self.fixture))
        self.assertEqual(result["error"], "CLI timeout")
        self.assertTrue((artifacts / "events.jsonl").exists())

    def test_wrapper_accepts_only_exact_allowed_commands(self):
        for command in ("bash -lc 'cat AGENTS.md'", "/bin/sh -c 'python3 -B -m unittest -v test_app'",
                        "cat .codex/agents/researcher-sol.toml", "cat calc.py"):
            with self.subTest(command=command):
                self.assertTrue(CascadeEval.command_allowed(command))
        for command in ("bash -lc 'cat AGENTS.md; cat /etc/passwd'", "cat /etc/passwd",
                        "cat calc.py display.py", "bash -lc 'cat calc.py display.py'",
                        "bash -c 'python3 -B -m unittest -v test_app && true'"):
            with self.subTest(command=command):
                self.assertFalse(CascadeEval.command_allowed(command))

    def test_shipped_inputs_are_copied_and_immutable(self):
        before, _ = SkillEvalEvidence.snapshot(self.fixture)
        self.assertEqual((self.fixture / "AGENTS.md").read_bytes(),
                         (ROOT / "tools/Codex/GlobalAgentInstructions.md").read_bytes())
        self.assertEqual((self.fixture / "policy/AgentRouting.json").read_bytes(),
                         (ROOT / "tools/Codex/AgentRouting.json").read_bytes())
        (self.fixture / "AGENTS.md").write_text("tampered")
        after, _ = SkillEvalEvidence.snapshot(self.fixture)
        failures = CascadeEval.check_fixture(SkillEvalEvidence.changes_between(before, after), after)
        self.assertTrue(any("AGENTS.md" in failure for failure in failures))

    def test_full_fake_cli_run_captures_fixture_and_remains_incomplete(self):
        fake = self.base / "fake_cli.py"
        fake.write_text(
            "import json, os, pathlib, sys\n"
            "assert 'INJECTED_TOKEN' not in os.environ\n"
            "assert os.environ.get('HTTPS_PROXY') == 'fixture-proxy-value'\n"
            "args = sys.argv[1:]\n"
            "assert '--ignore-user-config' in args and '--ephemeral' in args\n"
            "assert args[args.index('--model') + 1] == 'gpt-6.1-sol'\n"
            "assert 'model_reasoning_effort=\"high\"' in args\n"
            "assert 'service_tier=\"default\"' in args\n"
            "assert 'agents.enabled=true' in args\n"
            "assert 'agents.max_concurrent_threads_per_session=4' in args\n"
            "prompt = sys.stdin.read()\n"
            "assert 'synthetic' in prompt.lower() and 'propose' in prompt.lower()\n"
            "assert pathlib.Path('AGENTS.md').is_file()\n"
            "assert pathlib.Path('.codex/agents/researcher-sol.toml').is_file()\n"
            "assert pathlib.Path('policy/AgentRouting.json').is_file()\n"
            "pathlib.Path('calc.py').write_text('def total(values):\\n    return sum(values)\\n# fixture edit\\n')\n"
            "pathlib.Path('display.py').write_text('def describe(value):\\n    return str(value)\\n# fixture edit\\n')\n"
            "print(json.dumps({'type':'thread.started','thread_id':'root'}))\n"
            "print(json.dumps({'type':'turn.started'}))\n"
            "item={'type':'command_execution','id':'check','command':'python3 -B -m unittest -v test_app', 'status':'in_progress'}\n"
            "print(json.dumps({'type':'item.started','item':item}))\n"
            "item.update(status='completed',exit_code=0,aggregated_output='OK (synthetic)')\n"
            "print(json.dumps({'type':'item.completed','item':item}))\n"
            "print(json.dumps({'type':[], 'item':{}}))\n"
            "print(json.dumps({'type':'turn.completed'}))\n"
        )
        artifacts = self.base / "output"
        with mock.patch.dict(os.environ, {"INJECTED_TOKEN": "secret", "HTTPS_PROXY": "fixture-proxy-value"}):
            result = RunSkillEvals.run_cascade(ROOT, artifacts, [sys.executable, str(fake)], 2)
        self.assertEqual(result["status"], "incomplete", result)
        self.assertIn("event type is not text", result["evidence_gaps"])
        self.assertFalse(result["real_ui_delivery_observed"])
        self.assertTrue((artifacts / "fixture-events.jsonl").is_file())
        self.assertTrue((artifacts / "events.jsonl").is_file())
        self.assertIn("fixture edit", (artifacts / "fixture-output/calc.py").read_text())
        self.assertIn("fixture edit", (artifacts / "fixture-output/display.py").read_text())
        self.assertEqual(json.loads((artifacts / "after.json").read_text())["AGENTS.md"]["kind"], "file")
        invocation = json.loads((artifacts / "invocation.json").read_text())
        cwd = Path(invocation["cwd"])
        overrides = [invocation["command"][i + 1] for i, value in enumerate(invocation["command"][:-1]) if value == "-c"]
        role_configs = {key: json.loads(value) for entry in overrides
                        for key, value in [entry.split("=", 1)] if key.endswith(".config_file")}
        self.assertEqual(role_configs, {
            "agents.researcher_sol.config_file": str(cwd / ".codex/agents/researcher-sol.toml"),
            "agents.planner_sol.config_file": str(cwd / ".codex/agents/planner-sol.toml"),
        })
        self.assertIn('agents.researcher_sol.description="Read-only researcher for bounded fact-finding and evidence gathering."', overrides)
        self.assertIn('agents.planner_sol.description="Read-only design helper for a bounded planning question."', overrides)
        self.assertIn("do not substitute another role", invocation["prompt"])
        self.assertIn('`model="gpt-6.1-terra"` and `reasoning_effort="high"`', invocation["prompt"])
        self.assertIn("generic read-only Sol/xhigh review", invocation["prompt"])
        requested = json.loads(invocation["prompt"].split("\nRouting policy: ", 1)[1])
        self.assertEqual(requested["primary"], {"model": "gpt-6.1-sol", "effort": "high"})
        self.assertEqual(requested["lead"], {"model": "gpt-6.1-sol", "effort": "high"})
        self.assertEqual(requested["mechanical"], {"model": "gpt-6.1-terra", "effort": "high"})
        self.assertEqual(requested["review"], {"model": "gpt-6.1-sol", "effort": "xhigh"})
        self.assertFalse(cwd.exists())

    def test_native_trace_is_explicit_and_session_is_retained(self):
        for args in (["--native-trace"], ["--cascade", "--native-trace"], ["--run", "--native-trace"]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                RunSkillEvals.main(args)
        fake = self.base / "native_fake_cli.py"
        root_id = "01234567-89ab-cdef-0123-456789abcdef"
        fake.write_text(
            "import json, pathlib, sys\n"
            "assert '--ephemeral' not in sys.argv\n"
            "assert sys.argv[sys.argv.index('--model') + 1] == 'future-model'\n"
            "assert 'model_reasoning_effort=\"ultra\"' in sys.argv\n"
            "prompt = sys.stdin.read()\n"
            "assert 'researcher_sol' in prompt and 'planner_sol' in prompt\n"
            "assert 'question_id' in prompt and 'review_result' in prompt\n"
            "pathlib.Path('calc.py').write_text('# changed\\n')\n"
            "pathlib.Path('display.py').write_text('# changed\\n')\n"
            f"print(json.dumps({{'type':'thread.started','thread_id':{root_id!r}}}))\n"
            "print(json.dumps({'type':'turn.started'}))\n"
            "item={'type':'command_execution','id':'check','command':'python3 -B -m unittest -v test_app'}\n"
            "print(json.dumps({'type':'item.started','item':item}))\n"
            "item.update(status='completed',exit_code=0)\n"
            "print(json.dumps({'type':'item.completed','item':item}))\n"
            "print(json.dumps({'type':'turn.completed'}))\n"
        )
        artifacts = self.base / "native-output"
        fake_home = self.base / "fake-codex-home"
        expected_primary = {"model": "future-model", "effort": "ultra"}
        canonical_policy = copy.deepcopy(self.policy)
        with mock.patch.object(RunSkillEvals.routing, "load_routing", return_value=canonical_policy), \
             mock.patch.dict(os.environ, {"CODEX_HOME": str(fake_home)}), \
             mock.patch.object(RunSkillEvals.cascade, "inspect_events", wraps=CascadeEval.inspect_events) as inspect, \
             mock.patch.object(RunSkillEvals.native_trace, "collect_and_assess",
                               return_value=([], ["synthetic native gap"], {"synthetic": True})) as assess:
            result = RunSkillEvals.run_cascade(ROOT, artifacts, [sys.executable, str(fake)], 2,
                                              native=True, primary_override=expected_primary)
        self.assertEqual(result["status"], "incomplete", result)
        self.assertIn("synthetic native gap", result["evidence_gaps"])
        self.assertFalse(any("descendant events and complete" in gap for gap in result["evidence_gaps"]))
        self.assertEqual(assess.call_args.args[0], root_id)
        self.assertEqual(assess.call_args.args[1], fake_home / "sessions")
        self.assertEqual(assess.call_args.args[4]["primary"], expected_primary)
        self.assertEqual(inspect.call_args.args[2]["primary"], expected_primary)
        self.assertEqual(assess.call_args.args[4]["routes"]["integration"], expected_primary)
        self.assertEqual(inspect.call_args.args[2]["routes"]["integration"], expected_primary)
        self.assertIsNot(assess.call_args.args[4]["routes"]["integration"], assess.call_args.args[4]["primary"])
        self.assertEqual(canonical_policy, self.policy)
        self.assertEqual(result["requested_routing"]["primary"], expected_primary)
        self.assertEqual(result["requested_routing"]["routes"]["integration"], expected_primary)
        self.assertEqual(json.loads((artifacts / "invocation.json").read_text())["requested_primary"], expected_primary)
        self.assertEqual(self.policy, AgentRouting.load_routing(ROOT))
        self.assertIsInstance(assess.call_args.args[5], float)
        self.assertGreater(assess.call_args.kwargs["budget_seconds"], 0)
        self.assertLessEqual(assess.call_args.kwargs["budget_seconds"], 2)
        self.assertTrue(json.loads((artifacts / "invocation.json").read_text())["persistent_codex_session"])

    def test_primary_override_cli_validation_and_preflight(self):
        for args in (["--cascade", "--primary-model", "future-model"],
                     ["--cascade", "--primary-effort", "ultra"],
                     ["--primary-model", "future-model", "--primary-effort", "ultra"],
                     ["--cascade", "--primary-model", "", "--primary-effort", "ultra"],
                     ["--cascade", "--primary-model", "future-model", "--primary-effort", "  "]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                RunSkillEvals.main(args)
        output = io.StringIO()
        with redirect_stdout(output):
            result = RunSkillEvals.main(["--cascade", "--primary-model", "future-model",
                                         "--primary-effort", "ultra"])
        self.assertEqual(result, 0)
        preflight = json.loads(output.getvalue())
        self.assertEqual(preflight["primary"], {"model": "future-model", "effort": "ultra"})
        self.assertEqual(preflight["requested_routing"]["integration"], preflight["primary"])
        with mock.patch.object(RunSkillEvals.routing, "load_routing", return_value=self.policy), \
             mock.patch.object(RunSkillEvals, "run_cascade", return_value={"status": "incomplete"}) as run, \
             redirect_stdout(io.StringIO()):
            status = RunSkillEvals.main(["--root", str(self.base), "--cascade", "--run",
                                        "--primary-model", "future-model", "--primary-effort", "ultra"])
        self.assertEqual(status, 1)
        self.assertEqual(run.call_args.kwargs["primary_override"], {"model": "future-model", "effort": "ultra"})
        self.assertEqual(self.policy, AgentRouting.load_routing(ROOT))

    def test_primary_effort_is_safely_encoded_as_toml_string(self):
        effort = 'future"backslash\\emoji🚀'
        fake = self.base / "encoding_fake_cli.py"
        fake.write_text("import sys\nsys.stdin.read()\n")
        artifacts = self.base / "encoding-output"
        RunSkillEvals.run_cascade(ROOT, artifacts, [sys.executable, str(fake)], 2,
                                 primary_override={"model": "future-model", "effort": effort})
        invocation = json.loads((artifacts / "invocation.json").read_text())
        command = invocation["command"]
        overrides = [command[i + 1] for i, value in enumerate(command[:-1]) if value == "-c"]
        effort_options = [item for item in overrides if item.startswith("model_reasoning_effort=")]
        self.assertEqual(len(effort_options), 1)
        self.assertEqual(tomllib.loads(effort_options[0])["model_reasoning_effort"], effort)
        for model, level in (("bad\x00model", "ultra"), ("future-model", "bad\ud800"),
                             ("bad\udfff", "ultra")):
            with self.subTest(model=model, effort=level), self.assertRaises(ValueError):
                RunSkillEvals.validate_primary_selection(model, level)

    def test_ambiguous_root_thread_ids_are_rejected(self):
        self.path.write_text('\n'.join(json.dumps(event) for event in [
            {"type": "thread.started", "thread_id": "a"},
            {"type": "thread.started", "thread_id": "b"}]))
        with self.assertRaises(ValueError):
            CascadeEval.root_thread_id(self.path)

    def test_legacy_suite_remains_six_scenarios(self):
        self.assertEqual(len(RunSkillEvals.load_suite(ROOT / "tools/Codex/SkillEvals.yaml")["scenarios"]), 6)


if __name__ == "__main__":
    unittest.main()
