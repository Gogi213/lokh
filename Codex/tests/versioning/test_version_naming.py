"""Policy regressions use isolated source trees and never invoke CMake."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[4]


class VersionNamingTests(unittest.TestCase):
    def check_tree(self, files):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = root / "tools/Codex"
            policy.mkdir(parents=True)
            for name in ("CheckVersionNaming.sh", "VersionNamingAllowlist.txt"):
                shutil.copyfile(ROOT / "tools/Codex" / name, policy / name)
            (root / "CMakeLists.txt").write_text("project(Fixture LANGUAGES CXX)\n")
            for relative, text in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
            return subprocess.run(
                ["bash", str(policy / "CheckVersionNaming.sh")],
                text=True, capture_output=True, timeout=20, check=False)

    def test_rejects_owned_names_and_versioned_asset_paths(self):
        for files in ({"src/current.hpp": "struct FixtureV2 {};"},
                      {"apps/runtime_v3/payload.bin": "data"}):
            with self.subTest(files=files):
                result = self.check_tree(files)
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_rejects_boundary_guards_and_layout_fingerprints(self):
        for token in ("kAbiVersion", "schema_version", "protocolVersion",
                      "contractVersion", "formatVersion", "layoutFingerprint",
                      "compatibilityHash", "referenceDataPlaneAbiFingerprint"):
            with self.subTest(token=token):
                result = self.check_tree({"src/current.hpp": f"int {token} = 1;"})
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("guard:src/current.hpp:", result.stderr)

    def test_preprocessor_boundary_declarations_remain_visible(self):
        result = self.check_tree({"src/current.hpp": "#define OWN_ABI_VERSION 1\n"})
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_preserves_data_generation_integrity_and_failure_identity(self):
        result = self.check_tree({"src/current.hpp": """
            int generation = 4;
            int contentHash = 1;
            int queryFingerprint = 2;
            int provenanceHash = 3;
            struct ContractFaultFingerprint {};
        """})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_negative_test_strings_do_not_become_owned_declarations(self):
        result = self.check_tree({"tools/tests/test_current.py": """
old = {'schemaVersion': 4, 'fixture': 'ContractV2'}
assert 'schema_version' not in old
"""})
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.check_tree({"tools/tests/test_current.py": """
class ContractV2:
    pass
"""})
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_external_protocol_exceptions_are_exact(self):
        result = self.check_tree({"src/current.hpp": "struct AsterV3Auth {};"})
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.check_tree({"src/current.hpp": "struct AsterV3PrivateContract {};"})
        self.assertEqual(result.returncode, 1, result.stderr)
        result = self.check_tree({
            "src/src/Contracts/include/cxet/Parse/Sbe/SbeTypes.hpp":
                "struct Header { int schemaVersion; };"})
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.check_tree({"src/current.hpp": "struct Header { int schemaVersion; };"})
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_package_dependency_versions_survive_owned_metadata_refusal(self):
        result = self.check_tree({"apps/ui/package-lock.json": """
{"lockfileVersion":3,"packages":{"node_modules/react":{"version":"19.0.0"}}}
"""})
        self.assertEqual(result.returncode, 0, result.stderr)
        for text in ('{"version":"1.0.0"}',
                     '{"packages":{"":{"version":"1.0.0"}}}'):
            with self.subTest(text=text):
                result = self.check_tree({"apps/ui/package-lock.json": text})
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_rejects_owned_cmake_project_and_target_versions(self):
        for text in ("project(Fixture VERSION 1.2.3 LANGUAGES CXX)",
                     "set_target_properties(fixture PROPERTIES SOVERSION 1)"):
            with self.subTest(text=text):
                result = self.check_tree({"CMakeLists.txt": text})
                self.assertEqual(result.returncode, 1, result.stderr)
        result = self.check_tree({"CMakeLists.txt": """
cmake_minimum_required(VERSION 3.22)
find_package(SomeLibrary 1.2.3 REQUIRED)
project(Fixture LANGUAGES CXX)
"""})
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
