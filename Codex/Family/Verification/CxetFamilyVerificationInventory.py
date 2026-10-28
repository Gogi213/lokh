"""Exact source identities and unresolved includes for family verification."""

from __future__ import annotations


VERIFICATION_FRIEND_DEFINE = "CXET_FAMILY_DIFFERENTIAL_TESTING"
VERIFICATION_FRIEND_IDENTIFIERS = (
    "StrategyRunnerRuntimeFamilyVerificationFriend",
    # Retired diagnostic seam has no approved occurrence; reject reintroduction.
    "StrategyInstanceFamilyVerificationFriend",
)

_TRADER_GENERATED_STRATEGY_SOURCES = (
    'apps/trader/src/Runtime/src/Strategy/ProfileUniverseStrategyRunner.cpp',
    'apps/trader/src/Process/src/Launcher/StrategyLaunchPreparation.cpp',
    'apps/trader/src/Process/src/Traderd/Strategy/TraderdStrategyComposition.cpp',
    'apps/trader/src/Runtime/include/trader/Runtime/Strategy/ProfileStrategyLaunch.hpp',
    'apps/trader/src/Market/src/Algorithms/AlgorithmIniPrivate.hpp',
    'apps/trader/src/Process/src/Traderd/Profile/TraderdFleetProfileSupport.hpp',
)

_ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES = (
    'apps/hft-backtest/src/Runtime/src/Run/BacktestPreparation.cpp',
    'apps/hft-backtest/src/Runtime/src/Replay/BacktestReplaySupport.cpp',
    'apps/hft-backtest/src/Runtime/src/Run/BacktestFinalization.cpp',
    'apps/hft-backtest/src/Runtime/src/Run/BacktestArtifacts.cpp',
    'apps/hft-backtest/src/Runtime/src/Run/Internal/BacktestRunHelpers.hpp',
    'apps/hft-backtest/src/Runtime/src/Run/BacktestReplay.cpp',
    'apps/hft-backtest/src/Runtime/src/Run/BacktestReplayRisk.cpp',
)

VERIFICATION_UNRESOLVED_QUOTED_INCLUDES = {
    **{source: frozenset({'trading_core/Strategy/GeneratedStrategyRegistry.hpp'})
       for source in (*_TRADER_GENERATED_STRATEGY_SOURCES,
                      *_ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES)},
    "src/src/Core/src/Api/Config/ExchangeObjectConfig.cpp": frozenset({
        "absl/container/flat_hash_map.h"}),
    "src/src/Core/src/Api/Connector/ExchangeProductConnector.cpp": frozenset({
        "absl/container/flat_hash_map.h"}),
    "src/src/Core/src/Api/Run/Detail/RunMapHelpers.hpp": frozenset({
        "absl/container/btree_map.h",
        "absl/container/flat_hash_map.h",
    }),
    "src/src/Core/src/Api/Run/RunMapJsonBuilder.cpp": frozenset({
        "absl/container/btree_map.h",
        "absl/container/btree_set.h",
    }),
    "apps/hft-backtest/src/Runtime/src/Config/StrategyMetadata.cpp": frozenset({
        "trading_core/Strategy/GeneratedStrategyRegistry.hpp",
    }),
    "apps/hft-backtest/src/Runtime/src/Execution/Model/BacktestExecutionDepth.cpp":
        frozenset({"absl/container/inlined_vector.h"}),
    "apps/hft-backtest/src/Runtime/src/Results/BacktestResultWriter.cpp":
        frozenset({"absl/container/flat_hash_map.h"}),
    "apps/hft-backtest/src/Runtime/src/Results/Internal/BacktestResultWriterInternal.hpp":
        frozenset({"absl/container/flat_hash_map.h"}),
    **{f"apps/hft-backtest/src/Runtime/src/Results/{name}.cpp":
       frozenset({"absl/container/flat_hash_map.h"}) for name in (
           "BacktestResultDiagnostic", "BacktestResultOrderLifetimes",
           "BacktestResultStreams", "BacktestResultManifest")},
    "apps/hft-backtest/src/Runtime/src/Run/Backtest.cpp": frozenset({
        "trading_core/Strategy/GeneratedStrategyRegistry.hpp"}),
}

VERIFICATION_UNRESOLVED_DORMANT_ONLY = frozenset()

VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS = {
    ("src/src/Core/src/Api/Config/ExchangeObjectConfig.cpp",
     "absl/container/flat_hash_map.h"): "absl::flat_hash_map",
    ("src/src/Core/src/Api/Connector/ExchangeProductConnector.cpp",
     "absl/container/flat_hash_map.h"): "absl::flat_hash_map",
    ("src/src/Core/src/Api/Run/Detail/RunMapHelpers.hpp",
     "absl/container/btree_map.h"): "absl::btree",
    ("src/src/Core/src/Api/Run/Detail/RunMapHelpers.hpp",
     "absl/container/flat_hash_map.h"): "absl::flat_hash_map",
    ("src/src/Core/src/Api/Run/RunMapJsonBuilder.cpp",
     "absl/container/btree_map.h"): "absl::btree",
    ("src/src/Core/src/Api/Run/RunMapJsonBuilder.cpp",
     "absl/container/btree_set.h"): "absl::btree",
    ("apps/hft-backtest/src/Runtime/src/Execution/Model/BacktestExecutionDepth.cpp",
     "absl/container/inlined_vector.h"): "absl::inlined_vector",
    ("apps/hft-backtest/src/Runtime/src/Results/BacktestResultWriter.cpp",
     "absl/container/flat_hash_map.h"): "absl::flat_hash_map",
    ("apps/hft-backtest/src/Runtime/src/Results/Internal/BacktestResultWriterInternal.hpp",
     "absl/container/flat_hash_map.h"): "absl::flat_hash_map",
    **{(f"apps/hft-backtest/src/Runtime/src/Results/{name}.cpp",
        "absl/container/flat_hash_map.h"): "absl::flat_hash_map" for name in (
            "BacktestResultDiagnostic", "BacktestResultOrderLifetimes",
            "BacktestResultStreams", "BacktestResultManifest")},
}

_GENERATED_STRATEGY_INCLUDE = (
    "trading_core/Strategy/GeneratedStrategyRegistry.hpp")
_GENERATED_STRATEGY_SOURCES = (
    "apps/hft-backtest/src/Runtime/src/Config/StrategyMetadata.cpp",
    "apps/hft-backtest/src/Runtime/src/Run/Backtest.cpp",
) + _TRADER_GENERATED_STRATEGY_SOURCES + _ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES
VERIFICATION_UNRESOLVED_GENERATED_ROOTS = {
    **{
        (source, _GENERATED_STRATEGY_INCLUDE):
            "__CXET_CMAKE_BINARY__/apps/trading-core/generated"
        for source in _GENERATED_STRATEGY_SOURCES
    },
}

VERIFICATION_FRIEND_SOURCE_LINES = {
}

VERIFICATION_PROTECTED_FRIEND_LINES = {
    "apps/trader/src/Runtime/include/trader/Runtime/Strategy/ProfileUniverseStrategyRunner.hpp": (
        "friend class trader::process::TraderdProcess;",),
}

VERIFICATION_RETIRED_SEAM_PATHS = frozenset({
    "src/src/Core/include/cxet/Api/Market/PublicMarketDataSubscriptionManager.hpp",
    "apps/trader/tests/FamilyVerification/StrategyCycleAdapter.cpp",
})

VERIFICATION_PROTECTED_SHA256 = {
    "apps/trader/src/Runtime/include/trader/Runtime/Strategy/ProfileUniverseStrategyRunner.hpp":
        "fff9a4f001c3d151efe629defa71ea2f11dfb0653136060b7c6c97852ebf752f",
}
