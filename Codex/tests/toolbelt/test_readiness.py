"""Readiness regressions."""
from tools.Codex.tests.Support.toolbelt import (
    REPO_ROOT,
    TOOLS_DIR,
    ToolbeltFixture,
    importlib,
    json,
    load_module,
    mock,
    os,
    pathlib,
    re,
    shutil,
    subprocess,
    sys,
    tempfile,
    unittest,
)

class ReadinessTests(ToolbeltFixture, unittest.TestCase):
    def test_readiness_summary_is_static_only_and_names_manual_commands(self):
        report = self.toolbelt.build_readiness_report(REPO_ROOT, "binance", "futures")
        self.assertEqual(report["evidence"], "static-only")
        self.assertEqual(report["query"]["exchange"], "binance")
        self.assertEqual(report["query"]["market"], "futures")
        self.assertTrue(report["manual_verification_commands"])
        self.assertIn("src/src/Core/src/Exchanges/RegisterAll.cpp", report["anchors"])
        commands = report["manual_verification_commands"]
        self.assertFalse(any("compile.sh all" in command or "capability_view" in command
                             or "hft_private_api_audit" in command for command in commands))

    def test_readiness_sections_separate_exchange_and_common_evidence(self):
        report = self.toolbelt.build_readiness_report(REPO_ROOT, "definitely-missing", "futures")
        for section in report["sections"].values():
            self.assertEqual(section["status"], "not_observed")
            self.assertEqual(section["exchange_evidence"], [])
            self.assertIn("common_anchor_evidence", section)

    def test_readiness_exchange_filter_finds_case_insensitive_binance_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._write_readiness_config_fixture(root)

            report = self.toolbelt.build_readiness_report(root, "BiNaNcE", None)

            self.assertEqual(
                report["config_candidates"],
                [
                    "src/src/Core/src/Exchanges/Binance/Routing/Futures/Config.cpp",
                    "src/src/Core/src/Exchanges/Binance/Routing/Spot/Config.cpp",
                ],
            )

    def test_readiness_futures_filter_recognizes_fapi_without_exchange_filter(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._write_readiness_config_fixture(root)

            report = self.toolbelt.build_readiness_report(root, None, "FUTURES")

            self.assertEqual(
                report["config_candidates"],
                [
                    "src/src/Core/src/Exchanges/Binance/Routing/Futures/Config.cpp",
                    "src/src/Core/src/Exchanges/Other/Fapi/Config.cpp",
                ],
            )

    def test_readiness_binance_futures_selects_only_binance_fapi_config(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._write_readiness_config_fixture(root)

            report = self.toolbelt.build_readiness_report(root, "BINANCE", "fUtUrEs")

            self.assertEqual(
                report["config_candidates"],
                ["src/src/Core/src/Exchanges/Binance/Routing/Futures/Config.cpp"],
            )

    def test_readiness_unknown_exchange_does_not_scan_all_exchange_directories(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._write_readiness_config_fixture(root)

            report = self.toolbelt.build_readiness_report(root, "Unknown", "futures")

            self.assertEqual(report["config_candidates"], [])


if __name__ == '__main__':
    unittest.main()
