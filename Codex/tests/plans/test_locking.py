"""Locking regressions."""
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

class LockingTests(PlanFixture, unittest.TestCase):
    def test_all_existing_plan_mutators_refuse_a_cooperating_second_writer(self):
        plan_bytes = (self.plan_dir / "plan.md").read_bytes()
        state_bytes = (self.plan_dir / "state.json").read_bytes()
        invocations = [
            lambda: self.workflow.seal_plan(self.plan_dir),
            lambda: self.workflow.add_task(self.plan_dir, SimpleNamespace(), finding=False),
            lambda: self.workflow.add_task(self.plan_dir, SimpleNamespace(), finding=True),
            lambda: self.workflow.transition_task(self.plan_dir, "P1", "in_progress", None, None, []),
            lambda: self.workflow.archive_plan(self.plan_dir, Path(self.temporary.name) / "archive"),
        ]
        with self.workflow._plan_writer_lock(self.plan_dir):
            for invocation in invocations:
                with self.assertRaisesRegex(self.workflow.PlanError, "writer lock is busy"):
                    invocation()
        self.assertEqual((self.plan_dir / "plan.md").read_bytes(), plan_bytes)
        self.assertEqual((self.plan_dir / "state.json").read_bytes(), state_bytes)
        self.assertEqual(sorted(path.name for path in self.plan_dir.iterdir()), ["plan.md", "state.json"])

    def test_initialization_holds_directory_lock_through_first_write(self):
        new_dir = Path(self.temporary.name) / "second-plan"
        writer = self.workflow._atomic_text
        observed = []
        def guarded_writer(path, text):
            if path.parent == new_dir:
                with self.assertRaisesRegex(self.workflow.PlanError, "writer lock is busy"):
                    self.workflow.seal_plan(new_dir)
                observed.append(path.name)
            writer(path, text)
        with mock.patch.object(self.workflow, "_atomic_text", side_effect=guarded_writer):
            self.workflow.initialize_plan(new_dir, "second-plan", ".", "Second")
        self.assertEqual(observed, ["plan.md", "state.json"])
        self.workflow.seal_plan(new_dir)

    def test_archive_directory_lock_survives_rename(self):
        state, plan = self.state_and_plan()
        task = self.task()
        task.update(status="verified", evidence={"types": ["static"], "summary": "integrated review", "commandResults": []})
        state.update(tasks=[task], planStatus="clean")
        self.workflow._atomic_json(self.plan_dir / "state.json", state)
        rename = self.workflow.os.replace
        observed = []
        def guarded_rename(source, destination):
            rename(source, destination)
            if source == self.plan_dir:
                with self.assertRaisesRegex(self.workflow.PlanError, "writer lock is busy"):
                    self.workflow.seal_plan(destination)
                observed.append(destination)
        with mock.patch.object(self.workflow.os, "replace", side_effect=guarded_rename):
            destination = self.workflow.archive_plan(self.plan_dir, Path(self.temporary.name) / "archive")
        self.assertEqual(observed, [destination])
        self.workflow.seal_plan(destination)

    def test_missing_directory_lock_support_fails_closed(self):
        original = (self.plan_dir / "state.json").read_bytes()
        new_dir = Path(self.temporary.name) / "unsupported-plan"
        with mock.patch.object(self.workflow, "fcntl", None):
            with self.assertRaisesRegex(self.workflow.PlanError, "locking is unavailable"):
                self.workflow.seal_plan(self.plan_dir)
            with self.assertRaisesRegex(self.workflow.PlanError, "locking is unavailable"):
                self.workflow.initialize_plan(new_dir, "unsupported-plan", ".", "Unsupported")
        self.assertFalse(new_dir.exists())
        self.assertEqual((self.plan_dir / "state.json").read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
