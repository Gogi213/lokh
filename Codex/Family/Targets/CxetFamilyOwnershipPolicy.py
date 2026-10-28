"""Canonical source-root policy for the CXET active-family ownership check."""

from __future__ import annotations

from pathlib import PurePosixPath
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words

from Family.Sources.CxetFamilySourcePaths import source_artifact_path
from Family.Targets.CxetFamilyTargetInventory import PRODUCTION_TARGETS


TARGET_OWNERS = {
    "diagnostic_runtime": "apps/diagnostic/CMakeLists.txt",
    "diagnosticd": "apps/diagnostic/CMakeLists.txt",
    "cxet_lib": "src/src/CMakeLists.txt",
    "cxet_read_only_contracts": "src/src/CMakeLists.txt",
    "trading_core_contracts": "apps/trading-core/CMakeLists.txt",
    "trading_core_headers": "apps/trading-core/CMakeLists.txt",
    "capital_finance": "apps/trading-core/capital/CMakeLists.txt",
    "trading_core_algorithm": "apps/trading-core/CMakeLists.txt",
    "trading_core_execution": "apps/trading-core/CMakeLists.txt",
    "trading_core_strategy": "apps/trading-core/CMakeLists.txt",
    "hftp_market_client":
        "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hftp_market_demand_client":
        "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hft_parser_projection_client":
        "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hft_parser_history_client":
        "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hft_parser_session_client":
        "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hftp_reference_storage": "apps/hft-parser/cmake/HftpLibraries.cmake",
    "hft-parserd": "apps/hft-parser/cmake/HftpProcesses.cmake",
    "hft-algosd": "apps/hft-parser/cmake/HftpProcesses.cmake",
    "hftrec_corpus_contract":
        "apps/hft-recorder/src/Contracts/CMakeLists.txt",
    "hftrec_json_capture": "apps/hft-recorder/src/Runtime/CMakeLists.txt",
    "hft_backtest_core": "apps/hft-backtest/CMakeLists.txt",
    "traderd": "apps/trader/CMakeLists.txt",
    "trader_projection_client": "apps/trader/CMakeLists.txt",
    "trader_live_runtime": "apps/trader/CMakeLists.txt",
    "vetrond-read": "apps/vetron/CMakeLists.txt",
    "vetron_read_gateway": "apps/vetron/CMakeLists.txt",
    "vetron_read_runtime": "apps/vetron/CMakeLists.txt",
}

OBSOLETE_TARGETS = (
    "trader_diagnostic_runtime",
    "trader_diagnostic_session",
    "trader_diagnostic_process",
    "trader_account_session",
    "trader-accountd-diagnostic",
    "traderd-diagnostic",
    "hft-accountd",
    "hft-controld",
    "hft-configd",
    "hft-node-agent",
    "hftp_browser",
    "hftp_gateway",
    "hftp_control_projection_adapter",
    "hftp_account_data_plane",
    "hftp_account_history_ipc",
    "vetron-commandd",
)

_EXCLUDED_TOP_LEVEL_CMAKE_ROOTS = frozenset({
    "extra", "external", "third_party", "vendor",
})


def generated_cmake_path(parts: tuple[str, ...]) -> bool:
    """Classify full-repository CMake paths relative to their product owner."""
    if not parts:
        return False
    first = parts[0].casefold()
    if first == ".codex-output":
        return True
    if first in _EXCLUDED_TOP_LEVEL_CMAKE_ROOTS:
        return True
    relative = PurePosixPath(*parts).as_posix()
    top_level_artifact = (
        first == "build" or first.startswith("build-") or
        first.startswith("cmake-build-"))
    if top_level_artifact:
        owner_roots: tuple[str, ...] = ()
    elif first in {"apps", "src", "tools"} and len(parts) >= 2:
        owner_roots = (PurePosixPath(*parts[:2]).as_posix(),)
    else:
        owner_roots = (parts[0],)
    return source_artifact_path(relative, owner_roots)


def validate_generated_cmake_path_microcases(errors: list[str]) -> None:
    cases = (
        ((".codex-output", "runtime", "service.sock"), True),
        (("build", "CMakeLists.txt"), True),
        (("apps", "trader", "build", "CMakeLists.txt"), True),
        (("src", "src", "api", "build", "CMakeLists.txt"), False),
        (("apps", "vetron", "frontend", "dist", "asset.cmake"), True),
        (("apps", "trader", "api", ".git", "CMakeLists.txt"), True),
        (("vendor", "package", "CMakeLists.txt"), True),
    )
    for parts, expected in cases:
        if generated_cmake_path(parts) != expected:
            errors.append(
                "owner-relative CMake artifact classifier self-check failed: "
                + PurePosixPath(*parts).as_posix())


_HFTREC_JSON_CAPTURE_SOURCES = (
    "apps/hft-recorder/src/Runtime/src/Capture/Session/SessionId.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Serialization/ChannelJsonWriter.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Serialization/JsonSerializers.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Session/SupportArtifacts.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureChannelSupport.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureCoordinatorInternal.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureCoordinator.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureCoordinatorRuntime.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureCoordinatorRuntimeLoops.cpp",
    "apps/hft-recorder/src/Runtime/src/Capture/Coordinator/VenueMultiplexCapture.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/CorpusLoader.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/InstrumentMetadata.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Storage/EventStorage.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Storage/JsonSessionStorage.cpp",
    "apps/hft-recorder/src/Runtime/src/Replay/BookState.cpp",
    "apps/hft-recorder/src/Runtime/src/Replay/SessionReplay.cpp",
    "apps/hft-recorder/src/Runtime/src/Replay/SessionReplayTimeline.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Recordings/RecordingRoot.cpp",
    "apps/hft-recorder/src/Runtime/src/Corpus/Recordings/RecordingDiscovery.cpp",
    "apps/hft-recorder/src/Process/src/Finam/FinamEnvSync.cpp",
)

_REVIEWED_RECORDER_PARENT_SOURCES = {
    'hftrec_json_capture': frozenset({
        'apps/hft-recorder/src/Process/src/Finam/FinamEnvSync.cpp',
    }),
    'hftrec_capture_launch': frozenset({
        'apps/hft-recorder/src/Runtime/src/Capture/Coordinator/RecorderCaptureSelection.cpp',
    }),
    'hftrec_capture_client': frozenset({
        'apps/hft-recorder/src/Runtime/src/Capture/Parser/ParserMarketCaptureClient.cpp',
        'apps/hft-recorder/src/Runtime/src/Capture/Parser/Private/CorpusConversion.cpp',
    }),
    'hftrec_core': frozenset({
        'apps/hft-recorder/src/Lab/src/Arbitrage/BookTickerSpread.cpp',
        'apps/hft-recorder/src/Lab/src/Arbitrage/BookTickerSpreadMean.cpp',
        'apps/hft-recorder/src/Lab/src/Arbitrage/CandleSpread.cpp',
        'apps/hft-recorder/src/Lab/src/BookFrameSampler.cpp',
        'apps/hft-recorder/src/Lab/src/LabRunner.cpp',
        'apps/hft-recorder/src/Lab/src/RankingEngine.cpp',
        'apps/hft-recorder/src/Process/src/Tui/RecorderTuiLaunch.cpp',
        'apps/hft-recorder/src/Process/src/Tui/RecorderTuiPreset.cpp',
        'apps/hft-recorder/src/Process/src/Tui/RecorderTuiShard.cpp',
        'apps/hft-recorder/src/Process/src/Tui/RecorderTuiSymbols.cpp',
        'apps/hft-recorder/src/Process/src/Tui/Status/RecorderTuiShardStatus.cpp',
        'apps/hft-recorder/src/Process/src/Tui/TerminalRender.cpp',
    }),
}


def reviewed_recorder_parent_source(target, instance, source):
    """Permit only the exact existing intra-Recorder translation units."""
    spec = PRODUCTION_TARGETS.get(target)
    if spec is None or source not in _REVIEWED_RECORDER_PARENT_SOURCES.get(target, ()):
        return False
    base = PurePosixPath(spec.owner).parent
    return (instance.body.relative == spec.owner and
            instance.body.command.name in {'add_library', 'target_sources'} and
            cmake_list_words(instance.body.command.body)[:1] == [target] and
            instance.evaluation.source_base.as_posix() == base.as_posix() and
            instance.evaluation.binary_base.as_posix() == base.as_posix())


TARGET_SOURCE_ROOTS = {
    "hftp_reference_storage": (
        "apps/hft-parser/src/Runtime/src/History/Archive/CandleArchiveFileIo.cpp",
        "apps/hft-parser/src/Runtime/src/History/Archive/CandleArchiveSecureRoot.cpp",
        "apps/hft-parser/src/Runtime/src/History/Archive/CandleArchiveQuotaLedger.cpp",
        "apps/hft-parser/src/Runtime/src/History/Metadata/InstrumentSidecar.cpp",
        "apps/hft-parser/src/Runtime/src/History/Metadata/InstrumentSidecarCodec.cpp",
        "apps/hft-parser/src/Runtime/src/History/Metadata/InstrumentSidecarMigration.cpp",
        "apps/hft-parser/src/Runtime/src/History/Metadata/InstrumentSidecarStore.cpp",
        "apps/hft-parser/src/Runtime/src/History/Archive/LegacyCandleHistoryArchive.cpp",
        "apps/hft-parser/src/Runtime/src/History/Metadata/InstrumentArchiveMetadataAcquisition.cpp",
    ),
    "diagnostic_runtime": (
        "apps/diagnostic/src/Notifications/Notifications.cpp",
        "apps/diagnostic/src/Notifications/NotificationStore.cpp",
        "apps/diagnostic/src/Notifications/TelegramDelivery.cpp",
        "apps/diagnostic/src/Domain/Accounting/Reducer.cpp",
        "apps/diagnostic/src/Domain/Accounting/Finance.cpp",
        "apps/diagnostic/src/Storage/Postgres.cpp",
        "apps/diagnostic/src/Application/Config.cpp",
        "apps/diagnostic/src/Collector/Session/CredentialSession.cpp",
        "apps/diagnostic/src/Collector/Account/NativeObserver.cpp",
        "apps/diagnostic/src/Collector/Account/NativeAccountObservation.cpp",
        "apps/diagnostic/src/Collector/Market/MarketObserver.cpp",
        "apps/diagnostic/src/Collector/Reference/KeyRateObserver.cpp",
        "apps/diagnostic/src/Collector/Reference/DeliveryTermsObserver.cpp",
        "apps/diagnostic/src/Storage/PairBasisStore.cpp",
        "apps/diagnostic/src/Storage/DemoStore.cpp",
        "apps/diagnostic/src/Collector/Transport/RestWorker.cpp",
        "apps/diagnostic/src/Collector/Transport/NativePages.cpp",
        "apps/diagnostic/src/Collector/Transport/PrivateStream.cpp",
        "apps/diagnostic/src/Collector/Session/NativeSession.cpp",
        "apps/diagnostic/src/Collector/Account/UserEventProjection.cpp",
        "apps/diagnostic/src/Collector/Transport/NativeGrpcStream.cpp",
        "apps/diagnostic/src/Demo/Demo.cpp",
    ),
    "diagnosticd": ("apps/diagnostic/src/Application/Main.cpp",),
    "cxet_lib": ("src/src/Core/src/",),
    "cxet_read_only_contracts": ("src/src/Contracts/src/",),
    "trading_core_contracts": ("apps/trading-core/src/Contracts/include/",),
    "trading_core_headers": ("apps/trading-core/src/Core/include/",),
    "capital_finance": (
        "apps/trading-core/capital/src/Accounting/AccountStorage.cpp",
        "apps/trading-core/capital/src/Accounting/AccountSnapshot.cpp",
        "apps/trading-core/capital/src/Accounting/AccountAssets.cpp",
        "apps/trading-core/capital/src/Accounting/AccountPositions.cpp",
        "apps/trading-core/capital/src/Accounting/AccountFills.cpp",
        "apps/trading-core/capital/src/Accounting/FillPositionAccounting.cpp",
        "apps/trading-core/capital/src/Risk/PortfolioRisk.cpp",
        "apps/trading-core/capital/src/Risk/PositionRisk.cpp",
        "apps/trading-core/capital/src/Finance.cpp",
        "apps/trading-core/capital/src/FinancialExposure.cpp",
        "apps/trading-core/capital/src/Risk/PairAssessment.cpp",
    ),
    "trading_core_algorithm": (
        "apps/trading-core/src/Core/include/trading_core/Contracts/",
        "apps/trading-core/src/Core/include/trading_core/Algorithm/",
    ),
    "trading_core_execution": (
        "apps/trading-core/src/Core/src/Execution/",
        "apps/trading-core/src/Core/include/trading_core/Execution/",
    ),
    "trading_core_strategy": (
        "apps/trading-core/src/Core/src/Strategy/",
        "apps/trading-core/src/Core/include/trading_core/Strategy/",
    ),
    "hftp_market_client": (
        "apps/hft-parser/src/Clients/src/Market/PublicMarketSourceOwner.cpp",),
    "hftp_market_demand_client": (
        "apps/hft-parser/src/Clients/src/Market/MarketDemandClient.cpp",),
    "hft_parser_projection_client": (
        "apps/hft-parser/src/Clients/src/Projection/",),
    "hft_parser_history_client": (
        "apps/hft-parser/src/Clients/src/History/",),
    "hft_parser_session_client": (
        "apps/hft-parser/src/Clients/src/Session/",),
    "hft-parserd": ("apps/hft-parser/src/Process/src/ParserdMain.cpp",),
    "hft-algosd": ("apps/hft-parser/src/Process/src/AlgosdMain.cpp",),
    "hftrec_corpus_contract": (
        "apps/hft-recorder/src/Runtime/src/Capture/Session/SessionManifest.cpp",
        "apps/hft-recorder/src/Runtime/src/Corpus/Codec/Crc32c.cpp",
        "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusReader.cpp",
        "apps/hft-recorder/src/Runtime/src/Corpus/BinaryMarketCorpusWriter.cpp",
        "apps/hft-recorder/src/Runtime/src/Capture/Parser/BufferedCorpusWriter.cpp",
        "apps/hft-recorder/src/Runtime/src/Replay/JsonLineParser.cpp",
    ),
    "hft_backtest_core": ("apps/hft-backtest/src/Runtime/src/",),
    "hftrec_json_capture": _HFTREC_JSON_CAPTURE_SOURCES,
    "traderd": (
        "apps/trader/src/Process/src/Traderd/Application/TraderdDispatchMain.cpp",
        "apps/trader/src/Process/src/Traderd/Application/NativeBindingDescription.cpp",
    ),
    "trader_projection_client": (
        "apps/trader/src/Projection/src/Client/Client.cpp",
        "apps/trader/src/Projection/src/Client/ProjectionSource.cpp",
    ),
    "trader_live_runtime": (
        "apps/trader/src/Runtime/src/Recovery/RecoveryCapability.cpp",
        "apps/trader/src/Runtime/src/Account/",
        "apps/trader/src/Runtime/src/Order/",
        "apps/trader/src/Runtime/src/Strategy/",
    ),
    "vetrond-read": ("apps/vetron/src/Process/src/Read/VetrondMain.cpp",),
    "vetron_read_gateway": ("apps/vetron/src/Gateway/src/",),
    "vetron_read_runtime": ("apps/vetron/src/Runtime/src/",),
}

# Targets in this map have a deliberately closed implementation surface.  A
# source-root check alone is insufficient for them: removing one required
# translation unit (or attaching another file from the same root) changes the
# contract while still satisfying ordinary ownership.  Keep normalized
# repository paths here so every checker consumes one canonical inventory.
CANONICAL_EXACT_SOURCE_ATTACHMENTS = {
    "hftp_reference_storage": frozenset(TARGET_SOURCE_ROOTS["hftp_reference_storage"]),
    "capital_finance": frozenset(TARGET_SOURCE_ROOTS["capital_finance"]),
    "hftp_market_demand_client": frozenset(TARGET_SOURCE_ROOTS["hftp_market_demand_client"]),
    "hftrec_json_capture": frozenset(_HFTREC_JSON_CAPTURE_SOURCES),
    "cxet_read_only_contracts": frozenset({
        "src/src/Contracts/src/Api/Order/OrderResponseEvidence.cpp",
        "src/src/Contracts/src/Canon/CanonLookup.cpp",
        "src/src/Contracts/src/Canon/ExchangeRegistry.cpp",
        "src/src/Contracts/src/Canon/MarketMapping.cpp",
        "src/src/Contracts/src/Parse/DecimalToScaled.cpp",
    }),
}

# Interface/source-less declarations remain ownership-checked but are not
# required to acquire a concrete source merely to satisfy the checker.
OPTIONAL_SOURCE_TARGETS = frozenset({"trading_core_algorithm", "trading_core_headers", "trading_core_contracts"})
SOURCE_REQUIRED_TARGETS = frozenset(TARGET_OWNERS) - OPTIONAL_SOURCE_TARGETS

def _compiled_product_owner(cmake_owner: str) -> str:
    """Return the canonical first-party product for one production target."""
    parts = PurePosixPath(cmake_owner).parts
    if parts[:2] in {("src", "src"), ("src", "replay")}:
        return "/".join(parts[:2])
    if len(parts) >= 2 and parts[0] in {"apps", "tools"}:
        return "/".join(parts[:2])
    return cmake_owner


# Seed every concrete production target, not only the smaller acceptance-owner
# subset above. Static/shared twins and component targets inside one product
# share the same physical source authority; byte copies across product owners
# remain forbidden.
CANONICAL_COMPILED_OWNER_GROUPS = {
    target: _compiled_product_owner(spec.owner)
    for target, spec in PRODUCTION_TARGETS.items()
    if spec.kind not in {"INTERFACE"}
}

# The same physical cold entrypoint/helper intentionally serves these exact
# sibling binaries. This grants neither copied-source ownership nor another
# target permission to compile arbitrary files from the owner directory.
SHARED_COMPILED_SOURCE_TARGETS = {
    "apps/trader/src/Process/src/Traderd/Application/NativeBindingDescription.cpp":
        frozenset({"traderd", "trader-market-observed"}),
    "apps/trader/src/Process/src/Traderd/Application/TraderdDispatchMain.cpp":
        frozenset({"traderd", "trader-market-observed"}),
    "apps/hft-parser/src/Process/src/ZcrxProbeInternals.cpp":
        frozenset({"hft-zcrx-capability-probe", "hft-zcrx-functional-probe"}),
}


def allowed_owned_source(
    normalized_source: str,
    roots: tuple[str, ...],
) -> bool:
    """Return whether a normalized repository path lies in an exact owner root."""
    return any(
        normalized_source == root.rstrip("/") or
        normalized_source.startswith(root.rstrip("/") + "/")
        for root in roots
    )

CANONICAL_EVALUATION_ROOTS = {
    **dict.fromkeys(("diagnostic_runtime", "diagnosticd"), "apps/diagnostic"),
    **dict.fromkeys(
        ("cxet_lib", "cxet_read_only_contracts"), "src/src"),
    **dict.fromkeys(
        ("trading_core_headers", "trading_core_algorithm", "trading_core_strategy"),
        "apps/trading-core",
    ),
    "trading_core_execution": "apps/trading-core",
    "capital_finance": "apps/trading-core/capital",
    **dict.fromkeys(
        ("hftp_market_client", "hftp_market_demand_client", "hft_parser_projection_client",
         "hft_parser_history_client", "hft_parser_session_client",
         "hft-parserd", "hft-algosd", "hftp_reference_storage"),
        "apps/hft-parser",
    ),
    **dict.fromkeys(
        ("hftrec_corpus_contract",), "apps/hft-recorder/src/Contracts"),
    "hftrec_json_capture": "apps/hft-recorder/src/Runtime",
    **dict.fromkeys(("hft_backtest_core",), "apps/hft-backtest"),
    **dict.fromkeys(
        ("traderd", "trader_projection_client",
         "trader_live_runtime"),
        "apps/trader",
    ),
    **dict.fromkeys(
        ("vetrond-read", "vetron_read_gateway", "vetron_read_runtime"),
        "apps/vetron"),
}
