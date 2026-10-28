#!/usr/bin/env python3
"""Fail closed unless Parser sessions and trading analytics retain their owners."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from Family.Sources.CxetFamilyCppPolicy import CPP_SCAN_SUFFIXES


ROOT = Path(__file__).resolve().parents[2]
PARSER_ROOT = Path("apps/hft-parser")
HFT_TRADER_ROOT = Path("apps/hft-trader")
TRADING_PRODUCT_SOURCE_ROOTS = (
    Path("apps/trading-core/src/Core/include"),
    Path("apps/trading-core/src/Strategy/include/strategy"),
    Path("apps/trading-core/src/Core/src"),
)

RELATIVE_HEADER = Path(
    "apps/trading-core/src/Core/include/trading_core/Algorithm/Signals/Volatility/RelativeDifferenceVolatility.hpp"
)
SPREAD_PROCESSOR = Path("apps/trader/src/Market/src/Analysis/Volatility/SpreadVolatilityProcessor.cpp")
PARSER_BRIDGE = PARSER_ROOT / Path(
    "backend/include/hft_parser/analysis/TraderAlgorithmCore.hpp"
)
OLD_HFT_RELATIVE_HEADER = HFT_TRADER_ROOT / Path(
    "include/hft_trader/core/indicators/RelativeDifferenceVolatility.hpp"
)

SKIP_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "CMakeFiles",
    "_deps",
    "build",
    "dist",
    "node_modules",
    "out",
}

PARSER_BUILD_BOUNDARY_FILES = tuple(PARSER_ROOT / relative for relative in (
    ".github/workflows/local-ci.yml", ".github/workflows/local-control.yml",
    ".github/workflows/family-reuse.yml", "CMakeLists.txt", "compile.sh",
    "cmake/HftpLibraries.cmake", "cmake/HftpProcesses.cmake",
))


def skip_directory(name: str) -> bool:
    return (
        name in SKIP_DIRECTORY_NAMES
        or name.startswith("build-")
        or name.startswith("cmake-build-")
    )


def source_files(relative_root: Path) -> list[Path]:
    root = ROOT / relative_root
    if not root.is_dir():
        return []

    result: list[Path] = []
    for directory, directory_names, file_names in os.walk(root):
        directory_names[:] = [
            name for name in directory_names if not skip_directory(name)
        ]
        base = Path(directory)
        for file_name in file_names:
            path = base / file_name
            if path.suffix.lower() in CPP_SCAN_SUFFIXES:
                result.append(path)
    return sorted(result)


def read_required(relative: Path, errors: list[str]) -> str:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing required file: {relative.as_posix()}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {relative.as_posix()}: {exc}")
        return ""


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def require_pattern(
    relative: Path,
    text: str,
    pattern: str,
    description: str,
    errors: list[str],
    *,
    flags: int = 0,
) -> None:
    if re.search(pattern, text, flags) is None:
        errors.append(f"{relative.as_posix()}: missing required {description}")


def forbid_pattern(
    relative: Path,
    text: str,
    pattern: str,
    description: str,
    errors: list[str],
    *,
    flags: int = 0,
) -> None:
    match = re.search(pattern, text, flags)
    if match is None:
        return
    errors.append(
        f"{relative.as_posix()}:{line_number(text, match.start())}: "
        f"forbidden {description}"
    )


def check_parser_cpp_boundary(errors: list[str]) -> None:
    forbidden = (
        (
            r"#\s*include\s*[<\"]hft_trader/",
            "HFT Trader include in Parser C++ source",
        ),
        (r"\bhft_trader::", "HFT Trader namespace use in Parser C++ source"),
        (
            r"#\s*include\s*[<\"]trading_core/",
            "trading-core include in Parser C++ source",
        ),
        (r"\btrading_core::", "trading-core namespace use in Parser C++ source"),
    )
    for path in source_files(PARSER_ROOT):
        relative = path.relative_to(ROOT)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {relative.as_posix()}: {exc}")
            continue
        for pattern, description in forbidden:
            forbid_pattern(relative, text, pattern, description, errors)


def check_build_boundary(errors: list[str]) -> None:
    forbidden = (
        (r"\bHFT_PARSER_HFT_TRADER_ROOT\b", "HFT Trader source-root variable"),
        (r"\bHFT_TRADER_ALGORITHM_ROOT\b", "HFT Trader algorithm-root variable"),
        (r"\bHFTP_TRADER_ALGORITHM_CORE_CMAKE\b", "sibling CMake package path"),
        (r"\bhft_trader_define_algorithm_core\b", "sibling target factory"),
        (r"\bhft_trader::", "HFT Trader CMake target"),
        (r"\bhft_parser::trader_algorithm_core\b", "Parser compatibility target"),
        (r"\bhftp_trader_algorithm_core_bridge\b", "Parser compatibility bridge"),
        (r"\bCI_HFT_TRADER_SSH_KEY\b", "HFT Trader CI secret slot"),
        (r"repository\s*:\s*[^\n]*hft-trader", "HFT Trader CI checkout"),
        (r"apps/hft-trader", "HFT Trader sibling source traversal"),
        (r"include/hft_trader/core", "HFT Trader include-tree traversal"),
        (r"hft[-_]trader", "HFT Trader build or CI dependency residue"),
        (r"trading[-_]core", "trading-core build dependency residue"),
    )
    for relative in PARSER_BUILD_BOUNDARY_FILES:
        text = read_required(relative, errors)
        for pattern, description in forbidden:
            forbid_pattern(
                relative,
                text,
                pattern,
                description,
                errors,
                flags=re.IGNORECASE,
            )


def check_relative_owner(errors: list[str]) -> None:
    if (ROOT / PARSER_BRIDGE).exists():
        errors.append(
            f"obsolete compatibility bridge still exists: {PARSER_BRIDGE.as_posix()}"
        )
    if (ROOT / OLD_HFT_RELATIVE_HEADER).exists():
        errors.append(
            "obsolete HFT Trader RelativeDifferenceVolatility owner still exists: "
            f"{OLD_HFT_RELATIVE_HEADER.as_posix()}"
        )

    relative_text = read_required(RELATIVE_HEADER, errors)
    required = (
        (
            r"namespace\s+trading_core\s*\{",
            "canonical trading-core algorithm namespace",
        ),
        (
            r"struct\s+PreparedRelativeDifferenceVolatilityConfig\s*\{",
            "prepared configuration",
        ),
        (
            r"struct\s+RelativeDifferenceVolatilityState\s*\{",
            "fixed volatility state",
        ),
        (
            r"enum\s+class\s+RelativeDifferenceVolatilityPhase\b",
            "phase state machine",
        ),
        (
            r"RelativeDifferenceVolatilityPhase::Gap",
            "Gap lifecycle",
        ),
        (
            r"RelativeDifferenceVolatilityPhase::Stale",
            "Stale lifecycle",
        ),
        (
            r"RelativeDifferenceVolatilityDisposition::TimestampRollback",
            "timestamp rollback refusal",
        ),
        (r"resumeFreshAfterDelta", "one-delta recovery state"),
        (r"unsigned\s+__int128", "wide saturating arithmetic"),
        (r"<<\s*32u", "Q32 half-life exponent"),
        (
            r"prepareRelativeDifferenceVolatilityConfig\s*\(",
            "cold prepared configuration API",
        ),
        (
            r"updateRelativeDifferenceVolatility\s*\(",
            "bounded update API",
        ),
    )
    for pattern, description in required:
        require_pattern(
            RELATIVE_HEADER,
            relative_text,
            pattern,
            description,
            errors,
            flags=re.MULTILINE,
        )
    for pattern, description in (
        (r"\bhft_trader\b", "HFT Trader ownership residue"),
        (r"TraderAlgorithmCore", "compatibility facade"),
        (r"ParserAlgorithmCore", "generic Parser algorithm facade"),
        (r"\bFastU64Divisor\b", "copied generic fast-divisor API"),
        (r"\bBpsE8Divisor\b", "copied generic Bps divisor API"),
        (r"\bCachedBpsE8Divisor\b", "copied generic cached Bps API"),
        (r"\bprepareFastU64Divisor\b", "copied generic divisor preparation API"),
        (r"\bfastFloorDivU128\b", "copied generic division API"),
        (r"\bbpsE8\s*\(", "copied generic Bps API"),
        (r"\bemaDt", "copied generic EMA API"),
        (r"\bkEma", "copied generic EMA constants"),
    ):
        forbid_pattern(
            RELATIVE_HEADER,
            relative_text,
            pattern,
            description,
            errors,
        )

    production_roots = (
        PARSER_ROOT / "src",
        Path("apps/trader/src"),
        *TRADING_PRODUCT_SOURCE_ROOTS,
    )
    owners: list[str] = []
    declaration = re.compile(r"\bstruct\s+RelativeDifferenceVolatilityState\s*\{")
    for production_root in production_roots:
        for path in source_files(production_root):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(
                    f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}"
                )
                continue
            if declaration.search(text):
                owners.append(path.relative_to(ROOT).as_posix())
    if owners != [RELATIVE_HEADER.as_posix()]:
        errors.append(
            "RelativeDifferenceVolatility must have exactly one trading-core owner; "
            f"found {owners}"
        )


def check_volatility_duplicates(errors: list[str]) -> None:
    declaration = re.compile(r"\bstruct\s+RelativeDifferenceVolatilityState\s*\{")
    for production_root in TRADING_PRODUCT_SOURCE_ROOTS:
        for path in source_files(production_root):
            if path.relative_to(ROOT) == RELATIVE_HEADER:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                errors.append(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
                continue
            if declaration.search(text):
                errors.append(f"{path.relative_to(ROOT).as_posix()}: duplicated canonical volatility state")


def check_direct_consumers(errors: list[str]) -> None:
    check_volatility_duplicates(errors)

    processor = read_required(SPREAD_PROCESSOR, errors)
    require_pattern(
        SPREAD_PROCESSOR,
        processor,
        r"trading_core/Algorithm/Signals/Volatility/RelativeDifferenceVolatility\.hpp",
        "direct canonical trading-core volatility include",
        errors,
    )
    forbid_pattern(
        SPREAD_PROCESSOR,
        processor,
        r"TraderAlgorithmCore",
        "compatibility bridge include",
        errors,
    )
    for pattern, description in (
        (
            r"struct\s+SpreadPriceBasisDivisor\b",
            "Trader feature-shaped price-basis divisor",
        ),
        (
            r"static_assert\s*\(\s*sizeof\(SpreadPriceBasisDivisor\)\s*==\s*24u",
            "fixed price-basis divisor layout guard",
        ),
        (
            r"static_assert\s*\(\s*sizeof\(RelativeDifferenceVolatilityState\)\s*==\s*96u",
            "fixed relative-volatility state layout guard",
        ),
        (
            r"priceBasisQtyRaw\s*==\s*0\s*&&\s*entry\.quantityScale\s*>\s*18u",
            "bounded implicit quantity-scale validation",
        ),
        (
            r"spreadPriceBasisPowerOfTen\s*\(\s*entry\.quantityScale\s*\)",
            "implicit price basis derived from quantity scale",
        ),
    ):
        require_pattern(
            SPREAD_PROCESSOR,
            processor,
            pattern,
            description,
            errors,
            flags=re.MULTILINE,
        )
    for pattern, description in (
        (r"\bFastU64Divisor\b", "copied generic fast-divisor API"),
        (r"\bBpsE8Divisor\b", "copied generic Bps divisor API"),
        (r"\bprepareFastU64Divisor\b", "copied generic divisor preparation API"),
        (r"\bfastFloorDivU128\b", "copied generic division API"),
        (r"\bbpsE8\s*\(", "copied generic Bps API"),
        (r"\bemaDt", "copied generic EMA API"),
    ):
        forbid_pattern(
            SPREAD_PROCESSOR,
            processor,
            pattern,
            description,
            errors,
        )

    # Historical Parser test names are not inputs of the current graph.
    # Behavioral coverage is owned by the offline registrations, not this scanner.


def main() -> int:
    errors: list[str] = []
    check_parser_cpp_boundary(errors)
    check_build_boundary(errors)
    check_relative_owner(errors)
    check_direct_consumers(errors)

    if errors:
        print("Parser/trading boundary check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("Parser/trading boundary check passed (static-only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
