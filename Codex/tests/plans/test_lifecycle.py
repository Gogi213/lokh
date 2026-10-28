"""Lifecycle regressions."""
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

class LifecycleTests(PlanFixture, unittest.TestCase):
    def test_dependency_cycle_fails_closed(self):
        state, plan = self.state_and_plan()
        state["tasks"] = [self.task("P1", ["P2"]), self.task("P2", ["P1"])]
        with self.assertRaisesRegex(self.workflow.PlanError, "dependency cycle"):
            self.workflow.validate_state_data(state, plan)

    def test_plan_hash_drift_fails_closed(self):
        state, _ = self.state_and_plan()
        with self.assertRaisesRegex(self.workflow.PlanError, "planSha256"):
            self.workflow.validate_state_data(state, b"changed plan")

    def test_seal_rebinds_an_intentionally_edited_plan(self):
        plan_path = self.plan_dir / "plan.md"
        plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nNew decision.\n", encoding="utf-8")
        with self.assertRaisesRegex(self.workflow.PlanError, "planSha256"):
            self.workflow.validate_plan_dir(self.plan_dir)
        self.workflow.seal_plan(self.plan_dir)
        self.assertEqual(self.workflow.validate_plan_dir(self.plan_dir)["planId"], "sample-plan")

    def test_ready_task_waits_for_integrated_dependency(self):
        state, plan = self.state_and_plan()
        provider = self.task("P1")
        consumer = self.task("P2", ["P1"])
        state["tasks"] = [provider, consumer]
        self.workflow.validate_state_data(state, plan)
        self.assertEqual([task["id"] for task in self.workflow.ready_tasks(state)], ["P1"])
        provider["status"] = "done_unverified"
        self.assertEqual([task["id"] for task in self.workflow.ready_tasks(state)], ["P2"])

    def test_parallel_owned_path_overlap_fails_closed(self):
        state, plan = self.state_and_plan()
        state["tasks"] = [
            self.task("P1", owned_paths=["src/runtime/**"]),
            self.task("P2", owned_paths=["src/runtime/Owner.cpp"]),
        ]
        with self.assertRaisesRegex(self.workflow.PlanError, "overlap ownership"):
            self.workflow.validate_state_data(state, plan)

    def test_boolean_exit_status_is_not_a_process_result(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task["verificationCommands"] = ["gate-a"]
        task["evidence"] = {
            "types": ["build", "targeted-test"], "summary": "invalid process result",
            "commandResults": [{"command": "gate-a", "types": ["build", "targeted-test"], "exitStatus": False, "summary": "invalid"}],
        }
        state["tasks"] = [task]
        with self.assertRaisesRegex(self.workflow.PlanError, "must be an integer"):
            self.workflow.validate_state_data(state, plan)

    def test_resolve_requires_id_when_multiple_plans_are_active(self):
        repo_owner = Path(self.temporary.name) / "repo"
        active_root = repo_owner / 'docs' / "agent-plans" / "active"
        self.workflow.initialize_plan(active_root / "first-plan", "first-plan", ".", "First")
        self.workflow.initialize_plan(active_root / "second-plan", "second-plan", ".", "Second")
        with self.assertRaisesRegex(self.workflow.PlanError, "provide --plan-id"):
            self.workflow.resolve_plan(repo_owner, None)

    def test_verifier_finding_becomes_ready_task(self):
        args = SimpleNamespace(
            task_id="F1",
            title="Repair verifier finding",
            complexity="LOGIC",
            owner_role="architect",
            depends_on=[],
            owned_path=['docs/finding.md'],
            shared_path=[],
            anchor=['docs/finding.md:Contract'],
            accept=["Finding is resolved"],
            anti=["Verifier edits product source directly"],
            required_evidence=["static"],
            verification_command=[],
            permission=["выполни план"],
            prompt="Resolve the recorded finding within its owned path.",
            severity="HIGH",
        )
        self.workflow.add_task(self.plan_dir, args, finding=True)
        state = self.workflow.validate_plan_dir(self.plan_dir)
        self.assertEqual(state["tasks"][0]["status"], "ready")
        self.assertEqual(state["findings"], [{"taskId": "F1", "severity": "HIGH", "status": "open"}])

    def test_rule_index_has_existing_canonical_owners(self):
        index = self.workflow.validate_rule_index(REPO_ROOT)
        ids = {rule["id"] for rule in index["rules"]}
        self.assertIn("global-contracts", ids)
        self.assertIn("durable-plans", ids)
        self.assertIn("hot-path-fast-lane", ids)

    def test_live_does_not_cover_other_independent_requirements(self):
        for requirement in ("build", "targeted-test", "runtime", "browser", "model", "performance", "schema"):
            with self.subTest(requirement=requirement):
                state, plan = self.state_and_plan()
                task = self.task()
                task.update(status="verified", requiredEvidence=[requirement], verificationCommands=["live-gate"])
                task["evidence"] = {
                    "types": ["live"], "summary": "selected live action",
                    "commandResults": [{"command": "live-gate", "types": ["live"], "exitStatus": 0, "summary": "passed"}],
                }
                state.update(tasks=[task], planStatus="clean")
                with self.assertRaisesRegex(self.workflow.PlanError, "insufficient evidence"):
                    self.workflow.validate_state_data(state, plan)

    def test_every_claimed_non_static_type_needs_matching_latest_success(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task.update(status="verified", verificationCommands=["gate"])
        task["evidence"] = {
            "types": ["static", "build", "live"], "summary": "unproven live claim",
            "commandResults": [{"command": "gate", "types": ["build"], "exitStatus": 0, "summary": "build passed"}],
        }
        state.update(tasks=[task], planStatus="clean")
        with self.assertRaisesRegex(self.workflow.PlanError, "matching successful command evidence"):
            self.workflow.validate_state_data(state, plan)
        task["status"] = "done_unverified"
        state["planStatus"] = "verification_pending"
        with self.assertRaisesRegex(self.workflow.PlanError, "matching successful command evidence"):
            self.workflow.validate_state_data(state, plan)

    def test_transition_retains_failed_attempts_across_implementation_and_retry(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task.update(status="in_progress", requiredEvidence=["build"], verificationCommands=["gate"])
        state["tasks"] = [task]
        self.workflow._atomic_json(self.plan_dir / "state.json", state)
        failed = {"command": "gate", "types": ["build"], "exitStatus": 1, "summary": "first failed"}
        self.workflow.transition_task(self.plan_dir, "P1", "done_unverified", ["static"], "integrated; gate failed", [failed])
        self.workflow.transition_task(self.plan_dir, "P1", "ready", None, None, [])
        self.workflow.transition_task(self.plan_dir, "P1", "in_progress", None, None, [])
        self.workflow.transition_task(self.plan_dir, "P1", "done_unverified", None, None, [])
        passed = {"command": "gate", "types": ["build"], "exitStatus": 0, "summary": "retry passed"}
        self.workflow.transition_task(self.plan_dir, "P1", "verified", ["static", "build"], "integrated and built", [passed])
        final = self.workflow.validate_plan_dir(self.plan_dir)
        self.assertEqual(final["tasks"][0]["evidence"]["commandResults"], [failed, passed])


if __name__ == '__main__':
    unittest.main()
