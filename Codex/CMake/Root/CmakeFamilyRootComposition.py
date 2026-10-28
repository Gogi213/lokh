"""Private composition responsibilities of the family root checker."""

from __future__ import annotations

import re

from CMake.Syntax.CmakeFamilyLexer import words
from CMake.Policy.CmakeFamilyConditionPolicy import exact_provider_guard_inventory, exact_command_contexts as command_contexts, validate_app_guard_contract, validate_root_compiler_guard, validate_root_full_family_guard, validate_root_guard_order, validate_root_platform_guards, validate_root_provider_contract
from CMake.Root.CmakeFamilyRootPolicy import validate_root_ownership_effects
from CMake.Root.CmakeFamilyRootDialect import validate_root_dialect
from CMake.Root.CmakeFamilyRootProfilePolicy import (
    require_profile_command, validate_required_profiles_live,
)

from CMake.Policy.CmakeFamilyExternalEdges import validate_root_external_edges
from CMake.Root.CmakeFamilyRootGraphCommon import FULL_ONLY_FAMILY_PROVIDERS, ROOT_CMAKE, parse_commands, unquote

def _provider_first_offsets(
    core_offset: int,
    family_offsets: tuple[int, ...],
) -> bool:
    return bool(family_offsets) and all(
        core_offset < offset for offset in family_offsets)

def validate_provider_first_microcases(errors: list[str]) -> None:
    if not _provider_first_offsets(10, (20, 30)):
        errors.append(
            "root-graph self-check rejected provider-first source order")
    if _provider_first_offsets(20, (10, 30)):
        errors.append(
            "root-graph self-check accepted a consumer before src/src")

def check_owner_composition(text: str, errors: list[str]) -> None:
    """Validate the topology authority, including every list writer and edge.

    Exact conditions retain quote provenance in the lexer; normalized quotes
    below only compare reviewed literal owner/list names, never dynamic paths.
    """
    relative = "cmake/CxetCompileGraph.cmake"
    commands = parse_commands(relative, text, errors)
    contexts = command_contexts(commands)
    def tokens(body):
        return tuple(unquote(value) for value in words(body))
    def scope(context):
        return tuple((kind, tuple(unquote(value) for value in
                                 re.findall(r'"[^"\\]*(?:\\.[^"\\]*)*"|[()]|[^\s()]+', ' '.join(condition))))
                     for kind, condition in context)
    owners = ("CXETCPP", "hft-parser", "trading-core", "hft-backtest",
              "trader", "vetron", "hft-recorder", "hft-compressor", "diagnostic", "TestExchangesHelper")
    groups = {
        "_cxet_compile_owners": owners,
        "_cxet_parser_owners": ("hft-parser", "trader", "vetron", "hft-recorder"),
        "_cxet_strategy_owners": ("trading-core", "hft-backtest", "trader", "vetron", "hft-recorder", "diagnostic"),
        "_cxet_compressor_owners": ("hft-compressor", "hft-recorder", "hft-backtest", "vetron"),
        "_cxet_backtest_owners": ("hft-backtest", "hft-recorder", "vetron"),
        "_cxet_trader_owners": ("trader", "vetron"),
    }
    parser_scope = (("if", ("CXET_BUILD_OWNER", "STREQUAL", "hft-parser", "AND", "NOT", "CXET_LOCAL_TESTS")),)
    full_scope = parser_scope + (("if", ("CXET_FAMILY_PROFILE", "STREQUAL", "full")),)
    recorder_scope = (("if", ("CXET_LOCAL_TESTS", "AND", "CXET_BUILD_OWNER", "STREQUAL", "hft-recorder")),)
    remove_scope = recorder_scope + (("foreach", ("owner_list", "IN", "ITEMS",
        "_cxet_parser_owners", "_cxet_strategy_owners",
        "_cxet_backtest_owners")),)
    expected_writers = {
        ("list", ("APPEND", name, "hft-parser"), parser_scope)
        for name in ("_cxet_strategy_owners", "_cxet_trader_owners")
    } | {
        ("list", ("APPEND", name, "hft-parser"), full_scope)
        for name in ("_cxet_compressor_owners", "_cxet_backtest_owners")
    } | {("list", ("REMOVE_ITEM", "${owner_list}", "hft-recorder"), remove_scope)}
    writers = []
    assignments = {}
    for command, context in contexts:
        body, active = tokens(command.body), scope(context)
        if command.name == "set" and body and body[0] in groups:
            assignments.setdefault(body[0], []).append((body[1:], active))
        if command.name in {"list", "unset", "set"} and body:
            destination = body[1] if command.name == "list" and len(body) > 1 else body[0]
            if destination in groups or destination == "${owner_list}":
                if command.name != "set":
                    writers.append((command.name, body, active))
    for name, expected in groups.items():
        if assignments.get(name) != [(expected, ())]:
            errors.append(f"{relative}: {name} must have one unconditional canonical owner inventory")
    if len(writers) != len(expected_writers) or set(writers) != expected_writers:
        errors.append(f"{relative}: unreviewed owner-list mutation or missing profile mutation")
    group_edges = {
        "apps/hft-parser": "_cxet_parser_owners",
        "apps/trading-core": "_cxet_strategy_owners",
        "apps/hft-compressor": "_cxet_compressor_owners",
        "apps/hft-backtest": "_cxet_backtest_owners",
        "apps/trader": "_cxet_trader_owners",
    }
    expected_edges = [
        (directory, (("if", ("CXET_BUILD_OWNER", "IN_LIST", group)),))
        for directory, group in group_edges.items()
    ]
    expected_edges += [
        ("apps/hft-parser/src/Contracts", (("if", ("CXET_BUILD_OWNER", "IN_LIST", "_cxet_backtest_owners", "AND", "NOT", "TARGET", "hftp_contract_headers")),)),
        ("apps/hft-parser/src/Contracts", recorder_scope),
        ("apps/hft-recorder/src/Contracts", recorder_scope),
        ("apps/hft-recorder/src/Runtime", recorder_scope),
        ("apps/hft-recorder/src/Contracts", (("if", ("CXET_BUILD_OWNER", "IN_LIST", "_cxet_backtest_owners")),)),
        ("apps/vetron", (("if", ("CXET_BUILD_OWNER", "STREQUAL", "vetron", "OR", "(", "CXET_BUILD_OWNER", "STREQUAL", "hft-parser", "AND", "CXET_FAMILY_PROFILE", "STREQUAL", "full", "AND", "NOT", "CXET_LOCAL_TESTS", ")")),)),
        ("apps/hft-recorder", (("if", ("(", "CXET_BUILD_OWNER", "STREQUAL", "hft-recorder", "AND", "NOT", "CXET_LOCAL_TESTS", ")", "OR", "(", "CXET_BUILD_OWNER", "STREQUAL", "hft-parser", "AND", "CXET_FAMILY_PROFILE", "STREQUAL", "full", "AND", "NOT", "CXET_LOCAL_TESTS", ")")),)),
        ("tools/exchange_api_probe", (("if", ("CXET_BUILD_OWNER", "STREQUAL", "TestExchangesHelper")),)),
        ("apps/diagnostic", (("if", ("CXET_BUILD_OWNER", "STREQUAL", "diagnostic")),)),
    ]
    benchmark_scope = (("if", ("CXET_LOCAL_BENCHMARKS",)),)
    expected_edges += [
        ("src/benchmarks", benchmark_scope +
         (("if", ("CXET_BUILD_OWNER", "STREQUAL", "CXETCPP")),)),
        ("apps/${CXET_BUILD_OWNER}/benchmarks", benchmark_scope + (("else", ()),)),
    ]
    found = []
    offsets = {}
    for command, context in contexts:
        if command.name != "add_subdirectory":
            continue
        body, active = tokens(command.body), scope(context)
        if body and body[0] in {item[0] for item in expected_edges}:
            if len(body) != 2 or body[1] != "EXCLUDE_FROM_ALL":
                errors.append(f"{relative}:{command.line}: owner provider must be a direct EXCLUDE_FROM_ALL edge")
            found.append((body[0], active))
            offsets.setdefault(body[0], command.offset)
        elif body != ("${test_root}", "EXCLUDE_FROM_ALL"):
            errors.append(f"{relative}:{command.line}: unreviewed source edge {body}")
        elif body == ("${test_root}", "EXCLUDE_FROM_ALL") and active != (
                ("if", ("CXET_LOCAL_TESTS",)),
                ("foreach", ("test_root", "IN", "LISTS", "_cxet_local_test_roots"))):
            errors.append(f"{relative}:{command.line}: local tests escaped their selected owner stage")
    if len(found) != len(expected_edges) or set(found) != set(expected_edges):
        errors.append(f"{relative}: owner provider edge guard/inventory changed")
    benchmark_guard = (
        "CXET_LOCAL_BENCHMARKS", "AND", "(", "NOT", "CXET_LOCAL_TESTS", "OR",
        "NOT", "CXET_BUILD_OWNER", "MATCHES",
        "^(CXETCPP|hft-parser|trading-core|trader)$", ")")
    benchmark_fatals = [
        command for command, context in contexts
        if command.name == "message"
        and tokens(command.body)[:1] == ("FATAL_ERROR",)
        and scope(context) == (("if", benchmark_guard),)
    ]
    if (len(benchmark_fatals) != 1 or
            (offsets and benchmark_fatals[0].offset >= min(offsets.values()))):
        errors.append(f"{relative}: benchmarks must reject missing local tests or unsupported owners before provider edges")
    for provider, consumer in (("apps/hft-parser", "apps/trader"),
                               ("apps/hft-parser", "apps/vetron"),
                               ("apps/trading-core", "apps/trader"),
                               ("apps/trader", "apps/vetron"),
                               ("apps/hft-recorder/src/Contracts", "apps/hft-recorder/src/Runtime"),
                               ("apps/hft-recorder/src/Contracts", "apps/hft-backtest")):
        if provider not in offsets or consumer not in offsets or offsets[provider] >= offsets[consumer]:
            errors.append(f"{relative}: provider {provider} must precede consumer {consumer}")
    markers = [(tokens(command.body), scope(context)) for command, context in contexts
               if command.name == "set" and tokens(command.body)[:1] == ("CXET_ROOT_SOURCE_GRAPH",)]
    if markers != [(('CXET_ROOT_SOURCE_GRAPH', 'ON'), ())]:
        errors.append(f"{relative}: root authority marker must be unconditional before providers")
    marker_commands = [command for command in commands if command.name == "set"
                       and tokens(command.body)[:1] == ("CXET_ROOT_SOURCE_GRAPH",)]
    if len(marker_commands) == 1 and offsets and marker_commands[0].offset >= min(offsets.values()):
        errors.append(f"{relative}: root authority marker must precede every provider")
    guard = ("NOT", "CXET_BUILD_OWNER", "IN_LIST", "_cxet_compile_owners")
    fatals = [command for command, context in contexts if command.name == "message"
              and tokens(command.body)[:1] == ("FATAL_ERROR",)
              and scope(context) == (("if", guard),)]
    if len(fatals) != 1 or (offsets and fatals[0].offset >= min(offsets.values())):
        errors.append(f"{relative}: unknown owner must fail before any provider edge")


def check_root_graph(text: str, core_text: str, profile_caches: dict[str, dict[str, str]],
                     errors: list[str], *, owner_graph_text: str = "") -> None:
    commands = parse_commands(ROOT_CMAKE, text, errors)
    core_commands = parse_commands("src/src/CMakeLists.txt", core_text, errors)
    evidence = validate_root_dialect(commands, words, errors, profiles=profile_caches)
    validate_root_external_edges(commands, errors, evidence.viable_offsets)
    validate_root_provider_contract(commands, core_commands, errors)
    validate_root_compiler_guard(commands, errors)
    validate_root_platform_guards(commands, errors)
    validate_root_full_family_guard(commands, errors)
    validate_root_guard_order(commands, errors)
    validate_root_ownership_effects(commands, words, errors, evidence.viable_offsets)
    core_edges = [command for command, context in command_contexts(commands)
                  if command.name == "add_subdirectory" and words(command.body) == ["src/src"]
                  and not context]
    owner_edges = [command for command, context in command_contexts(commands)
                   if command.name == "include" and tuple(unquote(value) for value in words(command.body)) ==
                   ("${CMAKE_SOURCE_DIR}/cmake/CxetCompileGraph.cmake",)
                   and context == (("if", ("DEFINED", "CXET_BUILD_OWNER")),)]
    if len(core_edges) != 1 or len(owner_edges) != 1:
        errors.append(f"{ROOT_CMAKE}: require one unconditional core edge and one owner-controlled compile graph include")
    elif core_edges[0].offset >= owner_edges[0].offset:
        errors.append(f"{ROOT_CMAKE}: core provider must precede owner composition")
    else:
        validate_required_profiles_live(evidence, ROOT_CMAKE, errors)
        for profile_name in profile_caches:
            for command, description in ((core_edges[0], "core source provider"),
                                         (owner_edges[0], "owner source composition")):
                require_profile_command(evidence, profile_name, command.offset,
                    f"{ROOT_CMAKE}:{command.line}", description, errors)
    check_owner_composition(owner_graph_text, errors)

def check_provider_guards(
    relative: str,
    text: str,
    providers: tuple[str, ...],
    errors: list[str],
) -> None:
    commands = parse_commands(relative, text, errors)
    first_product = next(
        (
            command.offset for command in commands
            if command.name in {"add_library", "add_executable", "include"}
        ),
        len(text),
    )
    prelude = text[:first_product]
    if relative == "src/tests/Family/CMakeLists.txt":
        full_guard = 'if(CXET_FAMILY_PROFILE STREQUAL "full")'
        if prelude.count(full_guard) != 1:
            errors.append(f"{relative}: missing exact full-profile provider guard")
            return
        essential_prelude, full_prelude = prelude.split(full_guard, 1)
        essential_inventory = exact_provider_guard_inventory(essential_prelude)
        full_inventory = exact_provider_guard_inventory(full_prelude)
        if essential_inventory != providers or full_inventory != FULL_ONLY_FAMILY_PROVIDERS:
            errors.append(
                f"{relative}: exact provider guard inventory changed; "
                f"essential={essential_inventory}, full={full_inventory}"
            )
        return
    inventory = exact_provider_guard_inventory(prelude, conditional_guards=(
        (("CXET_EXCHANGE_FINAM",), ("hft-finam-metadata-store",)),
    ) if relative == "apps/vetron/CMakeLists.txt" else ())
    if inventory != providers:
        errors.append(
            f"{relative}: exact provider guard inventory changed; "
            f"expected {list(providers)}, found "
            f"{list(inventory) if inventory is not None else 'invalid'}")

def check_app_contract(relative: str, text: str, providers: tuple[str, ...], errors: list[str]) -> None:
    commands = parse_commands(relative, text, errors)
    validate_app_guard_contract(relative, commands, errors)
    if "CXET root graph required" not in text:
        errors.append(f"{relative}: missing explicit root-graph-required diagnostic")
    check_provider_guards(relative, text, providers, errors)

    for command in commands:
        if command.name != "add_subdirectory":
            continue
        command_words = words(command.body)
        if not command_words:
            errors.append(f"{relative}:{command.line}: empty add_subdirectory()")
            continue
        directory = unquote(command_words[0])
        if directory.startswith("../") or directory.startswith("apps/") or "/../" in directory:
            errors.append(
                f"{relative}:{command.line}: forbidden sibling source graph {directory}"
            )

def check_aliases(relative: str, text: str, aliases: tuple[tuple[str, str], ...], errors: list[str]) -> None:
    commands = parse_commands(relative, text, errors)
    declarations = [words(command.body) for command in commands if command.name == "add_library"]
    for alias, concrete in aliases:
        matches = [
            declaration for declaration in declarations
            if len(declaration) >= 3
            and declaration[0] == alias
            and declaration[1] == "ALIAS"
            and declaration[2] == concrete
        ]
        if len(matches) != 1:
            errors.append(
                f"{relative}: expected exactly one canonical alias {alias} -> "
                f"{concrete}, found {len(matches)}"
            )
