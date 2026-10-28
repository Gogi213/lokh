"""Offline diagnostic seams backed by validated owner helper registrations."""

from pathlib import Path

from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
from CMake.Syntax.CmakeFamilyContext import exact_context
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from Family.Targets.CxetFamilyTargetInventory import ROLE_SOURCE_EXCEPTIONS


_ROOT = "src/tests/offline/"
_CORE = "src/src/Core/"
_PARSER = "apps/hft-parser/"
_PARSER_ROOT = _PARSER + "tests/offline/"
_TRADER_ROOT = "apps/trader/tests/offline/"
_TRADER_RESIDENT_FIXTURE_TARGETS = frozenset({
    "trader_offline_cases", "trader_offline_private_cut",
    "trader_offline_finam_full_path", "trader_offline_tbank_full_path",
    "trader_offline_strategy_runtime",
})
# Diagnostic access to the private Order layout stays with exact registered
# target/TU/source edges; no Core/src include root is exported to consumers.
_ORDER_INTERNAL_HEADER = _CORE + "src/Api/Order/OrderSessionPoolInternal.hpp"
_ORDER_PRIVATE_EDGES = frozenset({
    *(("CXETCPP", target, _ROOT + source, _ROOT + source) for target, source in (
        ("cxet_offline_core_api", "Api/Boundary/CoreApiBoundaries.cpp"),
        ("cxet_offline_private_contract_lowering", "Api/User/PrivateContractLowering.cpp"),
        ("cxet_offline_order_lifecycle", "Api/Order/OrderLifecycleFence.cpp"),
        ("cxet_offline_order_correlation", "Api/Order/OrderCorrelation.cpp"),
        ("cxet_offline_grpc_buffered_poll", "Network/Grpc/GrpcClientBufferedPoll.cpp"),
        ("cxet_offline_finam_private_contracts", "Exchanges/Finam/FinamPrivateContracts.cpp"),
        ("cxet_offline_tbank_private_contracts", "Exchanges/Tbank/TbankPreparedPendingCases.cpp"),
    )),
    ("hft-parser", "hftp_offline_native_account_publication",
     _PARSER_ROOT + "Session/Account/NativeAccountPublication.cpp",
     _PARSER_ROOT + "Session/Account/NativeAccountPublication.cpp"),
    ("hft-parser", "hftp_offline_native_order_variants",
     _PARSER_ROOT + "Session/Order/NativeOrderVariants.cpp",
     _PARSER_ROOT + "Session/Order/NativeOrderVariants.cpp"),
    ("trader", "trader_offline_finam_full_path",
     _TRADER_ROOT + "Execution/FinamDelPairTransportCases.cpp",
     _TRADER_ROOT + "Execution/FinamDelPairTransportCases.cpp"),
    ("trader", "trader_offline_cases",
     _TRADER_ROOT + "Fleet/FleetNativeOwnerCases.cpp",
     _TRADER_ROOT + "Fleet/FleetNativeOwnerCases/StartupFailure.ipp"),
})
_PARSER_COMPILED_SOURCES = {
    "hftp_offline_catalogue_identities": _PARSER + "src/Runtime/src/Market/Ingestion/Detail/Topology/Source/PublicMarketStableIdentities.cpp",
    "hftp_offline_portable_catalog": _PARSER + "src/Process/src/Bootstrap/Reference/PortablePublicCatalog.cpp",
    "hftp_offline_cases": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_capture_subscription": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_public_market_catalog": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_selected_wire_config": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_private_subscription_plan": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_kernel_handoff": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_cold_reservoir": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_source_recovery": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_source_recovery_warm": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_native_account_publication": _ROOT + "Support/ResidentMemoryFixture.cpp",
    "hftp_offline_native_order_variants": _ROOT + "Support/ResidentMemoryFixture.cpp",
}
_PARSER_PRIVATE_EDGES = frozenset({
    ("hftp_offline_archive_file_authority", _PARSER_ROOT + "History/ArchiveFileAuthority.cpp", _CORE + "src/Api/User/Common/NativeAccountWriterLeaseInternal.hpp"),
    ("hftp_offline_native_account_publication", _PARSER_ROOT + "Session/Account/NativeAccountPublication.cpp", _CORE + "src/Api/User/Common/NativeAccountWriterLeaseInternal.hpp"),
    ("hftp_offline_cold_reservoir", _PARSER_ROOT + "Market/PublicMarketColdReservoir.cpp", _CORE + "src/Runtime/Market/Transport/Grpc/Private/PublicMarketGrpcDriver/PollBudget.hpp"),
})
# Complete current public-type closure of ReferenceTypes' two Core roots.
# These are diagnostic include edges, never exported/linked provider facts.
_PARSER_PORTABLE_REFERENCE_EDGES = frozenset({
    (_PARSER + "src/Runtime/include/hft_parser/Reference/ReferenceTypes.hpp",
     _CORE + "include/cxet/Api/Instrument/InstrumentCatalog.hpp"),
    (_PARSER + "src/Runtime/include/hft_parser/Reference/ReferenceTypes.hpp",
     _CORE + "include/cxet/Api/Market/Ticker/Ticker24hQuality.hpp"),
    *{(_CORE + "include/cxet/Api/Instrument/InstrumentCatalog.hpp", _CORE + "include/cxet/" + header)
      for header in ("Api/Instrument/InstrumentInfoCatalog.hpp", "Api/Reference/ReferenceWs.hpp",
                     "Network/Grpc/GrpcEndpoint.hpp")},
    (_CORE + "include/cxet/Api/Instrument/InstrumentInfoCatalog.hpp",
     _CORE + "include/cxet/Api/Reference/ReferenceRest.hpp"),
    (_CORE + "include/cxet/Api/Market/Ticker/Ticker24hQuality.hpp",
     _CORE + "include/cxet/Api/Market/Ticker/Ticker24hDiagnostic.hpp"),
    (_CORE + "include/cxet/Api/Market/Ticker/Ticker24hDiagnostic.hpp",
     _CORE + "include/cxet/Api/Market/Ticker/Ticker24hCatalog.hpp"),
    (_CORE + "include/cxet/Api/Market/Ticker/Ticker24hCatalog.hpp",
     _CORE + "include/cxet/Api/Reference/ReferenceRest.hpp"),
})
_PRIVATE_EDGES = frozenset(
    (_ROOT + source, _CORE + selected)
    for source, selected in (
        ("Exchanges/Binance/BinanceFixContracts.cpp", "src/Api/Order/Common/OrderExecutionDecode.hpp"),
        ("Api/Boundary/CoreApiBoundaries.cpp", "src/Api/Order/Rest/Detail/RestSessionPoolInternal.hpp"),
        ("Api/Boundary/CoreApiBoundaries.cpp", "src/Network/Common/BoundedDnsDoh.hpp"),
        ("Api/Account/AccountQueryRuntimeContract.cpp", "src/Api/User/AccountQueryRuntimeTestAccess.hpp"),
        ("Api/Account/AccountQueryRuntimeContract.cpp", "src/Api/User/AccountQueryFailurePolicy.hpp"),
        ("Api/Instrument/NativeReferenceRestRequest.cpp", "src/Api/Reference/Internal/NativeReferenceRestRequest.hpp"),
        ("Api/Instrument/NativeReferenceRestRequest.cpp", "src/Api/Reference/Internal/ReferenceRestPreparation.hpp"),
        ("Exchanges/Finam/FinamAuthBuffers.cpp", "src/Runtime/Market/Transport/Grpc/Private/GrpcCredentialSessionPolicy.hpp"),
        ("Network/Grpc/GrpcClientBufferedPoll.cpp", "src/Network/Grpc/Private/GrpcClientInternal.hpp"),
        ("Network/Grpc/GrpcClientBufferedPoll.cpp", "src/Api/Order/Grpc/GrpcClientOrderAccess.hpp"),
        ("Network/Grpc/GrpcClientBufferedPoll.cpp", "src/Runtime/Market/Transport/Grpc/Private/PublicMarketGrpcDriver/State.hpp"),
        ("Runtime/Market/MarketRuntimeContinuity.cpp", "src/Runtime/Market/Transport/Grpc/Private/PublicMarketGrpcDriver/PollBudget.hpp"),
        ("Runtime/Market/MarketRuntimeContinuity.cpp", "src/Runtime/Market/Transport/Grpc/Private/PublicMarketGrpcDriver/State.hpp"),
        ("Api/Instrument/NativeGrpcMetadataCatalog.cpp", "src/Api/Instrument/Internal/NativeGrpcMetadataCatalog.hpp"),
        ("Api/Instrument/NativeMetadataQuantity.cpp", "src/Api/Instrument/Internal/SymbolMetadataRules.ipp"),
        ("Network/Ws/OptionalBusyPoll.cpp", "src/Network/Ws/Runtime/WsNapiBusyPoll.hpp"),
        ("Network/Ws/OptionalBusyPoll.cpp", "src/Private/Network/Ws/Runtime/WsRuntimeDetail.hpp"),
        ("Api/Order/OrderCorrelation.cpp", "src/Api/Order/Rest/Detail/RestSessionPoolInternal.hpp"),
        ("Api/Order/OrderLifecycleFence.cpp", "src/Api/Order/Rest/Detail/RestSessionPoolInternal.hpp"),
        ("Api/User/PrivateContractLowering.cpp", "src/Network/Grpc/Private/GrpcClientInternal.hpp"),
        ("Primitives/Crypto/RsaTestAes.c", "src/Crypto/RsaMbedAesNames.h"),
        ("Network/Simba/SimbaProtocolCases.cpp", "src/Exchanges/Moex/Common/Sbe/SimbaPacket.hpp"),
        ("Network/Simba/SimbaProtocolCases.cpp", "src/Network/Simba/SimbaReplayProtocolAccess.hpp"),
        ("Api/Order/TerminalAttemptTime.cpp", "src/Private/Network/Ws/Runtime/WsRuntimeDetail.hpp"),
        ("Network/Tls/Support/TlsCertificates.cpp", "src/Network/Tls/Certificates.hpp"),
        ("Network/Tls/TlsColdStorage.cpp", "src/Network/Tls/Certificates.hpp"),
        ("Network/Tls/TlsNativeTerminal.cpp", "src/Network/Tls/TerminalWriter.hpp"),
        ("Network/Tls/TlsNativeTerminal.cpp", "src/Network/Tls/SocketState.hpp"),
        ("Network/Tls/TlsNativeTerminal.cpp", "src/Network/Grpc/Private/NativeGrpcTlsState.hpp"),
        ("Network/Tls/TlsNativeTerminal.cpp", "src/Network/Rest/Detail/NativeRestTlsState.hpp"),
        ("Network/Tls/TlsNativeTerminal.cpp", "src/Private/Network/Ws/Runtime/Detail/NativeWsTls.hpp"),
        ("Network/Common/TransportBoundaries.cpp", "src/Private/Network/Ws/Runtime/Detail/Common.hpp"),
        ("Network/Common/TransportBoundaries.cpp", "src/Private/Network/Ws/Runtime/WsRuntimeDetail.hpp"),
        ("Network/Common/TransportBoundaries.cpp", "src/Network/Ws/Compression/WsInflateWorkBudget.hpp"),
        ("Network/Ws/WsColdAdmissionCases.cpp", "src/Runtime/Market/Transport/Ws/Private/PublicMarketWsDriver/State.hpp"),
    ))


_RESIDENT_FIXTURE_CORE_EDGES = frozenset({
    (_ROOT + "Primitives/ResidentMemory.cpp", _CORE + "include/cxet/Api/Stream/RuntimeEventAdmission.hpp"),
    (_ROOT + "Primitives/ResidentMemory.cpp", _CORE + "include/cxet/Runtime/Market/MarketIngressDrain.hpp"),
    (_CORE + "include/cxet/Api/Stream/RuntimeEventAdmission.hpp", _CORE + "include/cxet/Api/Stream/RuntimeEventView.hpp"),
})


def offline_source_registrations(occurrences, registry):
    """Bind each diagnostic TU to its actual, uniquely covering declaration."""
    result = {}
    for target, instance, source in occurrences:
        registration = offline_registration(instance, target)
        if registration is None or source not in registration.sources:
            continue
        declaration = registry.context_for_use(target, instance, allow_same=True)
        if declaration is not None and offline_registration(declaration, target) is registration:
            result[target, source] = registration
    return result


def offline_shared_fixture_source(relative, owner, target, source):
    """One shared host-simulation TU, restricted to exact offline suites."""
    return (source == _ROOT + "Support/ResidentMemoryFixture.cpp" and
            ((owner == "hft-parser" and relative == _PARSER_ROOT + "CMakeLists.txt" and
              _PARSER_COMPILED_SOURCES.get(target) == source) or
             (owner == "trader" and relative == _TRADER_ROOT + "CMakeLists.txt" and
              target in _TRADER_RESIDENT_FIXTURE_TARGETS) or
             (owner == "diagnostic" and relative == "apps/diagnostic/tests/offline/CMakeLists.txt" and
              target == "diagnostic_offline_market")))


def startup_canonical_source(instance, target, source):
    """Only exact excluded startup declarations may borrow canonical TUs."""
    startup_owner = "apps/trader/tests/startup/CMakeLists.txt"
    startup_root = Path("apps/trader/tests/startup")
    return (target in {"trader_startup_fixture", "trader_tbank_startup_fixture",
                       "trader_startup_catalog_fixture", "trader_tbank_startup_catalog_fixture"} and
            instance.body.relative == startup_owner and
            instance.evaluation.relative == startup_owner and
            instance.body.command == instance.evaluation.command and
            instance.body.command.name == "add_executable" and
            cmake_list_words(instance.body.command.body)[:2] == [target, "EXCLUDE_FROM_ALL"] and
            instance.body.source_base == instance.evaluation.source_base == startup_root and
            instance.body.binary_base == instance.evaluation.binary_base == startup_root and
            exact_context(instance.body.structural_context, ()) and
            exact_context(instance.evaluation.structural_context, ()) and
            source in ROLE_SOURCE_EXCEPTIONS.get((target, startup_owner), ()))


def offline_canonical_source(instance, target, source):
    if startup_canonical_source(instance, target, source):
        return True
    registration = offline_registration(instance, target)
    return bool(registration is not None and source in registration.sources and
        ((registration.owner == "trader" and registration.relative == _TRADER_ROOT + "CMakeLists.txt" and
          target == "trader_offline_dispatch" and
          source == "apps/trader/src/Process/src/Traderd/Application/NativeBindingDescription.cpp") or
         (registration.owner == "hft-parser" and
          registration.relative == _PARSER_ROOT + "CMakeLists.txt" and
          _PARSER_COMPILED_SOURCES.get(target) == source) or
         offline_shared_fixture_source(registration.relative, registration.owner, target, source)))


def _parser_backend_header_edge(registration, source, selected, translation_unit):
    if (registration is None or registration.owner != "hft-parser" or
            registration.relative != _PARSER_ROOT + "CMakeLists.txt" or
            translation_unit not in registration.sources or
            not (source.startswith(_PARSER_ROOT) or source == translation_unit or
                 source.startswith(_PARSER + "src/Runtime/"))):
        return False
    return ("${CMAKE_CURRENT_SOURCE_DIR}/../../src/Runtime/include" in registration.includes and
            selected.startswith(_PARSER + "src/Runtime/include/"))


def offline_public_header_edge(registration, source, selected, translation_unit):
    """A core-owned header fixture is not a production transport-free target.

    Only the helper's explicit private Core/include root plus exact read-only
    fixture libraries grants this diagnostic reachability. Export interfaces
    and foreign/product consumers continue to require their canonical provider.
    """
    if _parser_backend_header_edge(registration, source, selected, translation_unit):
        return True
    if (registration is not None and registration.owner == "CXETCPP" and
            registration.relative == _ROOT + "CMakeLists.txt" and
            registration.target == "cxet_offline_resident_memory" and
            registration.libraries == ("cxet::resident_memory",) and
            translation_unit == _ROOT + "Primitives/ResidentMemory.cpp" and translation_unit in registration.sources and
            "${CMAKE_SOURCE_DIR}/src/src/Core/include" in registration.includes and
            (source, selected) in _RESIDENT_FIXTURE_CORE_EDGES):
        return True
    parser_reference = (translation_unit == _PARSER_ROOT + "Reference/PortablePublicCatalog.cpp" and
        (source, selected) in _PARSER_PORTABLE_REFERENCE_EDGES)
    parser_core = bool(registration is not None and registration.owner == "hft-parser" and
        registration.relative == _PARSER_ROOT + "CMakeLists.txt" and
        registration.target == "hftp_offline_portable_catalog" and
        registration.libraries == ("cxet::read_only_contracts", "hftp_contract_headers") and
        (source in registration.sources or parser_reference))
    return bool(registration is not None and translation_unit in registration.sources and
        (parser_core or registration.libraries in {("cxet::read_only_contracts",),
                                  ("cxet::read_only_contracts", "Threads::Threads")}) and
        "${CMAKE_SOURCE_DIR}/src/src/Core/include" in registration.includes and
        (parser_core or source.startswith((_ROOT, _CORE + "include/")) or
         (translation_unit, source) in _PRIVATE_EDGES) and
        selected.startswith(_CORE + "include/"))


def offline_private_header_edge(registration, source, selected, translation_unit):
    if (registration is not None and translation_unit in registration.sources and
            registration.relative == {
                "CXETCPP": _ROOT, "hft-parser": _PARSER_ROOT, "trader": _TRADER_ROOT,
            }.get(registration.owner, "") + "CMakeLists.txt" and
            selected == _ORDER_INTERNAL_HEADER and
            (registration.owner, registration.target, translation_unit, source) in _ORDER_PRIVATE_EDGES):
        return True
    return bool(registration is not None and translation_unit in registration.sources and
                source == translation_unit and ((source, selected) in _PRIVATE_EDGES or
                    registration.owner == "hft-parser" and
                    registration.relative == _PARSER_ROOT + "CMakeLists.txt" and
                    (registration.target, source, selected) in _PARSER_PRIVATE_EDGES))


def startup_resident_external_include(source, include):
    """The standalone source scanner has no target or exported-header context."""
    return (source == "apps/trader/tests/startup/StartupResidentMemory.cpp" and
            include == "cstdarg")


def offline_external_include(registration, source, include, translation_unit, *,
                             target=None, public_seed=False):
    if (registration is None and not public_seed and source == translation_unit and
            target in {"trader_startup_fixture", "trader_startup_alert_fixture",
                       "trader_tbank_startup_fixture", "trader_startup_catalog_fixture",
                       "trader_tbank_startup_catalog_fixture"} and
            startup_resident_external_include(source, include)):
        return True
    if (registration is not None and source == translation_unit and
            source == _ROOT + "Support/ResidentMemoryFixture.cpp" and
            source in registration.sources and include == "cstdarg"):
        return ((registration.owner == "CXETCPP" and
                 registration.relative == _ROOT + "CMakeLists.txt" and
                 registration.target in {
                     "cxet_offline_private_contract_lowering", "cxet_offline_finam_private_contracts",
                     "cxet_offline_terminal_attempt_time", "cxet_offline_transport",
                     "cxet_offline_core_api", "cxet_offline_ws_cold_admission",
                     "cxet_offline_order_lifecycle", "cxet_offline_order_correlation",
                     "cxet_offline_tls_terminal", "cxet_offline_tls_records",
                     "cxet_offline_tls_handshake", "cxet_offline_grpc_buffered_poll",
                     "cxet_offline_market_continuity"}) or
                (registration.owner == "hft-parser" and
                 registration.relative == _PARSER_ROOT + "CMakeLists.txt" and
                 _PARSER_COMPILED_SOURCES.get(registration.target) == source) or
                (registration.owner == "trader" and
                 registration.relative == _TRADER_ROOT + "CMakeLists.txt" and
                 registration.target in _TRADER_RESIDENT_FIXTURE_TARGETS) or
                (registration.owner == "diagnostic" and
                 registration.relative == "apps/diagnostic/tests/offline/CMakeLists.txt" and
                 registration.target == "diagnostic_offline_market"))
    if (registration is not None and registration.owner == "hft-parser" and
            registration.relative == _PARSER_ROOT + "CMakeLists.txt" and
            source == translation_unit and source in registration.sources and
            (registration.target, source) in {
                ("hftp_offline_native_account_publication", _PARSER_ROOT + "Session/Account/NativeAccountPublication.cpp"),
                ("hftp_offline_native_order_variants", _PARSER_ROOT + "Session/Order/NativeOrderVariants.cpp")}):
        return include == "barrier"
    return bool(registration is not None and registration.owner == "CXETCPP" and
                registration.relative == _ROOT + "CMakeLists.txt" and
                translation_unit in registration.sources and source == translation_unit and
                (registration.target, source) in {
                    ("cxet_offline_optional_busy_poll", _ROOT + "Network/Ws/OptionalBusyPoll.cpp"),
                    ("cxet_offline_resident_memory", _ROOT + "Primitives/ResidentMemory.cpp")} and include == "cstdarg")
