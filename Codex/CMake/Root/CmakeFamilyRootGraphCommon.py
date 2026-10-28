"""Private common responsibilities of the family root checker."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from CMake.Syntax.CmakeFamilyLexer import (
    cmake_argument_value,
    scan_commands,
    strip_cmake_comments,
    words,
)
from CMake.Flow.CmakeFamilyExecutionIdentity import unsymlinked_regular_path
from Family.Sources.CxetFamilySourcePaths import source_artifact_path

ROOT = Path(__file__).resolve().parents[4]

ROOT_CMAKE = "CMakeLists.txt"

ROOT_COMPILE = "compile.sh"

FAMILY_DIRS = (
    "apps/hft-parser",
    "apps/trading-core",
    "apps/hft-compressor",
    "apps/hft-recorder/src/Contracts",
    "apps/hft-backtest",
    "apps/trader",
    "apps/vetron",
    "apps/diagnostic",
)

FULL_ONLY_FAMILY_DIRS = frozenset({
    "apps/hft-compressor", "apps/hft-recorder/src/Contracts",
    "apps/hft-backtest", "apps/diagnostic",
})

APP_CONTRACTS = {
    "apps/diagnostic/CMakeLists.txt": (
        "cxet::cxet_lib", "cxet::read_only_contracts", "capital::finance",
    ),
    "apps/hft-parser/CMakeLists.txt": (
        "cxet::cxet_lib",
        "cxet::read_only_contracts",
        "liburing::uring",
        "absl::flat_hash_set",
    ),
    "apps/trading-core/CMakeLists.txt": (
        "cxet::read_only_contracts",
    ),
    "apps/hft-backtest/CMakeLists.txt": (
        "cxet::cxet_lib",
        "capital::finance",
        "trading_core::algorithm",
        "trading_core::execution",
        "trading_core_math",
        "trading_core::strategy",
        "hftrec::corpus_contract",
        "absl::flat_hash_map",
        "absl::inlined_vector",
    ),
    "apps/trader/CMakeLists.txt": (
        "cxet::read_only_contracts",
        "hftp_trading_runtime",
        "hft_parser::reference_client",
        "hft_parser::session_client",
        "trading_core_math",
        "trading_core::strategy",
    ),
    "apps/vetron/CMakeLists.txt": (
        "cxet::read_only_contracts",
        "hft_parser_projection_client",
        "hft_parser::projection_client",
        "hft_parser_history_client",
        "hft_parser::history_client",
        "hft_parser::market_demand_client",
        "trader_market_observe_projection_client",
        "trader::market_observe_projection_client",
        "trader_control_client",
        "trader::control_client",
        "hft-parserd",
        "hft-algosd",
        "hft-resource-planner",
        "trader-market-observe-product",
    ),
}

PROVIDER_ONLY_CONTRACTS = {}

FULL_ONLY_FAMILY_PROVIDERS = (
    "hft_backtest::core",
    "hftrec::corpus_contract",
)

CANONICAL_ALIASES = {
    "apps/diagnostic/CMakeLists.txt": (
        ("diagnostic::runtime", "diagnostic_runtime"),
    ),
    "src/src/CMakeLists.txt": (
        ("cxet::cxet_lib", "cxet_lib"),
        ("cxet::read_only_contracts", "cxet_read_only_contracts"),
    ),
    "apps/hft-parser/cmake/HftpLibraries.cmake": (
        ("hft_parser::projection_client", "hft_parser_projection_client"),
        ("hft_parser::reference_client", "hft_parser_reference_client"),
        ("hft_parser::history_client", "hft_parser_history_client"),
        ("hft_parser::market_demand_client", "hftp_market_demand_client"),
        ("hft_parser::session_client", "hft_parser_session_client"),
    ),
    "apps/trading-core/CMakeLists.txt": (
        ("trading_core::contracts", "trading_core_contracts"),
        ("trading_core::algorithm", "trading_core_algorithm"),
        ("trading_core::strategy", "trading_core_strategy"),
        ("trading_core::execution", "trading_core_execution"),
        ("trading_core::cold_ids", "trading_core_cold_ids"),
    ),
    "apps/trading-core/capital/CMakeLists.txt": (
        ("capital::finance", "capital_finance"),
        ("capital::planning", "capital_planning"),
    ),
    "apps/hft-backtest/CMakeLists.txt": (
        ("hft_backtest::core", "hft_backtest_core"),
    ),
    "apps/trader/CMakeLists.txt": (
        ("trader::projection_client", "trader_projection_client"),
        ("trader::market_observe_projection_client",
         "trader_market_observe_projection_client"),
        ("trader::control_client", "trader_control_client"),
        ("trader::live_runtime", "trader_live_runtime"),
    ),
    "apps/vetron/CMakeLists.txt": (
        ("vetron::browser_contracts", "vetron_browser_contracts"),
        ("vetron::read_gateway", "vetron_read_gateway"),
        ("vetron::read_runtime", "vetron_read_runtime"),
        ("vetron::read_process", "vetron_read_process"),
        ("vetron::read_source_boundary", "vetron_read_source_boundary"),
        ("vetron::full_control", "vetron_full_control"),
        ("vetron::full_process", "vetron_full_process"),
        ("vetron::full_source_boundary", "vetron_full_source_boundary"),
    ),
    "apps/hft-recorder/src/Contracts/CMakeLists.txt": (
        ("hftrec::corpus_contract", "hftrec_corpus_contract"),
    ),
}


@dataclass(frozen=True)
class Command:
    name: str
    body: str
    line: int
    offset: int

@dataclass(frozen=True)
class TestRegistration:
    command: tuple[str, ...]
    scope: tuple[str, ...]

def read_required(relative: str, errors: list[str]) -> str:
    path = ROOT / relative
    if not unsymlinked_regular_path(path):
        errors.append(
            f"required file is missing, nonregular, or symlinked: {relative}")
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {relative}: {exc}")
        return ""
    if not text.strip():
        errors.append(f"required file is empty: {relative}")
    return text

def parse_commands(relative: str, text: str, errors: list[str]) -> list[Command]:
    return scan_commands(
        relative,
        text,
        errors,
        lambda name, body, line, offset: Command(
            name, body, line, offset),
    )

def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] == '"':
        return value[1:-1]
    return value

def compact(value: str) -> str:
    return re.sub(r"\s+", "", strip_cmake_comments(value)).upper()

def generated_path(parts: tuple[str, ...]) -> bool:
    """Classify a path already expressed relative to its scanned owner."""
    if not parts:
        return False
    if parts[0].casefold() in {"extra", "external", "third_party", "vendor"}:
        return True
    return source_artifact_path(PurePosixPath(*parts).as_posix(), ())

def validate_generated_path_microcases(errors: list[str]) -> None:
    cases = (
        (("build", "CMakeLists.txt"), True),
        (("api", "build", "CMakeLists.txt"), False),
        (("frontend", "dist", "asset.cmake"), True),
        (("api", "CMakeFiles", "generated.cmake"), True),
        (("vendor", "package.cmake"), True),
    )
    for parts, expected in cases:
        if generated_path(parts) != expected:
            errors.append(
                "owner-relative fallback artifact classifier self-check "
                "failed: " + PurePosixPath(*parts).as_posix())
