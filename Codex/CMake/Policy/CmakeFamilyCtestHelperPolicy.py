"""Exact CTest helper and label-writer contracts for family applications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from CMake.Policy.CmakeFamilyConditionPolicy import exact_command_contexts
from CMake.Syntax.CmakeFamilyLexer import scan_commands, words
from Family.Targets.CxetFamilyTargetInventory import TRADING_CORE_CONTRACT_TESTS


_TRADING_CORE_INVOCATION_TAILS = {
    "trading-core-algorithm-contract-tests": (
        "trading_core::algorithm", 'Ported/Algorithm/AlgorithmCoreContractTests.cpp'),
    "trading-core-alert-condition-contract-tests": (
        "trading_core::algorithm", 'AlertConditionContractTests.cpp'),
    "trading-core-delivery-sum-signal-tests": (
        "trading_core::strategy", "DeliverySumSignalContractTests.cpp"),
    "trading-core-mid-price-contract-tests": (
        "trading_core::algorithm", 'Ported/Market/MidPriceContractTests.cpp'),
    "trading-core-aggregated-orderbook-tests": (
        "trading_core::algorithm", 'Ported/Market/AggregatedOrderBookTests.cpp'),
    "trading-core-bps-math-tests": (
        "trading_core::algorithm", 'Ported/Math/BpsMathTests.cpp'),
    "trading-core-public-analytics-parity-tests": (
        "trading_core::algorithm", 'Ported/Math/PublicAnalyticsParityTests.cpp'),
    "trading-core-ewma-math-tests": (
        "trading_core::algorithm", 'Ported/Math/EwmaMathTests.cpp'),
    "trading-core-wide-division-tests": (
        "trading_core::algorithm", 'Ported/Math/WideDivisionTests.cpp'),
    "trading-core-formula-contract-tests": (
        "trading_core::algorithm", 'Ported/Math/FormulaContractTests.cpp'),
    "trading-core-delivery-basis-tests": (
        "trading_core::algorithm", 'Ported/Signals/DeliveryBasisTests.cpp'),
    "trading-core-pair-mean-reversion-tests": (
        "trading_core::algorithm", 'Ported/Signals/PairMeanReversionTests.cpp'),
    "trading-core-recursive-signal-helpers-tests": (
        "trading_core::algorithm", 'Ported/Signals/RecursiveSignalHelpersTests.cpp'),
    "trading-core-toxic-flow-score-tests": (
        "trading_core::algorithm", 'Ported/Signals/ToxicFlowScoreTests.cpp'),
    "trading-core-trend-score-tests": (
        "trading_core::algorithm", 'Ported/Signals/TrendScoreTests.cpp'),
    "trading-core-volatility-bps-tests": (
        "trading_core::algorithm", 'Ported/Signals/VolatilityBpsTests.cpp'),
    "trading-core-execution-state-tracker-tests": (
        "trading_core::execution", 'Ported/Execution/ExecutionStateTrackerTests.cpp'),
    "trading-core-late-order-journal-tests": (
        "trading_core::execution", 'Ported/Execution/LateOrderJournalTests.cpp'),
    "trading-core-limit-quote-replace-tests": (
        "trading_core::execution", 'Ported/Execution/LimitQuoteReplaceTests.cpp'),
    "trading-core-maker-fill-evidence-tests": (
        "trading_core::execution", 'Ported/Execution/MakerFillEvidenceTests.cpp'),
    "trading-core-order-lifecycle-tests": (
        "trading_core::execution", 'Ported/Execution/OrderLifecycleToolsTests.cpp'),
    "trading-core-order-replace-policy-tests": (
        "trading_core::execution", 'Ported/Execution/OrderReplacePolicyTests.cpp'),
    "trading-core-order-state-rules-tests": (
        "trading_core::execution", 'Ported/Execution/OrderStateRulesTests.cpp'),
    "trading-core-position-tools-tests": (
        "trading_core::execution", 'Ported/Execution/PositionToolsTests.cpp'),
    "trading-core-speculative-fill-tools-tests": (
        "trading_core::execution", 'Ported/Execution/SpeculativeFillToolsTests.cpp'),
    "trading-core-user-event-identity-tests": (
        "trading_core::execution", 'Ported/Execution/UserEventIdentityTests.cpp'),
    "trading-core-rate-limit-maker-guard-tests": (
        "trading_core::execution", 'Ported/Risk/RateLimitMakerGuardTests.cpp'),
    "trading-core-rate-limit-state-tests": (
        "trading_core::execution", 'Ported/Risk/RateLimitStateTests.cpp'),
    "trading-core-strategy-input-freshness-tests": (
        "trading_core::strategy", 'Ported/Strategy/StrategyInputFreshnessTests.cpp'),
    "trading-core-strategy-warmup-tests": (
        "trading_core::strategy", 'Ported/Strategy/StrategyWarmupTests.cpp'),
    "trading-core-position-add-risk-tests": (
        "trading_core::execution", 'Ported/Risk/PositionAddRiskTests.cpp'),
    "trading-core-fill-position-accounting-semantic-tests": (
        "trading_core::execution", 'Semantic/FillPositionAccountingSemanticTests.cpp'),
    "trading-core-portfolio-risk-semantic-tests": (
        "trading_core::execution", 'Semantic/PortfolioRiskSemanticTests.cpp'),
    "trading-core-position-add-risk-semantic-tests": (
        "trading_core::execution", 'Semantic/PositionAddRiskSemanticTests.cpp'),
    "trading-core-recovery-journal-model-semantic-tests": (
        "trading_core::execution", 'Semantic/RecoveryJournalModelSemanticTests.cpp'),
    "trading-core-sequential-replace-lifecycle-semantic-tests": (
        "trading_core::execution", 'Semantic/SequentialReplaceLifecycleSemanticTests.cpp'),
    "trading-core-scoped-rate-limit-semantic-tests": (
        "trading_core::execution", 'Semantic/ScopedRateLimitSemanticTests.cpp'),
    "trading-core-account-risk-semantic-tests": (
        "trading_core::execution", 'Semantic/AccountRiskSemanticTests.cpp'),
    "trading-core-strategy-stop-policy-tests": (
        "trading_core::strategy", 'Semantic/StrategyStopPolicyTests.cpp'),
    "trading-core-strategy-checkpoint-tests": (
        "trading_core::strategy", 'Semantic/StrategyCheckpointTests.cpp'),
    "trading-core-strategy-checkpoint-state-tests": (
        "trading_core::strategy", 'Semantic/StrategyCheckpointStateTests.cpp'),
}
_OPTIONAL_TRADING_CORE_BBO_TEST = "trading-core-bbo-reconstruction-tests"
_OPTIONAL_TRADING_CORE_BBO_TAIL = (
    "trading_core::algorithm", "Ported/Market/BboReconstructionTests.cpp")


@dataclass(frozen=True)
class _Command:
    name: str
    body: str
    line: int
    offset: int


def _parse_commands(
    relative: str,
    text: str,
    errors: list[str],
) -> list[_Command]:
    return scan_commands(
        relative,
        text,
        errors,
        lambda name, body, line, offset: _Command(
            name, body, line, offset),
    )


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] == '"':
        return value[1:-1]
    return value


_EXPECTED_SIGNATURES = {
    "trading_core_add_contract_test": (
        "trading_core_add_contract_test", "target", "dependency"),
    "add_hft_backtest_test": (
        "add_hft_backtest_test", "target", "source"),
    "trader_contract_test": (
        "trader_contract_test", "target", "source"),
}

_EXPECTED_FUNCTION_DECLARATIONS = {
    "trading_core_add_contract_test": (
        ("function", (
            "trading_core_add_contract_test", "target", "dependency"), ()),
    ),
    "add_hft_backtest_test": (
        ("function", ("add_hft_backtest_test", "target", "source"), ()),
    ),
    "trader_contract_test": (
        ("function", ("trader_private_defaults", "target"), ()),
        ("function", ("trader_contract_test", "target", "source"), ()),
    ),
}

_EXPECTED_HELPER_COMMANDS = {
    "trading_core_add_contract_test": (
        ("add_executable", ("${target}", "${ARGN}")),
        ("target_compile_features", (
            "${target}", "PRIVATE", "cxx_std_23")),
        ("target_link_libraries", (
            "${target}", "PRIVATE", "${dependency}")),
        ("set_target_properties", (
            "${target}", "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            "${CMAKE_BINARY_DIR}")),
        ("add_test", (
            "NAME", "${target}", "COMMAND", "$<TARGET_FILE:${target}>")),
        ("set_tests_properties", (
            "${target}", "PROPERTIES", "WORKING_DIRECTORY",
            "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
            "cxet-family;trading-core;contract;trader-autonomous-acceptance")),
    ),
    "add_hft_backtest_test": (
        ("add_executable", ("${target}", "${source}")),
        ("target_include_directories", (
            "${target}", "PRIVATE",
            "${CMAKE_CURRENT_SOURCE_DIR}/src/Runtime/src")),
        ("target_link_libraries", (
            "${target}", "PRIVATE", "hft_backtest_core",
            "trading_core::strategy", "hftrec::corpus_contract",
            "${ARGN}")),
        ("target_compile_features", (
            "${target}", "PRIVATE", "cxx_std_23")),
        ("set_target_properties", (
            "${target}", "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            "${CMAKE_BINARY_DIR}")),
        ("add_test", (
            "NAME", "${target}", "COMMAND", "$<TARGET_FILE:${target}>")),
        ("set_tests_properties", (
            "${target}", "PROPERTIES", "WORKING_DIRECTORY",
            "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
            "cxet-family;hft-backtest;contract")),
    ),
    "trader_contract_test": (
        ("add_executable", ("${target}", "${source}")),
        ("target_link_libraries", (
            "${target}", "PRIVATE", "${ARGN}")),
        ("trader_private_defaults", ("${target}", "CONTRACT_TEST")),
        ("add_test", (
            "NAME", "${target}", "COMMAND", "$<TARGET_FILE:${target}>")),
        ("set_tests_properties", (
            "${target}", "PROPERTIES", "WORKING_DIRECTORY",
            "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
            "cxet-family;trader;contract;trader-autonomous-acceptance")),
    ),
}

_EXPECTED_INVOCATIONS = {
    "trading_core_add_contract_test": TRADING_CORE_CONTRACT_TESTS,
    "add_hft_backtest_test": (
        "hft-backtest-execution-tests",
        "hft-backtest-client-order-id-tests",
        "hft-backtest-replace-lifecycle-tests",
        "hft-backtest-stat-arb-late-fill-lifecycle-tests",
        "hft-backtest-strategy-config-tests",
        "hft-backtest-passive-bbo-touch-tests",
        "hft-backtest-stop-limit-tests",
        "hft-backtest-rate-limit-tests",
        "hft-backtest-multileg-context-tests",
        "hft-backtest-transaction-admission-tests",
        "hft-backtest-stat-arb-replay-tests",
        "hft-backtest-strategy-indicator-tests",
        "hft-backtest-strategy-profile-tests",
        "hft-backtest-metrics-tests",
        "hft-backtest-accounting-tests",
        "hft-backtest-session-loader-tests",
        "hft-backtest-sweep-tests",
    ),
    "trader_contract_test": (
        "trader-alert-service-contract-tests",
        "trader-alert-metric-contract-tests",
        "trader-alert-runtime-contract-tests",
        "trader-alert-pipeline-contract-tests",
        "trader-account-fixture-contract-tests",
        "trader-boundary-contract-tests",
        "trader-market-observe-runtime-contract-tests",
        "finam_live_recovery_contract_tests",
        "trader-multivenue-runtime-contract-tests",
        "trader-strategy-launch-contract-tests",
        "trader-finam-process-contract-tests",
        "trader-finam-admission-policy-contract-tests",
        "trader-profile-universe-runtime-contract-tests",
        "trader-profile-universe-live-cycle-contract-tests",
        "trader-profile-writer-lease-contract-tests",
        "trader-profile-journal-writer-contract-tests",
        "trader-profile-journal-segments-contract-tests",
        "trader-strategy-launch-preparation-contract-tests",
        "trader-profile-control-journal-contract-tests",
        "trader-durable-id-lease-store-contract-tests",
        "trader-private-capacity-contract-tests",
        "trader-private-client-contract-tests",
        "trader-private-protocol-contract-tests",
        "trader-order-protocol-contract-tests",
        "trader-order-client-contract-tests",
        "trader-order-bootstrap-native-identity-contract-tests",
        "trader-order-bootstrap-token-contract-tests",
        "trader-control-protocol-contract-tests",
        "trader-control-operations-contract-tests",
        "trader-projection-client-contract-tests",
        "trader-market-observe-projection-client-contract-tests",
        "trader-projection-transport-contract-tests",
        "trader-replace-lifecycle-contract-tests",
    ),
}

_PARSER_TEST_SCOPE = (("if", ("HFT_PARSER_BUILD_TESTS",)),)
_PARSER_REGISTERED_TESTS = (
    "hft-parser-bounded-dns-resolver-contract-tests",
    "hft-parser-sessiond-application-contract-tests",
    "hft-parser-session-protocol-contract-tests",
    "hft-parser-session-${_session_case}-contract-tests",
    "hft-parser-native-order-session-contract-tests",
    "hft-parser-native-account-session-contract-tests",
    "hft-parser-native-recovery-contract-tests",
    "hft-parser-native-account-${_native_identity_case}-contract-tests",
    "hft-parser-candle-history-startup-policy-contract-tests",
    "hft-parser-finam-catalog-refresh-policy-contract-tests",
    "hft-parser-finam-catalog-presentation-contract-tests",
    "hft-parser-launcher-storage-contract-tests",
    "hft-parser-finam-continuous-price-contract-tests",
    "hft-parser-finam-sidecar-quota-contract-tests",
    "hft-parser-moex-basis-reference-contract-tests",
    "hft-parser-instrument-catalog-selection-contract-tests",
    "hft-parser-grpc-instrument-catalog-budget-contract-tests",
    "hft-parser-tbank-topology-contract-tests",
    "hft-parser-tbank-credential-owner-contract-tests",
    "hft-parser-grpc-request-admission-contract-tests",
    "hft-parser-finam-catalog-cache-policy-contract-tests",
    "hft-parser-finam-reference-metadata-checkpoint-contract-tests",
    "hft-parser-reference-startup-projection-contract-tests",
    "hft-parser-reference-instrument-provenance-contract-tests",
    "hft-parser-public-market-execution-families-contract-tests",
    "hft-parser-startup-config-trust-contract-tests",
    "hft-parser-depth-source-reconciler-contract-tests",
    "hft-parser-depth-shared-contract-tests",
    "hft-parser-public-market-shard-planner-contract-tests",
    "hft-parser-public-market-registry-contract-tests",
    "hft-parser-spot-capability-bootstrap-contract-tests",
    "hft-parser-public-market-capacity-contract-tests",
    "hft-parser-execution-client-contract-tests",
    "hft-parser-execution-topology-client-contract-tests",
    "hft-parser-execution-publication-sink-contract-tests",
    "hft-parser-execution-production-owner-contract-tests",
    "hft-parser-projection-client-contract-tests",
    "hft-parser-public-market-fence-contract-tests",
    "hft-parser-projection-source-contract-tests",
    "hft-parser-reference-projection-client-contract-tests",
    "hft-parser-reference-projection-publisher-contract-tests",
    "hft-parser-history-client-contract-tests",
    "hft-parser-current-history-focus-contract-tests",
    "hft-parser-finam-candle-archive-owner-contract-tests",
    "hft-parser-${_saved_archive_test}-contract-tests",
    "hft-parser-finam-archive-directory-contract-tests",
    "hft-parser-history-source-owner-contract-tests",
    "hft-parser-resource-planner-contract-tests",
    "hft-parser-transport-runtime-contract-tests",
    "hft-parser-market-history-attempt-budget-contract-tests",
    "hft-parser-market-history-page-policy-contract-tests",
    "hft-parser-market-history-worker-stall-tests",
    "hft-parser-history-diagnostic-policy-contract-tests",
    "hft-parser-boundary-contract",
)
PARSER_FAMILY_ACCEPTANCE_TESTS = (
    "hft-parser-candle-history-startup-policy-contract-tests",
    "hft-parser-finam-catalog-refresh-policy-contract-tests",
    "hft-parser-finam-catalog-presentation-contract-tests",
    "hft-parser-launcher-storage-contract-tests",
    "hft-parser-finam-continuous-price-contract-tests",
    "hft-parser-finam-sidecar-quota-contract-tests",
    "hft-parser-moex-basis-reference-contract-tests",
    "hft-parser-instrument-catalog-selection-contract-tests",
    "hft-parser-grpc-instrument-catalog-budget-contract-tests",
    "hft-parser-tbank-topology-contract-tests",
    "hft-parser-tbank-credential-owner-contract-tests",
    "hft-parser-grpc-request-admission-contract-tests",
    "hft-parser-finam-catalog-cache-policy-contract-tests",
    "hft-parser-finam-reference-metadata-checkpoint-contract-tests",
    "hft-parser-reference-startup-projection-contract-tests",
    "hft-parser-reference-instrument-provenance-contract-tests",
    "hft-parser-public-market-execution-families-contract-tests",
    "hft-parser-startup-config-trust-contract-tests",
    "hft-parser-depth-source-reconciler-contract-tests",
    "hft-parser-depth-shared-contract-tests",
    "hft-parser-public-market-shard-planner-contract-tests",
    "hft-parser-public-market-registry-contract-tests",
    "hft-parser-spot-capability-bootstrap-contract-tests",
    "hft-parser-public-market-capacity-contract-tests",
    "hft-parser-execution-client-contract-tests",
    "hft-parser-execution-topology-client-contract-tests",
    "hft-parser-execution-publication-sink-contract-tests",
    "hft-parser-execution-production-owner-contract-tests",
    "hft-parser-projection-client-contract-tests",
    "hft-parser-public-market-fence-contract-tests",
    "hft-parser-projection-source-contract-tests",
    "hft-parser-reference-projection-client-contract-tests",
    "hft-parser-reference-projection-publisher-contract-tests",
    "hft-parser-history-client-contract-tests",
    "hft-parser-current-history-focus-contract-tests",
    "hft-parser-finam-candle-archive-owner-contract-tests",
    "hft-parser-history-source-owner-contract-tests",
    "hft-parser-finam-archive-directory-contract-tests",
    "hft-parser-resource-planner-contract-tests",
    "hft-parser-transport-runtime-contract-tests",
    "hft-parser-market-history-attempt-budget-contract-tests",
    "hft-parser-market-history-page-policy-contract-tests",
    "hft-parser-market-history-worker-stall-tests",
    "hft-parser-history-diagnostic-policy-contract-tests",
    "hft-parser-boundary-contract",
)
TRADING_CORE_FAMILY_ACCEPTANCE_TESTS = TRADING_CORE_CONTRACT_TESTS
_PARSER_SESSION_LOOP = ("foreach", (
    "_session_case", "IN", "ITEMS", "service", "socket"))
_PARSER_NATIVE_IDENTITY_LOOP = ("foreach", (
    "_native_identity_case", "IN", "ITEMS", "identity", "writer_lease"))
_PARSER_SAVED_ARCHIVE_LOOP = ("foreach", (
    "_saved_archive_test", "IN", "ITEMS", "tbank-candle-archive",
    "saved-archive-catalog-store"))

_EXPECTED_ACCEPTANCE_PROPERTY_WRITERS = {
    "apps/trading-core/tests/CMakeLists.txt": (
        ((("function", (
            "trading_core_add_contract_test", "target", "dependency")),),
         "set_tests_properties", (
             "${target}", "PROPERTIES", "WORKING_DIRECTORY",
             "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
             "cxet-family;trading-core;contract;"
             "trader-autonomous-acceptance")),
        ((), "set_property", (
            "TEST", "trading-core-execution-state-tracker-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-late-order-journal-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-limit-quote-replace-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-order-lifecycle-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-order-replace-policy-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-order-state-rules-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "trading-core-user-event-identity-tests", "APPEND",
            "PROPERTY", "LABELS", "private-recovery")),
        ((), "set_property", (
            "TEST", "trading-core-rate-limit-maker-guard-tests", "APPEND",
            "PROPERTY", "LABELS", "rate-limit")),
        ((), "set_property", (
            "TEST", "trading-core-rate-limit-state-tests", "APPEND",
            "PROPERTY", "LABELS", "rate-limit")),
        ((), "set_property", (
            "TEST", "trading-core-stat-arb-edge-maker-tests", "APPEND",
            "PROPERTY", "LABELS", "order-race;lifecycle")),
        ((), "set_property", (
            "TEST", "${trading_core_safety_tests}", "APPEND", "PROPERTY",
            "LABELS", "trading-core-safety;safety")),
        ((), "set_tests_properties", (
            "${trading_core_safety_tests}", "PROPERTIES", "TIMEOUT", "120")),
        ((("if", (
            "CXET_SANITIZER_PROFILE", "STREQUAL", '"address-undefined"')),),
         "set_tests_properties", (
             "${trading_core_safety_tests}", "PROPERTIES", "ENVIRONMENT",
             "ASAN_OPTIONS=detect_stack_use_after_return=1:"
             "detect_stack_use_after_scope=1:halt_on_error=1:abort_on_error=1;"
             "UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1")),
        ((("elseif", (
            "CXET_SANITIZER_PROFILE", "STREQUAL", '"thread"')),),
         "set_tests_properties", (
             "${trading_core_safety_tests}", "PROPERTIES", "ENVIRONMENT",
             "TSAN_OPTIONS=halt_on_error=1:abort_on_error=1")),
        ((), "set_property", (
            "TEST", "trading-core-fill-position-accounting-semantic-tests",
            "APPEND", "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-portfolio-risk-semantic-tests", "APPEND",
            "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-position-add-risk-semantic-tests", "APPEND",
            "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-recovery-journal-model-semantic-tests",
            "APPEND", "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-sequential-replace-lifecycle-semantic-tests",
            "APPEND", "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-scoped-rate-limit-semantic-tests", "APPEND",
            "PROPERTY", "LABELS", "semantic")),
        ((), "set_property", (
            "TEST", "trading-core-account-risk-semantic-tests",
            "trading-core-strategy-stop-policy-tests",
            "trading-core-strategy-checkpoint-tests",
            "trading-core-strategy-checkpoint-state-tests",
            "APPEND", "PROPERTY", "LABELS", "semantic")),
    ),
    "apps/hft-parser/cmake/HftpTests.cmake": (
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-bounded-dns-resolver-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;hft-parser;contract;transport")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-sessiond-application-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;hft-parser;contract;session")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-session-protocol-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;contract;session;"
            "trader-autonomous-acceptance")),
        ((_PARSER_TEST_SCOPE[0], _PARSER_SESSION_LOOP),
         "set_tests_properties", (
             "hft-parser-session-${_session_case}-contract-tests",
             "PROPERTIES", "LABELS", "cxet-family;contract;session;"
             "trader-autonomous-acceptance")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-native-order-session-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;contract;session;"
            "trader-autonomous-acceptance")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-native-account-session-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;contract;session;"
            "trader-autonomous-acceptance")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-native-recovery-contract-tests", "PROPERTIES",
            "LABELS", "cxet-family;contract;session;"
            "trader-autonomous-acceptance")),
        ((_PARSER_TEST_SCOPE[0], _PARSER_NATIVE_IDENTITY_LOOP),
         "set_tests_properties", (
             "hft-parser-native-account-${_native_identity_case}-contract-tests",
             "PROPERTIES", "LABELS", "cxet-family;contract;session;"
             "trader-autonomous-acceptance")),
        ((_PARSER_TEST_SCOPE[0], _PARSER_SAVED_ARCHIVE_LOOP),
         "set_tests_properties", (
             "hft-parser-${_saved_archive_test}-contract-tests", "PROPERTIES",
             "LABELS", "cxet-family;hft-parser;contract")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "hft-parser-market-history-worker-stall-tests", "PROPERTIES",
            "TIMEOUT", "20")),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            "${_hftp_family_contract_tests}", "PROPERTIES", "LABELS",
            "cxet-family;hft-parser;contract")),
        (_PARSER_TEST_SCOPE, "set_property", (
            "TEST", "hft-parser-execution-client-contract-tests", "APPEND",
            "PROPERTY", "LABELS",
            "public-execution;four-consumer-overload;"
            "selected-source-capacity;wire;ipc")),
        (_PARSER_TEST_SCOPE, "set_property", (
            "TEST", "hft-parser-execution-topology-client-contract-tests",
            "APPEND", "PROPERTY", "LABELS",
            "public-execution;topology;wire;ipc")),
        (_PARSER_TEST_SCOPE, "set_property", (
            "TEST", "hft-parser-transport-runtime-contract-tests", "APPEND",
            "PROPERTY", "LABELS", "transport")),
        (_PARSER_TEST_SCOPE, "set_property", (
            "TEST", "hft-parser-startup-config-trust-contract-tests",
            "APPEND", "PROPERTY", "LABELS",
            "security;startup-config;trust-boundary")),
        (_PARSER_TEST_SCOPE, "set_property", (
            "TEST", "hft-parser-boundary-contract", "APPEND", "PROPERTY",
            "LABELS", "static;ownership")),
    ),
    "apps/vetron/CMakeLists.txt": (
        ((), "set_tests_properties", (
            "vetron_backend_contract_tests", "PROPERTIES", "LABELS",
            "cxet-family;vetron;read-only;full;contract;"
            "trader-autonomous-acceptance")),
        ((), "set_tests_properties", (
            "vetron_reference_status_contract_tests", "PROPERTIES", "LABELS",
            "cxet-family;vetron;read-only;contract;"
            "trader-autonomous-acceptance")),
        ((), "set_tests_properties", (
            "vetron_history_focus_contract_tests", "PROPERTIES", "LABELS",
            "cxet-family;vetron;read-only;contract;"
            "trader-autonomous-acceptance")),
        ((), "set_tests_properties", (
            "vetron_gateway_queue_contract_tests", "PROPERTIES", "LABELS",
            "cxet-family;vetron;read-only;gateway;contract")),
        ((), "set_tests_properties", (
            "vetron_loopback_contract_tests", "PROPERTIES", "LABELS",
            "cxet-family;vetron;read-only;full;loopback;contract;"
            "trader-autonomous-acceptance")),
        ((("if", ("VETRON_BUILD_FRONTEND_CONTRACT_TESTS",)),),
         "set_tests_properties", (
             "vetron_frontend_contract_tests", "PROPERTIES",
             "WORKING_DIRECTORY", "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
             "cxet-family;vetron;read-only;frontend;contract;"
             "trader-autonomous-acceptance")),
    ),
    "src/tests/Family/CMakeLists.txt": (
        ((("if", ("CXET_FAMILY_PROFILE", "STREQUAL", '"full"')),),
         "set_tests_properties", (
            "cxet-family-strategy-differential", "PROPERTIES",
            "WORKING_DIRECTORY", "${PROJECT_SOURCE_DIR}", "LABELS",
            "cxet-family;strategy-differential;fault;contract")),
        ((), "set_tests_properties", (
            "cxet-family-public-execution-contract", "PROPERTIES",
            "WORKING_DIRECTORY", "${PROJECT_SOURCE_DIR}", "LABELS",
            "cxet-family;public-execution;shard-capacity;schema;contract")),
        ((), "set_tests_properties", (
            "cxet-family-root-graph-static", "PROPERTIES", "WORKING_DIRECTORY",
            "${PROJECT_SOURCE_DIR}", "LABELS",
            "cxet-family;static;ownership;root-graph")),
        ((), "set_tests_properties", (
            "cxet-family-ownership-static", "PROPERTIES", "WORKING_DIRECTORY",
            "${PROJECT_SOURCE_DIR}", "LABELS",
            "cxet-family;static;ownership;canonical-owner")),
    ),
}

_DIRECT_TEST_WRITER_ORDER = {
    "apps/vetron/CMakeLists.txt": (
        "vetron_backend_contract_tests",
        "vetron_reference_status_contract_tests",
        "vetron_history_focus_contract_tests",
        "vetron_gateway_queue_contract_tests",
        "vetron_loopback_contract_tests",
        "vetron_frontend_contract_tests",
    ),
    "src/tests/Family/CMakeLists.txt": (
        "cxet-family-strategy-differential",
        "cxet-family-public-execution-contract",
        "cxet-family-root-graph-static",
        "cxet-family-ownership-static",
    ),
}

_PARSER_TAIL_SHA256 = (
    "e689f715baedb9c0ff138fb70a6f6250dbe18d3147dc69960ef804081ff5ec9e")


def validate_acceptance_property_writer_inventory(
    relative: str,
    commands,
    errors: list[str],
) -> None:
    """Reject extra, reordered, bracket-obscured, or re-scoped TEST writers."""
    expected = _EXPECTED_ACCEPTANCE_PROPERTY_WRITERS.get(relative)
    if expected is None:
        errors.append(
            f"{relative}: missing exact acceptance property-writer policy")
        return
    actual = tuple(
        (scope, command.name,
         tuple(_unquote(value) for value in words(command.body)))
        for command, scope in exact_command_contexts(commands)
        if command.name in {"set_property", "set_tests_properties"}
    )
    if actual != expected:
        errors.append(
            f"{relative}: exact ordered acceptance property-writer inventory "
            "changed")
    if any(
            command.name in {"break", "continue", "return"}
            for command in commands):
        errors.append(
            f"{relative}: control transfer may not bypass acceptance "
            "registration")
    for test_name in _DIRECT_TEST_WRITER_ORDER.get(relative, ()):
        registrations = [
            command for command in commands
            if command.name == "add_test" and
            tuple(_unquote(value) for value in words(command.body))[:2] ==
            ("NAME", test_name)
        ]
        writers = [
            command for command in commands
            if command.name == "set_tests_properties" and
            test_name in tuple(
                _unquote(value) for value in words(command.body))
        ]
        if (len(registrations) != 1 or len(writers) != 1 or
                registrations[0].offset >= writers[0].offset):
            errors.append(
                f"{relative}: test {test_name} must be registered before "
                "its exact property writer")


def _exact_text_tail(
    relative: str,
    text: str,
    start_marker: str,
    end_marker: str,
    expected_sha256: str,
    errors: list[str],
) -> bool:
    if text.count(start_marker) != 1 or text.count(end_marker) != 1:
        errors.append(f"{relative}: exact CTest tail markers changed")
        return False
    start = text.find(start_marker)
    end_start = text.find(end_marker, start)
    if start < 0 or end_start < start:
        errors.append(f"{relative}: exact CTest tail order changed")
        return False
    end = end_start + len(end_marker)
    actual = hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()
    if actual != expected_sha256:
        errors.append(f"{relative}: exact CTest label tail changed")
        return False
    return True




def validate_parser_ctest_contract(
    relative: str,
    text: str,
    commands,
    tests,
    errors: list[str],
) -> bool:
    """Pin every Parser family test, command, label-list, and event order."""
    expected_commands = {
        test_name: (test_name,)
        for test_name in _PARSER_REGISTERED_TESTS
    }
    expected_commands["hft-parser-launcher-storage-contract-tests"] = (
        "python3",
        '${CMAKE_CURRENT_SOURCE_DIR}/tests/Parser/LauncherStorageContractTests.py',
    )
    expected_commands["hft-parser-boundary-contract"] = (
        "bash",
        '${CMAKE_CURRENT_SOURCE_DIR}/tests/Contracts/BoundaryTests.sh',
    )
    expected_scopes = {
        "hft-parser-session-${_session_case}-contract-tests": (
            _PARSER_TEST_SCOPE[0], _PARSER_SESSION_LOOP),
        "hft-parser-native-account-${_native_identity_case}-contract-tests": (
            _PARSER_TEST_SCOPE[0], _PARSER_NATIVE_IDENTITY_LOOP),
        "hft-parser-${_saved_archive_test}-contract-tests": (
            _PARSER_TEST_SCOPE[0], _PARSER_SAVED_ARCHIVE_LOOP),
    }
    expected_registrations = tuple(
        (expected_scopes.get(test_name, _PARSER_TEST_SCOPE), "add_test", (
            "NAME", test_name, "COMMAND", *expected_commands[test_name],
        ))
        for test_name in _PARSER_REGISTERED_TESTS
    )
    actual_registrations = tuple(
        (scope, command.name,
         tuple(_unquote(value) for value in words(command.body)))
        for command, scope in exact_command_contexts(commands)
        if command.name == "add_test"
    )
    registrations_ok = actual_registrations == expected_registrations
    if not registrations_ok:
        errors.append(
            f"{relative}: exact ordered Parser add_test inventory changed")

    variable = "_hftp_family_contract_tests"
    variable_reference = f"${{{variable}}}"
    expected_events = (
        (_PARSER_TEST_SCOPE, "set", (
            variable, *PARSER_FAMILY_ACCEPTANCE_TESTS)),
        (_PARSER_TEST_SCOPE, "set_tests_properties", (
            variable_reference, "PROPERTIES", "LABELS",
            "cxet-family;hft-parser;contract")),
        (_PARSER_TEST_SCOPE, "unset", (variable,)),
    )
    actual_events = tuple(
        (scope, command.name,
         tuple(_unquote(value) for value in words(command.body)))
        for command, scope in exact_command_contexts(commands)
        if any(
            _unquote(value) in {variable, variable_reference}
            for value in words(command.body))
    )
    events_ok = actual_events == expected_events
    if not events_ok:
        errors.append(
            f"{relative}: Parser family label-list lifecycle changed")

    modeled_ok = set(tests) == set(_PARSER_REGISTERED_TESTS)
    for test_name, expected_command in expected_commands.items():
        registration = tests.get(test_name)
        if (registration is None or
                registration.command != expected_command or
                registration.scope != expected_scopes.get(
                    test_name, _PARSER_TEST_SCOPE)):
            modeled_ok = False
    if not modeled_ok:
        errors.append(
            f"{relative}: modeled Parser family commands/scopes changed")

    add_tests = [
        command for command, _ in exact_command_contexts(commands)
        if command.name == "add_test"]
    lifecycle = [
        command for command, _ in exact_command_contexts(commands)
        if command.name in {"set", "set_tests_properties", "unset"}
        and any(
            _unquote(value) in {variable, variable_reference}
            for value in words(command.body))
    ]
    order_ok = (
        bool(add_tests) and len(lifecycle) == 3 and
        add_tests[-1].offset < lifecycle[0].offset < lifecycle[1].offset <
        lifecycle[2].offset
    )
    if not order_ok:
        errors.append(
            f"{relative}: Parser registrations and label lifecycle are "
            "reordered")

    tail_ok = _exact_text_tail(
        relative,
        text,
        "  set(_hftp_family_contract_tests\n",
        "  unset(_hftp_family_contract_tests)\nendif()\n",
        _PARSER_TAIL_SHA256,
        errors,
    )
    no_transfer = not any(
        command.name in {"break", "continue", "return"}
        for command in commands)
    return (
        registrations_ok and events_ok and modeled_ok and order_ok and
        tail_ok and no_transfer)


def _expected_label_writers(function_name: str, helper_frame: tuple) -> tuple:
    if function_name == "trading_core_add_contract_test":
        return _EXPECTED_ACCEPTANCE_PROPERTY_WRITERS[
            "apps/trading-core/tests/CMakeLists.txt"]
    if function_name == "add_hft_backtest_test":
        return (
            ((helper_frame,), "set_tests_properties", (
                "${target}", "PROPERTIES", "WORKING_DIRECTORY",
                "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
                "cxet-family;hft-backtest;contract")),
            ((), "set_property", (
                "TEST", "hft-backtest-execution-tests",
                "hft-backtest-client-order-id-tests",
                "hft-backtest-replace-lifecycle-tests",
                "hft-backtest-stat-arb-late-fill-lifecycle-tests",
                "APPEND", "PROPERTY", "LABELS", "order-race;lifecycle")),
            ((), "set_property", (
                "TEST", "hft-backtest-session-loader-tests", "APPEND",
                "PROPERTY", "LABELS", "corpus-contract")),
        )
    if function_name == "trader_contract_test":
        return (
            ((), "set_tests_properties", (
                "trader-market-client-contract-tests", "PROPERTIES",
                "LABELS", "cxet-family;contract;"
                "trader-autonomous-acceptance")),
            ((helper_frame,), "set_tests_properties", (
                "${target}", "PROPERTIES", "WORKING_DIRECTORY",
                "${CMAKE_CURRENT_SOURCE_DIR}", "LABELS",
                "cxet-family;trader;contract;"
                "trader-autonomous-acceptance")),
            ((), "set_property", (
                "TEST", "trader-account-fixture-contract-tests",
                "trader-private-capacity-contract-tests",
                "trader-private-client-contract-tests",
                "trader-private-protocol-contract-tests",
                "APPEND", "PROPERTY", "LABELS", "private-recovery")),
            ((), "set_property", (
                "TEST", "finam_live_recovery_contract_tests",
                "trader-finam-process-contract-tests",
                "trader-profile-journal-writer-contract-tests",
                "trader-replace-lifecycle-contract-tests",
                "APPEND", "PROPERTY", "LABELS", "order-race;lifecycle")),
            ((), "set_property", (
                "TEST", "trader-boundary-contract-tests",
                "trader-market-observe-runtime-contract-tests", "APPEND",
                "PROPERTY", "LABELS", "no-terminal-send")),
        )
    return ()


def helper_test_contract(
    relative: str,
    text: str,
    function_name: str,
    baseline_labels: set[str],
    errors: list[str],
) -> tuple[set[str], bool]:
    """Pin parsed helper structure, calls, and ordered LABELS mutations."""
    commands = _parse_commands(relative, text, errors)
    contexts = exact_command_contexts(commands)
    expected_signature = _EXPECTED_SIGNATURES.get(function_name)

    actual_declarations = tuple(
        (command.name,
         tuple(_unquote(value) for value in words(command.body)), scope)
        for command, scope in contexts
        if command.name in {"function", "macro"}
    )
    declaration_ok = (
        expected_signature is not None and
        actual_declarations ==
        _EXPECTED_FUNCTION_DECLARATIONS.get(function_name, ())
    )
    if not declaration_ok:
        errors.append(
            f"{relative}: exact top-level function inventory for "
            f"{function_name} changed")

    helper_frame = ("function", expected_signature or ())
    helper_commands = [
        command for command, scope in contexts
        if scope == (helper_frame,)
    ]
    nested_helper_commands = [
        command.name for command, scope in contexts
        if scope[:1] == (helper_frame,) and scope != (helper_frame,)
    ]
    helper_inventory = tuple(
        (command.name,
         tuple(_unquote(value) for value in words(command.body)))
        for command in helper_commands
    )
    body_ok = (
        helper_inventory == _EXPECTED_HELPER_COMMANDS.get(function_name) and
        not nested_helper_commands
    )
    if not body_ok:
        errors.append(
            f"{relative}: {function_name} exact straight-line helper body "
            "changed")

    helper_add_tests = [
        tuple(_unquote(value) for value in words(command.body))
        for command in helper_commands if command.name == "add_test"
    ]
    expected_add_test = (
        "NAME", "${target}", "COMMAND", "$<TARGET_FILE:${target}>")
    add_test_ok = helper_add_tests == [expected_add_test]
    if not add_test_ok:
        errors.append(
            f"{relative}: {function_name} must register exactly "
            "NAME ${target} COMMAND $<TARGET_FILE:${target}>")

    helper_properties = [
        tuple(_unquote(value) for value in words(command.body))
        for command in helper_commands
        if command.name == "set_tests_properties"
    ]
    valid_properties = [
        values for values in helper_properties
        if values[:4] == (
            "${target}", "PROPERTIES", "WORKING_DIRECTORY",
            "${CMAKE_CURRENT_SOURCE_DIR}")
        and len(values) == 6
        and values[4] == "LABELS"
        and set(values[5].split(";")) == baseline_labels
    ]
    properties_ok = len(valid_properties) == 1
    if not properties_ok:
        errors.append(
            f"{relative}: {function_name} must assign its exact baseline "
            "labels and working directory")

    no_return = not any(command.name == "return" for command in commands)
    if not no_return:
        errors.append(
            f"{relative}: return() may not terminate test registration")

    invocation_list: list[str] = []
    invocation_commands: list[_Command] = []
    invocation_arguments: dict[str, tuple[str, ...]] = {}
    invocations_top_level = True
    for command, scope in contexts:
        if command.name != function_name.lower():
            continue
        command_words = words(command.body)
        if not command_words:
            continue
        test_name = _unquote(command_words[0])
        if scope:
            invocations_top_level = False
            errors.append(
                f"{relative}:{command.line}: helper test {test_name} must be "
                "registered unconditionally in the root family graph")
        invocation_list.append(test_name)
        invocation_commands.append(command)
        invocation_arguments[test_name] = tuple(
            _unquote(value) for value in command_words[1:])
    expected_invocations = _EXPECTED_INVOCATIONS.get(function_name, ())
    expected_tails = _TRADING_CORE_INVOCATION_TAILS
    if function_name == "trading_core_add_contract_test":
        # The BBO suite is present only in an uncommitted app checkout. If it
        # is registered, pin its source, direct dependency, helper labels and
        # exact position without making clean HEAD require it.
        if _OPTIONAL_TRADING_CORE_BBO_TEST in invocation_list:
            anchor = "trading-core-formula-contract-tests"
            index = expected_invocations.index(anchor) + 1
            expected_invocations = (
                expected_invocations[:index] +
                (_OPTIONAL_TRADING_CORE_BBO_TEST,) +
                expected_invocations[index:])
            expected_tails = dict(_TRADING_CORE_INVOCATION_TAILS)
            expected_tails[_OPTIONAL_TRADING_CORE_BBO_TEST] = (
                _OPTIONAL_TRADING_CORE_BBO_TAIL)
        tails_ok = (
            tuple(_TRADING_CORE_INVOCATION_TAILS) ==
            TRADING_CORE_CONTRACT_TESTS and
            invocation_arguments == expected_tails)
    else:
        tails_ok = True
    invocations_ok = (
        invocations_top_level and
        tuple(invocation_list) == expected_invocations and tails_ok)
    if not invocations_ok:
        errors.append(
            f"{relative}: exact {function_name} test invocation inventory "
            "changed")

    rate_limit_thread_link_ok = True
    if function_name == "trading_core_add_contract_test":
        rate_limit_thread_links = [
            tuple(_unquote(value) for value in words(command.body))
            for command, scope in contexts
            if not scope and command.name == "target_link_libraries" and
            words(command.body)[:1] == [
                "trading-core-rate-limit-state-tests"]
        ]
        rate_limit_thread_link_ok = rate_limit_thread_links == [(
            "trading-core-rate-limit-state-tests", "PRIVATE",
            "Threads::Threads")]
        if not rate_limit_thread_link_ok:
            errors.append(
                f"{relative}: rate-limit-state test must add only the exact "
                "Threads::Threads leaf after its execution dependency")

    actual_label_writers = tuple(
        (scope, command.name,
         tuple(_unquote(value) for value in words(command.body)))
        for command, scope in contexts
        if command.name == "set_tests_properties" or
        (command.name == "set_property" and
         tuple(_unquote(value) for value in words(command.body))[:1] ==
         ("TEST",))
    )
    label_writers_ok = (
        actual_label_writers ==
        _expected_label_writers(function_name, helper_frame)
    )
    if not label_writers_ok:
        errors.append(
            f"{relative}: exact ordered TEST property writer inventory "
            "changed")

    helper_declarations = [
        command for command, scope in contexts
        if command.name == "function" and not scope and
        tuple(_unquote(value) for value in words(command.body)) ==
        expected_signature
    ]
    top_level_test_writers = [
        command for command, scope in contexts
        if not scope and command.name == "set_property" and
        tuple(_unquote(value) for value in words(command.body))[:1] ==
        ("TEST",)
    ]
    if function_name == "trading_core_add_contract_test":
        invocation_offsets = {
            _unquote(words(command.body)[0]): command.offset
            for command in invocation_commands
        }
        safety_targets = {
            "trading-core-rate-limit-state-tests",
            "trading-core-user-event-identity-tests",
            "trading-core-execution-state-tracker-tests",
            "trading-core-order-state-rules-tests",
        }
        ordered_writers = True
        for command in top_level_test_writers:
            command_words = tuple(
                _unquote(value) for value in words(command.body))
            owners = command_words[1:command_words.index("APPEND")]
            if owners == ("${trading_core_safety_tests}",):
                ordered_writers = ordered_writers and all(
                    invocation_offsets.get(target, command.offset) <
                    command.offset for target in safety_targets)
            else:
                ordered_writers = ordered_writers and all(
                    invocation_offsets.get(target, command.offset) <
                    command.offset for target in owners)
        event_order_ok = (
            len(helper_declarations) == 1 and bool(invocation_commands) and
            bool(top_level_test_writers) and ordered_writers and
            helper_declarations[0].offset < invocation_commands[0].offset)
    else:
        event_order_ok = (
            len(helper_declarations) == 1 and invocation_commands and
            top_level_test_writers and
            helper_declarations[0].offset < invocation_commands[0].offset and
            invocation_commands[-1].offset < top_level_test_writers[0].offset
        )
    if not event_order_ok:
        errors.append(
            f"{relative}: {function_name} definition, calls, and TEST label "
            "writers must retain their exact executable order")

    return set(invocation_list), (
        declaration_ok and body_ok and add_test_ok and properties_ok and
        no_return and invocations_ok and rate_limit_thread_link_ok and
        label_writers_ok and event_order_ok
    )
