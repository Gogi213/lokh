#!/usr/bin/env python3
"""Focused suffix-inventory regressions for trading-core BBO ownership."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from Family.Sources.CxetFamilyCppPolicy import CPP_SCAN_SUFFIXES  # noqa: E402


def load_checker():
    path = TOOLS_DIR / "CheckTradingCoreBboOwnership.py"
    spec = importlib.util.spec_from_file_location(
        "check_trading_core_bbo_ownership", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BboOwnershipSuffixInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.checker = load_checker()

    def test_source_inventory_reuses_canonical_case_insensitive_suffixes(self) -> None:
        self.assertIs(self.checker.CPP_SCAN_SUFFIXES, CPP_SCAN_SUFFIXES)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            fixtures = (
                root / "apps/product/module/Owner.CXXM",
                root / "apps/product/asm/Owner.ASM",
                root / "apps/product/detail/Owner.INC",
            )
            for path in fixtures:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("// bounded fixture\n", encoding="utf-8")
            ignored = root / "apps/product/README.TXT"
            ignored.write_text("BboReconstructionState\n", encoding="utf-8")

            original_root = self.checker.ROOT
            self.checker.ROOT = root
            try:
                scanned = set(self.checker.source_files(Path("apps")))
            finally:
                self.checker.ROOT = original_root

            self.assertEqual(scanned, set(fixtures))
            self.assertNotIn(ignored, scanned)


if __name__ == "__main__":
    unittest.main()
