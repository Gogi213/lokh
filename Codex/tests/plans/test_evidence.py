"""Evidence regressions."""
from tools.Codex.tests.Support.plans import (
    Path,
    PlanFixture,
    REPO_ROOT,
    SimpleNamespace,
    TOOLS_DIR,
    contextlib,
    copy,
    importlib,
    io,
    json,
    load_module,
    mock,
    sys,
    tempfile,
    unittest,
)

class EvidenceTests(PlanFixture, unittest.TestCase):
    def test_verified_task_requires_sufficient_evidence(self):
        state, plan = self.state_and_plan()
        task = self.task("P1")
        task["status"] = "verified"
        task["requiredEvidence"] = ["build", "targeted-test"]
        task["evidence"] = {"types": ["static"], "summary": "source read", "commandResults": []}
        state["tasks"] = [task]
        with self.assertRaisesRegex(self.workflow.PlanError, "insufficient evidence"):
            self.workflow.validate_state_data(state, plan)

    def test_evidence_command_must_be_listed_in_plan(self):
        state, plan = self.state_and_plan()
        task = self.task("P1")
        task["status"] = "verified"
        task["requiredEvidence"] = ["build", "targeted-test"]
        task["verificationCommands"] = ["python3 expected_test.py"]
        task["evidence"] = {
            "types": ["build", "targeted-test"],
            "summary": "a different command ran",
            "commandResults": [
                {"command": "python3 other_test.py", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "passed"}
            ],
        }
        state["tasks"] = [task]
        with self.assertRaisesRegex(self.workflow.PlanError, "was not listed"):
            self.workflow.validate_state_data(state, plan)

    def test_clean_plan_requires_all_tasks_verified(self):
        state, plan = self.state_and_plan()
        state["tasks"] = [self.task("P1")]
        state["planStatus"] = "clean"
        with self.assertRaisesRegex(self.workflow.PlanError, "requires every active task"):
            self.workflow.validate_state_data(state, plan)

    def test_verified_task_requires_successful_latest_result_for_every_gate(self):
        for results in (
            [],
            [{"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 1, "summary": "failed"}],
            [{"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "passed"}],
            [
                {"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "passed"},
                {"command": "gate-b", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "passed"},
                {"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 1, "summary": "latest failed"},
            ],
        ):
            with self.subTest(results=results):
                state, plan = self.state_and_plan()
                task = self.task()
                task["status"] = "verified"
                task["verificationCommands"] = ["gate-a", "gate-b"]
                task["evidence"] = {
                    "types": ["static"], "summary": "gate history",
                    "commandResults": results,
                }
                state["tasks"] = [task]
                state["planStatus"] = "clean"
                with self.assertRaisesRegex(self.workflow.PlanError, "successful latest result"):
                    self.workflow.validate_state_data(state, plan)

    def test_verified_task_preserves_failed_attempts_before_successful_retry(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task["status"] = "verified"
        task["requiredEvidence"] = ["build", "targeted-test"]
        task["verificationCommands"] = ["gate-a", "gate-b"]
        task["evidence"] = {
            "types": ["build", "targeted-test"], "summary": "both gates eventually passed",
            "commandResults": [
                {"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 1, "summary": "RED"},
                {"command": "gate-b", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "GREEN"},
                {"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 0, "summary": "GREEN"},
            ],
        }
        state["tasks"] = [task]
        state["planStatus"] = "clean"
        self.workflow.validate_state_data(state, plan)

    def test_verified_transition_does_not_close_finding_after_failed_gate(self):
        args = SimpleNamespace(
            task_id="F1", title="Finding", complexity="LOGIC", owner_role="architect",
            depends_on=[], owned_path=["src/finding.cpp"], shared_path=[],
            anchor=["src/finding.cpp:Owner"], accept=["gate passed"], anti=["false closure"],
            required_evidence=["build", "targeted-test"], verification_command=["gate-a"],
            permission=["выполни план"], prompt="Fix finding", severity="HIGH",
        )
        self.workflow.add_task(self.plan_dir, args, finding=True)
        self.workflow.transition_task(self.plan_dir, "F1", "in_progress", None, None, [])
        self.workflow.transition_task(self.plan_dir, "F1", "done_unverified", None, None, [])
        with self.assertRaisesRegex(self.workflow.PlanError, "successful latest result"):
            self.workflow.transition_task(
                self.plan_dir, "F1", "verified", ["build", "targeted-test"], "failed gate",
                [{"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": 1, "summary": "failed"}],
            )
        state = self.workflow.validate_plan_dir(self.plan_dir)
        self.assertEqual(state["tasks"][0]["status"], "done_unverified")
        self.assertEqual(state["findings"][0]["status"], "open")

    def test_archive_rejects_done_unverified_plan(self):
        state = self.workflow._json(self.plan_dir / "state.json")
        state["tasks"] = [self.task("P1")]
        state["tasks"][0]["status"] = "done_unverified"
        state["planStatus"] = "verification_pending"
        self.workflow._atomic_json(self.plan_dir / "state.json", state)
        with self.assertRaisesRegex(self.workflow.PlanError, "only a clean plan"):
            self.workflow.archive_plan(self.plan_dir, Path(self.temporary.name) / "archive")

    def test_added_task_renders_exact_gates_and_boundary_anchors(self):
        args = SimpleNamespace(
            task_id="P1", title="Reviewable task", complexity="LOGIC", owner_role="primary",
            depends_on=[], owned_path=["src/owner.cpp"], shared_path=["CMakeLists.txt"],
            anchor=["src/owner.cpp:actualCallback"], accept=["declared gate passes"],
            anti=["undeclared gate"], required_evidence=["build", "targeted-test"],
            verification_command=["python3 tests/owner.py --case exact"],
            permission=["affected offline check permission required"],
            prompt="Use the exact owner and command.",
        )
        self.workflow.add_task(self.plan_dir, args, finding=False)
        human_plan = (self.plan_dir / "plan.md").read_text(encoding="utf-8")
        for item in args.shared_path + args.anchor + args.verification_command + args.permission:
            with self.subTest(item=item):
                self.assertIn(item, human_plan)

    def test_latest_result_types_replace_earlier_proof_for_same_command(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task.update(status="verified", requiredEvidence=["build"], verificationCommands=["gate"])
        task["evidence"] = {
            "types": ["build"], "summary": "latest only built schema",
            "commandResults": [
                {"command": "gate", "types": ["build"], "exitStatus": 0, "summary": "old build"},
                {"command": "gate", "types": ["schema"], "exitStatus": 0, "summary": "latest schema check"},
            ],
        }
        state.update(tasks=[task], planStatus="clean")
        with self.assertRaisesRegex(self.workflow.PlanError, "matching successful command evidence"):
            self.workflow.validate_state_data(state, plan)

    def test_closed_finding_can_remain_integrated_without_verified_evidence(self):
        state, plan = self.state_and_plan()
        task = self.task("F1")
        task["status"] = "done_unverified"
        state.update(tasks=[task], planStatus="verification_pending", findings=[
            {"taskId": "F1", "severity": "HIGH", "status": "closed"},
        ])
        self.workflow.validate_state_data(state, plan)
        task["status"] = "ready"
        state["planStatus"] = "active"
        with self.assertRaisesRegex(self.workflow.PlanError, "without an integrated task"):
            self.workflow.validate_state_data(state, plan)

    def test_cli_roundtrip_independent_types_and_removed_level_option(self):
        arguments = [
            "add-task", str(self.plan_dir), "--task-id", "P1", "--title", "Selected gate",
            "--owner-role", "primary", "--owned-path", "src/p1.cpp", "--anchor", "src/p1.cpp:Owner",
            "--accept", "gate passed", "--anti", "invented proof", "--prompt", "Inspect and integrate",
            "--required-evidence", "static", "--required-evidence", "schema", "--verification-command", "gate",
        ]
        self.assertEqual(self.workflow.main(arguments), 0)
        for status in ("in_progress", "done_unverified"):
            self.assertEqual(self.workflow.main(["transition", str(self.plan_dir), "P1", status]), 0)
        result = {"command": "gate", "types": ["schema"], "exitStatus": 0, "summary": "schema passed"}
        self.assertEqual(self.workflow.main([
            "transition", str(self.plan_dir), "P1", "verified", "--evidence-type", "static",
            "--evidence-type", "schema", "--evidence-summary", "inspected and checked", "--command-result", json.dumps(result),
        ]), 0)
        self.assertEqual(self.workflow.validate_plan_dir(self.plan_dir)["planStatus"], "clean")
        original = (self.plan_dir / "state.json").read_bytes()
        with contextlib.redirect_stderr(io.StringIO()) as errors, self.assertRaises(SystemExit) as error:
            self.workflow.main(["transition", str(self.plan_dir), "P1", "superseded", "--evidence-level", "live"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("unrecognized arguments: --evidence-level", errors.getvalue())
        self.assertEqual((self.plan_dir / "state.json").read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
