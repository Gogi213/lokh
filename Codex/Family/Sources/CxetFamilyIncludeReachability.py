"""Compiler-effective, path-aware include reachability for the CXET family."""

from __future__ import annotations

from Family.Sources.CxetFamilySourcePolicy import (
    benchmark_translation_unit_context,
    native_crypto_include_edge, native_crypto_textual_source, native_crypto_include_data, native_crypto_config_bindings,
    native_crypto_owner, NATIVE_CRYPTO_VENDOR_INCLUDES,
    benchmark_include_edge, benchmark_backend_include_edge, benchmark_external_include,
)
from Family.Sources.CxetFamilyIncludeInputs import IncludeInputs, native_include_context
from Family.Sources.CxetFamilyOfflineSourcePolicy import (
    offline_source_registrations, offline_public_header_edge,
    offline_private_header_edge, offline_external_include,
)
from Family.Sources.CxetFamilyNativeInputs import (
    NativeInputs, native_syntax_data, native_external_include, native_test_configuration_error,
)

from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from CMake.Flow.CmakeFamilyFlow import (
    NO_PATHS,
    PathSet,
    bounded_merge,
    paths_cover,
)
from CMake.Policy.CmakeFamilyIncludeDirectories import target_include_groups
from CMake.Flow.CmakeFamilyState import normalize_synthetic_binary_path
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from Family.Targets.CxetFamilyAliasPolicy import canonical_target
from Family.Sources.CxetFamilyCppPolicy import (
    CPP_NON_TEXTUAL_INCLUDE_SUFFIXES,
    CPP_SCAN_SUFFIXES,
    CPP_TEXTUAL_INCLUDE_SUFFIXES,
    approved_external_angle_include,
    cpp_include_syntax,
)
from Family.Targets.CxetFamilyMayMustGraph import (
    MUST,
    parse_link_values,
    single_expanded_target_argument,
)
from Family.Sources.CxetFamilyHeaderContract import (
    compiler_visible_header_inventory,
    exported_header_targets,
    logical_header_owner,
    source_artifact_path,
)
from Family.Sources.CxetFamilyHeaderApiPolicy import (
    API_HEADER_OWNERS,
    canonical_api_headers, finance_leaf_include, experimental_api_available,
    vetron_full_api_available,
    parser_process_include, private_composition_include,
)
from Family.Targets.CxetFamilyOwnershipPolicy import TARGET_OWNERS
from Family.Targets.CxetFamilyBuildPolicy import BENCHMARK_INCLUDE_CONTRACTS
from Family.Targets.CxetFamilyCompressionPolicy import (
    COMPRESSION_HEADER_PROVIDERS, compression_link_values, compression_include_provider,
    COMPRESSOR_CMAKE, compression_conditional_include, compression_feature_mutation,
    compression_translation_unit_context,
)
from Family.Targets.CxetFamilyTargetInventory import (
    APPROVED_EXTERNAL_LINK_ITEMS,
    TRANSPORT_FREE_TARGETS,
    target_spec,
)
from Family.Targets.CxetFamilyTargetPolicy import (
    normalize_repo_include,
    verification_include_allowed,
    verification_unresolved_quoted_include,
    verification_unresolved_quoted_requirement,
)


_LINK_SCOPES = frozenset({
    "INTERFACE", "LINK_PRIVATE", "LINK_PUBLIC", "PRIVATE", "PUBLIC",
})
_COMPILE_LINK_SCOPES = frozenset({
    "LINK_PRIVATE", "LINK_PUBLIC", "PRIVATE", "PUBLIC",
})
_INTERFACE_LINK_SCOPES = frozenset({"INTERFACE", "LINK_PUBLIC", "PUBLIC"})
_FIRST_PARTY_PREFIXES = ("apps/", "src/", "tools/")
_TRADING_CORE_GENERATED = (
    "__CXET_CMAKE_BINARY__/apps/trading-core/generated")
_PARSER_BACKEND_INCLUDES = (
    "apps/hft-parser/src/Runtime/include",
    "apps/hft-parser/src/Process/include",
)
_PARSER_CLIENT_INCLUDE = "apps/hft-parser/src/Clients/include"
_CORE_CONTRACT_INCLUDE = "src/src/Contracts/include"
_CORE_PUBLIC_INCLUDE = "src/src/Core/include"
_CORE_PRIVATE_INCLUDE = "src/src/Core/src"
_CORE_PRIVATE_NESTED_INCLUDE = "src/src/Core/src/Private"
_READ_ONLY_FORBIDDEN_INCLUDE_ROOTS = (
    _CORE_PUBLIC_INCLUDE,
    _CORE_PRIVATE_INCLUDE,
    _CORE_PRIVATE_NESTED_INCLUDE,
    *_PARSER_BACKEND_INCLUDES,
)

# Reviewed current direct include surfaces retain exact order and visibility.
# These literals are independent of the observed mutation stream.
_EXACT_DIRECT_INCLUDE_ORDER = {
    'cxet_resident_memory': (
        ('PUBLIC', 'src/src/Contracts/include'),
    ),
    'cxet_crypto': (
        ('PUBLIC', 'src/src/Core/include'), ('PUBLIC', 'src/src/Contracts/include'),
        ('PRIVATE', 'extra/hacl-star/dist/gcc-compatible'),
        ('PRIVATE', 'extra/hacl-star/dist/karamel/include'),
        ('PRIVATE', 'extra/hacl-star/dist/karamel/krmllib/dist/minimal'),
        ('PRIVATE', 'cmake/Vendor/xkcp'), ('PRIVATE', 'extra/xkcp'),
        ('PRIVATE', 'extra/xkcp/lib/common'), ('PRIVATE', 'extra/xkcp/lib/high/Keccak'),
        ('PRIVATE', 'extra/xkcp/lib/low/KeccakP-1600/ref-64bits'),
        ('PRIVATE', 'src/src/Core/src/Crypto'),
        ('PRIVATE', 'extra/mbedtls-cold/include'), ('PRIVATE', 'extra/mbedtls-cold/library'),
    ),
    'cxet_crypto_rsa': (
        ('PRIVATE', 'src/src/Core/src/Crypto'),
        ('PRIVATE', 'extra/mbedtls-cold/include'), ('PRIVATE', 'extra/mbedtls-cold/library'),
    ),
    'cxet_crypto_import': (
        ('PUBLIC', 'extra/mbedtls-cold/include'),
        ('PUBLIC', 'cmake/Vendor/mbedtls-cold'), ('PUBLIC', 'extra/mbedtls-cold'),
    ),
    'cxet_tls_certificates': (('PRIVATE', 'extra/mbedtls-cold/library'),),
    'cxet_native_tls': (
        ('PUBLIC', 'src/src/Core/include'), ('PUBLIC', 'src/src/Contracts/include'),
    ),
    'diagnostic_runtime': (('PUBLIC', 'apps/diagnostic/include'),),
    'cxet_read_only_contracts': (
        ('PUBLIC', 'src/src/Contracts/include'),
    ),
    'cxet_lib': (
        ('PUBLIC', 'src/src/Core/include'),
        ('PUBLIC', 'src/src/Contracts/include'),
        ('PRIVATE', 'src/src/Core/src'),
        ('PRIVATE', 'src/src/Core/src/Private'),
    ),
    'trading_core_headers': (
        ('INTERFACE', 'apps/trading-core/src/Core/include'),
    ),
    'capital_finance': (
        ('PUBLIC', 'apps/trading-core/capital/include'),
    ),
    'trading_core_math': (),
    'trading_core_algorithm': (),
    'trading_core_execution': (
        ('PUBLIC', 'apps/trading-core/src/Core/include'),
    ),
    'trading_core_cold_ids': (
        ('PUBLIC', 'apps/trading-core/src/Cold/include'),
    ),
    'trading_core_strategy': (
        ('PUBLIC', 'apps/trading-core/src/Strategy/include'),
        ('PUBLIC', '__CXET_CMAKE_BINARY__/apps/trading-core/generated'),
    ),
    'hftp_contract_headers': (
        ('INTERFACE', 'apps/hft-parser/src/Contracts/include'),
    ),
    'hftp_contracts': (),
    'hftp_client_headers': (
        ('INTERFACE', 'apps/hft-parser/src/Clients/include'),
    ),
    'hftp_backend_headers': (
        ('INTERFACE', 'apps/hft-parser/src/Runtime/include'),
        ('INTERFACE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_public_market': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Runtime/src'),
    ),
    'hftp_resource': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_session_service': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_session_native_order': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_session_native_identity': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_session_native_account': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_sessiond_runtime': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_routing': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_catalog': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_transport': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_ingestion_common': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_ingestion': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_trading_ingestion': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_local_data_plane': (),
    'hftp_market_client': (),
    'hftp_current_reference_client': (),
    'hftp_session_private_client': (),
    'hft_parser_session_client': (),
    'hft_parser_projection_client': (),
    'hft_parser_reference_client': (),
    'hft_parser_history_client': (),
    'hftp_projection_publisher': (),
    'hftp_reference_projection_publisher': (),
    'hftp_session_private_publisher': (
        ('PUBLIC', 'apps/hft-parser/src/Runtime/include'),
        ('PUBLIC', 'apps/hft-parser/src/Process/include'),
    ),
    'hftp_ipc': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_reference_ipc': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_algos_public_runtime_objects': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_algos_runtime': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_reference': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_reference_storage': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Runtime/src/History'),
    ),
    'hftp_history': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Runtime/src/History'),
    ),
    'hftp_history_service': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Runtime/src/History'),
    ),
    'hftp_runtime_common': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/src/Bootstrap'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_parserd_runtime': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/src/Bootstrap'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftp_trading_runtime': (
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/include'),
        ('PRIVATE', 'apps/hft-parser/src/Process/src/Bootstrap'),
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hft-parserd': (),
    'hft-algosd': (
        ('PRIVATE', 'src/src/Core/include'),
        ('PRIVATE', 'src/src/Contracts/include'),
    ),
    'hftrec_corpus_contract': (
        ('PUBLIC', 'apps/hft-recorder/src/Contracts/include'),
        ('PRIVATE', 'apps/hft-recorder/src/Runtime/src'),
    ),
    'hftrec_capture_launch': (
        ('PRIVATE', 'apps/hft-recorder/src/Contracts/include'),
        ('PRIVATE', 'apps/hft-recorder/src/Runtime/src'),
    ),
    'hftrec_capture_client': (
        ('PRIVATE', 'apps/hft-recorder/src/Runtime/src'),
    ),
    'hftrec_json_capture': (
        ('PRIVATE', 'apps/hft-recorder/src/Runtime/src'),
    ),
    'hftrec_core': (
        ('PUBLIC', 'apps/hft-recorder/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-recorder/src/Runtime/src'),
    ),
    'hftrec_recorder_api': (),
    'hft_compressor_core': (
        ('PUBLIC', 'apps/hft-compressor/src/Api/include'),
        ('PRIVATE', 'apps/hft-compressor/src/Runtime/src'),
    ),
    'exchange_probe_lib': (
        ('PUBLIC', 'tools/exchange_api_probe/include'),
    ),
    'hft_backtest_core': (
        ('PUBLIC', 'apps/hft-backtest/src/Runtime/include'),
        ('PRIVATE', 'apps/hft-backtest/src/Runtime/src'),
    ),
    'trader_common_contracts': (
        ('INTERFACE', 'apps/trader/src/Contracts/include'),
    ),
    'trader_order_contracts': (
        ('INTERFACE', 'apps/trader/src/Contracts/Order/include'),
    ),
    'trader_control_contracts': (
        ('INTERFACE', 'apps/trader/src/Contracts/Control/include'),
    ),
    'trader_projection_contracts': (
        ('INTERFACE', 'apps/trader/src/Contracts/Projection/include'),
    ),
    'traderd': (),
    'trader_alert_contracts': (
        ('PUBLIC', 'apps/trader/alerts/include'),
    ),
    'trader_alert_bridge': (),
    'trader_alert_client': (),
    'trader_alert_observer': (),
    'trader_alert_service': (),
    'trader_alert_telegram': (),
    'trader-alertd': (),
    'trader_strategy_launch': (),
    'trader_source_boundary': (),
    'trader_projection_server': (),
    'trader_market_observe_projection_server': (),
    'trader_alert_evaluator': (
        ('PUBLIC', 'apps/trader/src/Market/include'),
    ),
    'trader_order_client': (
        ('PUBLIC', 'apps/trader/src/Order/include'),
    ),
    'trader_order_bootstrap_server': (
        ('PRIVATE', 'apps/trader/src/Order/src/Bootstrap'),
    ),
    'trader_control_client': (
        ('PUBLIC', 'apps/trader/src/Control/include'),
    ),
    'trader_projection_client': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_projection_publisher': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_projection_source': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_market_observe_projection_client': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_market_observe_projection_publisher': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_live_market_client': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_live_market_relay': (
        ('PUBLIC', 'apps/trader/src/Projection/include'),
    ),
    'trader_projection_server_transport': (
        ('PRIVATE', 'apps/trader/src/Projection/include'),
        ('PRIVATE', 'apps/trader/src/Projection/src/Publisher'),
    ),
    'trader_public_analytics': (
        ('PUBLIC', 'apps/trader/src/Market/include'),
    ),
    'trader_market_client': (
        ('PUBLIC', 'apps/trader/src/Market/include'),
    ),
    'trader_market_observe_runtime': (
        ('PUBLIC', 'apps/trader/src/Market/include'),
    ),
    'trader_market_observe_process': (
        ('PRIVATE', 'apps/trader/src/Process/src/MarketObserve'),
    ),
    'trader_live_runtime': (
        ('PUBLIC', 'apps/trader/src/Runtime/include'),
    ),
    'trader_private_ipc': (
        ('PRIVATE', 'apps/trader/src/Transport/src/LocalIpc'),
    ),
    'trader_projection_transport_io': (
        ('PRIVATE', 'apps/trader/src/Projection/src/Transport'),
    ),
    'trader_process_bootstrap': (
        ('PUBLIC', 'apps/trader/src/Process/include'),
    ),
    'trader_traderd_process': (
        ('PRIVATE', 'apps/trader/src/Process/src/Traderd'),
        ('PRIVATE', 'apps/hft-parser/src/Runtime/include'),
    ),
    'vetron_browser_contracts': (
        ('INTERFACE', 'apps/vetron/src/Contracts/include'),
    ),
    'vetrond-read': (),
    'vetrond-full': (),
    'vetron_read_source_boundary': (),
    'vetron_full_source_boundary': (),
    'vetron_read_gateway': (
        ('PUBLIC', 'apps/vetron/src/Gateway/include'),
    ),
    'vetron_full_control': (
        ('PUBLIC', 'apps/vetron/src/Gateway/include'),
    ),
    'vetron_read_runtime': (
        ('PUBLIC', 'apps/vetron/src/Runtime/include'),
    ),
    'vetron_read_process': (
        ('PUBLIC', 'apps/vetron/src/Process/include'),
    ),
    'vetron_full_process': (
        ('PUBLIC', 'apps/vetron/src/Process/include'),
    ),
}

# Exact source-local helper producers add tools/Testing first. Diagnostic targets
# are unconditional EXCLUDE_FROM_ALL declarations; KIND labels/instruments
# them and never authorizes declaration absence in an active owner.
_EXACT_OFFLINE_INCLUDE_CONTRACTS = {
    'apps/diagnostic/tests/offline/CMakeLists.txt': {
        'diagnostic_offline_collector': ('tools/Testing',),
        'diagnostic_offline_grpc': ('tools/Testing',),
    },
    'src/tests/offline/CMakeLists.txt': {
        'cxet_offline_resident_memory': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_optional_parser_primitives': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_byte_primitives': ('tools/Testing',),
        'cxet_offline_text_primitives': ('tools/Testing',),
        'cxet_offline_numeric_primitives': ('tools/Testing',),
        'cxet_offline_primitive_storage': ('tools/Testing',),
        'cxet_offline_primitive_sort': ('tools/Testing',),
        'cxet_offline_primitive_ranking': ('tools/Testing',),
        'cxet_offline_finam_candle_compat': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_optional_identity_primitives': ('tools/Testing',),
        'cxet_offline_optional_busy_poll': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_twime_transport': ('tools/Testing',),
        'cxet_offline_simba_transport': ('tools/Testing',),
        'cxet_offline_crypto_primitives': ('tools/Testing', 'src/src/Core/src/Crypto', 'extra/mbedtls-cold/library'),
        'cxet_offline_tls_records': ('tools/Testing',),
        'cxet_offline_tls_handshake': ('tools/Testing',),
        'cxet_offline_instrument_observation': ('tools/Testing',),
        'cxet_offline_exchange_selection': ('tools/Testing',),
        'cxet_offline_numeric_mechanics': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_decode': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_requests': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_user_identity': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_native_grpc_metadata_catalog': ('tools/Testing',),
        'cxet_offline_native_trade_identity': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_private_contract_lowering': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_binance_spot_json': ('tools/Testing',),
        'cxet_offline_binance_private_contracts': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_binance_fix_contracts': ('tools/Testing',),
        'cxet_offline_kucoin_private_contracts': ('tools/Testing',),
        'cxet_offline_kucoin_native_protocols': ('tools/Testing',),
        'cxet_offline_kucoin_prepared_private_catalog': ('tools/Testing',),
        'cxet_offline_bybit_native_protocols': ('tools/Testing',),
        'cxet_offline_bybit_prepared_private_catalog': ('tools/Testing',),
        'cxet_offline_okx_private_contracts': ('tools/Testing',),
        'cxet_offline_okx_prepared_private_catalog': ('tools/Testing',),
        'cxet_offline_hyperliquid_private': ('tools/Testing',),
        'cxet_offline_rpi_orders': ('tools/Testing',),
        'cxet_offline_dedicated_endpoint': ('tools/Testing',),
        'cxet_offline_rpi_depth': ('tools/Testing',),
        'cxet_offline_prepared_private_binding': ('tools/Testing',),
        'cxet_offline_mexc_spot_private': ('tools/Testing',),
        'cxet_offline_mexc_futures_private': ('tools/Testing',),
        'cxet_offline_bitget_private': ('tools/Testing',),
        'cxet_offline_phemex_private': ('tools/Testing',),
        'cxet_offline_aster_private': ('tools/Testing',),
        'cxet_offline_private_catalog_projection': ('tools/Testing',),
        'cxet_offline_instrument_universe_profiles': ('tools/Testing',),
        'cxet_offline_native_bindings': ('tools/Testing',),
        'cxet_offline_native_reference_catalog': ('tools/Testing',),
        'cxet_offline_native_metadata_catalog': ('tools/Testing',),
        'cxet_offline_parameter_requests': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_htx_endpoint_profiles': ('tools/Testing',),
        'cxet_offline_gate_sbe_market_contracts': ('tools/Testing',),
        'cxet_offline_public_subscription_stream': ('tools/Testing',),
        'cxet_offline_public_subscription_native': ('tools/Testing',),
        'cxet_offline_public_subscription_additional': ('tools/Testing',),
        'cxet_offline_public_subscription_gate': ('tools/Testing',),
        'cxet_offline_public_subscription_remaining': ('tools/Testing',),
        'cxet_offline_toobit_private_contracts': ('tools/Testing',),
        'cxet_offline_unsupported_rpi_writers': ('tools/Testing',),
        'cxet_offline_finam_private_contracts': ('tools/Testing',),
        'cxet_offline_gate_private_contracts': ('tools/Testing',),
        'cxet_offline_tbank_private_contracts': ('tools/Testing',),
        'cxet_offline_native_order_quantity': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_terminal_attempt_time': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_native_metadata_quantity': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_general_json': ('tools/Testing',),
        'cxet_offline_routes': ('tools/Testing',),
        'cxet_offline_depth': ('tools/Testing',),
        'cxet_offline_depth_runtime': ('tools/Testing',),
        'cxet_offline_transport': ('tools/Testing',),
        'cxet_offline_tls_terminal': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_core_api': ('tools/Testing',),
        'cxet_offline_grpc_fetch': ('tools/Testing',),
        'cxet_offline_grpc_buffered_poll': ('tools/Testing',),
        'cxet_offline_finam_auth_buffers': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_account_cashflows': ('tools/Testing',),
        'cxet_offline_account_query_runtime': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_cbr_decision': ('tools/Testing',),
        'cxet_offline_market_preparation': ('tools/Testing',),
        'cxet_offline_moex_normalization': ('tools/Testing',),
        'cxet_offline_native_pnl_contracts': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_native_reference_rest_request': ('tools/Testing', 'src/src/Core/src'),
        'cxet_offline_poloniex_normalization': ('tools/Testing',),
        'cxet_offline_tbank_order_observations': ('tools/Testing',),
        'cxet_offline_tbank_parity': ('tools/Testing',),
        'cxet_offline_trading_financial_contracts': ('tools/Testing',),
        'cxet_offline_market_continuity': ('tools/Testing',),
        'cxet_offline_ws_cold_admission': ('tools/Testing',),
        'cxet_offline_order_lifecycle': ('tools/Testing',),
        'cxet_offline_order_correlation': ('tools/Testing',),
        'cxet_offline_native_recovery_facts': ('tools/Testing',),
        'cxet_offline_queue_threads': ('tools/Testing', 'src/src/Core/include'),
        'cxet_offline_wire_fuzz': ('tools/Testing',),
        'cxet_offline_htx_private': ('tools/Testing',),
        'cxet_offline_xt_private': ('tools/Testing',),
        'cxet_offline_bingx_private': ('tools/Testing',),
    },
    'apps/trading-core/tests/offline/CMakeLists.txt': {
        'trading-core-offline-capacity': ('tools/Testing',),
        'trading-core-offline-identity': ('tools/Testing',),
        'trading-core-offline-freshness': ('tools/Testing',),
        'trading-core-offline-params': ('tools/Testing',),
        'trading-core-offline-pair-probe-params': ('tools/Testing', 'apps/trading-core/src/Strategy/include'),
        'trading-core-offline-checkpoint': ('tools/Testing', 'apps/trading-core/src/Strategy/include'),
        'trading-core-offline-book-decision': ('tools/Testing',),
        'trading-core-offline-book-grid': ('tools/Testing',),
        'trading-core-offline-signal': ('tools/Testing', 'apps/trading-core/src/Strategy/include'),
        'trading-core-offline-account': ('tools/Testing',),
        'trading-core-offline-transaction-reports': ('tools/Testing',),
        'trading-core-offline-feedback-races': ('tools/Testing',),
        'trading-core-offline-strategy-validation': ('tools/Testing',),
        'trading-core-offline-stop-transaction-fill': ('tools/Testing',),
        'trading-core-offline-strategy-authority': ('tools/Testing', 'apps/trading-core/src/Strategy/include'),
        'trading-core-offline-portfolio-risk': ('tools/Testing',),
        'trading-core-offline-position-admission': ('tools/Testing',),
    },
    'apps/hft-parser/tests/offline/CMakeLists.txt': {
        'hftp_offline_cases': ('tools/Testing', 'apps/hft-parser/src/Runtime/include', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_capture_subscription': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_public_market_catalog': ('tools/Testing',),
        'hftp_offline_catalogue_identities': ('tools/Testing', 'apps/hft-parser/src/Runtime/src', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_portable_catalog': ('tools/Testing', 'apps/hft-parser/src/Process/src/Bootstrap/Reference', 'apps/hft-parser/src/Runtime/include', 'src/src/Core/include'),
        'hftp_offline_resource_budget': ('tools/Testing',),
        'hftp_offline_public_handoff': ('tools/Testing',),
        'hftp_offline_reference_admission': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_public_handoff_thread': ('tools/Testing',),
        'hftp_offline_kernel_handoff': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_memory_admission': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_source_recovery': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_cold_reservoir': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_market_demand': ('tools/Testing',),
        'hftp_offline_history_profile': ('tools/Testing',),
        'hftp_offline_source_recovery_warm': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_projection_generation': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_ipc_arena_layout': ('tools/Testing', 'apps/hft-parser/src/Runtime/src'),
        'hftp_offline_archive_file_authority': ('tools/Testing', 'apps/hft-parser/src/Runtime/src', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_direct_transport_config': ('tools/Testing',),
        'hftp_offline_candle_checkpoint': ('tools/Testing',),
        'hftp_offline_private_native_facts': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_native_account_publication': ('tools/Testing', 'apps/hft-parser/src/Runtime/src', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_native_order_variants': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_rpi_orders': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_rpi_depth_identity': ('tools/Testing',),
        'hftp_offline_selected_wire_config': ('tools/Testing',),
        'hftp_offline_private_subscription_prerequisites': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_private_subscription_plan': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'hftp_offline_native_reference_rest_auth': ('tools/Testing',),
    },
    'apps/hft-backtest/tests/offline/CMakeLists.txt': {
        'hft_backtest_offline_quota': ('tools/Testing', 'apps/hft-backtest/src/Runtime/src'),
        'hft_backtest_offline_trade': ('tools/Testing', 'apps/hft-backtest/src/Runtime/src'),
        'hft_backtest_offline_quant': ('tools/Testing', 'apps/hft-backtest/src/Runtime/src'),
    },
    'apps/trader/tests/offline/CMakeLists.txt': {
        'trader_offline_cases': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'trader_offline_rpi_orders': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'trader_offline_close_position': ('tools/Testing',),
        'trader_offline_private_cut': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'trader_offline_canonical_attempt_time': ('tools/Testing',),
        'trader_offline_recovery_cut': ('tools/Testing', 'apps/hft-parser/src/Runtime/include'),
        'trader_offline_strategy_runtime': ('tools/Testing', 'apps/trader/src/Process/src/Traderd/Strategy', 'apps/hft-parser/src/Runtime/include'),
        'trader_offline_telegram_cursor': ('tools/Testing',),
        'trader_offline_telegram_error_report': ('tools/Testing',),
        'trader_offline_telegram_status': ('tools/Testing',),
        'trader_offline_service_errors': ('tools/Testing',),
        'trader_offline_service_admission': ('tools/Testing',),
        'trader_offline_pipeline_alert_recovery': ('tools/Testing',),
        'trader_offline_alert_facts': ('tools/Testing',),
        'trader_offline_alert_thread': ('tools/Testing',),
        'trader_alert_thread': ('tools/Testing',),
        'trader_offline_alert_evidence_regression': ('tools/Testing',),
        'trader_offline_delivery_sum_alerts': ('tools/Testing',),
        'trader_offline_algorithm_config': ('tools/Testing',),
        'trader_offline_dispatch': ('tools/Testing',),
        'trader_offline_processor_subset': ('tools/Testing',),
        'trader_offline_wide_market_workers': ('tools/Testing',),
        'trader_wide_market_thread': ('tools/Testing',),
        'trader_offline_parallel_pipeline_recovery': ('tools/Testing',),
    },
    'apps/vetron/tests/offline/CMakeLists.txt': {
        'vetron_offline_math': ('tools/Testing', 'apps/vetron/wasm'),
        'vetron_offline_browser_projection': ('tools/Testing', 'apps/vetron/src/Runtime/src', 'apps/hft-parser/src/Clients/src'),
        'vetron_offline_gateway_authority': ('tools/Testing',),
        'vetron_offline_full_process': ('tools/Testing',),
    },
    'apps/hft-recorder/tests/offline/CMakeLists.txt': {
        'hftrec_offline_corpus': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
        'hftrec_offline_json_terminal': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
        'hftrec_offline_capture_writer': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
        'hftrec_offline_capture_selection': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src', 'apps/hft-recorder/src/Contracts/include'),
        'hftrec_offline_capture_conversion': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
        'hftrec_offline_capture_session': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src', 'apps/hft-recorder/src/Contracts/include'),
        'hftrec_offline_capture_client_loss': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
        'hftrec_offline_owned_parser': ('tools/Testing', 'apps/hft-recorder/src/Runtime/src'),
    },
    'apps/hft-compressor/tests/offline/CMakeLists.txt': {
        'hftc_offline_cases': ('tools/Testing',),
        'hftc_offline_entropy': ('tools/Testing',),
    },
    'tools/exchange_api_probe/tests/offline/CMakeLists.txt': {
        'exchange_probe_offline_cases': ('tools/Testing',),
        'exchange_probe_tbank_protocol_cases': ('tools/Testing',),
        'exchange_probe_tbank_cli_credential_cases': ('tools/Testing',),
        'exchange_probe_tbank_lifecycle_cases': ('tools/Testing',),
        'exchange_probe_paired_cli_cases': ('tools/Testing',),
        'exchange_probe_paired_receipt_cases': ('tools/Testing',),
        'exchange_probe_paired_rest_cases': ('tools/Testing',),
        'exchange_probe_ws_deadline_cases': ('tools/Testing',),
        'exchange_probe_htx_reconnect_cases': ('tools/Testing',),
    },
}

_EXACT_OFFLINE_INCLUDE_OWNERS = {}
for _owner, _targets in _EXACT_OFFLINE_INCLUDE_CONTRACTS.items():
    for _target, _roots in _targets.items():
        _EXACT_OFFLINE_INCLUDE_OWNERS[_target] = _owner
        _EXACT_DIRECT_INCLUDE_ORDER[_target] = tuple(
            ("PRIVATE", root) for root in _roots)

for _target, (_owner, _roots) in BENCHMARK_INCLUDE_CONTRACTS.items():
    _EXACT_DIRECT_INCLUDE_ORDER[_target] = tuple(("PRIVATE", root) for root in _roots)

_EXACT_DIRECT_INCLUDE_ROOTS = {
    target: frozenset(values)
    for target, values in _EXACT_DIRECT_INCLUDE_ORDER.items()
}

_ABSL_HEADER_TARGETS = {
    "absl/container/btree_map.h": frozenset({"absl::btree"}),
    "absl/container/btree_set.h": frozenset({"absl::btree"}),
    "absl/container/flat_hash_map.h": frozenset({"absl::flat_hash_map"}),
    "absl/container/flat_hash_set.h": frozenset({"absl::flat_hash_set"}),
    "absl/container/inlined_vector.h": frozenset({"absl::inlined_vector"}),
    "absl/hash/hash.h": frozenset({"absl::hash"}),
}


@dataclass(frozen=True)
class _Effect:
    value: str
    paths: PathSet


@dataclass(frozen=True)
class _Environment:
    roots: tuple[str, ...] = ()
    external: frozenset[str] = frozenset()
    generated: frozenset[str] = frozenset()
    providers: frozenset[str] = frozenset()


@dataclass
class _Model:
    compile_roots: dict[str, list[_Effect]]
    interface_roots: dict[str, list[_Effect]]
    compile_generated: dict[str, list[_Effect]]
    interface_generated: dict[str, list[_Effect]]
    compile_external: dict[str, list[_Effect]]
    interface_external: dict[str, list[_Effect]]
    compile_links: dict[str, list[_Effect]]
    interface_links: dict[str, list[_Effect]]
    compile_may_links: dict[str, list[_Effect]]
    interface_may_links: dict[str, list[_Effect]]


def _flat(instance, start: int = 0) -> list[str]:
    return [
        value for group in instance.token_groups[start:] for value in group]


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _include_value(instance, value: str) -> tuple[str, str] | None:
    prefix = "$<BUILD_INTERFACE:"
    if value.startswith(prefix) and value.endswith(">"):
        value = value[len(prefix):-1]
        if (normalize_synthetic_binary_path(value) is None and
                not Path(value).is_absolute()):
            # CURRENT_SOURCE/LIST_DIR are absolute in real CMake. The bounded
            # interpreter represents them as repo-relative paths. Preserve
            # that proven producer spelling, never a raw relative BUILD_INTERFACE.
            carriers = {
                "${CMAKE_CURRENT_SOURCE_DIR}": instance.evaluation.source_base.as_posix(),
                "${CMAKE_CURRENT_LIST_DIR}": Path(instance.body.relative).parent.as_posix(),
            }
            proven = False
            for raw in cmake_list_words(instance.body.command.body):
                for carrier, base in carriers.items():
                    opening = prefix + carrier
                    if raw.startswith(opening) and raw.endswith(">"):
                        suffix = raw[len(opening):-1]
                        if (not suffix or suffix.startswith("/")) and base + suffix == value:
                            proven = True
            if not proven:
                return None
    synthetic = normalize_synthetic_binary_path(value)
    if synthetic is not None:
        return "generated", synthetic
    if "$<" in value:
        return None
    normalized = normalize_repo_include(instance.evaluation, value)
    target = (instance.token_groups[0][0]
              if instance.token_groups and len(instance.token_groups[0]) == 1 else None)
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instance_context
    vendor = (normalized in NATIVE_CRYPTO_VENDOR_INCLUDES.get(target, ()) and
              (native_crypto_owner(instance) or
               target == "cxet_offline_crypto_primitives" and offline_instance_context(instance, target)))
    if (normalized is None or
            not normalized.startswith(_FIRST_PARTY_PREFIXES) and not vendor):
        return None
    return "repo", normalized


def _scoped_link_items(
    values: list[str],
) -> tuple[tuple[tuple[str, str, str], ...], tuple[str, ...]]:
    """Retain TLL visibility and MUST/MAY certainty."""
    result: list[tuple[str, str, str]] = []
    failures: list[str] = []
    scope = "PUBLIC"  # CMake's legacy plain signature is transitive.
    pending: str | None = None
    for value in values:
        if value in _LINK_SCOPES:
            scope = value
            pending = None
            continue
        if value in {"debug", "general", "optimized"}:
            pending = value
            continue
        if "$<LINK_ONLY:" in value:
            failures.append(
                f"LINK_ONLY cannot prove compiler usage requirements: {value}")
            pending = None
            continue
        parsed, parse_failures = parse_link_values(
            ([pending] if pending is not None else []) + [value])
        pending = None
        if parse_failures:
            failures.extend(parse_failures)
            continue
        result.extend(
            (scope, provider, certainty)
            for provider, certainty in parsed)
    if pending is not None:
        failures.append(f"dangling link configuration selector: {pending}")
    return tuple(result), tuple(failures)


def validate_include_reachability_microcases(errors: list[str]) -> None:
    """Keep link-only usage requirements out of compiler environments."""
    items, failures = _scoped_link_items([
        "PUBLIC", "$<LINK_ONLY:provider>",
    ])
    if items or not failures:
        errors.append(
            "include-reachability self-check accepted LINK_ONLY provider")
    if (not source_artifact_path(
            "apps/hft-parser/dev-state/runtime.hpp") or
            source_artifact_path(
                "apps/hft-parser/dev-stateful/runtime.hpp")):
        errors.append(
            "include-reachability self-check broke the exact HFT Parser "
            "runtime-state header boundary")
    if (not _read_only_forbidden_include_root("src/src/Core/include") or
            not _read_only_forbidden_include_root(
                "src/src/Core/include/cxet/api") or
            not _read_only_forbidden_include_root("src/src/Core/src") or
            not _read_only_forbidden_include_root(
                "src/src/Core/src/Private") or
            not _read_only_forbidden_include_root(
                "apps/hft-parser/src/Runtime/include/hft_parser/Runtime") or
            _read_only_forbidden_include_root(
                "src/src/Contracts/include") or
            _read_only_forbidden_include_root(
                "apps/hft-parser/src/Clients/include")):
        errors.append(
            "include-reachability self-check broke read-only root boundary")


def _empty_model(targets: list[str]) -> _Model:
    def table() -> dict[str, list[_Effect]]:
        return {target: [] for target in targets}
    return _Model(*(table() for _ in range(10)))


def _add_effect(table: dict[str, list[_Effect]], target: str,
                value: str, paths: PathSet) -> None:
    effect = _Effect(value, paths)
    if effect not in table[target]:
        table[target].append(effect)


def _exact_include_owner(target: str) -> str | None:
    if target in BENCHMARK_INCLUDE_CONTRACTS:
        return BENCHMARK_INCLUDE_CONTRACTS[target][0]
    origin = _EXACT_OFFLINE_INCLUDE_OWNERS.get(target)
    if origin is None:
        spec = target_spec(target, None, "")
    else:
        owner = "/".join(PurePosixPath(origin).parts[:2])
        spec = target_spec(target, owner, origin)
    return spec.owner if spec is not None else None


def _build_model(instances, registry, aliases: dict[str, str],
                 exact_root_targets: frozenset[str],
                 errors: list[str], *,
                 active_origins: frozenset[str] | None = None) -> _Model:
    targets = sorted(registry.concrete_names())
    model = _empty_model(targets)
    direct_inventory = {target: [] for target in targets}
    expected_owners = {
        target: _exact_include_owner(target)
        for target in _EXACT_DIRECT_INCLUDE_ROOTS
    }
    for target, owner in expected_owners.items():
        if owner is None:
            errors.append(
                f"{target}: exact direct include contract has no reviewed profile owner")
    applicable = {
        target: expected
        for target, expected in _EXACT_DIRECT_INCLUDE_ROOTS.items()
        if ((target not in BENCHMARK_INCLUDE_CONTRACTS or target in targets) and
            not (hasattr(registry, 'optional_target_disabled') and
                 registry.optional_target_disabled(target)) and
            (active_origins is None or expected_owners[target] is None or
             expected_owners[target] in active_origins))
    }

    for instance in instances:
        command = instance.body.command.name
        if command not in {
                "target_include_directories", "target_link_libraries"}:
            continue
        first_group = (
            tuple(instance.token_groups[0])
            if instance.token_groups else ())
        raw_target, target_failure = single_expanded_target_argument(
            first_group)
        if target_failure is not None or raw_target is None:
            errors.append(
                f"{instance.body.relative}:"
                f"{instance.body.command.line}: {command}: "
                f"{target_failure}")
            continue
        trailing = _flat(instance, 1)
        if command == "target_include_directories":
            target = canonical_target(raw_target, aliases)
            if target not in direct_inventory:
                continue
            expected_owner = expected_owners.get(target)
            if (expected_owner is not None and
                    instance.body.relative != expected_owner):
                errors.append(
                    f"{instance.body.relative}:{instance.body.command.line}: "
                    f"{target}: direct include mutation escaped exact owner "
                    f"{expected_owner}")
            groups, failure = target_include_groups(
                [raw_target, *trailing])
            if failure is not None:
                continue
            for scope, raw_value in groups:
                compression = compression_include_provider(instance, target, scope, raw_value)
                if compression is not None:
                    _add_effect(model.compile_external, target, compression, instance.path_alternatives)
                    _add_effect(model.interface_external, target, compression, instance.path_alternatives)
                    continue
                from Family.Targets.CxetFamilyBuildPolicy import (
                    OFFLINE_LIBURING_INCLUDE, offline_liburing_include_context,
                )
                if (scope == "PRIVATE" and raw_value == OFFLINE_LIBURING_INCLUDE and
                        offline_liburing_include_context(instance, target, registry, instances)):
                    _add_effect(model.compile_external, target, "liburing::uring", instance.path_alternatives)
                    continue
                value = _include_value(instance, raw_value)
                if value is None:
                    continue
                kind, normalized = value
                direct_inventory[target].append((scope, normalized))
                if kind == "repo":
                    if scope in {"PRIVATE", "PUBLIC"}:
                        _add_effect(model.compile_roots, target, normalized,
                                    instance.path_alternatives)
                    if scope in {"INTERFACE", "PUBLIC"}:
                        _add_effect(model.interface_roots, target, normalized,
                                    instance.path_alternatives)
                else:
                    if scope in {"PRIVATE", "PUBLIC"}:
                        _add_effect(model.compile_generated, target,
                                    normalized, instance.path_alternatives)
                    if scope in {"INTERFACE", "PUBLIC"}:
                        _add_effect(model.interface_generated, target,
                                    normalized, instance.path_alternatives)
            continue
        target = canonical_target(raw_target, aliases)
        if target not in direct_inventory:
            continue
        scoped_items, link_failures = _scoped_link_items(compression_link_values(instance, trailing))
        for failure in link_failures:
            errors.append(
                f"{instance.body.relative}:"
                f"{instance.body.command.line}: {failure}")
        for scope, raw_provider, certainty in scoped_items:
            provider = canonical_target(raw_provider, aliases)
            if provider in direct_inventory:
                if scope in _COMPILE_LINK_SCOPES:
                    _add_effect(model.compile_may_links, target, provider,
                                instance.path_alternatives)
                if scope in _INTERFACE_LINK_SCOPES:
                    _add_effect(model.interface_may_links, target, provider,
                                instance.path_alternatives)
            if certainty != MUST:
                continue
            if provider in APPROVED_EXTERNAL_LINK_ITEMS:
                if scope in _COMPILE_LINK_SCOPES:
                    _add_effect(model.compile_external, target, provider,
                                instance.path_alternatives)
                if scope in _INTERFACE_LINK_SCOPES:
                    _add_effect(model.interface_external, target, provider,
                                instance.path_alternatives)
            elif provider in direct_inventory:
                if scope in _COMPILE_LINK_SCOPES:
                    _add_effect(model.compile_links, target, provider,
                                instance.path_alternatives)
                if scope in _INTERFACE_LINK_SCOPES:
                    _add_effect(model.interface_links, target, provider,
                                instance.path_alternatives)

    unreviewed = {
        target: tuple(values)
        for target, values in direct_inventory.items()
        if (values and target in exact_root_targets and
            target not in _EXACT_DIRECT_INCLUDE_ROOTS)
    }
    if unreviewed:
        errors.append(
            "unreviewed target direct include roots: " + str(unreviewed))
    missing = sorted(set(applicable) - exact_root_targets)
    if missing:
        errors.append(
            "exact direct include-root targets missing from active family: " +
            str(missing))
    for target, expected in applicable.items():
        actual_order = tuple(direct_inventory.get(target, ()))
        expected_order = _EXACT_DIRECT_INCLUDE_ORDER.get(
            target, tuple(expected))
        if (frozenset(actual_order) != expected or
                actual_order != expected_order):
            errors.append(
                f"{target}: exact direct include roots changed: "
                f"expected={list(expected_order)}, actual={list(actual_order)}")
    return model


def _read_only_forbidden_include_root(root: str) -> bool:
    return any(
        root == forbidden or root.startswith(forbidden + "/")
        for forbidden in _READ_ONLY_FORBIDDEN_INCLUDE_ROOTS)


class _MayIncludeRootResolver:
    """Resolve semantic MAY include roots independently of exact inventories."""

    def __init__(self, model: _Model) -> None:
        self.model = model
        self.interface_cache: dict[str, frozenset[str]] = {}

    @staticmethod
    def _values(effects: list[_Effect]) -> set[str]:
        return {effect.value for effect in effects}

    def interface(self, target: str,
                  stack: tuple[str, ...] = ()) -> frozenset[str]:
        cached = self.interface_cache.get(target)
        if cached is not None:
            return cached
        if target in stack:
            return frozenset()
        roots = self._values(self.model.interface_roots[target])
        for provider in self._values(self.model.interface_may_links[target]):
            roots.update(self.interface(provider, (*stack, target)))
        result = frozenset(roots)
        self.interface_cache[target] = result
        return result

    def compile(self, target: str) -> frozenset[str]:
        roots = self._values(self.model.compile_roots[target])
        for provider in self._values(self.model.compile_may_links[target]):
            roots.update(self.interface(provider))
        return frozenset(roots)


def _validate_read_only_include_root_closures(
    model: _Model,
    registry,
    errors: list[str],
) -> None:
    resolver = _MayIncludeRootResolver(model)
    concrete = registry.concrete_names()
    for target in sorted(TRANSPORT_FREE_TARGETS):
        if target not in concrete:
            continue
        interface_leaks = sorted(
            root for root in resolver.interface(target)
            if _read_only_forbidden_include_root(root))
        compile_leaks = sorted(
            root for root in resolver.compile(target)
            if _read_only_forbidden_include_root(root))
        if interface_leaks or compile_leaks:
            errors.append(
                f"{target}: read-only MAY include closure exposes forbidden "
                f"roots: interface={interface_leaks}, compile={compile_leaks}")


def _covered(
    effects: list[_Effect],
    universe: PathSet,
    errors: list[str],
    context: str,
) -> tuple[str, ...]:
    grouped: dict[str, list[PathSet]] = {}
    for effect in effects:
        grouped.setdefault(effect.value, []).append(effect.paths)
    result: list[str] = []
    for value, groups in grouped.items():
        evidence = bounded_merge(
            errors, f"{context}: {value} path union", *groups)
        if paths_cover(universe=universe, evidence=evidence):
            result.append(value)
    return tuple(result)


def _strict_direct_roots(
    effects: list[_Effect],
    universe: PathSet,
    errors: list[str],
    context: str,
) -> tuple[str, ...]:
    """Reject roots that are compiler-visible on only some target paths."""
    grouped: dict[str, list[PathSet]] = {}
    for effect in effects:
        grouped.setdefault(effect.value, []).append(effect.paths)
    result: list[str] = []
    for value, groups in grouped.items():
        evidence = bounded_merge(
            errors, f"{context}: {value} path union", *groups)
        if not paths_cover(universe=universe, evidence=evidence):
            errors.append(
                f"{context}: conditional direct interface root unsupported: "
                f"{value}")
            continue
        result.append(value)
    return tuple(result)


class _EnvironmentResolver:
    def __init__(self, model: _Model, registry, errors: list[str]) -> None:
        self.model = model
        self.registry = registry
        self.errors = errors
        self.interface_cache: dict[str, _Environment] = {}
        # The model/registry are complete before this resolver is created.
        # Keep exact target and path-universe identity inside this one proof.
        self.compile_cache: dict[tuple[str, PathSet], _Environment] = {}

    @staticmethod
    def _merge(base: _Environment, other: _Environment) -> _Environment:
        roots = list(base.roots)
        for root in other.roots:
            _append_unique(roots, root)
        return _Environment(
            tuple(roots),
            base.external | other.external,
            base.generated | other.generated,
            base.providers | other.providers,
        )

    def interface(self, target: str, stack: tuple[str, ...] = ()) -> _Environment:
        cached = self.interface_cache.get(target)
        if cached is not None:
            return cached
        if target in stack:
            self.errors.append(
                "target include-interface cycle: " +
                " -> ".join((*stack, target)))
            return _Environment()
        universe = self.registry.declaration_paths(target)
        if universe == NO_PATHS:
            return _Environment()
        environment = _Environment(
            _covered(
                self.model.interface_roots[target], universe, self.errors,
                f"{target} interface include roots"),
            frozenset(_covered(
                self.model.interface_external[target], universe, self.errors,
                f"{target} interface external capabilities")),
            frozenset(_covered(
                self.model.interface_generated[target], universe, self.errors,
                f"{target} interface generated roots")),
            frozenset({target}),
        )
        for provider in _covered(
                self.model.interface_links[target], universe, self.errors,
                f"{target} interface links"):
            environment = self._merge(
                environment, self.interface(provider, (*stack, target)))
        self.interface_cache[target] = environment
        return environment

    def compile(self, target: str, universe: PathSet) -> _Environment:
        key = (target, universe)
        cached = self.compile_cache.get(key)
        if cached is not None:
            return cached
        environment = _Environment(
            _covered(
                self.model.compile_roots[target], universe, self.errors,
                f"{target} compile include roots"),
            frozenset(_covered(
                self.model.compile_external[target], universe, self.errors,
                f"{target} compile external capabilities")),
            frozenset(_covered(
                self.model.compile_generated[target], universe, self.errors,
                f"{target} compile generated roots")),
            frozenset({target}),
        )
        for provider in _covered(
                self.model.compile_links[target], universe, self.errors,
                f"{target} compile links"):
            environment = self._merge(environment, self.interface(provider))
        self.compile_cache[key] = environment
        return environment


def _scoped_external_include(
    include: str, capabilities: frozenset[str],
) -> bool:
    if include in COMPRESSION_HEADER_PROVIDERS:
        return bool(COMPRESSION_HEADER_PROVIDERS[include] & capabilities)
    if include == "liburing/io_uring_version.h":
        return "liburing::uring" in capabilities
    if not approved_external_angle_include(include):
        return False
    if include.startswith("absl/"):
        required = _ABSL_HEADER_TARGETS.get(include)
        return required is not None and bool(required & capabilities)
    required: frozenset[str] | None = None
    if include.startswith("gtest/"):
        required = frozenset({"GTest::gtest", "GTest::gtest_main"})
    elif include.startswith("openssl/"):
        required = frozenset({"OpenSSL::SSL", "OpenSSL::Crypto"})
    elif include == "nghttp2/nghttp2.h":
        required = frozenset({"PkgConfig::NGHTTP2"})
    elif include.startswith("boost/"):
        required = frozenset({"Boost::json"})
    elif include == "liburing.h":
        required = frozenset({"liburing::uring"})
    elif include == "libpq-fe.h":
        required = frozenset({"PostgreSQL::PostgreSQL"})
    elif include.startswith("secp256k1"):
        required = frozenset({"secp256k1"})
    elif include.startswith(("spdlog/", "tracy/")):
        return False
    return required is None or bool(required & capabilities)


def _cold_full_quoted_external(target, source, translation_unit, include,
                               capabilities, *, public_seed):
    """Pin the cold fleet scratch allocator's two quoted Abseil imports."""
    owner = 'apps/trader/src/Process/src/Traderd/Fleet/Financial/FleetFinancialMemory.cpp'
    required = {
        'absl/container/flat_hash_map.h': 'absl::flat_hash_map',
        'absl/hash/hash.h': 'absl::hash',
    }.get(include)
    return (not public_seed and target == 'trader_traderd_process' and
            source == owner and translation_unit == owner and
            required is not None and required in capabilities)


def _generated_include_allowed(
    include: str, generated: frozenset[str],
) -> bool:
    if include == "trading_core/Strategy/GeneratedStrategyRegistry.hpp":
        return _TRADING_CORE_GENERATED in generated
    return False


def _seed_exported_headers(
    root: Path,
    model: _Model,
    registry,
    queue: deque[tuple[str, str, PathSet, bool, str | None]],
    errors: list[str],
) -> tuple[dict[str, tuple[str, ...]], dict[str, frozenset[str]]]:
    """Inventory every physical header; seed each canonical semantic API."""
    direct_roots: dict[str, tuple[str, ...]] = {}
    for target in sorted(registry.concrete_names()):
        universe = registry.declaration_paths(target)
        if universe == NO_PATHS:
            continue
        roots = _strict_direct_roots(
            model.interface_roots[target], universe, errors,
            f"{target} direct interface header roots")
        # Vendor usage requirements are target-scoped dependency roots, not
        # project-owned exported header surfaces. Reachable vendor text is
        # still scanned recursively in the exact consuming environment.
        roots = tuple(value for value in roots
                      if value not in NATIVE_CRYPTO_VENDOR_INCLUDES.get(target, ()))
        if roots:
            direct_roots[target] = roots
    inventory = compiler_visible_header_inventory(
        root, direct_roots, errors)
    concrete = registry.concrete_names()
    api_inventory = canonical_api_headers(inventory, concrete, errors)
    # A compiler-visible declaration carrier need not own every API's seed
    # environment. Actual consumers must still obtain the real CMake carrier
    # and recursively prove all required headers in their own environment.
    header_targets = exported_header_targets(inventory)
    for target, headers in api_inventory.items():
        if target not in concrete:
            errors.append(f"exported header target is not concrete: {target}")
            continue
        universe = registry.declaration_paths(target)
        if universe == NO_PATHS:
            continue
        for relative in headers:
            queue.append((target, relative, universe, True, None))
    return inventory, header_targets


def _private_owner_header_access(target, selected, universe, model, errors):
    """Honor only reviewed, guaranteed owner-local direct PRIVATE roots."""
    spec = target_spec(target, None, "")
    if spec is None:
        return False
    owner = logical_header_owner(spec.owner)
    if owner is None or logical_header_owner(selected) != owner:
        return False
    # Capital is a separate finance authority even though legacy product owner
    # labels group it with trading-core. Its narrow leaf rule remains separate.
    if selected.startswith("apps/trading-core/capital/"):
        return False
    reviewed = {
        root for scope, root in _EXACT_DIRECT_INCLUDE_ORDER.get(target, ())
        if scope == "PRIVATE" and logical_header_owner(root) == owner
    }
    actual = set(_covered(model.compile_roots[target], universe, errors,
                          f"{target} direct private header roots"))
    public = {effect.value for effect in model.interface_roots[target]}
    return any(selected.startswith(root + "/")
               for root in reviewed & actual - public)


class CppIncludeSyntaxMemo:
    """Bounded invocation-local memo of one pure lexer result per source.

    Every caller must first reread and verify/adapt its current input. These
    immutable normalized text and literal records carry no target, path,
    environment or proof facts.
    """

    def __init__(self, scanner=cpp_include_syntax, *, max_sources=8192,
                 max_bytes=256 * 1024 * 1024):
        if max_sources <= 0 or max_bytes <= 0:
            raise ValueError("syntax memo bounds must be positive")
        self.scanner = scanner
        self.max_sources = max_sources
        self.max_bytes = max_bytes
        self.entries = OrderedDict()
        self.payload_bytes = 0

    def syntax(self, source, data):
        _, records, failures = self.full_syntax(source, data)
        return records, failures

    def full_syntax(self, source, data):
        cached = self.entries.get(source)
        if cached is not None:
            previous, normalized, records, failures, weight = cached
            if previous == data:
                self.entries.move_to_end(source)
                return normalized, records, failures
            del self.entries[source]
            self.payload_bytes -= weight
        normalized, records, failures = self.scanner(data)
        records, failures = tuple(records), tuple(failures)
        # Bound key count and all retained text, including input, normalized,
        # include and diagnostic bytes. Oversized entries are not retained.
        weight = (len(source.encode("utf-8")) + len(data) + len(normalized) +
                  sum(len(value) for value, _ in records) +
                  sum(len(value.encode("utf-8")) for value in failures))
        if weight <= self.max_bytes:
            while self.entries and (
                    len(self.entries) >= self.max_sources or
                    self.payload_bytes + weight > self.max_bytes):
                _, (_, _, _, _, removed) = self.entries.popitem(last=False)
                self.payload_bytes -= removed
            self.entries[source] = (data, normalized, records, failures, weight)
            self.payload_bytes += weight
        return normalized, records, failures


def validate_compiler_include_reachability(
    root: Path,
    instances,
    registry,
    aliases: dict[str, str],
    occurrences: tuple[tuple[str, object, str], ...],
    exact_root_targets: frozenset[str],
    errors: list[str],
    *,
    active_origins: frozenset[str] | None = None,
    syntax_memo: CppIncludeSyntaxMemo | None = None,
) -> dict[str, tuple[str, ...]]:
    """Resolve each compiled TU recursively in its guaranteed environment."""
    config_bindings = native_crypto_config_bindings(instances, registry.declaration_paths, errors)
    model = _build_model(
        instances, registry, aliases, exact_root_targets, errors,
        active_origins=active_origins)
    _validate_read_only_include_root_closures(model, registry, errors)
    resolver = _EnvironmentResolver(model, registry, errors)
    offline_registrations = offline_source_registrations(occurrences, registry)
    queue: deque[tuple[str, str, PathSet, bool, str | None]] = deque(
        (target, source, instance.path_alternatives, False, source)
        for target, instance, source in occurrences)
    exported_inventory, exported_targets = _seed_exported_headers(
        root, model, registry, queue, errors)
    seen: set[tuple[str, str, PathSet, bool, str | None, str | None]] = set()
    inputs = IncludeInputs(root)
    native_inputs = NativeInputs(inputs)
    # Only pure byte syntax can cross profile boundaries. All traversal,
    # environments, physical inputs/probes and final freshness stay local.
    if syntax_memo is None:
        syntax_memo = CppIncludeSyntaxMemo()

    while queue:
        target, source_relative, universe, public_seed, translation_unit = queue.popleft()
        native_config = native_include_context(
            target, translation_unit, public_seed, config_bindings)
        offline_registration = (offline_registrations.get((target, translation_unit))
                                if not public_seed else None)
        key = (target, source_relative, universe, public_seed, native_config,
               (translation_unit if offline_registration is not None else
                (compression_translation_unit_context(target, translation_unit) or
                 benchmark_translation_unit_context(target, translation_unit))))
        if key in seen:
            continue
        seen.add(key)
        path = root / source_relative
        try:
            inputs.regular_relative(path)
        except (OSError, ValueError):
            errors.append(
                f"{target}: reachable source is missing, nonregular, or "
                f"symlinked: {source_relative}")
            continue
        suffix = path.suffix.lower()
        if suffix not in CPP_SCAN_SUFFIXES:
            errors.append(
                f"{target}: reachable repository include has unsupported "
                f"textual suffix: {source_relative}")
            continue
        try:
            data = inputs.read(source_relative)
            if compression_feature_mutation(target, translation_unit, data, public_seed=public_seed):
                raise OSError(f'unreviewed codec feature macro mutation: {source_relative}')
            native_verified = native_inputs.verify(source_relative, data)
            if (target == "cxet_offline_crypto_primitives" and native_config is not None and
                    native_test_configuration_error(source_relative, data)):
                raise OSError(f"unreviewed oracle source-local native/platform macro: {source_relative}")
        except OSError as exc:
            errors.append(f"cannot read reachable include {source_relative}: {exc}")
            continue
        effective_bindings = {target: native_config} if native_config is not None else {}
        environment = (
            resolver.interface(target)
            if public_seed else resolver.compile(target, universe))
        def native_probe(include):
            candidates = [path.parent / include,
                          *(root / include_root / include for include_root in environment.roots)]
            for candidate in candidates:
                if inputs.probe(candidate):
                    inputs.regular_relative(candidate)
                    return True
            return False
        data = native_crypto_include_data(
            root, target, source_relative, data, effective_bindings,
            read_input=inputs.read)
        try:
            configuration = native_inputs.configuration(native_config) if native_config is not None else None
            data = native_syntax_data(
                source_relative, data, verified=native_verified,
                config_data=configuration, probe_include=native_probe)
        except OSError as exc:
            errors.append(f"cannot prove native include configuration {source_relative}: {exc}")
            continue
        includes, include_failures = syntax_memo.syntax(source_relative, data)
        errors.extend(
            f"{source_relative}: {failure}"
            for failure in include_failures)
        for raw_include, quoted in includes:
            try:
                include = raw_include.decode("utf-8")
            except UnicodeError:
                errors.append(f"{source_relative}: non-UTF8 include path")
                continue
            if ("\\" in include or Path(include).is_absolute() or
                    not quoted and ".." in PurePosixPath(include).parts):
                errors.append(
                    f"{source_relative}: include has unsafe path syntax: "
                    f"{include}")
                continue
            local = path.parent / include
            try:
                candidates = (
                    [local] if quoted and inputs.probe(local) else
                    [root / include_root / include
                     for include_root in environment.roots])
            except OSError as exc:
                errors.append(f"{source_relative}: cannot probe include {include}: {exc}")
                continue
            selected: str | None = None
            for candidate in candidates:
                try:
                    exists = inputs.probe(candidate)
                except OSError as exc:
                    errors.append(f"{source_relative}: cannot probe include {include}: {exc}")
                    selected = ""
                    break
                if not exists:
                    continue
                try:
                    relative = inputs.regular_relative(candidate)
                except (OSError, ValueError):
                    errors.append(
                        f"{source_relative}: include is nonregular/symlinked: "
                        f"{include}")
                    selected = ""
                    break
                if source_artifact_path(relative):
                    errors.append(
                        f"{source_relative}: include enters generated tree: "
                        f"{relative}")
                    selected = ""
                    break
                selected = relative
                break
            if selected == "":
                continue
            exact_unresolved = verification_unresolved_quoted_include(
                source_relative, include)
            unresolved_requirement = (
                verification_unresolved_quoted_requirement(
                    source_relative, include))
            native_external = native_external_include(
                source_relative, include, verified=native_verified)
            benchmark_external = (not public_seed and benchmark_external_include(
                target, source_relative, include, translation_unit))
            offline_external = offline_external_include(
                offline_registration, source_relative, include, translation_unit,
                target=target, public_seed=public_seed)
            if (selected is not None and
                    (approved_external_angle_include(include) or native_external or benchmark_external or offline_external or
                     include in COMPRESSION_HEADER_PROVIDERS or
                     include == "liburing/io_uring_version.h")):
                errors.append(
                    f"{source_relative}: external include spelling is shadowed "
                    f"by repository file: {include} -> {selected}")
                continue
            if selected is not None and exact_unresolved:
                errors.append(
                    f"{source_relative}: reviewed provider/generated include "
                    f"became a repository shadow: {include} -> {selected}")
                continue
            if selected is None:
                if (include in COMPRESSION_HEADER_PROVIDERS and not public_seed and
                        compression_translation_unit_context(target, translation_unit) is not None):
                    try:
                        if not quoted and compression_conditional_include(
                                target, source_relative, include, translation_unit, data,
                                instances, inputs.read(COMPRESSOR_CMAKE), public_seed=False):
                            continue
                    except OSError as exc:
                        errors.append(f'{source_relative}: cannot prove codec feature/provider recipe: {exc}')
                        continue
                    errors.append(f'{source_relative}: unproved exact codec feature/provider include: {include}')
                    continue
                if exact_unresolved:
                    if unresolved_requirement is None:
                        errors.append(
                            f"{source_relative}: unresolved include has no "
                            f"typed provider contract: {include}")
                        continue
                    kind, required = unresolved_requirement
                    if kind == "external":
                        if (required in environment.external and
                                _scoped_external_include(
                                    include, environment.external)):
                            continue
                    elif kind == "generated":
                        if (required in environment.generated and
                                _generated_include_allowed(
                                    include, environment.generated)):
                            continue
                    elif kind == "dormant":
                        errors.append(
                            f"{source_relative}: dormant-only include became "
                            f"compiler-reachable: {include}")
                        continue
                elif (not quoted and (native_external or benchmark_external or offline_external or _scoped_external_include(
                        include, environment.external))):
                    continue
                elif (quoted and _cold_full_quoted_external(
                        target, source_relative, translation_unit, include,
                        environment.external, public_seed=public_seed)):
                    continue
                errors.append(
                    f"{source_relative}: {target} cannot resolve reviewed "
                    f"include {include}")
                continue
            if public_seed and not any(
                    selected == include_root or
                    selected.startswith(include_root.rstrip("/") + "/")
                    for include_root in environment.roots):
                errors.append(
                    f"{source_relative}: exported header reaches file outside "
                    f"its interface roots: {selected}")
                continue
            selected_exporters = exported_targets.get(selected, frozenset())
            if not vetron_full_api_available(selected, environment.providers):
                errors.append(
                    f"{source_relative}: Full Vetron API lacks its separate "
                    f"control/process provider: {selected}")
                continue
            source_owner = logical_header_owner(source_relative)
            selected_owner = logical_header_owner(selected)
            native_edge = native_crypto_include_edge(
                target, source_relative, selected, config=native_config)
            benchmark_edge = (not public_seed and benchmark_include_edge(
                target, source_relative, selected, translation_unit))
            offline_private = offline_private_header_edge(
                offline_registration, source_relative, selected, translation_unit)
            offline_public = offline_public_header_edge(
                offline_registration, source_relative, selected, translation_unit)
            private_owner = (not public_seed and
                _private_owner_header_access(target, selected, universe, model, errors))
            if not experimental_api_available(selected, environment.providers):
                errors.append(
                    f"{source_relative}: experimental API lacks its selected "
                    f"offline provider: {selected}")
                continue
            private_composition = private_composition_include(
                target, source_relative, selected, environment.roots,
                public_seed=public_seed)
            if (selected in API_HEADER_OWNERS and
                    API_HEADER_OWNERS[selected] is None and not private_composition):
                errors.append(
                    f"{source_relative}: private composition header lacks "
                    f"reviewed implementation ownership: {selected}")
                continue
            if not finance_leaf_include(source_relative, selected, target):
                errors.append(
                    f"{source_relative}: production finance includes a non-leaf "
                    f"trading-core API: {selected}")
                continue
            if ((public_seed and not selected_exporters or
                    selected_owner is not None and
                    selected_owner != source_owner and
                    not selected_exporters) and not native_edge and not benchmark_edge and not offline_private):
                errors.append(
                    f"{source_relative}: include reaches non-exported family "
                    f"header across a public/owner boundary: {selected}")
                continue
            if (selected_exporters and
                    not (selected_exporters & environment.providers) and
                    not private_owner and
                    not (benchmark_edge and benchmark_backend_include_edge(target, selected)) and not offline_public):
                errors.append(
                    f"{source_relative}: include reaches {selected} without "
                    "the canonical exporting target interface")
                continue
            selected_suffix = Path(selected).suffix.lower()
            native_textual = native_crypto_textual_source(target, source_relative, selected)
            if selected_suffix in CPP_NON_TEXTUAL_INCLUDE_SUFFIXES and not native_textual:
                errors.append(
                    f"{source_relative}: include names compiled source: "
                    f"{selected}")
                continue
            if selected_suffix not in CPP_TEXTUAL_INCLUDE_SUFFIXES and not native_textual:
                errors.append(
                    f"{source_relative}: reachable repository include has "
                    f"unsupported textual suffix: {selected}")
                continue
            if (not verification_include_allowed(source_relative, selected) and
                    not (not public_seed and
                         parser_process_include(target, source_relative, selected)) and
                    not native_edge and not benchmark_edge and not offline_private and not offline_public):
                errors.append(
                    f"{source_relative}: {target} include crosses canonical "
                    f"ownership: {selected}")
                continue
            queue.append((target, selected, universe, public_seed, translation_unit))
    errors.extend(inputs.validate())
    return exported_inventory
