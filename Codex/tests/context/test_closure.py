"""Closure regressions."""
from tools.Codex.tests.Support.context import (
    ContextFixture,
    REPO_ROOT,
    TOOLS_DIR,
    importlib,
    json,
    load_module,
    mock,
    pathlib,
    subprocess,
    sys,
    tempfile,
    unittest,
)

class ClosureTests(ContextFixture, unittest.TestCase):
    def test_closure_groups_references_without_claiming_callers(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root)
            (source / "Route.cpp").write_text("OldRoute(); // candidate\n", encoding="utf-8")
            (source / "CMakeLists.txt").write_text("target_sources(owner PRIVATE old/Route.cpp)\n")
            (source / "notes.md").write_text("OldRoute was removed\n")
            report = self.index.build_closure(root, "demo", ["OldRoute"], ["old/Route.cpp"])
            self.assertTrue(report["search_complete"])
            self.assertEqual(report["status"], "references_remaining")
            self.assertEqual({row["category"] for row in report["references"]}, {"source", "build", "docs"})
            self.assertEqual(report["caller_proof"], "not_observed")

    def test_closure_includes_qualified_symbols_without_identifier_substrings(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root)
            (source / "qualified.cpp").write_text(
                "ns::OldRoute();\nOldRoute::method();\nOldRouteExtra();\nNotOldRoute();\n")
            report = self.index.build_closure(root, "demo", ["OldRoute"], [])
            self.assertEqual(report["status"], "references_remaining")
            self.assertEqual([row["line"] for row in report["references"]], [1, 2])

    def test_closure_incomplete_scan_never_claims_no_references(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root, max_files=1)
            (source / "a.cpp").write_text("current();\n")
            (source / "b.cpp").write_text("OldRoute();\n")
            report = self.index.build_closure(root, "demo", ["OldRoute"], [])
            self.assertFalse(report["search_complete"])
            self.assertEqual(report["status"], "incomplete")

    def test_closure_requires_explicit_retirement_and_scoped_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._search_fixture(root)
            for symbols, paths in (([], []), ([], ["../outside"]), (["bad symbol"], [])):
                with self.subTest(symbols=symbols, paths=paths):
                    with self.assertRaises(ValueError):
                        self.index.build_closure(root, "demo", symbols, paths)

    def test_closure_clean_scan_is_only_static_reference_evidence(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root)
            (source / "current.cpp").write_text("NewRoute();\n")
            report = self.index.build_closure(root, "demo", ["OldRoute"], [])
            self.assertEqual(report["status"], "no_references_observed")
            self.assertEqual(report["caller_proof"], "not_observed")
            self.assertEqual(report["build_proof"], "not_observed")


if __name__ == '__main__':
    unittest.main()
