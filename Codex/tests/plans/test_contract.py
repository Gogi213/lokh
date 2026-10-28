"""Current plan structure regressions; incompatible saved data is never converted."""
from tools.Codex.tests.Support.plans import PlanFixture, contextlib, copy, io, unittest


class ContractTests(PlanFixture, unittest.TestCase):
    def test_unknown_duplicate_and_unsupported_evidence_types_fail_closed(self):
        for value in (["static", "static"], ["build-test"], ["static-only"], "static", []):
            with self.subTest(value=value):
                state, plan = self.state_and_plan()
                task = self.task()
                task["requiredEvidence"] = value
                state["tasks"] = [task]
                with self.assertRaises(self.workflow.PlanError):
                    self.workflow.validate_state_data(state, plan)
        state, plan = self.state_and_plan()
        task = self.task()
        task["evidence"] = {"level": "static-only", "summary": "unsupported", "commandResults": []}
        state["tasks"] = [task]
        with self.assertRaisesRegex(self.workflow.PlanError, "unsupported"):
            self.workflow.validate_state_data(state, plan)

    def test_state_requires_exact_current_fields_without_rewriting_saved_data(self):
        state, plan = self.state_and_plan()
        original = (self.plan_dir / "state.json").read_bytes()
        self.assertEqual(set(state), {"planId", "planStatus", "repoOwner", "planSha256", "tasks", "findings"})
        for field in state:
            invalid = copy.deepcopy(state)
            del invalid[field]
            with self.subTest(missing=field), self.assertRaises(self.workflow.PlanError):
                self.workflow.validate_state_data(invalid, plan)
        invalid = copy.deepcopy(state)
        invalid["obsoleteField"] = "old layout"
        with self.assertRaisesRegex(self.workflow.PlanError, "unexpected"):
            self.workflow.validate_state_data(invalid, plan)
        self.assertEqual((self.plan_dir / "state.json").read_bytes(), original)

    def test_nested_unknown_fields_fail_closed(self):
        for section in ("task", "evidence", "result", "finding"):
            state, plan = self.state_and_plan()
            task = self.task()
            task["verificationCommands"] = ["gate"]
            result = {"command": "gate", "types": ["static"], "exitStatus": 0, "summary": "inspected"}
            task["evidence"] = {"types": ["static"], "summary": "inspected", "commandResults": [result]}
            finding = {"taskId": task["id"], "severity": "HIGH", "status": "open"}
            state.update(tasks=[task], findings=[finding])
            value = {"task": task, "evidence": task["evidence"], "result": result, "finding": finding}[section]
            value["obsoleteField"] = True
            with self.subTest(section=section), self.assertRaisesRegex(self.workflow.PlanError, "unexpected"):
                self.workflow.validate_state_data(state, plan)

    def test_converter_command_is_unavailable(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.workflow.build_parser().parse_args(["migrate", str(self.plan_dir)])
        self.assertEqual(error.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
