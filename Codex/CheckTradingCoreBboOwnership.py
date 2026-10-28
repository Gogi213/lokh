#!/usr/bin/env python3
"""Fail closed unless trade-inferred BBO reconstruction has one trading-core owner."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from Family.Sources.CxetFamilyCppPolicy import CPP_SCAN_SUFFIXES


ROOT = Path(__file__).resolve().parents[2]

CANONICAL_HEADER = Path(
    "apps/trading-core/src/Core/include/trading_core/Algorithm/Market/BboReconstruction.hpp")
CORE_TEST = Path("apps/trading-core/tests/Ported/Market/BboReconstructionTests.cpp")
CORE_TEST_CMAKE = Path("apps/trading-core/tests/CMakeLists.txt")
OLD_CXET_HEADER = Path(
    "src/src/Contracts/include/cxet/Primitives/Composite/BboReconstruction.hpp")
OLD_HFT_TRADER_HEADER = Path(
    "apps/hft-trader/src/Core/include/hft_trader/core/market/BboReconstruction.hpp"
)
CANONICAL_INCLUDE = "trading_core/Algorithm/Market/BboReconstruction.hpp"

PRODUCT_ROOTS = {
    "Backtest": Path("apps/hft-backtest"),
    "Trader": Path("apps/trader"),
}

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

NON_PRODUCTION_DIRECTORY_NAMES = {
    "benchmark",
    "benchmarks",
    "test",
    "tests",
}

BBO_SYMBOLS = (
    "BboReconstructionSource",
    "BboReconstructionFlag",
    "BboReconstructionView",
    "BboReconstructionState",
    "kBboReconstructionSourceUnset",
    "kBboReconstructionSourceBookTicker",
    "kBboReconstructionSourceTrade",
    "kBboReconstructionFlagFalse",
    "kBboReconstructionFlagTrue",
    "resetBboReconstruction",
    "bboReconstructionView",
    "validBboReconstruction",
    "bboReconstructionTimestampRollback",
    "applyBboReconstructionBookTicker",
    "applyBboReconstructionBookTickerSide",
    "applyBboReconstructionKnownInitiatorTrade",
)

PUBLIC_FUNCTIONS = (
    "resetBboReconstruction",
    "bboReconstructionView",
    "validBboReconstruction",
    "bboReconstructionTimestampRollback",
    "applyBboReconstructionBookTicker",
    "applyBboReconstructionBookTickerSide",
    "applyBboReconstructionKnownInitiatorTrade",
)

FORBIDDEN_APP_BBO_HELPERS = (
    "validBookTickerPrice",
    "validBboTrade",
    "validReconstructedBbo",
    "markBboTradeUpdate",
)


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


def read_source(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        relative = path.relative_to(ROOT).as_posix()
        errors.append(f"cannot read source file {relative}: {exc}")
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
        errors.append(
            f"{relative.as_posix()}: missing required {description}"
        )


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


def strip_cpp_comments(text: str) -> str:
    def preserve_newlines(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    without_blocks = re.sub(r"/\*.*?\*/", preserve_newlines, text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", without_blocks)


def check_canonical_header(text: str, errors: list[str]) -> None:
    required_fragments = (
        (r"namespace\s+trading_core\s*\{", "trading_core namespace"),
        (
            r"#\s*include\s*[<\"]cxet/primitives/buf/CompilerHints\.hpp[>\"]",
            "direct CompilerHints dependency",
        ),
        (r"struct\s+BboReconstructionSource\s*:\s*Count<8>", "byte source type"),
        (r"struct\s+BboReconstructionFlag\s*:\s*Count<8>", "byte flag type"),
        (r"struct\s+BboReconstructionView\s*\{", "view type"),
        (
            r"struct\s+alignas\(rawdata::kCacheLineBytes\)\s+"
            r"BboReconstructionState\s*\{",
            "cache-line-aligned state type",
        ),
        (r"kBboReconstructionSourceUnset\s*\{\s*0u\s*\}", "source unset value 0"),
        (
            r"kBboReconstructionSourceBookTicker\s*\{\s*1u\s*\}",
            "source bookTicker value 1",
        ),
        (r"kBboReconstructionSourceTrade\s*\{\s*2u\s*\}", "source trade value 2"),
        (r"kBboReconstructionFlagFalse\s*\{\s*0u\s*\}", "flag false value 0"),
        (r"kBboReconstructionFlagTrue\s*\{\s*1u\s*\}", "flag true value 1"),
        (
            r"validCompleteBookTickerRuntime\s*\(",
            "reuse of canonical complete-bookTicker validation",
        ),
        (r"known initiator", "known-initiator Trade contract"),
        (r"clock domain", "single caller-selected timestamp clock-domain contract"),
    )
    for pattern, description in required_fragments:
        require_pattern(
            CANONICAL_HEADER,
            text,
            pattern,
            description,
            errors,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    ordered_fields = (
        r"BookTicker\s+bookTicker[^;]*;\s*"
        r"TimeNs\s+lastBookTickerTs[^;]*;\s*"
        r"TimeNs\s+lastTradeTs[^;]*;\s*"
        r"Side\s+lastTradeSide[^;]*;\s*"
        r"BboReconstructionSource\s+source[^;]*;\s*"
        r"BboReconstructionFlag\s+valid[^;]*;\s*"
        r"BboReconstructionFlag\s+bidPresent[^;]*;\s*"
        r"BboReconstructionFlag\s+askPresent[^;]*;\s*"
        r"BboReconstructionFlag\s+bidQtyKnown[^;]*;\s*"
        r"BboReconstructionFlag\s+askQtyKnown[^;]*;"
    )
    require_pattern(
        CANONICAL_HEADER,
        text,
        r"struct\s+BboReconstructionView\s*\{\s*" + ordered_fields + r"\s*\};",
        "exact View field order and narrow field types",
        errors,
        flags=re.DOTALL,
    )
    require_pattern(
        CANONICAL_HEADER,
        text,
        r"struct\s+alignas\(rawdata::kCacheLineBytes\)\s+"
        r"BboReconstructionState\s*\{\s*" + ordered_fields +
        r".*?Price\s+tickSize[^;]*;\s*"
        r"BboReconstructionTimestampOrigin\s+bookTickerTimestampOrigin[^;]*;\s*\};",
        "exact State field order and narrow field types",
        errors,
        flags=re.DOTALL,
    )

    for function in PUBLIC_FUNCTIONS:
        require_pattern(
            CANONICAL_HEADER,
            text,
            rf"\b{re.escape(function)}\s*\(",
            f"public API {function}",
            errors,
        )

    layout_patterns = (
        (r"sizeof\(BboReconstructionState\)\s*==\s*128u", "State size 128"),
        (
            r"alignof\(BboReconstructionState\)\s*==\s*"
            r"rawdata::kCacheLineBytes",
            "State cache-line alignment",
        ),
        (r"sizeof\(BboReconstructionView\)\s*==\s*72u", "View size 72"),
        (
            r"is_standard_layout_v<BboReconstructionState>",
            "State standard-layout assertion",
        ),
        (
            r"is_trivially_copyable_v<BboReconstructionState>",
            "State trivially-copyable assertion",
        ),
        (
            r"is_standard_layout_v<BboReconstructionView>",
            "View standard-layout assertion",
        ),
        (
            r"is_trivially_copyable_v<BboReconstructionView>",
            "View trivially-copyable assertion",
        ),
    )
    for pattern, description in layout_patterns:
        require_pattern(
            CANONICAL_HEADER,
            text,
            pattern,
            description,
            errors,
        )

    expected_offsets = (
        ("bookTicker", 0),
        ("lastBookTickerTs", 48),
        ("lastTradeTs", 56),
        ("lastTradeSide", 64),
        ("source", 65),
        ("valid", 66),
        ("bidPresent", 67),
        ("askPresent", 68),
        ("bidQtyKnown", 69),
        ("askQtyKnown", 70),
    )
    for type_name in ("BboReconstructionView", "BboReconstructionState"):
        for field_name, offset in expected_offsets:
            require_pattern(
                CANONICAL_HEADER,
                text,
                rf"offsetof\({type_name},\s*{field_name}\)\s*==\s*{offset}u",
                f"{type_name}.{field_name} offset {offset}",
                errors,
            )

    forbidden = (
        (r"\bhft_trader\b", "runtime dependency in the trading-core owner"),
        (r"\bAlgoFlag\b", "HFT Trader flag type"),
        (r"\bvalidBookTickerPrice\s*\(", "duplicate bookTicker validator"),
        (r"\b(?:double|float)\b", "floating-point state or arithmetic"),
        (r"\bstd::(?:vector|string|deque|list|map|unordered_map)\b", "dynamic storage"),
        (r"\b(?:new|delete|throw)\b", "allocation or exception operation"),
        (r"\bstd::(?:mutex|lock_guard|unique_lock)\b", "locking primitive"),
        (r"\b(?:printf|fprintf|iostream|ostream)\b", "hot-path I/O"),
    )
    for pattern, description in forbidden:
        forbid_pattern(
            CANONICAL_HEADER,
            text,
            pattern,
            description,
            errors,
        )


def check_core_test(text: str, errors: list[str]) -> None:
    require_pattern(
        CORE_TEST,
        text,
        rf"#\s*include\s*[<\"]{re.escape(CANONICAL_INCLUDE)}[>\"]",
        "direct canonical trading-core BBO include",
        errors,
    )

    assertions = (
        (
            r"static_assert\s*\(\s*sizeof\s*\(\s*"
            r"trading_core::BboReconstructionState\s*\)\s*==\s*128[uU]?\s*\)",
            "State size assertion",
        ),
        (
            r"static_assert\s*\(\s*alignof\s*\(\s*"
            r"trading_core::BboReconstructionState\s*\)\s*==\s*"
            r"(?:64[uU]?|rawdata::kCacheLineBytes)\s*\)",
            "State alignment assertion",
        ),
        (
            r"static_assert\s*\(\s*sizeof\s*\(\s*"
            r"trading_core::BboReconstructionView\s*\)\s*==\s*72[uU]?\s*\)",
            "View size assertion",
        ),
        (
            r"static_assert\s*\(\s*std::is_standard_layout_v<\s*"
            r"trading_core::BboReconstructionState\s*>\s*\)",
            "State standard-layout assertion",
        ),
        (
            r"static_assert\s*\(\s*std::is_trivially_copyable_v<\s*"
            r"trading_core::BboReconstructionState\s*>\s*\)",
            "State trivially-copyable assertion",
        ),
        (
            r"static_assert\s*\(\s*std::is_standard_layout_v<\s*"
            r"trading_core::BboReconstructionView\s*>\s*\)",
            "View standard-layout assertion",
        ),
        (
            r"static_assert\s*\(\s*std::is_trivially_copyable_v<\s*"
            r"trading_core::BboReconstructionView\s*>\s*\)",
            "View trivially-copyable assertion",
        ),
    )
    for pattern, description in assertions:
        require_pattern(CORE_TEST, text, pattern, description, errors)

    for function in PUBLIC_FUNCTIONS:
        require_pattern(
            CORE_TEST,
            text,
            rf"\btrading_core::{re.escape(function)}\s*\(",
            f"direct API exercise of {function}",
            errors,
        )


def check_core_test_cmake(text: str, errors: list[str]) -> None:
    patterns = (
        (
            r"trading_core_add_contract_test\(\s*trading-core-bbo-reconstruction-tests\s+"
            r"trading_core::algorithm\s+Ported/Market/BboReconstructionTests\.cpp\s*\)",
            "trading-core contract test registration",
        ),
    )
    for pattern, description in patterns:
        require_pattern(
            CORE_TEST_CMAKE,
            text,
            pattern,
            description,
            errors,
            flags=re.MULTILINE,
        )


def check_app_sources(errors: list[str]) -> None:
    old_include_pattern = re.compile(
        r"#\s*include\s*[<\"]hft_trader/core/market/"
        r"BboReconstruction\.hpp[>\"]"
    )
    canonical_include_pattern = re.compile(
        rf"#\s*include\s*[<\"]{re.escape(CANONICAL_INCLUDE)}[>\"]"
    )
    old_cxet_include_pattern = re.compile(
        r"#\s*include\s*[<\"]cxet/Primitives/Composite/BboReconstruction\.hpp[>\"]"
    )
    alias_patterns = (
        re.compile(
            r"\busing\s+(?:BboReconstruction(?:Source|Flag|View|State)\s*=|"
            r"trading_core::(?:BboReconstruction\w+|kBboReconstruction\w+|"
            r"resetBboReconstruction|bboReconstructionView|"
            r"validBboReconstruction|bboReconstructionTimestampRollback|"
            r"applyBboReconstruction\w+))"
        ),
        re.compile(
            r"\bnamespace\s+\w+\s*=\s*cxet::composite\s*;"
        ),
        re.compile(
            r"\btypedef\s+trading_core::BboReconstruction"
            r"(?:Source|Flag|View|State)\s+"
            r"BboReconstruction(?:Source|Flag|View|State)\s*;"
        ),
        re.compile(
            r"#\s*define\s+(?:BboReconstruction\w+|kBboReconstruction\w+)\s+"
            r"trading_core::"
        ),
    )
    declaration_pattern = re.compile(
        r"\b(?:struct|class|using)\s+"
        r"BboReconstruction(?:Source|Flag|View|State)\b"
    )
    hft_owner_pattern = re.compile(
        r"\bhft_trader::core::(?:"
        + "|".join(re.escape(symbol) for symbol in BBO_SYMBOLS)
        + r")\b"
    )
    forwarding_function_patterns = (
        re.compile(
            r"\b(?:auto|trading_core::BboReconstructionView)\s+"
            r"(?:(?:hft_trader::)?core::)?reconstructedBbo\s*\("
        ),
        re.compile(
            r"\b(?:auto|bool|void)\s+"
            r"(?:(?:hft_trader::)?core::)?"
            r"(?:applyBookTicker|applyBookTickerSide|applyTrade)\s*\(\s*"
            r"(?:const\s+)?trading_core::BboReconstructionState\b"
        ),
    )

    all_app_sources = source_files(Path("apps"))
    texts: dict[Path, str] = {}
    for path in all_app_sources:
        text = read_source(path, errors)
        if text:
            texts[path] = text

    for path, text in texts.items():
        if path == ROOT / CANONICAL_HEADER:
            continue
        relative = path.relative_to(ROOT)
        code = strip_cpp_comments(text)
        stale_include = old_cxet_include_pattern.search(code)
        if stale_include is not None:
            errors.append(
                f"{relative.as_posix()}:{line_number(code, stale_include.start())}: "
                "forbidden include of the removed CXET BBO owner"
            )
        old_include = old_include_pattern.search(code)
        if old_include is not None:
            errors.append(
                f"{relative.as_posix()}:{line_number(code, old_include.start())}: "
                "forbidden include of the removed HFT Trader BBO owner"
            )

        for alias_pattern in alias_patterns:
            alias = alias_pattern.search(code)
            if alias is not None:
                errors.append(
                    f"{relative.as_posix()}:{line_number(code, alias.start())}: "
                    "forbidden BBO forwarding/compatibility alias"
                )

        for forwarding_pattern in forwarding_function_patterns:
            forwarding = forwarding_pattern.search(code)
            if forwarding is None:
                continue
            errors.append(
                f"{relative.as_posix()}:{line_number(code, forwarding.start())}: "
                "forbidden BBO forwarding/compatibility function"
            )

        declaration = declaration_pattern.search(code)
        if declaration is not None:
            errors.append(
                f"{relative.as_posix()}:{line_number(code, declaration.start())}: "
                "BBO production type is declared outside the canonical trading-core owner"
            )

        hft_owner = hft_owner_pattern.search(code)
        if hft_owner is not None:
            errors.append(
                f"{relative.as_posix()}:{line_number(code, hft_owner.start())}: "
                "BBO production symbol remains qualified by hft_trader::core"
            )

        for helper in FORBIDDEN_APP_BBO_HELPERS:
            duplicate = re.search(rf"\b{re.escape(helper)}\b", code)
            if duplicate is None:
                continue
            errors.append(
                f"{relative.as_posix()}:{line_number(code, duplicate.start())}: "
                f"forbidden app-owned BBO helper {helper}"
            )

        for symbol in BBO_SYMBOLS:
            for match in re.finditer(rf"\b{re.escape(symbol)}\b", code):
                prefix_start = match.start() - len("trading_core::")
                canonical = (
                    prefix_start >= 0
                    and code[prefix_start : match.start()] == "trading_core::"
                )
                if canonical:
                    continue
                errors.append(
                    f"{relative.as_posix()}:{line_number(code, match.start())}: "
                    f"BBO symbol {symbol} must reference trading_core directly"
                )
                break

    for product, relative_root in PRODUCT_ROOTS.items():
        production_include_found = False
        production_owner_reference_found = False
        for path, text in texts.items():
            try:
                local = path.relative_to(ROOT / relative_root)
            except ValueError:
                continue
            if any(
                part.lower() in NON_PRODUCTION_DIRECTORY_NAMES
                for part in local.parts[:-1]
            ):
                continue
            code = strip_cpp_comments(text)
            if canonical_include_pattern.search(code) is not None:
                production_include_found = True
            if re.search(r"\btrading_core::BboReconstructionState\b", code):
                production_owner_reference_found = True

        if not production_include_found:
            errors.append(
                f"{relative_root.as_posix()}: {product} production sources do not "
                f"include {CANONICAL_INCLUDE}"
            )
        if not production_owner_reference_found:
            errors.append(
                f"{relative_root.as_posix()}: {product} production sources do not "
                "reference trading_core::BboReconstructionState"
            )


def main() -> int:
    errors: list[str] = []

    if (ROOT / OLD_HFT_TRADER_HEADER).exists():
        errors.append(
            f"forbidden old owner still exists: {OLD_HFT_TRADER_HEADER.as_posix()}"
        )
    if (ROOT / OLD_CXET_HEADER).exists():
        errors.append(
            f"forbidden old owner still exists: {OLD_CXET_HEADER.as_posix()}"
        )

    header = read_required(CANONICAL_HEADER, errors)
    core_test = read_required(CORE_TEST, errors)
    core_test_cmake = read_required(CORE_TEST_CMAKE, errors)

    if header:
        check_canonical_header(header, errors)
    if core_test:
        check_core_test(core_test, errors)
    if core_test_cmake:
        check_core_test_cmake(core_test_cmake, errors)

    check_app_sources(errors)

    if errors:
        print("trading-core BBO ownership check: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "trading-core BBO ownership check: PASS "
        "(one trading-core owner; Trader/Backtest consumers)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
