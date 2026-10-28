"""Deterministic eval runner tests; no authenticated Codex process is launched."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RunSkillEvalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "cxet_skill_evals", ROOT / "tools/Codex/RunSkillEvals.py"
        )
        cls.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runner)

    def fixture(self, folder, mode="good", writable=True):
        base = Path(folder)
        root = base / "repo"
        root.mkdir()
        (root / "AGENTS.md").write_text("Only authorized changes.\n")
        fake = base / "fake_codex.py"
        fake.write_text(
            "import json, pathlib, sys, time\n"
            f"mode = {mode!r}\n"
            "args = sys.argv[1:]\n"
            "assert '--ignore-user-config' in args and '--ephemeral' in args\n"
            "assert '--skip-git-repo-check' in args and '--json' in args\n"
            "assert args[args.index('--model') + 1] == 'gpt-6.1-sol'\n"
            "assert 'model_reasoning_effort=\"high\"' in args\n"
            "assert 'service_tier=\"default\"' in args\n"
            "if mode == 'blockedstdin': time.sleep(2); sys.exit(0)\n"
            "sys.stdin.read()\n"
            "if mode == 'timeout': time.sleep(20)\n"
            "if mode == 'infra':\n"
            " print('authentication unavailable', file=sys.stderr); sys.exit(3)\n"
            "print(json.dumps({'type':'thread.started','thread_id':'fake'}))\n"
            "print(json.dumps({'type':'turn.started'}))\n"
            "command = 'cat src/sample.txt'\n"
            "if mode == 'commentread': command = 'printf alpha # cat src/sample.txt'\n"
            "if mode == 'quotedread': command = \"printf '%s' 'cat src/sample.txt alpha'\"\n"
            "if mode == 'wrappedread': command = \"/bin/bash -lc 'cat src/sample.txt'\"\n"
            "if mode == 'suffixread': command = 'cat src/sample.txt#suffix'\n"
            "if mode == 'wrappedsuffixread': command = \"/bin/bash -lc 'cat src/sample.txt#suffix'\"\n"
            "if mode == 'commentoperandread': command = 'cat other.txt # src/sample.txt'\n"
            "if mode == 'forbidden': command = 'python3 -m unittest'\n"
            "if mode == 'noop': command = 'true'\n"
            "event_type = 'item.started' if mode == 'started' else 'item.completed'\n"
            "status = 'in_progress' if mode == 'started' else 'completed'\n"
            "code = 1 if mode == 'failedread' else 0\n"
            "output = '' if mode == 'noop' else 'alpha\\n'\n"
            "if mode == 'commentread': output = 'alpha'\n"
            "if mode == 'quotedread': output = 'cat src/sample.txt alpha'\n"
            "print(json.dumps({'type':event_type,'item':{'id':'c','type':'command_execution','command':command,'status':status,'exit_code':code,'aggregated_output':output}}))\n"
            "if mode not in ('unchanged', 'commentread', 'quotedread', 'directread', 'wrappedread', 'suffixread', 'wrappedsuffixread', 'commentoperandread'): pathlib.Path('src/sample.txt').write_text('beta\\n')\n"
            "if mode == 'extra': pathlib.Path('other.txt').write_text('oops')\n"
            "if mode == 'symlink': pathlib.Path('escape').symlink_to('/etc/passwd')\n"
            "if mode == 'badplan':\n"
            " p=pathlib.Path('docs/agent-plans/active/bad'); p.mkdir(parents=True)\n"
            " (p/'state.json').write_text('{\"tasks\":\"invalid\"}'); (p/'plan.md').write_text('TODO')\n"
            "if mode == 'unknown':\n"
            " print(json.dumps({'type':'item.completed','item':{'type':'future_execution'}}))\n"
            "if mode == 'network':\n"
            " print(json.dumps({'type':'item.completed','item':{'type':'web_search','query':'market'}}))\n"
            "if mode == 'denied_edit':\n"
            " print(json.dumps({'type':'item.completed','item':{'type':'file_change','status':'failed','changes':[{'path':'forbidden.txt','kind':'add'}]}}))\n"
            "if mode == 'malformed': print('invalid json')\n"
            "result = {'outcome':'completed','evidence_types':['static-only'],'summary':'fake'}\n"
            "out = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
            "out.write_text(json.dumps(result))\n"
            "if mode != 'incomplete': print(json.dumps({'type':'turn.completed','usage':{}}))\n"
            "if mode == 'escapedpipe':\n"
            " import os\n"
            " if os.fork() == 0: os.setsid(); time.sleep(2); os._exit(0)\n"
        )
        scenario = {
            "id": "sample", "prompt": "Replace alpha with beta." if writable else "Read src/sample.txt without edits or checks.",
            "fixtureFiles": {"src/sample.txt": "alpha\n"},
            "assertions": {
                "allowedChangedGlobs": ["src/sample.txt"] if writable else [],
                "requiredChangedGlobs": ["src/sample.txt"] if writable else [],
                "expectedFileContents": {"src/sample.txt": "beta\n"} if writable else {},
                "requiredReadPaths": ["src/sample.txt"],
                "forbiddenCommandPatterns": [r"-m\s+unittest"],
                "networkAllowed": False, "outcomes": ["completed"],
                "evidenceTypes": ["static-only"],
            },
        }
        if mode in ("suffixread", "wrappedsuffixread", "commentoperandread"):
            scenario["fixtureFiles"].update({"src/sample.txt#suffix": "alpha\n", "other.txt": "alpha\n"})
        return root, fake, scenario

    def run_fake(self, folder, mode="good", writable=True, timeout=2):
        root, fake, scenario = self.fixture(folder, mode, writable)
        result = self.runner.run_scenario(
            root, scenario, Path(folder) / "artifacts", [sys.executable, str(fake)], timeout
        )
        self.assertEqual((root / "AGENTS.md").read_text(), "Only authorized changes.\n")
        self.assertFalse((root / "src").exists())
        return result

    def test_fake_cli_passes_with_actual_file_and_event_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_fake(folder)
            self.assertEqual(result["status"], "passed", result)
            self.assertEqual([c["path"] for c in result["changes"]], ["src/sample.txt"])
            self.assertTrue(Path(result["events_path"]).is_file())

    def test_missing_required_edit_and_extra_changes_fail(self):
        for mode in ("unchanged", "extra", "symlink"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                self.assertEqual(self.run_fake(folder, mode)["status"], "failed")

    def test_forbidden_attempts_fail_even_when_denied(self):
        for mode in ("forbidden", "network", "denied_edit"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                self.assertEqual(self.run_fake(folder, mode)["status"], "failed")

    def test_missing_malformed_or_unknown_events_are_incomplete(self):
        for mode in ("incomplete", "malformed", "unknown"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                self.assertEqual(self.run_fake(folder, mode)["status"], "incomplete")

    def test_cli_failure_and_timeout_are_infrastructure_errors(self):
        for mode in ("infra", "timeout"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                result = self.run_fake(folder, mode, timeout=0.15)
                self.assertEqual(result["status"], "error")

    def test_started_failed_and_noop_actions_cannot_prove_inspection(self):
        for mode in ("started", "failedread", "noop"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                self.assertEqual(self.run_fake(folder, mode)["status"], "incomplete")

    def test_comment_and_quoted_reader_text_cannot_prove_readonly_inspection(self):
        for mode in ("commentread", "quotedread"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                result = self.run_fake(folder, mode, writable=False)
                self.assertEqual(result["status"], "incomplete", result)
                self.assertIn("required inspection lacks successful output evidence: src/sample.txt", result["evidence_gaps"])
                self.assertEqual(result["changes"], [])

    def test_direct_and_explicit_shell_wrapped_readers_prove_readonly_inspection(self):
        for mode in ("directread", "wrappedread"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                result = self.run_fake(folder, mode, writable=False)
                self.assertEqual(result["status"], "passed", result)
                self.assertEqual(result["evidence_gaps"], [])
                self.assertEqual(result["changes"], [])

    def test_hash_suffix_file_is_not_the_required_read_path(self):
        for mode in ("suffixread", "wrappedsuffixread"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                result = self.run_fake(folder, mode, writable=False)
                self.assertEqual(result["status"], "incomplete", result)
                self.assertIn("required inspection lacks successful output evidence: src/sample.txt", result["evidence_gaps"])
                self.assertEqual(result["changes"], [])

    def test_comment_operands_cannot_name_the_required_read_path(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_fake(folder, "commentoperandread", writable=False)
            self.assertEqual(result["status"], "incomplete", result)
            self.assertIn("required inspection lacks successful output evidence: src/sample.txt", result["evidence_gaps"])
            self.assertEqual(result["changes"], [])

    @unittest.skipUnless(os.name == "posix", "local POSIX CLI capture")
    def test_timeout_covers_blocked_stdin_and_escaped_pipe(self):
        for mode in ("blockedstdin", "escapedpipe"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder:
                root, fake, scenario = self.fixture(folder, mode)
                if mode == "blockedstdin":
                    scenario["prompt"] = "x" * 131072
                started = time.monotonic()
                result = self.runner.run_scenario(root, scenario, Path(folder) / "out", [sys.executable, str(fake)], 0.15)
                self.assertLess(time.monotonic() - started, 1)
                self.assertEqual(result["status"], "error")

    def test_created_plan_must_pass_canonical_schema_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            root, fake, scenario = self.fixture(folder, "badplan")
            scenario["assertions"]["allowedChangedGlobs"].append("docs/agent-plans/**")
            scenario["assertions"]["validPlanDirectories"] = ["docs/agent-plans/active/bad"]
            result = self.runner.run_scenario(root, scenario, Path(folder) / "out", [sys.executable, str(fake)], 2)
            self.assertEqual(result["status"], "failed")

    def test_fixture_path_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            root, fake, scenario = self.fixture(folder)
            scenario["fixtureFiles"] = {"../outside": "bad"}
            with self.assertRaises(ValueError):
                self.runner.run_scenario(root, scenario, Path(folder) / "out", [sys.executable, str(fake)], 1)
            self.assertFalse((Path(folder) / "outside").exists())

    def test_six_repository_scenarios_have_content_assertions_for_edits(self):
        data = self.runner.load_suite(ROOT / "tools/Codex/SkillEvals.yaml")
        self.assertEqual(len(data["scenarios"]), 6)
        for scenario in data["scenarios"]:
            if "src/sample.txt" in scenario["assertions"]["requiredChangedGlobs"]:
                self.assertEqual(scenario["assertions"]["expectedFileContents"]["src/sample.txt"], "beta\n")

    def test_eval_suite_rejects_unknown_structure_fields(self):
        for section in ("suite", "scenario", "assertions"):
            with self.subTest(section=section), tempfile.TemporaryDirectory() as folder:
                data = json.loads((ROOT / "tools/Codex/SkillEvals.yaml").read_text())
                scenario = data["scenarios"][0]
                value = {"suite": data, "scenario": scenario, "assertions": scenario["assertions"]}[section]
                value["obsoleteField"] = True
                path = Path(folder) / "suite.json"
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "fields"):
                    self.runner.load_suite(path)


if __name__ == "__main__":
    unittest.main()
