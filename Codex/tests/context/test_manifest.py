"""Manifest regressions."""
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

class ManifestTests(ContextFixture, unittest.TestCase):
    def test_manifest_rejects_unknown_fields_without_a_format_marker(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._search_fixture(root)
            for section in ("manifest", "limits", "common", "scope"):
                manifest = self.index._load_manifest_file(root)
                value = {"manifest": manifest, "limits": manifest["limits"],
                         "common": manifest["common"], "scope": manifest["scopes"]["demo"]}[section]
                value["obsoleteField"] = True
                report = self.index.validate_manifest(root, manifest)
                with self.subTest(section=section):
                    self.assertFalse(report["valid"])
                    self.assertTrue(any("unexpected" in error for error in report["errors"]))

    def test_manifest_does_not_advertise_install_named_recipe(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._search_fixture(root)
            manifest = self.index._load_manifest_file(root)
            manifest["scopes"]["demo"]["static_checks"] = ["bash tools/Codex/InstallSkills.sh"]
            self.assertFalse(self.index.validate_manifest(root, manifest)["valid"])

    def test_manifest_rejects_malformed_quoted_recipe_without_crashing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._search_fixture(root)
            manifest = self.index._load_manifest_file(root)
            manifest["scopes"]["demo"]["static_checks"] = ["python3 tools/Codex/CxetContextIndex.py validate '"]
            self.assertFalse(self.index.validate_manifest(root, manifest)["valid"])

    def test_repository_manifest_is_valid_and_lists_context_scopes(self):
        report = self.index.validate_manifest(REPO_ROOT)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["evidence"], "static-only")
        self.assertEqual(
            set(report["scopes"]),
            {
                "contracts",
                "parser",
                "transport",
                "hotpath",
                "strategy",
                "capital",
                "trader",
                "hft-parser",
                "vetron",
                "readiness",
                "ci",
            },
        )

    def test_manifest_validator_rejects_missing_root_and_absolute_path(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            manifest = {
                "limits": {"map_bytes": 6144, "detail_bytes": 8192, "max_results": 20},
                "common": {"route_docs": [], "rules": []},
                "scopes": {
                    "demo": {
                        "owner": "demo",
                        "keywords": ["demo"],
                        "roots": ["missing", "/tmp/outside"],
                        "route_docs": [],
                        "anchors": [],
                        "static_checks": [],
                    }
                },
            }
            report = self.index.validate_manifest(root, manifest)
            self.assertFalse(report["valid"])
            self.assertTrue(any("missing" in error for error in report["errors"]))
            self.assertTrue(any("absolute" in error for error in report["errors"]))

    def test_manifest_validator_rejects_arbitrary_python_commands(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            (root / "root").mkdir()
            manifest = {
                "limits": {
                    "map_bytes": 6144,
                    "detail_bytes": 8192,
                    "max_results": 20,
                    "max_files": 2000,
                    "max_entries": 20000,
                    "max_file_bytes": 1048576,
                },
                "common": {"route_docs": [], "rules": ["static"]},
                "scopes": {
                    "demo": {
                        "owner": "demo",
                        "keywords": ["demo"],
                        "roots": ["root"],
                        "route_docs": [],
                        "anchors": [],
                        "static_checks": ["python3 -c 'print(1)'"],
                    }
                },
            }
            report = self.index.validate_manifest(root, manifest)
            self.assertFalse(report["valid"])
            self.assertTrue(any("allowlisted" in error for error in report["errors"]))


if __name__ == '__main__':
    unittest.main()
