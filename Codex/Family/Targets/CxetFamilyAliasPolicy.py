"""Declaration-ordered CMake ALIAS policy for the active family graph."""

from __future__ import annotations

from CMake.Syntax.CmakeFamilyContext import exact_context, first_if, recorder_contract_context
from CMake.Flow.CmakeFamilyMutations import has_unresolved_cmake_carrier
from Family.Targets.CxetFamilyBuildPolicy import exact_target_alias
from Family.Targets.CxetFamilyTargetInventory import PRODUCTION_TARGETS, ROLE_PRODUCTION, ROLE_TEST


EXACT_ALIASES = {
    "diagnostic::runtime": "diagnostic_runtime",
    "cxet::cxet_lib": "cxet_lib",
    "cxet::read_only_contracts": "cxet_read_only_contracts",
    "cxet::resident_memory": "cxet_resident_memory",
    "trading_core::contracts": "trading_core_contracts",
    "capital::finance": "capital_finance",
    "capital::planning": "capital_planning",
    "trading_core::algorithm": "trading_core_algorithm",
    "trading_core::cold_ids": "trading_core_cold_ids",
    "trading_core::execution": "trading_core_execution",
    "trading_core::strategy": "trading_core_strategy",
    "hftrec::corpus_contract": "hftrec_corpus_contract",
    "hftrec::capture_launch": "hftrec_capture_launch",
    "hftrec::capture_client": "hftrec_capture_client",
    "hftrec::core": "hftrec_core",
    "hftrec::recorder_api": "hftrec_recorder_api",
    "hft_compressor::core": "hft_compressor_core",
    "hft_backtest::core": "hft_backtest_core",
    "trader::common_contracts": "trader_common_contracts",
    "trader::alert_client": "trader_alert_client",
    "trader::control_contracts": "trader_control_contracts",
    "trader::local_ipc": "trader_private_ipc",
    "trader::order_client": "trader_order_client",
    "trader::control_client": "trader_control_client",
    "trader::projection_source": "trader_projection_source",
    "trader::projection_client": "trader_projection_client",
    "trader::market_observe_projection_client":
        "trader_market_observe_projection_client",
    "trader::market_observe_projection_publisher":
        "trader_market_observe_projection_publisher",
    "trader::market_observe_projection_server":
        "trader_market_observe_projection_server",
    "trader::public_analytics": "trader_public_analytics",
    "trader::market_client": "trader_market_client",
    "trader::live_market_client": "trader_live_market_client",
    "trader::market_observe_runtime": "trader_market_observe_runtime",
    "trader::market_observe_process": "trader_market_observe_process",
    "trader::live_runtime": "trader_live_runtime",
    "trader::traderd_process": "trader_traderd_process",
    "trader::source_boundary": "trader_source_boundary",
    "vetron::browser_contracts": "vetron_browser_contracts",
    "vetron::read_gateway": "vetron_read_gateway",
    "vetron::read_runtime": "vetron_read_runtime",
    "vetron::read_process": "vetron_read_process",
    "vetron::read_source_boundary": "vetron_read_source_boundary",
    "vetron::full_control": "vetron_full_control",
    "vetron::full_process": "vetron_full_process",
    "vetron::full_source_boundary": "vetron_full_source_boundary",
    "hft_parser::public_market": "hftp_public_market",
    "hft_parser::contracts": "hftp_contracts",
    "hft_parser::resource": "hftp_resource",
    "hft_parser::local_data_plane": "hftp_local_data_plane",
    "hft_parser::market_client": "hftp_market_client",
    "hft_parser::market_demand_client": "hftp_market_demand_client",
    "hft_parser::current_reference_client": "hftp_current_reference_client",
    "hft_parser::session_client": "hft_parser_session_client",
    "hft_parser::projection_client": "hft_parser_projection_client",
    "hft_parser::reference_client": "hft_parser_reference_client",
    "hft_parser::history_client": "hft_parser_history_client",
    "hft_parser::ipc": "hftp_ipc",
    "hft_parser::algos_runtime": "hftp_algos_runtime",
    "hft_parser::routing": "hftp_routing",
    "hft_parser::catalog": "hftp_catalog",
    "hft_parser::transport": "hftp_transport",
    "hft_parser::history": "hftp_history",
    "hft_parser::reference": "hftp_reference",
    "hft_parser::ingestion": "hftp_ingestion",
}


def _flat(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def source_owned_recorder_alias(alias, active_commands) -> bool:
    """Only the actual canonical corpus source can bound this alias namespace."""
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    if alias != "hftrec::corpus_contract":
        return False
    concrete = EXACT_ALIASES[alias]
    owner = PRODUCTION_TARGETS[concrete].owner
    aliases, declarations = [], []
    for active in active_commands:
        if (active.relative != owner or active.command.name != "add_library" or
                not recorder_contract_context(active)):
            continue
        tokens = cmake_list_words(active.command.body)
        if tokens == [alias, "ALIAS", concrete]:
            aliases.append(active)
        if tokens[:2] == [concrete, "STATIC"] and "IMPORTED" not in tokens[2:]:
            declarations.append(active)
    return (len(aliases) == len(declarations) == 1 and
            declarations[0].ordinal < aliases[0].ordinal and
            declarations[0].structural_context == aliases[0].structural_context and
            declarations[0].execution_chain == aliases[0].execution_chain)


def target_aliases(
    instances, errors: list[str], registry=None
) -> dict[str, str]:
    """Validate aliases against the concrete instantiated declaration stream.

    CMake does not permit an ALIAS to name another ALIAS.  A direct concrete
    or imported target must already exist at the alias command's actual nested
    execution position; lexical definition-body lines are not execution order.
    """
    aliases: dict[str, str] = {}
    locations: dict[str, list[object]] = {}

    for instance in instances:
        if instance.body.command.name not in {
                "add_library", "add_executable"}:
            continue
        tokens = _flat(instance)
        if exact_target_alias(instance):
            alias, _, concrete = tokens
            if any(has_unresolved_cmake_carrier(value) or "$<" in value
                   for value in (alias, concrete)):
                errors.append(
                    f"{_origin(instance)}: unresolved dynamic active-family "
                    f"alias: {alias} -> {concrete}")
                continue
            if alias in aliases:
                errors.append(
                    f"{_origin(instance)}: active-family alias {alias} is "
                    f"declared more than once ({aliases[alias]}, {concrete})")
            aliases[alias] = concrete
            locations.setdefault(alias, []).append(instance)
            continue

    for alias, concrete in aliases.items():
        location = locations[alias][0]
        expected_context = ((first_if(
            'apps/hft-recorder/src/Contracts/CMakeLists.txt', 36,
            ('TARGET', 'hftp_contract_headers')),)
            if alias == 'hftrec::capture_client' else ())
        if concrete in aliases:
            errors.append(
                f"{_origin(location)}: alias {alias} targets alias "
                f"{concrete}; CMake requires a direct concrete target")
            continue
        corpus_alias = alias in {"hftrec::corpus_contract", "hftrec::capture_launch", "hftrec::capture_client"}
        context_valid = (recorder_contract_context(location.body, expected_context) and
            recorder_contract_context(location.evaluation, expected_context)) if corpus_alias else (
            exact_context(location.body.structural_context, expected_context) and
            exact_context(location.evaluation.structural_context, expected_context))
        if not context_valid:
            errors.append(
                f"{_origin(location)}: alias {alias} is not a direct "
                "top-level declaration")
        if registry is None:
            errors.append(
                f"{_origin(location)}: alias validation has no global target "
                "registry")
            continue
        declarations = registry.resolve(
            concrete,
            location,
            require_prior=True,
            roles=frozenset({ROLE_TEST}) if alias in {
                "capital::planning"} else frozenset({ROLE_PRODUCTION}),
        )
        if not declarations:
            errors.append(
                f"{_origin(location)}: alias {alias} does not name an earlier "
                f"concrete first-party library {concrete}")
            continue
        if any(declaration.kind not in {
                "STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE"}
                for declaration in declarations):
            errors.append(
                f"{_origin(location)}: alias {alias} target {concrete} is not "
                "a concrete library")
        for declaration in declarations:
            target_instance = declaration.instance
            if (target_instance.evaluation.source_base !=
                    location.evaluation.source_base or
                    target_instance.evaluation.binary_base !=
                    location.evaluation.binary_base):
                errors.append(
                    f"{_origin(location)}: alias {alias} is evaluated outside "
                    f"the concrete target {concrete} directory")
    active_origins = getattr(registry, "active_origins", None)
    expected = {
        alias: concrete for alias, concrete in EXACT_ALIASES.items()
        if (concrete in {"capital_planning"} and
            registry is not None and concrete in registry.concrete_names()) or
           (concrete in PRODUCTION_TARGETS and
            (active_origins is None or PRODUCTION_TARGETS[concrete].owner in active_origins) and
            not (registry is not None and hasattr(registry, 'optional_target_disabled') and
                 registry.optional_target_disabled(concrete)))
    }
    if aliases != expected or any(
            len(found) != 1 for found in locations.values()):
        redirected = sorted(
            alias for alias, concrete in aliases.items()
            if (alias in expected and concrete != expected[alias]))
        errors.append(
            "active-family alias inventory changed: "
            f"missing={sorted(set(expected) - set(aliases))}, "
            f"extra={sorted(set(aliases) - set(expected))}, "
            f"redirected={redirected}")
    return aliases


def canonical_target(target: str, aliases: dict[str, str]) -> str:
    """Resolve a valid alias; retain a sentinel if invalid input cycled."""
    seen: set[str] = set()
    current = target
    while current in aliases:
        if current in seen:
            return f"UNRESOLVED_ALIAS_CYCLE:{target}"
        seen.add(current)
        current = aliases[current]
    return current
