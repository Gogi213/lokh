"""Boundaries regressions."""
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

class BoundariesTests(ToolbeltFixture, unittest.TestCase):
    def test_native_boundary_checker_uses_canonical_trading_core_roots(self):
        checker = (TOOLS_DIR / "CheckNativeBoundaries.sh").read_text(
            encoding="utf-8"
        )
        for root in (
            "apps/trading-core/src/Core/include",
            "apps/trading-core/src/Strategy/include/strategy",
            "apps/trading-core/src/Core/src",
        ):
            self.assertIn(f'"$repo_root/{root}"', checker)
        self.assertNotIn(
            '"$repo_root/apps/trading-core/src/Core/include/trading_core/core"', checker
        )
        self.assertNotIn(
            '"$repo_root/apps/trading-core/src/Core/include/trading_core/Strategy"', checker
        )
        self.assertIn(
            'check_stale_source_root "apps/hft-trader/strategy"', checker
        )
        self.assertIn(
            'check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/core"',
            checker,
        )
        self.assertIn(
            'check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/api"',
            checker,
        )
        self.assertIn(
            'check_stale_source_root "apps/hft-trader/src/Core/include/hft_trader/market"',
            checker,
        )
        self.assertIn(
            'check_stale_source_root "apps/hft-trader/strategy_profiles"',
            checker,
        )
        suffix_block = re.search(
            r"canonical_cpp_suffixes=\((.*?)\n\)",
            checker,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(suffix_block)
        self.assertEqual(
            set(re.findall(r'"([^"\n]+)"', suffix_block.group(1))),
            set(self.cpp_policy.CPP_SCAN_SUFFIXES),
        )
        self.assertIn('--iglob "*${suffix}"', checker)

    def test_native_boundary_checker_rejects_reintroduced_hft_sources(self):
        source_checker = TOOLS_DIR / "CheckNativeBoundaries.sh"
        stale_roots = (
            pathlib.Path("apps/hft-trader/strategy"),
            pathlib.Path("apps/hft-trader/strategy_profiles"),
            pathlib.Path("apps/hft-trader/src/Core/include/hft_trader/api"),
            pathlib.Path("apps/hft-trader/src/Core/include/hft_trader/core"),
            pathlib.Path("apps/hft-trader/src/Core/include/hft_trader/market"),
        )
        for stale_root in stale_roots:
            with self.subTest(stale_root=stale_root.as_posix()):
                with tempfile.TemporaryDirectory() as raw:
                    root = pathlib.Path(raw)
                    checker = root / "tools/Codex/CheckNativeBoundaries.sh"
                    checker.parent.mkdir(parents=True)
                    shutil.copy2(source_checker, checker)
                    physical_root = root / stale_root
                    physical_root.mkdir(parents=True)
                    (root / ".gitignore").write_text(
                        "apps/hft-trader/**\n", encoding="utf-8"
                    )

                    empty = subprocess.run(
                        ["bash", str(checker)],
                        cwd=root,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertEqual(empty.returncode, 0, empty.stderr)

                    stale_source = physical_root / ".legacy/README.txt"
                    stale_source.parent.mkdir()
                    stale_source.write_text("#pragma once\n", encoding="utf-8")
                    rejected = subprocess.run(
                        ["bash", str(checker)],
                        cwd=root,
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertIn(
                        "stale source root reintroduced", rejected.stderr
                    )
                    self.assertIn("README.txt", rejected.stdout)

    def test_native_boundary_checker_rejects_stale_symlink(self):
        source_checker = TOOLS_DIR / "CheckNativeBoundaries.sh"
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            checker = root / "tools/Codex/CheckNativeBoundaries.sh"
            checker.parent.mkdir(parents=True)
            shutil.copy2(source_checker, checker)
            stale_root = root / "apps/hft-trader/strategy"
            stale_root.mkdir(parents=True)
            stale_link = stale_root / ".legacy/dangling"
            stale_link.parent.mkdir()
            stale_link.symlink_to("missing-target")

            rejected = subprocess.run(
                ["bash", str(checker)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("stale source root reintroduced", rejected.stderr)
            self.assertIn("dangling", rejected.stdout)

    def test_native_boundary_scans_hidden_ignored_modules_and_assembly(self):
        source_checker = TOOLS_DIR / "CheckNativeBoundaries.sh"
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            for relative in (
                "src/src/Contracts/include",
                "src/src/Contracts/src",
                "src/src/Core/include",
                "src/src/Core/src",
                "src/benchmarks",
                "src/tests",
                "apps/hft-parser/src/backend",
                "apps/hft-parser/src/Clients/include",
                "apps/hft-parser/src/Contracts/include",
                "apps/trading-core/src/Core/include",
                "apps/trading-core/src/Strategy/include/strategy",
                "apps/trading-core/src/Core/src",
                        "apps/trader/tools",
                "apps/trader/benchmarks",
                "apps/trader/tests",
            ):
                (root / relative).mkdir(parents=True, exist_ok=True)
            checker = root / "tools/Codex/CheckNativeBoundaries.sh"
            checker.parent.mkdir(parents=True)
            shutil.copy2(source_checker, checker)
            fixtures = (
                root / "apps/trading-core/src/Strategy/include/strategy/.hidden/Hidden.INC",
                root / "apps/trading-core/src/Strategy/include/strategy/module/Strategy.CXXM",
                root / "apps/trading-core/src/Strategy/include/strategy/asm/FastPath.ASM",
            )
            for path in fixtures:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("std::string_view forbidden;\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                "apps/trading-core/src/Strategy/include/strategy/.hidden/**\n",
                encoding="utf-8",
            )

            rejected = subprocess.run(
                ["bash", str(checker)],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(rejected.returncode, 0)
            for fixture in fixtures:
                self.assertIn(fixture.name, rejected.stdout)

    def test_parser_boundary_scans_canonical_trading_strategy_root(self):
        expected = (
            pathlib.Path("apps/trading-core/src/Core/include"),
            pathlib.Path("apps/trading-core/src/Strategy/include/strategy"),
            pathlib.Path("apps/trading-core/src/Core/src"),
        )
        self.assertEqual(
            self.parser_boundary.TRADING_PRODUCT_SOURCE_ROOTS,
            expected,
        )
        self.assertEqual(
            self.parser_boundary.CPP_SCAN_SUFFIXES,
            self.cpp_policy.CPP_SCAN_SUFFIXES,
        )

        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            fixtures = (
                root / "apps/trading-core/src/Strategy/include/strategy/regression/Strategy.hpp",
                root / "apps/trading-core/src/Strategy/include/strategy/.hidden/Hidden.INC",
                root / "apps/trading-core/src/Strategy/include/strategy/module/Strategy.CXXM",
                root / "apps/trading-core/src/Strategy/include/strategy/asm/FastPath.ASM",
            )
            for strategy in fixtures:
                strategy.parent.mkdir(parents=True, exist_ok=True)
                strategy.write_text(
                    "struct RelativeDifferenceVolatilityState {};\n",
                    encoding="utf-8",
                )
            (root / ".gitignore").write_text(
                "apps/trading-core/src/Strategy/include/strategy/.hidden/**\n",
                encoding="utf-8",
            )
            original_root = self.parser_boundary.ROOT
            self.parser_boundary.ROOT = root
            try:
                errors = []
                self.parser_boundary.check_volatility_duplicates(errors)
            finally:
                self.parser_boundary.ROOT = original_root
            for fixture in fixtures:
                self.assertTrue(
                    any(fixture.relative_to(root).as_posix() in error
                        and "volatility" in error for error in errors), errors,
                )

    def test_parser_build_boundary_uses_current_source_graph_files(self):
        relative_files = (
            "apps/hft-parser/.github/workflows/local-ci.yml",
            "apps/hft-parser/.github/workflows/local-control.yml",
            "apps/hft-parser/.github/workflows/family-reuse.yml",
            "apps/hft-parser/CMakeLists.txt", "apps/hft-parser/compile.sh",
            "apps/hft-parser/cmake/HftpLibraries.cmake",
            "apps/hft-parser/cmake/HftpProcesses.cmake",
        )
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            for relative in relative_files:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# independent Parser input\n")
            with mock.patch.object(self.parser_boundary, "ROOT", root):
                errors = []
                self.parser_boundary.check_build_boundary(errors)
                self.assertEqual(errors, [])
                (root / relative_files[-1]).write_text("target_link_libraries(parser PRIVATE trading_core::execution)\n")
                self.parser_boundary.check_build_boundary(errors)
                self.assertTrue(any("trading-core" in error for error in errors), errors)

    def test_relative_volatility_has_one_current_trading_core_owner(self):
        canonical = pathlib.Path("apps/trading-core/src/Core/include/trading_core/Algorithm/Signals/Volatility/RelativeDifferenceVolatility.hpp")
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            path = root / canonical
            path.parent.mkdir(parents=True)
            path.write_text((REPO_ROOT / canonical).read_text())
            with mock.patch.object(self.parser_boundary, "ROOT", root):
                errors = []
                self.parser_boundary.check_relative_owner(errors)
                self.assertEqual(errors, [])
                duplicate = root / "apps/trading-core/src/Core/include/Duplicate.hpp"
                duplicate.write_text("struct RelativeDifferenceVolatilityState {};\n")
                self.parser_boundary.check_relative_owner(errors)
                self.assertTrue(any("exactly one" in error for error in errors), errors)

    def test_native_boundary_scanner_errors_do_not_pass_silently(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            checker = root / "tools/Codex/CheckNativeBoundaries.sh"
            checker.parent.mkdir(parents=True)
            shutil.copy2(TOOLS_DIR / "CheckNativeBoundaries.sh", checker)
            binary = root / "bin"
            binary.mkdir()
            rg = binary / "rg"
            rg.write_text("#!/bin/sh\nexit 2\n")
            rg.chmod(0o755)
            (root / "src/src/Core/include").mkdir(parents=True)
            result = subprocess.run(["bash", str(checker)], cwd=root,
                                    env={**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]},
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scan failed", result.stderr)

    def test_native_boundary_inaccessible_ancestor_does_not_hide_scan_roots(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            checker = root / "tools/Codex/CheckNativeBoundaries.sh"
            checker.parent.mkdir(parents=True)
            shutil.copy2(TOOLS_DIR / "CheckNativeBoundaries.sh", checker)
            ancestor = root / "src/src/Core"
            (ancestor / "include").mkdir(parents=True)
            ancestor.chmod(0)
            try:
                result = subprocess.run(["bash", str(checker)], cwd=root,
                                        text=True, capture_output=True, timeout=10)
            finally:
                ancestor.chmod(0o755)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scan failed", result.stderr)


if __name__ == '__main__':
    unittest.main()
