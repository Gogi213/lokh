"""Hotpath regressions."""
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

class HotpathTests(ToolbeltFixture, unittest.TestCase):
    def test_toolbelt_imports_in_a_fresh_package_process(self):
        proc = subprocess.run(
            [sys.executable, "-c", "import tools.Codex.CxetToolbelt; import tools.Codex.CxetMcpServer"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_sources_include_register_all_anchor(self):
        sources = self.toolbelt.collect_sources(REPO_ROOT)
        self.assertEqual(sources["evidence"], "static-only")
        self.assertIn("src/src/Core/src/Exchanges/RegisterAll.cpp", sources["anchors"])
        self.assertGreaterEqual(len(sources["registered_exchanges"]), 10)

    def test_hotpath_accepts_current_owner_production_cache(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = root / "apps/trader/src/Runtime/include/trader/Runtime/Strategy/ProfileUniverseStrategyRunner.hpp"
            source.parent.mkdir(parents=True)
            source.write_text("// fixture\n")
            build = root / "build/owner"
            build.mkdir(parents=True)
            (build / "compile_commands.json").write_text(json.dumps([{"file": str(source)}]))
            cache = {"CMAKE_HOME_DIRECTORY": str(root), "CMAKE_BUILD_TYPE": "Release",
                     "CXET_BUILD_OWNER": "trader", "CXET_FAMILY_SOURCE_GRAPH": "OFF",
                     "CXET_FULL_BUILD": "OFF",
                     "CXET_ENABLE_HFT_MAGIC": "ON"}
            (build / "CMakeCache.txt").write_text("".join(f"{key}:STRING={value}\n" for key, value in cache.items()))
            report = self.toolbelt.build_hotpath_surface(root, "strategy", build)
            self.assertEqual(report["build_artifacts"]["root"]["status"], "available")

    def test_cli_sources_json(self):
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "CxetToolbelt.py"), "sources", "--format", "json"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["evidence"], "static-only")

    def test_hotpath_surface_is_static_only_and_keeps_candidates_unranked(self):
        report = self.toolbelt.build_hotpath_surface(REPO_ROOT, "transport")
        self.assertEqual(report["evidence"], "static-only")
        self.assertEqual(report["surface"], "transport")
        self.assertIn(
            "src/src/Core/include/cxet/Network/Ws/Runtime/WsRuntimeContract.hpp",
            report["canonical_anchors"],
        )
        self.assertIn("review_candidates", report)
        self.assertNotIn("severity", report)
        self.assertNotIn("violations", report)

    def test_hotpath_surface_rejects_unknown_surface(self):
        with self.assertRaises(ValueError):
            self.toolbelt.build_hotpath_surface(REPO_ROOT, "unknown")

    def test_parser_hotpath_uses_physical_contract_root(self):
        report = self.toolbelt.build_hotpath_surface(REPO_ROOT, "parser")
        self.assertIn(
            "src/src/Contracts/include/cxet/Primitives/Composite/Trade.hpp",
            report["canonical_anchors"],
        )
        self.assertNotIn(
            "src/src/primitives/composite/Trade.hpp",
            report["canonical_anchors"],
        )
        self.assertTrue(
            any(
                path.startswith("src/src/Contracts/include/cxet/Parse/")
                for path in report["files"]
            )
        )

    def test_strategy_hotpath_uses_trading_core_and_retains_parser_backed_trader(self):
        roots = {
            path.as_posix()
            for path in self.toolbelt.HOTPATH_ROOTS["strategy"]
        }
        self.assertTrue(
            {
                "apps/trading-core/src/Core/include",
                "apps/trading-core/src/Strategy/include/strategy",
                "apps/trading-core/src/Core/src",
                "apps/trader/src/Runtime/include/trader/Runtime/Strategy",
                "apps/trader/src/Runtime/src/Strategy",
            }.issubset(roots)
        )
        self.assertNotIn("apps/hft-trader/src/Core/include/hft_trader/core", roots)
        self.assertNotIn("apps/hft-trader/strategy", roots)

        report = self.toolbelt.build_hotpath_surface(REPO_ROOT, "strategy")
        files = set(report["files"])
        self.assertTrue(
            any(path.startswith("apps/trading-core/src/Strategy/include/strategy/") for path in files)
        )
        self.assertTrue(
            any(
                path.startswith("apps/trading-core/src/Core/include/trading_core/Algorithm/")
                for path in files
            )
        )
        self.assertIn(
            "apps/trading-core/src/Core/include/trading_core/Strategy/StrategyApi.hpp",
            files,
        )
        self.assertTrue(
            any(
                path.startswith("apps/trader/src/Runtime/src/Strategy/")
                for path in files
            )
        )
        self.assertFalse(
            any(path.startswith("apps/hft-trader/strategy/") for path in files)
        )
        self.assertIn(
            "apps/trading-core/src/Core/include/trading_core/Contracts/Strategy/StrategyContract.hpp",
            report["canonical_anchors"],
        )
        self.assertIn(
            "apps/trader/src/Runtime/src/Strategy/ProfileUniverseStrategyRunner.cpp",
            report["canonical_anchors"],
        )

    def test_order_hotpath_uses_trading_core_and_retains_parser_backed_trader(self):
        roots = {
            path.as_posix()
            for path in self.toolbelt.HOTPATH_ROOTS["order"]
        }
        self.assertIn(
            "apps/trading-core/src/Core/include/trading_core/Execution/Order",
            roots,
        )
        self.assertNotIn(
            "apps/hft-trader/src/Core/include/hft_trader/api/order",
            roots,
        )
        self.assertIn(
            "apps/trader/src/Runtime/include/trader/Runtime/Order",
            roots,
        )
        self.assertIn("apps/hft-parser/src/Runtime/src/Session", roots)

    def test_hotpath_inventory_reuses_every_canonical_cpp_suffix(self):
        self.assertEqual(
            self.toolbelt.CPP_SCAN_SUFFIXES,
            self.cpp_policy.CPP_SCAN_SUFFIXES,
        )
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            fixtures = (
                root / "apps/trading-core/src/Strategy/include/strategy/.hidden/Hidden.INC",
                root / "apps/trading-core/src/Strategy/include/strategy/module/Strategy.CXXM",
                root / "apps/trading-core/src/Strategy/include/strategy/asm/FastPath.ASM",
            )
            for path in fixtures:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// fixture\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                "apps/trading-core/src/Strategy/include/strategy/.hidden/**\n",
                encoding="utf-8",
            )

            files = set(
                self.toolbelt.build_hotpath_surface(root, "strategy")["files"]
            )
            self.assertTrue(
                {path.relative_to(root).as_posix() for path in fixtures}.issubset(
                    files
                )
            )

    def test_artifact_surface_keeps_compiled_trading_core_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = root / "apps/trading-core/src/Core/src/Strategy/StrategyParams.cpp"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("// fixture\n", encoding="utf-8")
            build = root / "build"
            build.mkdir()
            (build / "compile_commands.json").write_text(
                json.dumps([{"file": str(source)}]), encoding="utf-8"
            )
            (build / "CMakeCache.txt").write_text("", encoding="utf-8")

            report = self.toolbelt.build_artifact_report(
                root, pathlib.Path("build"), {}
            )
            self.assertEqual(
                report["compiled_sources"],
                ["apps/trading-core/src/Core/src/Strategy/StrategyParams.cpp"],
            )

    def test_parser_hotpath_retains_compiled_contract_translation_units(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            canon = root / "src/src/Contracts/src/Canon/CanonLookup.cpp"
            decimal = root / "src/src/Contracts/src/Parse/DecimalToScaled.cpp"
            for path in (canon, decimal):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// fixture\n", encoding="utf-8")

            core_build = root / "build"
            trader_build = root / "apps/trader/build"
            for build, rows, cache in (
                (
                    core_build,
                    [{"file": str(canon)}, {"file": str(decimal)}],
                    {
                        "CMAKE_BUILD_TYPE": "Release",
                        "CXET_FULL_BUILD": "OFF",
                        "CXET_ENABLE_HFT_MAGIC": "ON",
                        "CXET_FAMILY_SOURCE_GRAPH": "OFF",
                        "CXET_BUILD_OWNER": "hft-parser",
                        "CMAKE_HOME_DIRECTORY": str(root),
                    },
                ),
                (
                    trader_build,
                    [],
                    {
                        "CMAKE_BUILD_TYPE": "Release",
                        "CXET_BUILD_OWNER": "trader",
                        },
                ),
            ):
                build.mkdir(parents=True, exist_ok=True)
                (build / "compile_commands.json").write_text(
                    json.dumps(rows), encoding="utf-8"
                )
                (build / "CMakeCache.txt").write_text(
                    "".join(
                        f"{key}:STRING={value}\n"
                        for key, value in cache.items()
                    ),
                    encoding="utf-8",
                )

            report = self.toolbelt.build_hotpath_surface(root, "parser")
            expected = {
                "src/src/Contracts/src/Canon/CanonLookup.cpp",
                "src/src/Contracts/src/Parse/DecimalToScaled.cpp",
            }
            self.assertTrue(expected.issubset(set(report["files"])))
            self.assertEqual(
                set(report["compiled_surface_translation_units"]), expected
            )
            self.assertEqual(report["surface_status"], "available")
            self.assertEqual(set(report["build_artifacts"]), {"root"})

    def test_hotpath_explicit_build_never_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            report = self.toolbelt.build_hotpath_surface(
                root, "parser", pathlib.Path("build/compiler-candidate/hft-low"))
            self.assertEqual(report["surface_status"], "surface_unavailable")
            self.assertEqual(report["build_artifacts"]["root"]["build_dir"],
                             "build/compiler-candidate/hft-low")

    def test_artifact_rejects_missing_compiled_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            build = root / "build"
            build.mkdir()
            source = root / "src/src/Core/src/Network/OldMoved.cpp"
            (build / "compile_commands.json").write_text(json.dumps([{"file": str(source)}]))
            (build / "CMakeCache.txt").write_text("")
            report = self.toolbelt.build_artifact_report(root, pathlib.Path("build"), {})
            self.assertEqual(report["status"], "source_mismatch")
            self.assertEqual(report["missing_sources"], [str(source.relative_to(root))])

    def test_cli_hotpath_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "CxetToolbelt.py"),
                "hotpath",
                "--surface",
                "parser",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["evidence"], "static-only")
        self.assertEqual(payload["surface"], "parser")


if __name__ == '__main__':
    unittest.main()
