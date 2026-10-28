"""Positive target and closure inventory for the direct-source CXET family."""

from __future__ import annotations

import re
from dataclasses import dataclass

from CMake.Policy.CmakeFamilyBenchmarkRecipe import benchmark_target_owner
from Family.Targets.CxetFamilyCompressionPolicy import COMPRESSION_EXTERNAL_LEAVES


LIBRARY_KINDS = frozenset({
    "STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE",
})

ROLE_PRODUCTION = "PRODUCTION"
ROLE_TEST = "TEST"
ROLE_BENCH = "BENCH"
ROLE_FUZZ = "FUZZ"
ROLE_CUSTOM = "CUSTOM"
ROLE_IMPORTED = "IMPORTED"
ROLE_ALIAS = "ALIAS"


@dataclass(frozen=True)
class TargetSpec:
    kind: str
    owner: str
    role: str = ROLE_PRODUCTION


def _add(
    result: dict[str, TargetSpec],
    owner: str,
    kind: str,
    names: tuple[str, ...],
    role: str = ROLE_PRODUCTION,
) -> None:
    for name in names:
        result[name] = TargetSpec(kind, owner, role)


PRODUCTION_TARGETS: dict[str, TargetSpec] = {}

_add(PRODUCTION_TARGETS, "apps/diagnostic/CMakeLists.txt", "STATIC", ("diagnostic_runtime",))
_add(PRODUCTION_TARGETS, "apps/diagnostic/CMakeLists.txt", "EXECUTABLE", ("diagnosticd",))

_add(PRODUCTION_TARGETS, "src/src/CMakeLists.txt", "STATIC", ("cxet_lib",))
_add(PRODUCTION_TARGETS, "src/src/CMakeLists.txt", "STATIC", ("cxet_resident_memory",))
_add(
    PRODUCTION_TARGETS,
    "src/src/CMakeLists.txt",
    "STATIC",
    ("cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
     "cxet_tls_certificates", "cxet_native_tls"),
)
_add(
    PRODUCTION_TARGETS,
    "src/src/CMakeLists.txt",
    "STATIC",
    ("cxet_read_only_contracts",),
)


_add(
    PRODUCTION_TARGETS,
    "apps/trading-core/CMakeLists.txt",
    "INTERFACE",
    ("trading_core_contracts", "trading_core_headers", "trading_core_algorithm"),
)
_add(
    PRODUCTION_TARGETS,
    "apps/trading-core/CMakeLists.txt",
    "STATIC",
    ("trading_core_math", "trading_core_cold_ids", "trading_core_execution", "trading_core_strategy"),
)
_add(PRODUCTION_TARGETS, "apps/trading-core/capital/CMakeLists.txt", "STATIC",
     ("capital_finance",))
# The retired Family helper has no current declarations. Its policy consumers
# receive an empty inventory; current tests are producer-proved owner suites.
TRADING_CORE_CONTRACT_TESTS: tuple[str, ...] = ()

_PARSER_LIBRARIES = {
    "hftp_public_market": "STATIC",
    "hftp_contracts": "INTERFACE",
    "hftp_client_headers": "INTERFACE",
    "hftp_market_client": "STATIC",
    "hftp_market_demand_client": "STATIC",
    "hftp_current_reference_client": "STATIC",
    "hftp_backend_headers": "INTERFACE",
    "hftp_resource": "STATIC",
    "hftp_local_data_plane": "STATIC",
    "hftp_session_private_client": "STATIC",
    "hftp_session_private_publisher": "STATIC",
    "hft_parser_session_client": "STATIC",
    "hftp_session_service": "STATIC",
    "hftp_session_native_order": "STATIC",
    "hftp_session_native_identity": "STATIC",
    "hftp_session_native_account": "STATIC",
    "hftp_sessiond_runtime": "STATIC",
    "hft_parser_projection_client": "STATIC",
    "hft_parser_reference_client": "INTERFACE",
    "hftp_projection_publisher": "STATIC",
    "hftp_reference_projection_publisher": "INTERFACE",
    "hft_parser_history_client": "STATIC",
    "hftp_ipc": "STATIC",
    "hftp_reference_ipc": "STATIC",
    "hftp_algos_public_runtime_objects": "OBJECT",
    "hftp_algos_runtime": "STATIC",
    "hftp_routing": "STATIC",
    "hftp_catalog": "STATIC",
    "hftp_transport": "STATIC",
    "hftp_reference_storage": "STATIC",
    "hftp_history": "STATIC",
    "hftp_history_service": "STATIC",
    "hftp_reference": "STATIC",
    "hftp_ingestion_common": "STATIC",
    "hftp_ingestion": "STATIC",
    "hftp_trading_ingestion": "STATIC",
    "hftp_runtime_common": "STATIC",
    "hftp_parserd_runtime": "STATIC",
    "hftp_trading_runtime": "STATIC",
}
for _name, _kind in _PARSER_LIBRARIES.items():
    _add(
        PRODUCTION_TARGETS,
        "apps/hft-parser/cmake/HftpLibraries.cmake",
        _kind,
        (_name,),
    )
_add(
    PRODUCTION_TARGETS,
    "apps/hft-parser/src/Contracts/CMakeLists.txt",
    "INTERFACE",
    ("hftp_contract_headers",),
)
_add(
    PRODUCTION_TARGETS,
    "apps/hft-parser/cmake/HftpProcesses.cmake",
    "EXECUTABLE",
    (
        "hft-public-market-catalog-dump",
        "hft-parserd",
        "hft-finam-metadata-store",
        "hft-algosd",
        "hft-resource-planner",
        "hft-zcrx-capability-probe",
        "hft-zcrx-functional-probe",
    ),
)

_add(
    PRODUCTION_TARGETS,
    "apps/hft-recorder/src/Contracts/CMakeLists.txt",
    "STATIC",
    ("hftrec_corpus_contract", "hftrec_capture_launch", "hftrec_capture_client", "hftrec_service_client"),
)
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Contracts/CMakeLists.txt", "INTERFACE",
     ("hftrec_reference_contract",))
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Service/CMakeLists.txt", "STATIC",
     ("hftrec_service",))
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Service/CMakeLists.txt", "EXECUTABLE",
     ("hft-recorderd",))
_add(PRODUCTION_TARGETS, "apps/hft-backtest/src/Research/CMakeLists.txt", "STATIC",
     ("hft_backtest_research_client", "hft_backtest_research_service"))
_add(PRODUCTION_TARGETS, "apps/hft-backtest/src/Research/CMakeLists.txt", "EXECUTABLE",
     ("hft-backtestd", "hft-backtest-tui"))
_add(PRODUCTION_TARGETS, "apps/hft-compressor/CMakeLists.txt", "STATIC",
     ("hft_compressor_core",))
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Runtime/CMakeLists.txt", "OBJECT",
     ("hftrec_json_capture",))
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Runtime/CMakeLists.txt", "STATIC",
     ("hftrec_core",))
_add(PRODUCTION_TARGETS, "apps/hft-recorder/src/Runtime/CMakeLists.txt", "INTERFACE",
     ("hftrec_recorder_api",))
_add(PRODUCTION_TARGETS, "apps/hft-compressor/CMakeLists.txt", "EXECUTABLE",
     ("hft-compressor",))
_add(PRODUCTION_TARGETS, "tools/exchange_api_probe/CMakeLists.txt", "STATIC",
     ("exchange_probe_lib",))
_add(PRODUCTION_TARGETS, "tools/exchange_api_probe/CMakeLists.txt", "EXECUTABLE",
     ("exchange-api-probe",))

_add(
    PRODUCTION_TARGETS,
    "apps/hft-backtest/CMakeLists.txt",
    "STATIC",
    ("hft_backtest_core",),
)
_add(
    PRODUCTION_TARGETS,
    "apps/hft-backtest/CMakeLists.txt",
    "EXECUTABLE",
    ("hft-backtest",),
)

_TRADER_KINDS = {
    "trader_alert_contracts": "STATIC",
    "trader_alert_bridge": "STATIC",
    "trader_alert_client": "STATIC",
    "trader_alert_observer": "STATIC",
    "trader_alert_evaluator": "STATIC",
    "trader_alert_presentation": "STATIC",
    "trader_alert_service": "STATIC",
    "trader_alert_telegram": "STATIC",
    "trader-alertd": "EXECUTABLE",
    "trader_common_contracts": "INTERFACE",
    "trader_order_contracts": "INTERFACE",
    "trader_control_contracts": "INTERFACE",
    "trader_projection_contracts": "INTERFACE",
    "trader_private_ipc": "STATIC",
    "trader_order_client": "STATIC",
    "trader_order_bootstrap_server": "STATIC",
    "trader_control_client": "STATIC",
    "trader_projection_transport_io": "STATIC",
    "trader_projection_source": "STATIC",
    "trader_projection_client": "STATIC",
    "trader_market_observe_projection_client": "STATIC",
    "trader_projection_publisher": "STATIC",
    "trader_market_observe_projection_publisher": "STATIC",
    "trader_projection_server_transport": "OBJECT",
    "trader_projection_server": "STATIC",
    "trader_market_observe_projection_server": "STATIC",
    "trader_public_analytics": "STATIC",
    "trader_market_client": "STATIC",
    "trader_market_observe_runtime": "STATIC",
    "trader_market_observe_process": "STATIC",
    "trader_live_market_client": "STATIC",
    "trader_live_market_relay": "STATIC",
    "trader_live_runtime": "STATIC",
    "trader_process_bootstrap": "STATIC",
    "trader_strategy_launch": "STATIC",
    "trader_traderd_process": "STATIC",
    "traderd": "EXECUTABLE",
    "trader-control": "EXECUTABLE",
    "trader-market-observed": "EXECUTABLE",
    "trader_source_boundary": "INTERFACE",
}
for _name, _kind in _TRADER_KINDS.items():
    _owner = (
        "apps/trader/cmake/PublicAnalytics.cmake"
        if _name == "trader_public_analytics"
        else "apps/trader/CMakeLists.txt")
    _add(PRODUCTION_TARGETS, _owner, _kind, (_name,))

_TRADER_STARTUP_OWNER = "apps/trader/tests/startup/CMakeLists.txt"
_add(PRODUCTION_TARGETS, _TRADER_STARTUP_OWNER, "OBJECT",
     ("trader_startup_network", "trader_tbank_startup_network"), ROLE_TEST)
_add(PRODUCTION_TARGETS, _TRADER_STARTUP_OWNER, "EXECUTABLE", (
    "trader_startup_fixture", "trader_startup_alert_fixture",
    "trader_startup_certificates", "trader_startup_isolation_probe",
    "trader_offline_finam_startup_process",
    "trader_tbank_startup_fixture", "trader_tbank_startup_certificates",
    "trader_offline_tbank_startup_process",
), ROLE_TEST)

_VETRON_KINDS = {
    "vetron_browser_contracts": "INTERFACE",
    "vetron_research_contracts": "INTERFACE",
    "vetron_research_bridge": "STATIC",
    "vetron_read_gateway": "STATIC",
    "vetron_read_runtime": "STATIC",
    "vetron_read_process": "STATIC",
    "vetrond-read": "EXECUTABLE",
    "vetron_read_source_boundary": "INTERFACE",
    "vetron_full_control": "STATIC",
    "vetron_full_process": "STATIC",
    "vetrond-full": "EXECUTABLE",
    "vetron_full_source_boundary": "INTERFACE",
}
for _name, _kind in _VETRON_KINDS.items():
    _add(
        PRODUCTION_TARGETS, "apps/vetron/CMakeLists.txt", _kind, (_name,))

CUSTOM_TARGETS = {
    "diagnostic-product": TargetSpec(
        "CUSTOM", "apps/diagnostic/CMakeLists.txt", ROLE_CUSTOM),
    "cxet_liburing_ep": TargetSpec(
        "CUSTOM", "src/src/CMakeLists.txt", ROLE_CUSTOM),
    "cxet_tls_x509_source": TargetSpec(
        "CUSTOM", "src/src/CMakeLists.txt", ROLE_CUSTOM),
    "trading_core_generate_strategy_registry": TargetSpec(
        "CUSTOM", "apps/trading-core/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-math-wasm": TargetSpec(
        "CUSTOM", "apps/vetron/wasm/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-frontend": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
    "trading-core-product": TargetSpec(
        "CUSTOM", "apps/trading-core/CMakeLists.txt", ROLE_CUSTOM),
    "trading-core-all": TargetSpec(
        "CUSTOM", "apps/trading-core/CMakeLists.txt", ROLE_CUSTOM),
    "hft-parser-product": TargetSpec(
        "CUSTOM", "apps/hft-parser/CMakeLists.txt", ROLE_CUSTOM),
    "hft-parser-all": TargetSpec(
        "CUSTOM", "apps/hft-parser/CMakeLists.txt", ROLE_CUSTOM),
    "hft-backtest-product": TargetSpec(
        "CUSTOM", "apps/hft-backtest/CMakeLists.txt", ROLE_CUSTOM),
    "hft-backtest-all": TargetSpec(
        "CUSTOM", "apps/hft-backtest/CMakeLists.txt", ROLE_CUSTOM),
    "hft-compressor-product": TargetSpec(
        "CUSTOM", "apps/hft-compressor/CMakeLists.txt", ROLE_CUSTOM),
    "hft-compressor-all": TargetSpec(
        "CUSTOM", "apps/hft-compressor/CMakeLists.txt", ROLE_CUSTOM),
    "exchange-probe-product": TargetSpec(
        "CUSTOM", "tools/exchange_api_probe/CMakeLists.txt", ROLE_CUSTOM),
    "exchange-probe-all": TargetSpec(
        "CUSTOM", "tools/exchange_api_probe/CMakeLists.txt", ROLE_CUSTOM),
    "trader-product": TargetSpec(
        "CUSTOM", "apps/trader/CMakeLists.txt", ROLE_CUSTOM),
    "trader-full-product": TargetSpec(
        "CUSTOM", "apps/trader/CMakeLists.txt", ROLE_CUSTOM),
    "trader-market-observe-product": TargetSpec(
        "CUSTOM", "apps/trader/CMakeLists.txt", ROLE_CUSTOM),
    "trader-all": TargetSpec(
        "CUSTOM", "apps/trader/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-read-product": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-full-control-product": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-full-product": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-product": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
    "vetron-all": TargetSpec(
        "CUSTOM", "apps/vetron/CMakeLists.txt", ROLE_CUSTOM),
}

IMPORTED_TARGETS = {
    "liburing::uring": TargetSpec(
        "STATIC", "src/src/CMakeLists.txt", ROLE_IMPORTED),
}

CANONICAL_KINDS = {
    name: PRODUCTION_TARGETS[name].kind
    for name in (
        "cxet_lib", "cxet_read_only_contracts",
        "trading_core_contracts", "trading_core_headers", "capital_finance",
        "trading_core_algorithm", "trading_core_execution",
        "trading_core_strategy",
        "hftp_market_client", "hftp_market_demand_client", "hft_parser_projection_client",
        "hft_parser_history_client", "hft_parser_session_client",
        "hft-parserd", "hft-algosd", "hftp_reference_storage",
        "hftrec_corpus_contract", "hft_backtest_core",
        "traderd",
        "trader_projection_client", "trader_live_runtime",
    )
}


OBJECT_ATTACHMENTS = {
    "trader_tbank_startup_fixture": frozenset({"trader_tbank_startup_network"}),
    "trader_tbank_startup_catalog_fixture": frozenset({"trader_tbank_startup_network"}),
    "trader_startup_fixture": frozenset({"trader_startup_network"}),
    "trader_startup_catalog_fixture": frozenset({"trader_startup_network"}),
    "trader_startup_alert_fixture": frozenset({"trader_startup_network"}),
    "trader_startup_isolation_probe": frozenset({"trader_startup_network"}),
    "hftp_algos_runtime": frozenset({
        "hftp_algos_public_runtime_objects",
    }),
    "trader_projection_server": frozenset({
        "trader_projection_server_transport",
    }),
    "trader_market_observe_projection_server": frozenset({
        "trader_projection_server_transport",
    }),
}

# Test infrastructure acquires registration only through these exact producer
# commands and dependency sets. Ordinary tests still require their own CTest.
TEST_REGISTRATION_DEPENDENCIES = {
    (_TRADER_STARTUP_OWNER, "add_dependencies", "trader_offline_tbank_startup_process"): (
        "trader_tbank_startup_fixture", "trader_tbank_startup_catalog_fixture", "trader_tbank_startup_certificates"),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_tbank_startup_fixture"): (
        "trader_tbank_startup_network",),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_tbank_startup_catalog_fixture"): (
        "trader_tbank_startup_network",),
    (_TRADER_STARTUP_OWNER, "add_dependencies", "trader_offline_finam_startup_process"): (
        "trader_startup_fixture", "trader_startup_catalog_fixture", "trader_startup_alert_fixture",
        "trader_startup_certificates", "trader_startup_isolation_probe"),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_startup_fixture"): (
        "trader_startup_network",),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_startup_catalog_fixture"): (
        "trader_startup_network",),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_startup_alert_fixture"): (
        "trader_startup_network",),
    (_TRADER_STARTUP_OWNER, "add_executable", "trader_startup_isolation_probe"): (
        "trader_startup_network",),
    ("apps/trading-core/capital/CMakeLists.txt", "target_link_libraries", "trading-core-offline-capital"): (
        "capital_planning", "trading_core_execution"),
    ("apps/trading-core/capital/CMakeLists.txt", "target_link_libraries", "capital_planning"): (
        "capital_finance",),
}

EXCLUDED_LOCAL_TARGETS = {
    _TRADER_STARTUP_OWNER: frozenset({
        "trader_startup_network", "trader_startup_fixture", "trader_startup_alert_fixture",
        "trader_startup_catalog_fixture",
        "trader_startup_certificates", "trader_startup_isolation_probe",
        "trader_offline_finam_startup_process",
        "trader_tbank_startup_network", "trader_tbank_startup_fixture",
        "trader_tbank_startup_catalog_fixture",
        "trader_tbank_startup_certificates", "trader_offline_tbank_startup_process",
    }),
    "apps/trading-core/capital/CMakeLists.txt": frozenset({
        "capital_planning",
    }),
}


APPROVED_EXTERNAL_LINK_ITEMS = COMPRESSION_EXTERNAL_LEAVES | frozenset({
    "PostgreSQL::PostgreSQL", "CURL::libcurl",
    "OpenSSL::SSL", "OpenSSL::Crypto", "Threads::Threads", "PkgConfig::NGHTTP2", "Boost::json",
    "absl::btree", "absl::flat_hash_map", "absl::flat_hash_set", "absl::hash",
    "absl::inlined_vector", "GTest::gtest", "GTest::gtest_main",
    "liburing::uring", "secp256k1", "secp256k1_precomputed", "anl",
})


REQUIRED_DIRECT_LINKS = {
    "hftp_reference_ipc": frozenset({"hftp_backend_headers", "hftp_contracts", "hftp_local_data_plane"}),
    "hftp_ipc": frozenset({"hftp_backend_headers", "hftp_contracts", "hftp_local_data_plane", "hftp_reference_ipc"}),
    "hftp_reference_storage": frozenset({"hftp_backend_headers", "hftp_contracts", "cxet_lib", "hftp_local_data_plane", "hftp_transport"}),
    "hftp_history_service": frozenset({"hftp_history", "hftp_local_data_plane", "hftp_transport"}),
    "hftp_ingestion_common": frozenset({"hftp_backend_headers", "hftp_contracts", "hftp_transport", "hftp_catalog", "hftp_routing", "cxet_lib", "hftp_public_market", "hftp_market_client"}),
    "hftp_ingestion": frozenset({"hftp_ingestion_common", "hftp_ipc"}),
    "hftp_trading_ingestion": frozenset({"hftp_ingestion_common"}),
    "hftp_runtime_common": frozenset({"hftp_backend_headers", "hftp_routing", "hftp_catalog", "hftp_public_market", "hftp_reference", "hftp_reference_ipc", "hftp_resource", "hftp_reference_storage", "hftp_history", "hftp_transport"}),
    "hftp_trading_runtime": frozenset({"hftp_runtime_common", "hftp_trading_ingestion"}),
    "diagnostic_runtime": frozenset({"cxet_lib", "cxet_read_only_contracts", "capital_finance", "trading_core_algorithm"}),
    "diagnosticd": frozenset({"diagnostic_runtime"}),
    "cxet_read_only_contracts": frozenset(),
    "cxet_lib": frozenset({"cxet_read_only_contracts", "cxet_crypto", "cxet_native_tls"}),
    "cxet_crypto": frozenset({"cxet_crypto_rsa"}),
    "cxet_crypto_rsa": frozenset(),
    "cxet_crypto_import": frozenset(),
    "cxet_tls_certificates": frozenset({"cxet_crypto_import"}),
    "cxet_native_tls": frozenset({"cxet_crypto", "cxet_tls_certificates", "cxet_resident_memory"}),
    "cxet_resident_memory": frozenset(),
    "trading_core_contracts": frozenset({"cxet_read_only_contracts"}),
    "trading_core_headers": frozenset({"trading_core_contracts", "capital_finance"}),
    "capital_finance": frozenset({"trading_core_contracts", "cxet_read_only_contracts"}),
    "trading_core_math": frozenset({"trading_core_headers", "capital_finance"}),
    "trading_core_algorithm": frozenset({"trading_core_headers", "trading_core_math"}),
    "trading_core_cold_ids": frozenset({"cxet_read_only_contracts", "trading_core_headers"}),
    "trading_core_execution": frozenset({"trading_core_math", "capital_finance", "cxet_read_only_contracts"}),
    "trading_core_strategy": frozenset({"trading_core_algorithm", "trading_core_execution"}),
    "hftp_contract_headers": frozenset({"cxet_read_only_contracts"}),
    "hftp_contracts": frozenset({"hftp_contract_headers", "cxet_lib"}),
    "hftp_client_headers": frozenset({"hftp_contract_headers"}),
    "hftp_market_client": frozenset({"hftp_client_headers", "cxet_resident_memory"}),
    "hftp_market_demand_client": frozenset({"hftp_client_headers", "hftp_local_data_plane"}),
    "hftp_current_reference_client": frozenset({"hftp_client_headers"}),
    "hftp_backend_headers": frozenset({
        "hftp_client_headers", "hftp_contracts"}),
    "hftp_session_private_client": frozenset({"hftp_client_headers", "cxet_resident_memory"}),
    "hftp_session_private_publisher": frozenset({
        "hftp_session_private_client"}),
    "hft_parser_session_client": frozenset({
        "hftp_client_headers", "hftp_session_private_client"}),
    "hftp_session_service": frozenset({"hft_parser_session_client"}),
    "hftp_session_native_order": frozenset({
        "hftp_session_service", "cxet_lib"}),
    "hftp_session_native_identity": frozenset({
        "hftp_client_headers", "cxet_lib"}),
    "hftp_session_native_account": frozenset({
        "hftp_session_service", "hftp_session_private_publisher",
        "cxet_lib"}),
    "hftp_sessiond_runtime": frozenset({
        "hftp_session_native_account", "hftp_session_native_order",
        "hftp_session_native_identity"}),
    "hft_parser_projection_client": frozenset({
        "hftp_client_headers", "hftp_local_data_plane"}),
    "hft_parser_reference_client": frozenset({
        "hft_parser_projection_client"}),
    "hftp_reference_projection_publisher": frozenset({
        "hftp_projection_publisher"}),
    "hft_parser_history_client": frozenset({
        "hftp_client_headers", "hftp_local_data_plane"}),
    "hft-parserd": frozenset({"hftp_parserd_runtime"}),
    "hft-algosd": frozenset({"hftp_algos_runtime", "hftp_resource"}),
    "hftrec_corpus_contract": frozenset({"hft_compressor_core", "cxet_read_only_contracts"}),
    "hftrec_service_client": frozenset({"hftrec_corpus_contract", "cxet_read_only_contracts"}),
    "hftrec_reference_contract": frozenset({"hftrec_corpus_contract", "hftp_contract_headers"}),
    "hftrec_service": frozenset({"hftrec_service_client", "hftrec_core",
        "hftrec_reference_contract", "hftp_current_reference_client"}),
    "hft-recorderd": frozenset({"hftrec_service"}),
    "hftrec_capture_launch": frozenset(),
    "hftrec_capture_client": frozenset({
        "hftrec_corpus_contract", "hftp_contract_headers"}),
    "hftrec_json_capture": frozenset({"hftrec_corpus_contract", "cxet_lib"}),
    "hftrec_core": frozenset({
        "hftrec_json_capture", "hftrec_corpus_contract", "hftrec_capture_launch",
        "hftrec_capture_client", "hftp_client_headers", "hftp_current_reference_client", "cxet_lib"}),
    "hftrec_recorder_api": frozenset({"hftrec_core"}),
    "hft_compressor_core": frozenset(),
    "hft-compressor": frozenset({"hft_compressor_core"}),
    "exchange_probe_lib": frozenset(),
    "exchange-api-probe": frozenset({"exchange_probe_lib", "cxet_lib"}),
    "hft_backtest_core": frozenset({
        "cxet_lib", "capital_finance", "trading_core_math", "trading_core_execution", "trading_core_algorithm",
        "trading_core_strategy", "hftrec_corpus_contract", "hftrec_reference_contract"}),
    "hft_backtest_research_client": frozenset({"cxet_read_only_contracts", "hftrec_corpus_contract"}),
    "hft_backtest_research_service": frozenset({"hft_backtest_research_client",
        "hft_backtest_core", "hftrec_service_client", "hftrec_reference_contract"}),
    "hft-backtestd": frozenset({"hft_backtest_research_service"}),
    "hft-backtest-tui": frozenset({"hft_backtest_research_client", "hftrec_service_client"}),
    "trader_common_contracts": frozenset({"trading_core_contracts"}),
    "trader_alert_contracts": frozenset({"trader_common_contracts", "hftp_contract_headers", "trading_core_headers"}),
    "trader_alert_bridge": frozenset({"trader_alert_contracts"}),
    "trader_alert_client": frozenset({"trader_alert_contracts"}),
    "trader_alert_observer": frozenset({"trader_alert_bridge", "trading_core_strategy"}),
    "trader_alert_evaluator": frozenset({
        "trader_alert_bridge", "trader_alert_observer", "trading_core_strategy"}),
    "trader_alert_presentation": frozenset({"trader_alert_contracts", "trading_core_algorithm"}),
    "trader_alert_service": frozenset({
        "trader_alert_bridge", "trader_alert_client", "trader_alert_presentation",
        "trader_alert_evaluator"}),
    "trader_alert_telegram": frozenset({
        "trader_alert_contracts", "trader_alert_presentation", "trader_alert_service", "cxet_lib"}),
    "trader-alertd": frozenset({
        "trader_alert_service", "trader_alert_telegram", "cxet_lib"}),
    "trader_order_contracts": frozenset({"trader_common_contracts"}),
    "trader_control_contracts": frozenset({"trader_order_contracts"}),
    "trader_projection_contracts": frozenset({
        "trader_common_contracts", "trading_core_headers",
        "hftp_contract_headers"}),
    "trader_private_ipc": frozenset({"cxet_read_only_contracts"}),
    "trader_order_client": frozenset({
        "trader_order_contracts", "trader_private_ipc"}),
    "trader_order_bootstrap_server": frozenset({
        "trader_order_contracts", "trader_private_ipc"}),
    "trader_control_client": frozenset({
        "trader_control_contracts", "trader_order_client", "trader_private_ipc"}),
    "trader-control": frozenset({"trader_control_client", "trader_private_ipc"}),
    "trader_projection_transport_io": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts"}),
    "trader_projection_source": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts",
        "trader_projection_transport_io"}),
    "trader_projection_client": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts",
        "trader_projection_source"}),
    "trader_market_observe_projection_client": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts",
        "trader_projection_source"}),
    "trader_projection_publisher": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts"}),
    "trader_market_observe_projection_publisher": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts"}),
    "trader_projection_server_transport": frozenset({
        "trader_projection_contracts", "cxet_read_only_contracts"}),
    "trader_projection_server": frozenset({
        "trader_projection_publisher", "trader_projection_transport_io",
        "trader_projection_server_transport"}),
    "trader_market_observe_projection_server": frozenset({
        "trader_market_observe_projection_publisher",
        "trader_projection_transport_io", "trader_projection_server_transport"}),
    "trader_public_analytics": frozenset({
        "trader_projection_contracts", "trading_core_algorithm", "trading_core_strategy",
        "hftp_contract_headers", "trader_market_client",
        "hftp_current_reference_client", "trader_alert_bridge"}),
    "trader_market_client": frozenset({"hftp_market_client", "trading_core_algorithm"}),
    "trader_market_observe_runtime": frozenset({
        "trader_public_analytics", "trader_market_client",
        "cxet_read_only_contracts"}),
    "trader_market_observe_process": frozenset({
        "trader_market_observe_runtime",
        "trader_market_observe_projection_server", "trader_live_market_relay",
        "hftp_trading_runtime"}),
    "trader_live_market_client": frozenset({"hft_parser_projection_client"}),
    "trader_live_market_relay": frozenset({"hft_parser_projection_client"}),
    "trader_live_runtime": frozenset({
        "trader_common_contracts", "trader_order_contracts",
        "trader_projection_contracts",
        "trading_core_cold_ids", "trading_core_math",
        "trading_core_strategy", "hft_parser_session_client"}),
    "trader_process_bootstrap": frozenset({
        "trader_common_contracts", "cxet_read_only_contracts", "trading_core_algorithm", "cxet_lib", "hftp_contract_headers"}),
    "trader_strategy_launch": frozenset({
        "trader_process_bootstrap", "trading_core_strategy"}),
    "trader_traderd_process": frozenset({
        "trader_process_bootstrap", "trader_live_runtime",
        "trader_market_client", "trader_order_bootstrap_server",
        "hft_parser_session_client",
        "trader_projection_server", "hftp_trading_runtime",
        "hft_parser_reference_client", "trader_alert_observer", "trader_public_analytics",
        "hftp_sessiond_runtime"}),
    "traderd": frozenset({"trader_traderd_process"}),
    "trader-market-observed": frozenset({
        "trader_market_observe_process", "trader_process_bootstrap", "hftp_trading_runtime"}),
    "trader_startup_network": frozenset({"cxet_lib"}),
    "trader_startup_fixture": frozenset({"trader_traderd_process", "trader_startup_network"}),
    "trader_startup_catalog_fixture": frozenset({
        "hftp_public_market", "hftp_reference", "hftp_ingestion", "hftp_runtime_common", "trader_startup_network"}),
    "trader_startup_alert_fixture": frozenset({
        "trader_alert_service", "trader_alert_telegram", "cxet_lib", "trader_startup_network"}),
    "trader_startup_certificates": frozenset(),
    "trader_startup_isolation_probe": frozenset({"cxet_lib", "trader_startup_network"}),
    "trader_offline_finam_startup_process": frozenset({"trader_projection_client"}),
    "trader_tbank_startup_network": frozenset({"cxet_lib"}),
    "trader_tbank_startup_fixture": frozenset({"trader_traderd_process", "trader_tbank_startup_network"}),
    "trader_tbank_startup_catalog_fixture": frozenset({
        "hftp_public_market", "hftp_reference", "hftp_ingestion", "hftp_runtime_common", "trader_tbank_startup_network"}),
    "trader_tbank_startup_certificates": frozenset(),
    "trader_offline_tbank_startup_process": frozenset({"trader_projection_client"}),
    "vetron_browser_contracts": frozenset({"cxet_read_only_contracts"}),
    "vetron_research_contracts": frozenset(),
    "vetron_research_bridge": frozenset({"vetron_read_gateway",
        "hftrec_service_client", "hft_backtest_research_client"}),
    "vetron_read_gateway": frozenset({
        "vetron_browser_contracts", "vetron_research_contracts", "cxet_read_only_contracts"}),
    "vetron_read_runtime": frozenset({
        "vetron_read_gateway", "hft_parser_projection_client",
        "hft_parser_history_client",
        "hftp_market_demand_client",
        "trader_live_market_client", "trader_market_observe_projection_client"}),
    "vetron_read_process": frozenset({"vetron_read_runtime", "vetron_research_bridge"}),
    "vetrond-read": frozenset({"vetron_read_process"}),
    "vetron_read_source_boundary": frozenset({
        "vetron_read_process", "hft_parser_projection_client",
        "hft_parser_history_client",
        "trader_live_market_client", "trader_market_observe_projection_client"}),
    "vetron_full_control": frozenset({
        "vetron_read_gateway", "trader_control_client"}),
    "vetron_full_process": frozenset({
        "vetron_read_runtime", "vetron_full_control"}),
    "vetrond-full": frozenset({"vetron_full_process"}),
    "vetron_full_source_boundary": frozenset({
        "vetron_full_process", "hft_parser_projection_client",
        "hft_parser_history_client",
        "trader_market_observe_projection_client", "trader_control_client"}),
}

# Current Parser process/backend composition. Public producer clients retain
# their independent terminal-capability deny-list below.
_PARSER_PROCESS_CLOSURE = frozenset({
    "hftp_parserd_runtime", "hftp_runtime_common", "hftp_ingestion_common",
    "hftp_routing", "hftp_catalog", "hftp_ingestion",
    "hftp_public_market", "hftp_reference", "hftp_resource", "hftp_reference_storage", "hftp_history",
    "hftp_transport", "hftp_backend_headers", "hftp_contracts", "hftp_ipc",
    "hftp_reference_ipc", "hftp_history_service",
    "hftp_market_client", "hftp_algos_runtime", "hftp_algos_public_runtime_objects",
    "hftp_projection_publisher", "hft_parser_projection_client",
    "hftp_local_data_plane", "hftp_client_headers", "hftp_contract_headers",
    "cxet_lib", "cxet_read_only_contracts",
})

# Embedded targets have no standalone publisher/service closure. Reference
# snapshots and archive computation remain real producer-owned dependencies.
_TRADING_PARSER_PROCESS_CLOSURE = (_PARSER_PROCESS_CLOSURE - {
    "hftp_parserd_runtime", "hftp_ingestion", "hftp_ipc", "hftp_history_service",
    "hftp_algos_runtime", "hftp_algos_public_runtime_objects", "hftp_projection_publisher",
    "hft_parser_projection_client",
}) | {"hftp_trading_runtime", "hftp_trading_ingestion"}

# These internal process owners execute Parser public market work. This exact
# composition may carry the monolithic Core archive, but never account/order
# clients or a Full runtime. It is not the consumer-visible Observe boundary.
_TRADER_PUBLIC_PROCESS_CLOSURE = frozenset({
    "trader_market_observe_process", "trader_market_observe_runtime",
    "trader_market_observe_projection_server", "trader_market_observe_projection_publisher",
    "trader_projection_transport_io", "trader_projection_server_transport",
    "trader_projection_contracts", "trader_common_contracts",
    "trader_live_market_relay", "hft_parser_projection_client",
    "trader_public_analytics", "trader_market_client",
    "trader_alert_contracts", "trader_alert_bridge", "hftp_current_reference_client",
    "hftp_client_headers", "hftp_contract_headers", "hftp_local_data_plane",
    "cxet_read_only_contracts", "trading_core_algorithm", "trading_core_headers", "trading_core_contracts",
    "trading_core_math", "trading_core_execution", "trading_core_strategy", "capital_finance",
}) | _TRADING_PARSER_PROCESS_CLOSURE

EXACT_TRANSITIVE_CLOSURES = {
    "trader_live_runtime": frozenset({
        'capital_finance',
        'cxet_read_only_contracts',
        'hft_parser_session_client',
        'hftp_client_headers',
        'hftp_contract_headers',
        'hftp_session_private_client',
        'trader_common_contracts',
        'trader_live_runtime',
        'trader_order_contracts',
        'trader_projection_contracts',
        'trading_core_algorithm',
        'trading_core_cold_ids',
        'trading_core_contracts',
        'trading_core_execution',
        'trading_core_headers',
        'trading_core_math',
        'trading_core_strategy',
    }),
    "hft_backtest_core": frozenset({
        'capital_finance',
        'cxet_lib',
        'cxet_read_only_contracts',
        'hft_backtest_core',
        'hft_compressor_core',
        'hftrec_corpus_contract',
        'trading_core_algorithm',
        'trading_core_contracts',
        'trading_core_execution',
        'trading_core_headers',
        'trading_core_math',
        'trading_core_strategy',
    }),
    "hft-parserd": _PARSER_PROCESS_CLOSURE | {"hft-parserd"},
    "hft-algosd": frozenset({
        "hft-algosd", "hftp_algos_runtime", "hftp_algos_public_runtime_objects",
        "hftp_ipc", "hftp_reference_ipc", "hftp_backend_headers",
        "hftp_contracts",
        "hftp_projection_publisher", "hft_parser_projection_client",
        "hftp_local_data_plane", "hftp_resource", "hftp_client_headers",
        "hftp_contract_headers", "cxet_lib", "cxet_read_only_contracts"}),
    "trader_market_observe_process": _TRADER_PUBLIC_PROCESS_CLOSURE,
    "trader-market-observed": _TRADER_PUBLIC_PROCESS_CLOSURE | {
        "trader-market-observed", "trader_process_bootstrap"},
    "trader_traderd_process": frozenset({
        'capital_finance',
        'hft_parser_reference_client',
        'hft_parser_projection_client',
        'hft_parser_session_client',
        'hftp_current_reference_client',
        'hftp_session_native_account',
        'hftp_session_native_identity',
        'hftp_session_native_order',
        'hftp_session_private_client',
        'hftp_session_private_publisher',
        'hftp_session_service',
        'hftp_sessiond_runtime',
        'trader_alert_bridge',
        'trader_alert_contracts',
        'trader_alert_observer',
        'trader_common_contracts',
        'trader_live_runtime',
        'trader_market_client',
        'trader_order_bootstrap_server',
        'trader_order_contracts',
        'trader_private_ipc',
        'trader_process_bootstrap',
        'trader_projection_contracts',
        'trader_projection_publisher',
        'trader_projection_server',
        'trader_projection_server_transport',
        'trader_projection_transport_io',
        'trader_public_analytics',
        'trader_traderd_process',
        'trading_core_algorithm',
        'trading_core_cold_ids',
        'trading_core_contracts',
        'trading_core_execution',
        'trading_core_headers',
        'trading_core_math',
        'trading_core_strategy',
    }) | _TRADING_PARSER_PROCESS_CLOSURE,
    "vetron_read_runtime": frozenset({
        'capital_finance',
        'cxet_read_only_contracts',
        'hft_parser_history_client',
        'hft_parser_projection_client',
        'hftp_client_headers',
        'hftp_contract_headers',
        'hftp_local_data_plane',
        'hftp_market_demand_client',
        'trader_common_contracts',
        'trader_live_market_client',
        'trader_market_observe_projection_client',
        'trader_projection_contracts',
        'trader_projection_source',
        'trader_projection_transport_io',
        'trading_core_contracts',
        'trading_core_headers',
        'vetron_browser_contracts',
        'vetron_read_gateway',
        'vetron_read_runtime',
    }),
    "vetrond-read": frozenset({
        'capital_finance',
        'cxet_read_only_contracts',
        'hft_parser_history_client',
        'hft_parser_projection_client',
        'hftp_client_headers',
        'hftp_contract_headers',
        'hftp_local_data_plane',
        'hftp_market_demand_client',
        'trader_common_contracts',
        'trader_live_market_client',
        'trader_market_observe_projection_client',
        'trader_projection_contracts',
        'trader_projection_source',
        'trader_projection_transport_io',
        'trading_core_contracts',
        'trading_core_headers',
        'vetron_browser_contracts',
        'vetron_read_gateway',
        'vetron_read_process',
        'vetron_read_runtime',
        'vetrond-read',
    }),
    "vetron_full_control": frozenset({
        'cxet_read_only_contracts',
        'trader_common_contracts',
        'trader_control_client',
        'trader_control_contracts',
        'trader_order_client',
        'trader_order_contracts',
        'trader_private_ipc',
        'trading_core_contracts',
        'vetron_browser_contracts',
        'vetron_full_control',
        'vetron_read_gateway',
    }),
    "vetrond-full": frozenset({
        'capital_finance',
        'cxet_read_only_contracts',
        'hft_parser_history_client',
        'hft_parser_projection_client',
        'hftp_client_headers',
        'hftp_contract_headers',
        'hftp_local_data_plane',
        'hftp_market_demand_client',
        'trader_common_contracts',
        'trader_control_client',
        'trader_control_contracts',
        'trader_live_market_client',
        'trader_market_observe_projection_client',
        'trader_order_client',
        'trader_order_contracts',
        'trader_private_ipc',
        'trader_projection_contracts',
        'trader_projection_source',
        'trader_projection_transport_io',
        'trading_core_contracts',
        'trading_core_headers',
        'vetron_browser_contracts',
        'vetron_full_control',
        'vetron_full_process',
        'vetron_read_gateway',
        'vetron_read_runtime',
        'vetrond-full',
    }),
}
EXACT_TRANSITIVE_CLOSURES["traderd"] = (
    EXACT_TRANSITIVE_CLOSURES["trader_traderd_process"] | {"traderd"})
EXACT_TRANSITIVE_CLOSURES["capital_finance"] = frozenset({'capital_finance', 'cxet_read_only_contracts', 'trading_core_contracts'})
EXACT_TRANSITIVE_CLOSURES["hftp_market_demand_client"] = frozenset({'cxet_read_only_contracts', 'hftp_client_headers', 'hftp_contract_headers', 'hftp_local_data_plane', 'hftp_market_demand_client'})


# Production Core now carries exactly the native provider closure. Public
# transport-free roots keep their existing independent deny-list below.
_NATIVE_CRYPTO_CLOSURE = frozenset({
    "cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
    "cxet_tls_certificates", "cxet_native_tls",
})
EXACT_TRANSITIVE_CLOSURES = {
    owner: closure | _NATIVE_CRYPTO_CLOSURE if "cxet_lib" in closure else closure
    for owner, closure in EXACT_TRANSITIVE_CLOSURES.items()
}
EXACT_TRANSITIVE_CLOSURES.update({
    "cxet_crypto": frozenset({"cxet_crypto", "cxet_crypto_rsa"}),
    "cxet_crypto_rsa": frozenset({"cxet_crypto_rsa"}),
    "cxet_crypto_import": frozenset({"cxet_crypto_import"}),
    "cxet_tls_certificates": frozenset({"cxet_tls_certificates", "cxet_crypto_import"}),
    "cxet_native_tls": _NATIVE_CRYPTO_CLOSURE,
})
EXACT_TRANSITIVE_CLOSURES = {
    owner: closure | {"cxet_resident_memory"}
    if closure & {"cxet_native_tls", "hftp_market_client", "hftp_session_private_client"}
    else closure
    for owner, closure in EXACT_TRANSITIVE_CLOSURES.items()
}
EXACT_TRANSITIVE_CLOSURES["cxet_resident_memory"] = frozenset({"cxet_resident_memory"})


# These diagnostic/read-only roots may gain new bounded helper targets only
# after review, but no policy update may ever make the monolithic terminal
# CXET runtime reachable from them. This semantic deny-list is intentionally
# independent of the positive exact-closure inventory above.
FORBIDDEN_TRANSITIVE_TARGETS = {
    root: frozenset({
        "cxet_lib", "cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
        "cxet_tls_certificates", "cxet_native_tls",
        "hftp_contracts", "hftp_backend_headers",
        "hftp_transport", "hftp_public_market", "hftp_routing",
        "hftp_ingestion_common", "hftp_runtime_common", "hftp_ingestion", "hftp_parserd_runtime", "hftp_trading_ingestion", "hftp_trading_runtime", "hft-parserd",
    })
    for root in (
        "cxet_read_only_contracts",
        "trading_core_headers",
        "capital_finance",
        "trading_core_algorithm",
        "trading_core_execution",
        "trading_core_strategy",
        "hftp_contract_headers",
        "hftp_client_headers",
        "hftp_market_client",
        "hftp_market_demand_client",
        "hftp_current_reference_client",
        "hft_parser_session_client",
        "hftp_session_private_client",
        "hftp_session_private_publisher",
        "hftp_local_data_plane",
        "hft_parser_execution_client",
        "hft_parser_reference_client",
        "hftp_execution_publisher",
        "hft_parser_projection_client",
        "hftp_projection_publisher",
        "hftp_reference_projection_publisher",
        "hft_parser_history_client",
        "trader_common_contracts",
        "trader_private_contracts",
        "trader_order_contracts",
        "trader_control_contracts",
        "trader_private_capacity",
        "trader_private_ipc",
        "trader_private_client",
        "trader_private_publisher",
        "trader_account_fixture",
        "trader-accountd",
        "trader_projection_contracts",
        "trader_projection_transport_io",
        "trader_projection_source",
        "trader_projection_client",
        "trader_market_observe_projection_client",
        "trader_projection_publisher",
        "trader_market_observe_projection_publisher",
        "trader_projection_server",
        "trader_market_observe_projection_server",
        "trader_market_observe_runtime",
        "trader_live_runtime",
        "trader_source_boundary",
        "vetron_browser_contracts",
        "vetron_read_gateway",
        "vetron_read_runtime",
        "vetron_read_process",
        "vetrond-read",
        "vetron_read_source_boundary",
        "vetron_full_control",
        "vetron_full_process",
        "vetrond-full",
        "vetron_full_source_boundary",
    )
}

# Only the two internal public process compositions above may execute Parser
# public/backend work. Core includes terminal implementation units; archive
# membership alone neither grants account/order authority nor proves its
# absence. Deny the concrete private/order/control/Full ownership edges while
# retaining the blanket backend ban for ObserveRuntime, clients and Vetron.
# This producer is internal: it deliberately exports its backend publisher
# header. Public/private clients retain the physical backend-root fence and
# cannot acquire the producer transitively. Its terminal link deny-list above
# remains enforced independently.
TRANSPORT_FREE_TARGETS = frozenset(FORBIDDEN_TRANSITIVE_TARGETS) - {
    "hftp_session_private_publisher"}
_PUBLIC_PROCESS_AUTHORITY_DENIALS = frozenset({
    "hft_parser_session_client", "hftp_session_private_client",
    "hftp_session_private_publisher", "hftp_session_service",
    "hftp_session_native_account", "hftp_session_native_order",
    "hftp_session_native_identity", "hftp_sessiond_runtime",
    "trader_private_contracts", "trader_private_capacity", "trader_private_ipc",
    "trader_private_client", "trader_private_publisher", "trader_account_fixture",
    "trader_accountd_process", "trader-accountd", "trader_order_contracts",
    "trader_order_client", "trader_order_bootstrap_server", "trader_control_contracts",
    "trader_control_client", "trader_profile_persistence",
    "trader_live_runtime", "trader_traderd_process", "trader_source_boundary",

})
FORBIDDEN_TRANSITIVE_TARGETS.update({
    "trader_market_observe_process": _PUBLIC_PROCESS_AUTHORITY_DENIALS,
    "trader-market-observed": _PUBLIC_PROCESS_AUTHORITY_DENIALS,
})

# Read-only consumers also stay independent of the scenario/planning graph.
# The product-edge role gate rejects production links to those test targets.
for _name in tuple(FORBIDDEN_TRANSITIVE_TARGETS):
    FORBIDDEN_TRANSITIVE_TARGETS[_name] |= {
        "capital_planning"}
FORBIDDEN_TRANSITIVE_TARGETS["capital_finance"] |= {
    "trading_core_algorithm", "trading_core_math", "trading_core_execution",
    "trading_core_strategy",
}


_DYNAMIC_ROLES = (
    ("apps/trading-core", re.compile(
        r"trading-core-bbo-reconstruction-tests$"), ROLE_TEST),
    ("src/tests", re.compile(r"[a-z][a-z0-9_]*_tests$"), ROLE_TEST),
    ("src/tests", re.compile(r"cxet_fuzz_[a-z0-9_]+$"), ROLE_FUZZ),
    ("apps/hft-parser", re.compile(
        r"hft-parser-(?:[a-z0-9_-]+-contract-tests|"
        r"market-history-worker-stall-tests)$"), ROLE_TEST),
    ("apps/hft-parser", re.compile(r"hft-parser-public-market-v2-fuzz$"), ROLE_FUZZ),
    ("apps/hft-parser", re.compile(r"hft-parser-(?:bench|delivery-basis-bench)$"), ROLE_BENCH),
    ("apps/hft-backtest", re.compile(r"hft-backtest-[a-z0-9-]+-tests$"), ROLE_TEST),
    ("apps/trader", re.compile(
        r"(?:trader-[a-z0-9-]+-contract-tests|"
        r"finam_live_recovery_contract_tests)$"), ROLE_TEST),
    ("apps/vetron", re.compile(
        r"vetron_(?:backend|gateway_queue|history_focus|reference_status|loopback)_contract_tests$"),
     ROLE_TEST),
    ("src/tests", re.compile(r"cxet-family-(?:strategy-differential|public-execution-contract)$"), ROLE_TEST),
)


ROLE_SOURCE_ROOTS = {
    ("src/benchmarks", ROLE_BENCH): ("src/benchmarks",),
    ("apps/diagnostic", ROLE_TEST): ("apps/diagnostic/tests/offline",),
    ("src/tests", ROLE_TEST): ("src/tests",),
    ("src/tests", ROLE_FUZZ): ("src/tests",),
    ("apps/hft-parser", ROLE_TEST): (
        'apps/hft-parser/tests/Parser', "apps/hft-parser/benchmarks",
        "apps/hft-parser/tests/offline"),
    ("apps/hft-parser", ROLE_FUZZ): ('apps/hft-parser/benchmarks/Fuzz',),
    ("apps/hft-parser", ROLE_BENCH): ("apps/hft-parser/benchmarks",),
    ("apps/trading-core", ROLE_TEST): ("apps/trading-core/tests",),
    ("apps/trading-core", ROLE_BENCH): ("apps/trading-core/benchmarks",),
    ("apps/hft-backtest", ROLE_TEST): ("apps/hft-backtest/tests",),
    ("apps/trader", ROLE_TEST): ("apps/trader/tests",),
    ("apps/trader", ROLE_BENCH): ("apps/trader/benchmarks",),
    ("apps/vetron", ROLE_TEST): ("apps/vetron/tests",),
    ("apps/hft-recorder", ROLE_TEST): ("apps/hft-recorder/tests/offline",),
    ("apps/hft-compressor", ROLE_TEST): ("apps/hft-compressor/tests/offline",),
    ("tools/exchange_api_probe", ROLE_TEST): ("tools/exchange_api_probe/tests/offline",),
}

ROLE_SOURCE_EXCEPTIONS = {
    ("trader_startup_catalog_fixture", _TRADER_STARTUP_OWNER): frozenset({
        "apps/trader/tests/startup/StartupResidentMemory.cpp",
        "apps/hft-parser/src/Process/src/PublicMarketCatalogDumpMain.cpp",
        "apps/hft-parser/src/Process/src/PublicMarketCatalogDescription.cpp",
        "apps/hft-parser/src/Process/src/PortableCatalogCapture.cpp",
    }),
    ("trader_tbank_startup_catalog_fixture", _TRADER_STARTUP_OWNER): frozenset({
        "apps/trader/tests/startup/StartupResidentMemory.cpp",
        "apps/hft-parser/src/Process/src/PublicMarketCatalogDumpMain.cpp",
        "apps/hft-parser/src/Process/src/PublicMarketCatalogDescription.cpp",
        "apps/hft-parser/src/Process/src/PortableCatalogCapture.cpp",
    }),
    ("trader_tbank_startup_fixture", _TRADER_STARTUP_OWNER): frozenset({
        "apps/trader/src/Process/src/Traderd/Application/TraderdDispatchMain.cpp",
        "apps/trader/src/Process/src/Traderd/Application/NativeBindingDescription.cpp",
    }),
    ("trader_startup_fixture", _TRADER_STARTUP_OWNER): frozenset({
        "apps/trader/src/Process/src/Traderd/Application/TraderdDispatchMain.cpp",
        "apps/trader/src/Process/src/Traderd/Application/NativeBindingDescription.cpp",
    }),
    ("trader_startup_alert_fixture", _TRADER_STARTUP_OWNER): frozenset({
        "apps/trader/alerts/src/Main.cpp",
    }),
    ("capital_planning", "apps/trading-core/capital/CMakeLists.txt"): frozenset({
        "apps/trading-core/capital/src/Planning/Dp.cpp",
        "apps/trading-core/capital/src/Planning/Market.cpp",
        "apps/trading-core/capital/src/Planning/Graph.cpp",
        "apps/trading-core/capital/src/Planning/AccountDp.cpp",
    }),
    ("trading-core-offline-capital", "apps/trading-core/capital/CMakeLists.txt"): frozenset({
        "apps/trading-core/capital/tests/offline/OfflineCases.cpp",
        "apps/trading-core/capital/tests/offline/Planning/DpTests.cpp",
        "apps/trading-core/capital/tests/offline/Planning/MarketTests.cpp",
        "apps/trading-core/capital/tests/offline/Planning/PlanningTests.cpp",
        "apps/trading-core/capital/tests/offline/Risk/PairAssessmentTests.cpp",
        "apps/trading-core/capital/tests/offline/Planning/AccountDpTests.cpp",
        "apps/trading-core/capital/tests/offline/Budget/QuotaProjectionTests.cpp",
        "apps/trading-core/capital/tests/offline/Budget/CapitalBudgetTests.cpp",
        "apps/trading-core/capital/tests/offline/Accounting/AccountCostsTests.cpp",
        "apps/trading-core/capital/tests/offline/Accounting/CanonicalSettlementTests.cpp",
        "apps/trading-core/capital/tests/offline/Decision/StandardPairTests.cpp",
    }),
}


def dynamic_target_spec(name: str, owner_root: str | None, origin: str) -> TargetSpec | None:
    if (owner_root == "apps/trader" and origin == _TRADER_STARTUP_OWNER and
            name in {"trader_startup_catalog_fixture", "trader_tbank_startup_catalog_fixture"}):
        return TargetSpec("EXECUTABLE", origin, ROLE_TEST)
    if benchmark_target_owner(name, origin) is not None:
        expected_root = "src/benchmarks" if origin.startswith("src/") else "/".join(origin.split("/")[:2])
        if owner_root == expected_root:
            return TargetSpec("EXECUTABLE", origin, ROLE_BENCH)
    if (owner_root == "apps/trading-core" and
            origin == "apps/trading-core/capital/CMakeLists.txt"):
        if name == "capital_planning":
            return TargetSpec("STATIC", origin, ROLE_TEST)
        if name == "trading-core-offline-capital":
            return TargetSpec("EXECUTABLE", origin, ROLE_TEST)
    if owner_root == "apps/trading-core" and (
            origin == "apps/trading-core/tests/offline/Math/CMakeLists.txt" and name == "trading-core-math-tests" or
            origin == "apps/trading-core/tests/offline/Execution/CMakeLists.txt" and name in {
                "trading-core-execution-tests", "trader-execution-adapter-tests", }):
        return TargetSpec("EXECUTABLE", origin, ROLE_TEST)
    # The current offline producer and each physical registration/source are
    # proved before their declarations reach this registry.
    if (origin == "src/tests/offline/CMakeLists.txt" and owner_root == "src/tests" or
            origin == f"{owner_root}/tests/offline/CMakeLists.txt" and
            owner_root in {"apps/trading-core", "apps/hft-parser", "apps/hft-backtest",
                           "apps/trader", "apps/vetron", "apps/hft-recorder",
                           "apps/hft-compressor", "apps/diagnostic", "tools/exchange_api_probe"}):
        return TargetSpec("EXECUTABLE", origin, ROLE_TEST)
    for expected_owner, pattern, role in _DYNAMIC_ROLES:
        if owner_root == expected_owner and pattern.fullmatch(name):
            return TargetSpec("EXECUTABLE", origin, role)
    return None


def target_spec(name: str, owner_root: str | None, origin: str) -> TargetSpec | None:
    return (
        PRODUCTION_TARGETS.get(name) or CUSTOM_TARGETS.get(name) or
        IMPORTED_TARGETS.get(name) or dynamic_target_spec(
            name, owner_root, origin)
    )

for _root in ("traderd", "trader_traderd_process", "trader_market_observe_process", "trader-market-observed"):
    FORBIDDEN_TRANSITIVE_TARGETS[_root] = FORBIDDEN_TRANSITIVE_TARGETS.get(_root, frozenset()) | frozenset({
        "hftp_parserd_runtime", "hftp_ingestion", "hftp_ipc", "hftp_history_service",
        "hftp_algos_runtime", "hftp_algos_public_runtime_objects", "hftp_projection_publisher",
        "hft-parserd", "hft-algosd", "hft-resource-planner",
    })
