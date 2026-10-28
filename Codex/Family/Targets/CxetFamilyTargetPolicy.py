"""Cross-target ownership policy for the composed CXET family graph."""

from __future__ import annotations

from Family.Sources.CxetFamilySourcePolicy import (
    NATIVE_CRYPTO_VENDOR_SOURCES, NATIVE_CRYPTO_VENDOR_INCLUDES, native_crypto_owner,
    native_crypto_definition_error,
)

import os
from pathlib import Path, PurePosixPath

from CMake.Syntax.CmakeFamilyContext import exact_context, first_if
from CMake.Flow.CmakeFamilyFlow import paths_cover
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words, words
from CMake.Flow.CmakeFamilyState import normalize_synthetic_binary_path
from Family.Targets.CxetFamilyBuildPolicy import (
    approved_cxet_include, BENCHMARK_INCLUDE_CONTRACTS,
    benchmark_instance_context, exact_offline_include_roots,
    OFFLINE_LIBURING_INCLUDE, offline_liburing_include_context,
)
from Family.Sources.CxetFamilyCppPolicy import (
    CPP_ASSEMBLY_SUFFIXES as _CPP_ASSEMBLY_SUFFIXES,
    CPP_NON_TEXTUAL_INCLUDE_SUFFIXES as _CPP_NON_TEXTUAL_INCLUDE_SUFFIXES,
)
from Family.Sources.CxetFamilyCppMicrocases import validate_cpp_syntax_microcases
from Family.Targets.CxetFamilyCompileDefinitionPolicy import dangerous_compile_definition
from Family.Sources.CxetFamilySourcePaths import source_artifact_path as _source_artifact_path
from Family.Targets.CxetFamilyTargetPropertyPolicy import evaluate_target_property_effect
from Family.Targets.CxetFamilyCompressionPolicy import compression_include_provider
from Family.Verification.CxetFamilyVerificationInventory import (
    VERIFICATION_UNRESOLVED_DORMANT_ONLY as
        _VERIFICATION_UNRESOLVED_DORMANT_ONLY,
    VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS as
        _VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS,
    VERIFICATION_UNRESOLVED_GENERATED_ROOTS as
        _VERIFICATION_UNRESOLVED_GENERATED_ROOTS,
    VERIFICATION_UNRESOLVED_QUOTED_INCLUDES as
        _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES,
)


ROOT = Path(__file__).resolve().parents[4]
_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")

_PARSER_CXET_INCLUDE_TARGETS = frozenset({
    "hft-algosd",
    "hftp_algos_public_runtime_objects",
    "hftp_algos_runtime",
    "hftp_ipc",
    "hftp_reference_ipc",
    "hftp_trading_runtime",
    "hftp_market_state",
    "hftp_parserd_runtime",
    "hftp_runtime_common",
    "hftp_reference",
    "hft-parser-depth-source-reconciler-contract-tests",
    "hft-parser-moex-basis-reference-contract-tests",
    "hft-parser-public-market-capacity-contract-tests",
    "hft-parser-public-market-registry-contract-tests",
    "hft-parser-public-market-shard-planner-contract-tests",
    "hft-parser-spot-capability-bootstrap-contract-tests",
    "hft-parser-transport-runtime-contract-tests",
})

_VERIFICATION_ADAPTERS = frozenset({
    "apps/trader/tests/FamilyVerification/StrategyCycleAdapter.cpp",
    "apps/hft-backtest/tests/FamilyVerification/StrategyCycleAdapter.cpp",
})

_PARSER_PROCESS_CONTEXT = (
    first_if(
        "apps/hft-parser/cmake/HftpProcesses.cmake", 3,
        ("HFT_PARSER_BUILD_PROCESSES",)),
)

_VERIFICATION_SOURCE_ROOTS = (
    "apps/diagnostic",
    "src/src/Core",
    "src/src/Contracts",
    "src/src",
    "src/tests",
    "src/benchmarks",
    "src/java",
    "apps/hft-parser",
    "apps/trading-core",
    "apps/hft-compressor",
    "apps/hft-recorder/src/Contracts",
    "apps/hft-recorder/src/Runtime",
    "apps/hft-recorder/src/Lab/src",
    "apps/hft-recorder/src/Process/src",
    "apps/hft-recorder/tests/offline",
    "apps/hft-recorder/src/Runtime/src/Capture",
    "apps/hft-recorder/src/Runtime/src/Corpus/Codec",
    "apps/hft-recorder/src/Runtime/src/Common",
    "apps/hft-recorder/src/Runtime/src/Corpus",
    "apps/hft-recorder/src/Runtime/src/Replay",
    "apps/hft-backtest",
    "apps/trader",
    "apps/vetron",
)
_TARGET_SOURCE_AUTHORITY_ROOTS = {
    "cxet_read_only_contracts": "src/src/Contracts",
    "cxet_market_ingress_bench_support": "src/benchmarks/MarketIngress",
    "cxet_market_ingress_peer": "src/benchmarks/MarketIngress",
}
_RECORDER_LOGICAL_OWNER = "apps/hft-recorder/src/Contracts"
_VERIFICATION_OWNER_ALIASES = {
    root: _RECORDER_LOGICAL_OWNER
    for root in _VERIFICATION_SOURCE_ROOTS
    if root.startswith("apps/hft-recorder/")
}
_VERIFICATION_OWNER_ALIASES.update({
    "src/src/Core": "src/src",
    "src/src/Contracts": "src/src",
    "src/tests": "src/src",
    "src/benchmarks": "src/src",
    "src/java": "src/src",
})
_VERIFICATION_OPTIONAL_SOURCE_ROOTS = frozenset({"src/java"})
_VERIFICATION_RECORDER_FILES = frozenset({
    "apps/hft-recorder/src/Runtime/src/Capture/Session/SessionManifest.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Session/SessionManifest.hpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Session/ChannelKind.hpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Codec/Crc32c.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Codec/Crc32c.hpp",
    "apps/hft-recorder/src/Runtime/src/Common/JsonString.hpp",
    "apps/hft-recorder/src/Runtime/src/Common/MiniJsonParser.hpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusReader.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusReader.hpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusWriter.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusWriter.hpp",
    "apps/hft-recorder/src/Runtime/src/Replay/JsonLineParser.cpp",
    "apps/hft-recorder/src/Runtime/src/Replay/JsonLineParser.hpp",
    "apps/hft-recorder/src/Contracts/include/hftrec/Status.hpp",
})
_VERIFICATION_GENERATED_ROOTS = frozenset({
    "apps/hft-parser/build",
    "apps/hft-parser/build-cxet-runtime",
    "apps/hft-backtest/build",
    "apps/trading-core/build",
    "apps/trader/build",
    "apps/vetron/build",
    "apps/vetron/frontend/dist",
    "src/benchmarks/MarketIngress/build",
    "src/tests/Family/build",
})
_GENERATED_INCLUDE_PARTS = frozenset({
    ".git", "cmakefiles", "_deps", "generated", "node_modules",
})
_VERIFICATION_PUBLIC_INCLUDE_ROOTS = {
    "apps/diagnostic": ("apps/diagnostic/include",),
    "src/src": (
        "src/src/Core/include",
        "src/src/Contracts/include",
    ),
    "apps/hft-parser": (
        "apps/hft-parser/src/Clients/include",
        "apps/hft-parser/src/Contracts/include",
    ),
    "apps/trading-core": (
        "apps/trading-core/src/Core/include", "apps/trading-core",
        "apps/trading-core/capital/include"),
    "apps/hft-recorder/src/Contracts": (
        "apps/hft-recorder/src/Contracts/include",
        "apps/hft-recorder/src/Runtime/include"),
    "apps/hft-compressor": ("apps/hft-compressor/src/Api/include",),
    "apps/hft-backtest": ("apps/hft-backtest/src/Runtime/include",),
    "apps/trader": (
        "apps/trader/alerts/include",
        "apps/trader/src/Contracts/include",
        "apps/trader/src/Contracts/Order/include",
        "apps/trader/src/Contracts/Control/include",
        "apps/trader/src/Contracts/Projection/include",
        "apps/trader/src/Order/include",
        "apps/trader/src/Control/include",
        "apps/trader/src/Projection/include",
        "apps/trader/src/Market/include",
        "apps/trader/src/Runtime/include",
        "apps/trader/src/Process/include",
    ),
    "apps/vetron": (
        "apps/vetron/src/Contracts/include",
        "apps/vetron/src/Gateway/include",
        "apps/vetron/src/Runtime/include",
        "apps/vetron/src/Process/include",
    ),
}
_VERIFICATION_PRIVATE_INCLUDE_ROOTS = {
    "src/src": (
        "src/src/Core/src",
        "src/src/Core/src/Private",
    ),
    _RECORDER_LOGICAL_OWNER: ("apps/hft-recorder/src/Runtime/src",),
    "apps/hft-compressor": ("apps/hft-compressor/src/Runtime/src",),
    "apps/hft-parser": (
        "apps/hft-parser/src/Runtime/src",
        "apps/hft-parser/src/Runtime/src/Market/Ingestion",
        "apps/hft-parser/src/Runtime/src/History",
        "apps/hft-parser/src/Process/src/Bootstrap",
        "apps/hft-parser/benchmarks/include",
    ),
    "apps/trader": (
        "apps/trader/src/Transport/src/LocalIpc",
        "apps/trader/src/Order/src/Bootstrap",
        "apps/trader/tests/Support/AccountFixture",
        "apps/trader/src/Projection/src/Transport",
        "apps/trader/src/Projection/src/Publisher",
        "apps/trader/src/Process/src/MarketObserve",
        "apps/trader/src/Process/src/Account",
        "apps/trader/src/Process/src/Traderd",
        "apps/trader/src/Market/src",
    ),
}
_VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS = {
    "apps/diagnostic": frozenset({"apps/diagnostic/include"}),
    "src/src": frozenset({
        "src/src/Core/include",
        "src/src/Contracts/include",
    }),
    "src/tests": frozenset({
        "src/src/Core/include",
        "src/src/Contracts/include",
        "src/tests",
    }),
    "apps/hft-parser": frozenset({
        "apps/hft-parser/src/Runtime/include",
        "apps/hft-parser/src/Process/include",
        "apps/hft-parser/src/Clients/include",
        "apps/hft-parser/src/Contracts/include",
    }),
    "apps/trading-core": frozenset({
        "apps/trading-core/src/Core/include",
        "apps/trading-core/src/Cold/include", "apps/trading-core/src/Strategy/include",
        "apps/trading-core/capital/include",
    }),
    "apps/hft-recorder": frozenset({
        "apps/hft-recorder/src/Contracts/include",
        "apps/hft-recorder/src/Runtime/include",
    }),
    "apps/hft-compressor": frozenset({"apps/hft-compressor/src/Api/include"}),
    "apps/hft-backtest": frozenset({
        "apps/hft-backtest/src/Runtime/include",
    }),
    "apps/trader": frozenset({
        "apps/trader/alerts/include",
        "apps/trader/src/Contracts/include",
        "apps/trader/src/Contracts/Order/include",
        "apps/trader/src/Contracts/Control/include",
        "apps/trader/src/Contracts/Projection/include",
        "apps/trader/src/Order/include",
        "apps/trader/src/Control/include",
        "apps/trader/src/Projection/include",
        "apps/trader/src/Market/include",
        "apps/trader/src/Runtime/include",
        "apps/trader/src/Process/include",
    }),
    "apps/vetron": frozenset({
        "apps/vetron/src/Contracts/include",
        "apps/vetron/src/Gateway/include",
        "apps/vetron/src/Runtime/include",
        "apps/vetron/src/Process/include",
    }),
    "src/benchmarks": frozenset(),
}
_VERIFICATION_TARGET_PRIVATE_INCLUDE_ROOTS = {
    "trader-execution-adapter-tests": frozenset({"apps/trading-core/tests/offline/Support"}),
    "trader_order_bootstrap_server": frozenset({"apps/trader/src/Order/src/Bootstrap"}),
    "trader_projection_server_transport": frozenset({
        "apps/trader/src/Projection/include", "apps/trader/src/Projection/src/Publisher"}),
    "trader_market_observe_process": frozenset({"apps/trader/src/Process/src/MarketObserve"}),
    "trader_accountd_process": frozenset({"apps/trader/src/Process/src/Account"}),
    "trader_traderd_process": frozenset({
        "apps/trader/src/Process/src/Traderd", "apps/hft-parser/src/Runtime/include"}),

    "cxet_lib": frozenset({
        "src/src/Core/src",
        "src/src/Core/src/Private",
    }),
    "hftp_public_market": frozenset({"apps/hft-parser/src/Runtime/src"}),
    "hftp_reference_storage": frozenset({"apps/hft-parser/src/Runtime/src/History"}),
    "hftp_history": frozenset({"apps/hft-parser/src/Runtime/src/History"}),
    "hftp_history_service": frozenset({"apps/hft-parser/src/Runtime/src/History"}),
    "hftp_runtime_common": frozenset({
        "apps/hft-parser/src/Process/src/Bootstrap", "src/src"}),
    "hftp_parserd_runtime": frozenset({
        "apps/hft-parser/src/Process/src/Bootstrap", "src/src"}),
    "hftp_trading_runtime": frozenset({
        "apps/hft-parser/src/Process/src/Bootstrap", "src/src"}),
    "hft-parser-relative-difference-volatility-contract-tests": frozenset({
        "apps/hft-parser/src/Runtime/src"}),
    "local_symbol_tests": frozenset({"src/src/Core/src"}),
    "hft-parser-public-market-shard-planner-contract-tests": frozenset({
        "apps/hft-parser/src/Runtime/src/Market/Ingestion", "src/src"}),
    "hftrec_corpus_contract": frozenset({
        "apps/hft-recorder/src/Runtime/src"}),
    "hftrec_capture_launch": frozenset({
        "apps/hft-recorder/src/Contracts/include", "apps/hft-recorder/src/Runtime/src"}),
    "hftrec_capture_client": frozenset({"apps/hft-recorder/src/Runtime/src"}),
    "hftrec_core": frozenset({"apps/hft-recorder/src/Runtime/src"}),
    "hftrec_json_capture": frozenset({"apps/hft-recorder/src/Runtime/src"}),
    "hft_compressor_core": frozenset({"apps/hft-compressor/src/Runtime/src"}),
    "hft_backtest_core": frozenset({"apps/hft-backtest/src/Runtime/src"}),
    "trader_private_ipc": frozenset({"apps/trader/src/Transport/src/LocalIpc"}),
    "trader_private_publisher": frozenset({"apps/trader/src/private"}),
    "trader_account_fixture": frozenset({"apps/trader/tests/Support/AccountFixture"}),
    "trader_projection_transport_io": frozenset({
        "apps/trader/src/Projection/src/Transport"}),
    "trader_projection_server": frozenset({
        "apps/trader/src/Projection/src/Publisher"}),
}
_VERIFICATION_INCLUDE_DEPENDENCIES = {
    "apps/diagnostic": frozenset({"src/src", "apps/trading-core"}),
    "src/src": frozenset(),
    "apps/hft-parser": frozenset({"src/src"}),
    "apps/trading-core": frozenset({"src/src"}),
    "apps/hft-recorder/src/Contracts": frozenset({
        "src/src", "apps/hft-compressor", "apps/hft-parser"}),
    "apps/hft-compressor": frozenset(),
    "apps/hft-backtest": frozenset({
        "src/src", "apps/trading-core",
        "apps/hft-recorder/src/Contracts",
    }),
    "apps/trader": frozenset({
        "src/src", "apps/hft-parser", "apps/trading-core",
    }),
    "apps/vetron": frozenset({
        "src/src", "apps/hft-parser", "apps/trader", "apps/trading-core",
    }),
}
_VERIFICATION_SPECIAL_INCLUDE_ROOTS = {
}
_VERIFICATION_SOURCE_INCLUDE_DEPENDENCIES = {
    "apps/hft-parser/benchmarks/src/IngressBench.cpp": frozenset({
        "src/benchmarks/MarketIngress"}),
    "apps/hft-parser/benchmarks/src/TransportIngressBench.cpp": frozenset({
        "src/benchmarks/MarketIngress"}),
    "src/benchmarks/MarketIngressRps/CxetIngressHarness.cpp": frozenset({
        "src/benchmarks/MarketIngress"}),
    "src/benchmarks/MarketIngressRps/BenchmarkRunner.cpp": frozenset({
        "src/benchmarks/MarketIngress"}),
}
_VERIFICATION_SOURCE_CANDIDATE_ROOTS = {
    "apps/hft-parser/src/Runtime/src/Market/Registry": (
        "apps/hft-parser/src/Runtime/src",),
    "apps/hft-parser/src/Runtime/src/History": (
        "apps/hft-parser/src/Runtime/src/History",),
    'apps/hft-parser/tests/Parser/RelativeDifferenceVolatilityContractTests.cpp': (
        "apps/hft-parser/src/Runtime/src",),
    'apps/hft-parser/tests/Parser/PublicMarketShardPlannerContractTests.cpp': (
        "apps/hft-parser/src/Runtime/src/Market/Ingestion",),
    "apps/hft-recorder/src/Contracts": (
        "apps/hft-recorder/src/Runtime/src",),
    "apps/hft-recorder/src/Runtime": ("apps/hft-recorder/src/Runtime/src",),
    "apps/hft-backtest": ("apps/hft-backtest/src/Runtime/src",),
    "apps/trader/src/Transport/src": ("apps/trader/src/Transport/src/LocalIpc",),
    "apps/trader/src/Process/src/Traderd": (
        "apps/trader/src/Process/src/Traderd",),
    "apps/trader/src/Process": ("apps/trader/src/Process/include",),
    "src/benchmarks/MarketIngressRps": (
        "src/benchmarks/MarketIngressRps",),
    "src/benchmarks/PrimitivesParse": (
        "src/benchmarks/PrimitivesParse",),
    "src/benchmarks/Sort": ("src/benchmarks/Sort",),
    "src/tests/Sort": ("src/benchmarks/Sort",),
    "src/java": ("src/java/include",),
}
def _verification_source_root(path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return None
    matches = [
        root for root in _VERIFICATION_SOURCE_ROOTS
        if relative == root or relative.startswith(root + "/")
    ]
    if not matches:
        return None
    physical = max(matches, key=len)
    return _VERIFICATION_OWNER_ALIASES.get(physical, physical)


def _unsymlinked_repo_path(path: Path) -> bool:
    """Require every lexical path component to remain inside the repo."""
    try:
        relative = path.relative_to(ROOT)
        root_resolved = ROOT.resolve(strict=True)
    except (OSError, ValueError):
        return False
    current = ROOT
    try:
        if current.is_symlink() or not current.is_dir():
            return False
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        current.resolve(strict=True).relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return True


def _verification_relative_owner(relative: str) -> str | None:
    matches = [
        root for root in _VERIFICATION_SOURCE_ROOTS
        if relative == root or relative.startswith(root + "/")
    ]
    if not matches:
        return None
    physical = max(matches, key=len)
    return _VERIFICATION_OWNER_ALIASES.get(physical, physical)


def _verification_physical_root(relative: str) -> str | None:
    matches = [
        root for root in _VERIFICATION_SOURCE_ROOTS
        if relative == root or relative.startswith(root + "/")
    ]
    return max(matches, key=len) if matches else None


def _core_alias_direction_allowed(
    source_relative: str,
    target_relative: str,
) -> bool:
    """Keep implementation/contracts/satellite aliases directional."""
    source = _verification_physical_root(source_relative)
    target = _verification_physical_root(target_relative)
    satellites = frozenset({"src/tests", "src/benchmarks", "src/java"})
    core = frozenset({"src/src/Core", "src/src/Contracts"})
    if source not in satellites | core or target not in satellites | core:
        return True
    if source == target:
        return True
    if source in satellites and target in core:
        return True
    if source == "src/src/Core" and target == "src/src/Contracts":
        return True
    return (
        source_relative.startswith("src/tests/Sort/") and
        target_relative.startswith("src/benchmarks/Sort/")
    )


def _reviewed_recorder_source(relative: str) -> bool:
    return (
        relative == "apps/hft-recorder/src/Contracts" or
        relative == "apps/hft-recorder/tests/offline/Corpus/CorpusCases.cpp" or
        relative.startswith("apps/hft-recorder/src/Contracts/") or
        relative.startswith(
            "apps/hft-recorder/src/Contracts/include/hftrec/") or
        relative in _VERIFICATION_RECORDER_FILES
    )


def _exported_include_allowed(
    source_owner: str,
    source_relative: str,
    relative: str,
) -> bool:
    target_owner = _verification_relative_owner(relative)
    if target_owner is None:
        return False
    if (target_owner == _RECORDER_LOGICAL_OWNER and
            source_owner != _RECORDER_LOGICAL_OWNER and
            not _reviewed_recorder_source(relative)):
        return False
    if not _core_alias_direction_allowed(source_relative, relative):
        return False
    if target_owner == source_owner:
        return True
    if target_owner in _VERIFICATION_SOURCE_INCLUDE_DEPENDENCIES.get(
            source_relative, frozenset()):
        return any(
            relative == root or relative.startswith(root + "/")
            for root in _VERIFICATION_PUBLIC_INCLUDE_ROOTS[target_owner])
    if target_owner not in _VERIFICATION_INCLUDE_DEPENDENCIES[source_owner]:
        return False
    roots = list(_VERIFICATION_PUBLIC_INCLUDE_ROOTS[target_owner])
    roots.extend(
        _VERIFICATION_SPECIAL_INCLUDE_ROOTS.get(source_owner, {}).get(
            target_owner, ()))
    return any(
        relative == root or relative.startswith(root + "/")
        for root in roots)


def _generated_verification_path(relative: str) -> bool:
    return _source_artifact_path(
        relative,
        _VERIFICATION_SOURCE_ROOTS,
        exact_generated_roots=_VERIFICATION_GENERATED_ROOTS,
    )


def _include_path_syntax_error(include: str, *, quoted: bool) -> str | None:
    if "\\" in include:
        return f"include path uses unsupported escape: {include}"
    normalized = include
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or (not quoted and ".." in pure.parts):
        return f"include path escapes its declared include root: {include}"
    folded = tuple(part.casefold() for part in pure.parts)
    if (any(part in _GENERATED_INCLUDE_PARTS for part in folded) or
            folded and (
                folded[0] == "build" or
                folded[0].startswith("build-") or
                folded[0].startswith("cmake-build-")) or
            any(folded[index:index + 2] == ("frontend", "dist")
                for index in range(max(0, len(folded) - 1)))):
        return f"include path enters generated tree: {include}"
    if pure.suffix.lower() in _CPP_NON_TEXTUAL_INCLUDE_SUFFIXES:
        return f"textual include of compiled source is forbidden: {include}"
    return None


def _validate_cpp_include_microcases(errors: list[str]) -> None:
    validate_cpp_syntax_microcases(errors)
    artifact_cases = {
        "src/src/build/x.hpp": True,
        "src/src/Core/src/api/build/x.hpp": False,
        "apps/hft-parser/dev-state/runtime.cpp": True,
        "apps/hft-parser/dev-stateful/runtime.cpp": False,
        "apps/vetron/frontend/dist/x.js": True,
        "src/tests/build/x.cpp": True,
    }
    for relative, expected in artifact_cases.items():
        if _generated_verification_path(relative) != expected:
            errors.append(
                "verification artifact classifier self-check changed for "
                f"{relative}")
    for source, target in (
        ("src/src/Core/src/api/A.cpp", "src/tests/Private.hpp"),
        ("src/src/Core/src/api/A.cpp", "src/benchmarks/Private.hpp"),
        ("src/src/Core/src/api/A.cpp", "src/java/Private.hpp"),
        ("src/src/Contracts/include/cxet/Canon/Enums.hpp", "src/src/Core/include/cxet/api/Private.hpp"),
        ("src/src/Contracts/include/cxet/Canon/Enums.hpp", "src/tests/private.hpp"),
        ("src/src/Contracts/include/cxet/Canon/Enums.hpp", "src/benchmarks/private.hpp"),
        ("src/src/Contracts/include/cxet/Canon/Enums.hpp", "src/java/private.hpp"),
        ("src/tests/a.cpp", "src/benchmarks/private.hpp"),
        ("src/benchmarks/a.cpp", "src/tests/private.hpp"),
        ("src/java/a.cpp", "src/tests/private.hpp"),
    ):
        if _core_alias_direction_allowed(source, target):
            errors.append(
                "verification include self-check accepted reverse physical "
                f"core alias {source} -> {target}")
    for source, target in (
        ("src/tests/a.cpp", "src/src/Contracts/include/cxet/Canon/Enums.hpp"),
        ("src/benchmarks/a.cpp", "src/src/Contracts/include/cxet/Canon/Enums.hpp"),
        ("src/java/a.cpp", "src/src/Contracts/include/cxet/Canon/Enums.hpp"),
        ("src/src/Core/src/api/A.cpp", "src/src/Contracts/include/cxet/Canon/Enums.hpp"),
        ("src/tests/Sort/a.cpp", "src/benchmarks/Sort/BenchmarkTypes.hpp"),
    ):
        if not _core_alias_direction_allowed(source, target):
            errors.append(
                "verification include self-check rejected reviewed physical "
                f"core alias {source} -> {target}")
    for label, include in (
        ("angle traversal", "../build/CxetFriend.hpp"),
        ("generated path", "generated/build/CxetFriend.hpp"),
        ("mixed-case generated path", "generated/BUILD/CxetFriend.hpp"),
        ("compiled source", "parser/RankingQuotePolicy.cpp"),
        ("C++ module source", "parser/RankingQuotePolicy.cppm"),
        ("Objective-C source", "parser/RankingQuotePolicy.mm"),
        ("assembly source", "parser/payload.S"),
        ("assembly source alias", "parser/payload.asm"),
        ("NASM source", "parser/payload.nasm"),
    ):
        if _include_path_syntax_error(include, quoted=False) is None:
            errors.append(
                f"verification include self-check accepted {label}")
    for suffix in (".asm", ".nasm", ".s"):
        if suffix not in _CPP_ASSEMBLY_SUFFIXES:
            errors.append(
                "verification source self-check missed unsupported assembly "
                f"suffix {suffix}")
    if _declared_source_root(
            "cxet_market_ingress_bench_support",
            "src/benchmarks") != "src/benchmarks/MarketIngress":
        errors.append(
            "verification source-authority self-check widened market-ingress "
            "support ownership")
    if _declared_source_root(
            "cxet_market_ingress_peer",
            "src/benchmarks") != "src/benchmarks/MarketIngress":
        errors.append(
            "verification source-authority self-check widened market-ingress "
            "peer ownership")
    if _declared_source_root(
            "cxet_read_only_contracts", "src/src") != "src/src/Contracts":
        errors.append(
            "verification source-authority self-check widened read-only "
            "CXET contract ownership")


def _project_root(active) -> str | None:
    parts = active.source_base.parts
    if parts[:2] in {("src", "src"), ("src", "tests"), ("src", "benchmarks")}:
        return "/".join(parts[:2])
    if len(parts) >= 2 and parts[0] in {"apps", "tools"}:
        return "/".join(parts[:2])
    return None


def _declared_source_root(target: str, product_root: str) -> str:
    """Return the exact source authority without changing graph ownership."""
    return _TARGET_SOURCE_AUTHORITY_ROOTS.get(target, product_root)



def unsafe_compile_definition_carriers(
    instance,
    target: str,
    values: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Default-deny unresolved definition carriers and opaque genex forms."""
    values = tuple(values)
    native_configs = {
        "cxet_crypto_rsa": ("PRIVATE", "RsaMbedConfig.h"),
        "cxet_crypto_import": ("PUBLIC", "cxet_mbedtls_config.h"),
    }
    recipe = native_configs.get(target)
    canonical_native = bool(recipe and native_crypto_owner(instance) and
        instance.body.command.name == "target_compile_definitions" and
        tuple(words(instance.body.command.body)) == (
            target, recipe[0], f'MBEDTLS_CONFIG_FILE="{recipe[1]}"') and
        values == (f"MBEDTLS_CONFIG_FILE={recipe[1]}",))
    dangerous = tuple(
        value for value in values if dangerous_compile_definition(value) or
        native_crypto_definition_error(target, value) and not canonical_native)
    opaque = tuple(
        value for value in values
        if any(marker in value for marker in _CARRIERS))
    if dangerous:
        return dangerous
    if not opaque:
        return ()
    if (target == "hftp_backend_headers" and
            instance.body == instance.evaluation and
            instance.body.relative == "apps/hft-parser/cmake/HftpLibraries.cmake" and
            instance.body.source_base == instance.body.binary_base == Path("apps/hft-parser") and
            not instance.body.structural_context and
            instance.body.command.name == "target_compile_definitions" and
            tuple(words(instance.body.command.body)) == (
                target, "INTERFACE", "HFTP_CANDLE_HISTORY=$<BOOL:${HFT_PARSER_CANDLE_HISTORY}>") and
            values in {("HFTP_CANDLE_HISTORY=$<BOOL:ON>",),
                       ("HFTP_CANDLE_HISTORY=$<BOOL:OFF>",),
                       ("HFTP_CANDLE_HISTORY=$<BOOL:1>",),
                       ("HFTP_CANDLE_HISTORY=$<BOOL:0>",)}):
        return ()
    from Family.Targets.CxetFamilyCompressionPolicy import compression_compile_definitions
    if compression_compile_definitions(instance, target, opaque):
        return ()
    return opaque


def target_contexts(
    instances,
    errors: list[str] | None = None,
    *,
    live_eof_paths=None,
):
    """Compatibility constructor for the path-aware global registry."""
    from Family.Targets.CxetFamilyTargetRegistry import build_target_registry
    compatibility_without_live_eof = live_eof_paths is None
    return build_target_registry(
        instances,
        errors if errors is not None else [],
        # Compatibility callers get an explicitly empty map: same-scope
        # resolution remains available, while every cross-root use fails
        # closed.  Production construction must pass modeled live EOF paths.
        live_eof_paths=(
            live_eof_paths if live_eof_paths is not None else {}),
        require_complete_live_eof=not compatibility_without_live_eof,
    )


def declaration_precedes(declaration, mutation) -> bool:
    """Order same-scope effects in direct/instantiated callable streams.

    Cross-root visibility needs the registry's provider-scope EOF proof and
    must never be approximated by comparing unrelated decision namespaces.
    """
    # Definition-body ordinals are lexical locations, not execution order:
    # a later caller may invoke a helper whose body lives above the target
    # declaration.  The instantiated stream ordinal records the real nested
    # call/loop emission order and is therefore the only sound comparison.
    return (
        declaration.evaluation.scope == mutation.evaluation.scope and
        declaration.emission_ordinal < mutation.emission_ordinal and
        paths_cover(
            universe=mutation.path_alternatives,
            evidence=declaration.path_alternatives)
    )


def _context_for_use(
    contexts, target: str, instance, *, allow_same: bool = False
):
    if hasattr(contexts, "context_for_use"):
        return contexts.context_for_use(target, instance, allow_same=allow_same)
    return contexts.get(target)


def target_mutation_context_error(
    instance,
    target: str,
    contexts: dict[str, object],
) -> str | None:
    declaration = _context_for_use(contexts, target, instance)
    if declaration is None:
        return f"target mutation owner {target} is not declared"
    if not declaration_precedes(declaration, instance):
        return f"target {target} is mutated before its declaration"
    declared_root = _project_root(declaration.evaluation)
    mutation_root = _project_root(instance.evaluation)
    if declared_root is None or mutation_root != declared_root:
        return (
            f"target {target} is mutated from {mutation_root or '<unknown>'}; "
            f"declared owner is {declared_root or '<unknown>'}")
    return None


def target_source_context_error(
    instance,
    target: str,
    contexts: dict[str, object],
) -> str | None:
    """Allow initial declaration sources at the declaration emission only."""
    declaration = _context_for_use(
        contexts, target, instance, allow_same=True)
    if declaration is None:
        return f"target source owner {target} is not declared"
    initial = (
        instance is declaration and
        instance.body.command.name in {"add_library", "add_executable"}
    )
    if not initial and not declaration_precedes(declaration, instance):
        return f"target {target} receives sources before its declaration"
    declared_root = _project_root(declaration.evaluation)
    mutation_root = _project_root(instance.evaluation)
    if declared_root is None or mutation_root != declared_root:
        return (
            f"target {target} receives sources from "
            f"{mutation_root or '<unknown>'}; declared owner is "
            f"{declared_root or '<unknown>'}")
    return None


def canonical_source_structural_error(target: str, instance) -> str | None:
    """Require canonical source-bearing effects in their reviewed block."""
    if target == "hftrec_corpus_contract":
        from CMake.Syntax.CmakeFamilyContext import recorder_contract_context
        if not recorder_contract_context(instance.body):
            return "canonical source command escaped its reviewed body context"
        if not recorder_contract_context(instance.evaluation):
            return "canonical source command escaped its reviewed evaluation context"
        return None
    expected = (
        _PARSER_PROCESS_CONTEXT
        if target in {"hft-parserd", "hft-algosd"} else
        (first_if("src/src/CMakeLists.txt", 443, ("DEFINED", "CXET_BUILD_OWNER")),)
        if target == "cxet_lib" and instance.body.command.name == "add_library" else ()
    )
    if not exact_context(instance.body.structural_context, expected):
        return "canonical source command escaped its reviewed body context"
    if not exact_context(instance.evaluation.structural_context, expected):
        return "canonical source command escaped its reviewed evaluation context"
    return None


def approved_external_compile_options(
    instance,
    target: str,
    values: list[str],
) -> bool:
    secp = (
        target in {"secp256k1", "secp256k1_precomputed"} and
        values == [
            "$<$<CONFIG:Release>:-O3>",
            "$<$<CONFIG:Release>:-march=native>"] and
        instance.body.relative == "src/src/CMakeLists.txt" and
        instance.body.command.line == (
            213 if target == "secp256k1" else 214) and
        instance.evaluation.source_base == Path("src/src") and
        instance.evaluation.binary_base == Path("src/src")
    )
    return secp


def declared_source_owner_error(
    target: str,
    declaration,
    mutation,
    source: str,
) -> str | None:
    """Require every compiled helper/object source to stay in its product."""
    product_root = _project_root(declaration.evaluation)
    if product_root is None:
        return f"target {target} has no modeled product source root"
    if _project_root(mutation.evaluation) != product_root:
        return (
            f"target {target} receives sources outside owner context "
            f"{product_root}")
    if _generated_verification_path(source):
        return f"target {target} compiles source from generated tree: {source}"
    if (source in NATIVE_CRYPTO_VENDOR_SOURCES.get(target, ()) and
            native_crypto_owner(mutation)):
        return None
    if (target.endswith("_traced") and
            source == "tools/Benchmarks/native/SendTrace.cpp" and
            mutation.body.command.name == "target_sources" and
            benchmark_instance_context(declaration, target) and
            benchmark_instance_context(mutation, target) and
            declaration.body.relative == mutation.body.relative):
        return None
    source_root = _declared_source_root(target, product_root)
    if source == source_root or source.startswith(source_root + "/"):
        return None
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
    from Family.Sources.CxetFamilyOfflineSourcePolicy import (
        offline_shared_fixture_source, startup_canonical_source,
    )
    if (startup_canonical_source(declaration, target, source) and
            startup_canonical_source(mutation, target, source)):
        return None
    registration = offline_registration(mutation, target)
    if (registration is not None and offline_registration(declaration, target) is registration and
            source in registration.sources and offline_shared_fixture_source(
                registration.relative, registration.owner, target, source)):
        return None
    if (target == "cxet-family-strategy-differential" and
            source in _VERIFICATION_ADAPTERS):
        return None
    return (
        f"target {target} compiles source outside {source_root}: {source}")


def build_dependency_error(
    instance,
    source: str,
    dependency: str,
    contexts: dict[str, object],
    *,
    source_attachment: bool = False,
) -> str | None:
    """Allow build-order edges only inside one product or exact core bridges."""
    if any(marker in value for value in (source, dependency) for marker in _CARRIERS):
        return f"unresolved build dependency {source} -> {dependency}"
    source_context = _context_for_use(
        contexts, source, instance, allow_same=source_attachment)
    if source_context is None:
        return f"unmodeled build-dependency owner {source}"
    initial_source_attachment = (
        source_attachment and
        source_context is instance and
        instance.body.command.name in {"add_library", "add_executable"}
    )
    if (not initial_source_attachment and
            not declaration_precedes(source_context, instance)):
        return f"build dependency mutates {source} before declaration"
    source_root = _project_root(source_context.evaluation)
    if _project_root(instance.evaluation) != source_root:
        return f"build dependency mutates {source} outside {source_root}"
    if (source, dependency) == ("cxet_lib", "secp256k1"):
        from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_external_authority
        if (instance.body.relative == "src/src/CMakeLists.txt" and
                instance.body.source_base == Path("src/src") and
                instance.body.binary_base == Path("src/src") and
                instance.evaluation.source_base == Path("src/src") and
                instance.evaluation.binary_base == Path("src/src") and
                cmake_list_words(instance.body.command.body) == ["cxet_lib", "secp256k1"] and
                exact_context(instance.body.structural_context, (first_if(
                    "src/src/CMakeLists.txt", 545, ("TARGET", "secp256k1")),)) and
                reviewed_external_authority("secp256k1")):
            return None
        return "secp256k1 build dependency escaped its exact native provider recipe"
    dependency_context = _context_for_use(contexts, dependency, instance)
    if dependency_context is None:
        return f"unmodeled build dependency {source} -> {dependency}"
    if not declaration_precedes(dependency_context, instance):
        return f"build dependency {dependency} is used before declaration"
    dependency_root = _project_root(dependency_context.evaluation)
    if source_root is None or source_root != dependency_root:
        return f"cross-product build dependency {source} -> {dependency}"
    return None


def _normalize_repo_include(active, value: str) -> str | None:
    if "\\" in value:
        return None
    path = Path(value)
    normalized = path.as_posix().rstrip("/")
    source_base = active.source_base.as_posix().rstrip("/")
    if path.is_absolute():
        candidate = path
    elif normalized == source_base or normalized.startswith(source_base + "/"):
        # CMAKE_CURRENT_SOURCE_DIR expands to a repository-relative modeled
        # path; keep that producer context instead of prefixing it twice.
        candidate = ROOT / path
    else:
        candidate = ROOT / active.source_base / path
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None
    if not _unsymlinked_repo_path(candidate):
        return None
    candidate = Path(os.path.abspath(candidate))
    if not candidate.is_dir():
        return None
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def normalize_repo_include(active, value: str) -> str | None:
    """Public exact repository-root normalizer for reachability proof."""
    return _normalize_repo_include(active, value)


def verification_include_allowed(
    source_relative: str,
    target_relative: str,
) -> bool:
    """Apply physical and logical ownership direction to a resolved include."""
    if (target_relative == "tools/Testing/OfflineCase.hpp" and
            any(source_relative.startswith(prefix) for prefix in (
                "src/tests/offline/", "tools/exchange_api_probe/tests/offline/",
                *(f"apps/{owner}/tests/offline/" for owner in (
                    "trading-core", "hft-parser",  "trader", "vetron",
                    "hft-recorder", "hft-compressor", "diagnostic"))))):
        return True
    owner = _verification_relative_owner(source_relative)
    return owner is not None and _exported_include_allowed(
        owner, source_relative, target_relative)


def verification_unresolved_quoted_include(
    source_relative: str,
    include: str,
) -> bool:
    """Keep the exact generated/optional quoted include inventory visible."""
    return include in _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES.get(
        source_relative, frozenset())


def verification_unresolved_quoted_inventory(
) -> frozenset[tuple[str, str]]:
    """Expose the exact reviewed inventory to the target-aware resolver."""
    return frozenset(
        (relative, include)
        for relative, includes in
        _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES.items()
        for include in includes
    )


def verification_unresolved_quoted_requirement(
    source_relative: str,
    include: str,
) -> tuple[str, str] | None:
    """Return the one typed provider contract for an unresolved include."""
    pair = (source_relative, include)
    if pair in _VERIFICATION_UNRESOLVED_DORMANT_ONLY:
        return "dormant", ""
    external = _VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS.get(pair)
    if external is not None:
        return "external", external
    generated = _VERIFICATION_UNRESOLVED_GENERATED_ROOTS.get(pair)
    if generated is not None:
        return "generated", generated
    return None


def _same_owner_include(
    target: str, declaration, mutation, value: str
) -> bool:
    evaluation = (
        declaration.evaluation if mutation is None else mutation.evaluation)
    normalized = _normalize_repo_include(evaluation, value)
    owner = _project_root(declaration.evaluation)
    if normalized is None or owner is None:
        return False
    if mutation is not None:
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Targets.CxetFamilyBuildPolicy import registered_offline_include_roots
        registration = offline_registration(declaration, target)
        if (registration is not None and offline_registration(mutation, target) is registration and
                normalized in registered_offline_include_roots(mutation, target)):
            return True
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instance_context
        if (offline_instance_context(declaration, target) and
                normalized in exact_offline_include_roots(mutation, target)):
            return True
    contract = BENCHMARK_INCLUDE_CONTRACTS.get(target)
    if (contract is not None and normalized in contract[1] and
            benchmark_instance_context(declaration, target) and
            (mutation is None or benchmark_instance_context(mutation, target))):
        return True
    if (normalized == "tools/Testing" and
            declaration.body.relative.endswith("/tests/offline/CMakeLists.txt") and
            declaration.body.command.name == "add_executable" and
            (mutation is None or mutation.body.relative == declaration.body.relative)):
        # Only the exact offline helper can create these reviewed declarations;
        # the shared harness is private and never becomes a public root.
        return True
    if normalized in _VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS.get(
            owner, frozenset()):
        return True
    if normalized in _VERIFICATION_TARGET_PRIVATE_INCLUDE_ROOTS.get(
            target, frozenset()):
        return True
    if (owner == "apps/hft-parser" and
            target in _PARSER_CXET_INCLUDE_TARGETS and
            normalized in {
                "src/src/Core/include",
                "src/src/Contracts/include",
            }):
        return True
    if (owner == "src/tests" and
            normalized in {
                "src/src/Core/include",
                "src/src/Contracts/include",
            }):
        return True
    if (owner == "apps/hft-backtest" and
            target.startswith("hft-backtest-") and
            normalized == "apps/hft-backtest/src/Runtime/src"):
        return True
    return (
        target == "cxet-family-strategy-differential" and
        normalized == "apps/hft-backtest/src/Runtime/src"
    )


def target_include_error(
    target: str,
    declaration,
    value: str,
    mutation=None,
    *,
    contexts=None,
    instances=(),
) -> str | None:
    """Validate target include carriers against declaration product ownership."""
    if (mutation is not None and
            _project_root(mutation.evaluation) !=
            _project_root(declaration.evaluation)):
        return "include mutation is evaluated outside declaration product"
    if (target in {"cxet_crypto", "cxet_native_tls"} and
            value == "$<INSTALL_INTERFACE:include>" and
            mutation is not None and native_crypto_owner(mutation)):
        return None
    if target == "cxet_lib" and approved_cxet_include(value):
        return None
    if (mutation is not None and compression_include_provider(
            mutation, target, 'PUBLIC', value) is not None):
        return None
    if (value == OFFLINE_LIBURING_INCLUDE and mutation is not None and
            offline_liburing_include_context(mutation, target, contexts, instances)):
        return None
    if value.startswith("$<INSTALL_INTERFACE:") and value.endswith(">"):
        return f"unapproved install include carrier {value}"
    if value.startswith("$<BUILD_INTERFACE:") and value.endswith(">"):
        payload = value[len("$<BUILD_INTERFACE:"):-1]
        if (normalize_synthetic_binary_path(payload) is None and
                not Path(payload).is_absolute()):
            # The interpreter stores CURRENT_SOURCE/LIST_DIR relative to the
            # repo. Accept only the independently proved raw absolute carrier.
            from Family.Sources.CxetFamilyIncludeReachability import _include_value
            if mutation is None or _include_value(mutation, value) is None:
                return (
                    "relative BUILD_INTERFACE include payload is unsupported: "
                    f"{value}")
        return target_include_error(
            target, declaration, payload, mutation, contexts=contexts, instances=instances)
    if any(marker in value for marker in _CARRIERS):
        return f"unresolved or opaque include carrier {value}"
    synthetic = normalize_synthetic_binary_path(value)
    approved_generated = {
        "trading_core_strategy":
            "__CXET_CMAKE_BINARY__/apps/trading-core/generated",
    }
    if synthetic is not None:
        if synthetic == approved_generated.get(target):
            return None
        return f"unapproved generated include carrier {value}"
    if mutation is not None and native_crypto_owner(mutation):
        try:
            vendor_include = Path(value).resolve().relative_to(ROOT.resolve()).as_posix()
        except (ValueError, OSError):
            vendor_include = ""
        if vendor_include in NATIVE_CRYPTO_VENDOR_INCLUDES.get(target, ()):
            return None
        native_own = {
            "cxet_crypto": {"src/src/Core/include", "src/src/Contracts/include", "src/src/Core/src/Crypto"},
            "cxet_crypto_rsa": {"src/src/Core/src/Crypto"},
            "cxet_native_tls": {"src/src/Core/include", "src/src/Contracts/include"},
        }
        if vendor_include in native_own.get(target, ()):
            return None
    if _same_owner_include(target, declaration, mutation, value):
        return None
    return f"include carrier escapes target product ownership: {value}"


def target_property_effect_error(
    instance,
    target: str,
    mutation,
    declaration,
    contexts: dict[str, object],
    approved_external: frozenset[str],
) -> tuple[bool, str | None]:
    """Preserve the target-policy API while delegating property effects."""
    return evaluate_target_property_effect(
        instance,
        target,
        mutation,
        declaration,
        contexts,
        approved_external,
        build_dependency_error=build_dependency_error,
    )
