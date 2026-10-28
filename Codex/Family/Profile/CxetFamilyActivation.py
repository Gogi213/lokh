"""Bounded ownership facts from the current owner drivers and offline helper.

This is a static adapter, never a CMake runner. Unknown helper identities,
registration branches and dynamic carriers fail closed before facts are lowered.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path

from CMake.Flow.CmakeFamilyExecutionIdentity import (
    reviewed_file_identity, unsymlinked_regular_path,
)
from CMake.Flow.CmakeFamilyGraph import Command, cmake_list_words, parse_commands
from CMake.Root.CmakeFamilyRootComposition import check_owner_composition
from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
from CMake.Flow.CmakeFamilyFlow import Truth, evaluate_condition
from CMake.Flow.CmakeFamilyState import expand_variable_tokens
from CMake.Syntax.CmakeFamilyContext import structural_contexts

OFFLINE_HELPER = "cmake/CxetOfflineTests.cmake"
# Exact producer identity proves case/catalog commands, labels, instrumenting,
# source attachment and private include/link visibility before lowering calls.
_HELPER_SHA256 = "02b0f72dde2672c9bc2ff3fe421ad5cc14b545ce649ca59d2f5bad3deddde65a"
_TARGET = re.compile(r"[A-Za-z][A-Za-z0-9_.-]*\Z")
_SINGLE = {"OWNER", "EXPECTED", "KIND", "ENTRY", "TSCONFIG", "ENVIRONMENT"}
_MULTI = {"SOURCES", "LIBRARIES", "INCLUDE_DIRECTORIES", "LABELS"}
_HELPERS = {"cxet_add_offline_suite", "cxet_add_offline_diagnostic", "cxet_add_offline_typescript_suite"}
_STARTUP_CMAKE = "apps/trader/tests/startup/CMakeLists.txt"
_STARTUP_SHA256 = "1a8164a71be09c573e7dd506672b64f853a04af19aa1e51ed207e3e83432c188"


def startup_cases(root: Path, *, tbank: bool = False) -> list[dict]:
    """The exact startup producer reads one bounded JSON matrix at configure."""
    text = _read(root, _STARTUP_CMAKE)
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != _STARTUP_SHA256:
        raise ValueError("startup registration producer changed; review declarations, JSON catalog and executable oracle")
    matrix = _read(root, "apps/trader/tests/startup/" +
        ("tbank_scenarios" if tbank else "scenarios") + "/cases.json")
    if len(matrix.encode("utf-8")) > 1024 * 1024:
        raise ValueError("startup matrix exceeds 1 MiB")
    data = json.loads(matrix)
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list) or not 0 < len(cases) <= 256:
        raise ValueError("startup matrix requires 1..256 cases")
    names = set()
    for case in cases:
        name = case.get("name") if isinstance(case, dict) else None
        timeout = case.get("timeout_s") if isinstance(case, dict) else None
        if (not isinstance(name, str) or not _TARGET.fullmatch(name) or
                tbank and not name.startswith("tbank.") or name in names or
                type(timeout) is not int or not 1 <= timeout <= 180):
            raise ValueError("invalid/duplicate startup identity or watchdog")
        names.add(name)
    return cases


def _lower_startup(root: Path, commands, errors: list[str]):
    try:
        catalogs = (("matrix", "trader_offline_finam_startup_process", startup_cases(root)),
                    ("tbank_matrix", "trader_offline_tbank_startup_process", startup_cases(root, tbank=True)))
        # Pin the actual supplied input too: callers must not replace parsed
        # commands while borrowing the unchanged on-disk producer identity.
        expected = parse_commands(_STARTUP_CMAKE, _read(root, _STARTUP_CMAKE), errors)
        if list(commands) != expected:
            raise ValueError("startup parsed producer differs from its reviewed physical source")
        lowered = []
        tbank_start = next(index for index, command in enumerate(commands)
            if command.name == "add_library" and cmake_list_words(command.body)[:1] == ["trader_tbank_startup_network"])
        for start, (matrix, target, cases) in zip((0, tbank_start), catalogs):
            stop = next(index for index, command in enumerate(commands)
                if command.name == "set" and cmake_list_words(command.body)[:1] == [matrix])
            in_metadata_loop = False
            for command in commands[start:stop]:
                values = cmake_list_words(command.body)
                if command.name == "foreach":
                    in_metadata_loop = True
                    continue
                if command.name == "endforeach":
                    in_metadata_loop = False
                    continue
                if (in_metadata_loop or command.name == "cxet_offline_instrument" or
                        command.name == "add_dependencies" and values[:1] == ["cxet-compile-tests"] or
                        command.name == "target_compile_definitions" and values[:1] == [target]):
                    continue
                lowered.append(command)
            for case in cases:
                lowered.append(Command("add_test", _body([
                    "NAME", "offline.trader." + case["name"], "COMMAND",
                    target, "--case", case["name"]]), commands[stop].line))
        # JSON reads, GENERATE and catalog-test commands create no C++ ownership
        # facts. Their exact producer remains pinned above; --list stays a real
        # independent CheckCaseCatalog.py invocation in the original CMake.
        return lowered
    except (OSError, UnicodeError, ValueError, StopIteration) as exc:
        errors.append(f"{_STARTUP_CMAKE}: unsupported startup registration: {exc}")
        return []


def offline_registration_inventory(root: Path, owner: str, errors: list[str]) -> list[str]:
    """Count the full all-exchange owner closure, including exact descendants.

    Physical ownership and conditional CMake execution remain separate: the
    deep checker retains guards; this inventory selects the canonical full
    owner profile explicitly rather than summing unreachable commands.
    """
    directory = ("src/tests/offline" if owner == "CXETCPP" else
                 "tools/exchange_api_probe/tests/offline" if owner == "TestExchangesHelper" else
                 f"apps/{owner}/tests/offline")
    state = {"CXET_SELECTION_ALL": ("1",), "CXET_LOCAL_TESTS": ("ON",),
             "CXET_BUILD_OWNER": (owner,)}
    names, visited = [], set()

    def visit(relative):
        if relative in visited or len(visited) >= 32 or offline_owner(relative) != owner:
            raise ValueError(f"cyclic/foreign/unbounded offline registration edge {relative}")
        visited.add(relative)
        commands = parse_commands(relative, _read(root, relative), errors)
        lowered = lower_offline_registrations(root, relative, commands, errors)
        if relative == _STARTUP_CMAKE:
            commands = lowered
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        local = dict(state)
        for command, context in zip(commands, contexts):
            if command.name not in _HELPERS | {"set", "add_subdirectory", "add_test", "return"}:
                continue
            truth = _profile_context_truth(context, local)
            if truth is Truth.FALSE:
                continue
            if truth is not Truth.TRUE:
                raise ValueError(f"{relative}:{command.line}: unresolved full-owner registration condition")
            values = cmake_list_words(command.body)
            if command.name == "return":
                return
            if command.name == "set" and values:
                local[values[0]] = tuple(values[1:])
            elif command.name in _HELPERS:
                if command.name == "cxet_add_offline_diagnostic":
                    continue
                _, _, _, _, cases = _suite(root, relative, command)
                names.extend(f"offline.{owner}.{case}" for case in cases)
            elif command.name == "add_subdirectory":
                if relative != "apps/trader/tests/offline/CMakeLists.txt" or values != [
                        "../startup", "${CMAKE_CURRENT_BINARY_DIR}/startup"]:
                    raise ValueError(f"{relative}:{command.line}: unreviewed registration descendant")
                visit(_STARTUP_CMAKE)
            elif command.name == "add_test":
                if len(values) < 4 or values[0] != "NAME" or values[2] != "COMMAND":
                    raise ValueError(f"{relative}:{command.line}: direct registration lacks exact name/command")
                bindings = [{}]
                for frame in context:
                    if frame.kind != "foreach":
                        continue
                    tokens = frame.opener
                    if len(tokens) < 4 or tokens[1:3] not in {("IN", "LISTS"), ("IN", "ITEMS")}:
                        raise ValueError("unsupported direct-registration loop")
                    items = (local.get(tokens[3], ()) if tokens[2] == "LISTS" and len(tokens) == 4 else
                             tokens[3:] if tokens[2] == "ITEMS" else ())
                    if not items or len(items) > 256 or any(not _TARGET.fullmatch(item) for item in items):
                        raise ValueError("empty/unbounded direct-registration loop")
                    bindings = [dict(binding, **{tokens[0]: (item,)}) for binding in bindings for item in items]
                for binding in bindings:
                    expanded = expand_variable_tokens(values[1:2], dict(local, **binding))
                    if len(expanded) != 1 or not re.fullmatch(r"offline\." + re.escape(owner) + r"\.[A-Za-z0-9_.-]+", expanded[0]):
                        raise ValueError(f"{relative}:{command.line}: foreign/dynamic direct offline identity")
                    names.append(expanded[0])

    try:
        visit(directory + "/CMakeLists.txt")
        if owner == "trading-core":
            relative = "apps/trading-core/CMakeLists.txt"
            provider_commands = parse_commands(relative, _read(root, relative), errors)
            edges = [(command, context) for command, context in zip(provider_commands,
                structural_contexts(relative, provider_commands, cmake_list_words, errors))
                if command.name == "add_subdirectory" and cmake_list_words(command.body) == ["capital"]]
            if len(edges) != 1 or edges[0][1]:
                raise ValueError("Capital catalog requires its unconditional canonical provider edge")
            visit("apps/trading-core/capital/CMakeLists.txt")
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate offline registration for owner {owner}")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"offline registration inventory {owner}: {exc}")
    return names


def offline_owner(relative: str) -> str | None:
    if relative == "apps/trading-core/capital/CMakeLists.txt":
        return "trading-core"
    if relative == "apps/trader/tests/startup/CMakeLists.txt":
        return "trader"
    if relative == "src/tests/offline/CMakeLists.txt":
        return "CXETCPP"
    if relative == "tools/exchange_api_probe/tests/offline/CMakeLists.txt":
        return "TestExchangesHelper"
    parts = Path(relative).parts
    if len(parts) == 5 and parts[0] == "apps" and parts[2:] == ("tests", "offline", "CMakeLists.txt"):
        return parts[1]
    return None


def _offline_condition(tokens) -> bool:
    values = tuple(tokens)
    return (values == ("CXET_SELECTION_ALL",) or
            values == ("CXET_LOCAL_TESTS", "AND", "CXET_BUILD_OWNER", "STREQUAL", "trader") or
            len(values) == 3 and values[:2] == ("CXET_SELECTION_ALL", "OR") and
            (re.fullmatch(r"CXET_EXCHANGE_[A-Z]+", values[2]) is not None or
             values[2] in {"CXET_HAS_MOEX_NATIVE", "CXET_HAS_GRPC"}))


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not unsymlinked_regular_path(path, root):
        raise ValueError(f"missing/nonregular/symlinked activation input {relative}")
    return path.read_text(encoding="utf-8")


def _profile_truth(tokens, state, known_targets=None):
    """Evaluate only data predicates; host/tool predicates remain unknown."""
    values = []
    for token in tokens:
        # The value lexer retains adjacent condition parentheses. The validated
        # CompileGraph uses them only around boolean owner/profile expressions.
        while token.startswith("("):
            values.append("(")
            token = token[1:]
        suffix = []
        while token.endswith(")"):
            suffix.append(")")
            token = token[:-1]
        if token:
            values.append(token)
        values.extend(suffix)
    index = 0
    while index < len(values):
        if values[index] == "DEFINED" and index + 1 < len(values):
            values[index:index + 2] = ["TRUE" if values[index + 1] in state else "FALSE"]
        elif index + 2 < len(values) and values[index + 1] in {"IN_LIST", "MATCHES"}:
            left = state.get(values[index], (values[index],))
            right = state.get(values[index + 2], (values[index + 2],))
            if len(left) != 1 or any(marker in value for value in (*left, *right)
                for marker in ("${", "$ENV{", "$CACHE{", "$<")):
                return Truth.UNKNOWN
            if values[index + 1] == "IN_LIST":
                if values[index + 2] not in state:
                    return Truth.UNKNOWN
                accepted = left[0] in right
            else:
                if len(right) != 1:
                    return Truth.UNKNOWN
                try:
                    accepted = re.search(right[0], left[0]) is not None
                except re.error:
                    return Truth.UNKNOWN
            values[index:index + 3] = ["TRUE" if accepted else "FALSE"]
        index += 1
    return evaluate_condition(values, state,
        lambda raw, preserve: expand_variable_tokens(raw, state, preserve_empty=preserve),
        known_targets=known_targets)


def _profile_context_truth(context, state, known_targets=None):
    result = Truth.TRUE
    for frame in context:
        if frame.kind != "if":
            continue
        for prior in frame.prior_arms:
            truth = _profile_truth(prior.tokens, state, known_targets)
            if prior.kind == "else" or truth is Truth.TRUE:
                return Truth.FALSE
            if truth is Truth.UNKNOWN:
                result = Truth.UNKNOWN
        if frame.arm.kind != "else":
            truth = _profile_truth(frame.arm.tokens, state, known_targets)
            if truth is Truth.FALSE:
                return Truth.FALSE
            if truth is Truth.UNKNOWN:
                result = Truth.UNKNOWN
    return result


def _parser_contract_profile_provider(root: Path, errors: list[str]) -> bool:
    """Prove the sole contract declaration and Parser's unconditional edge."""
    relative = "apps/hft-parser/src/Contracts/CMakeLists.txt"
    commands = parse_commands(relative, _read(root, relative), errors)
    expected = [
        ("if", ["NOT", "TARGET", "hftp_contract_headers"]),
        ("add_library", ["hftp_contract_headers", "INTERFACE"]),
        ("target_include_directories", ["hftp_contract_headers", "INTERFACE",
            "${CMAKE_CURRENT_LIST_DIR}/include"]),
        ("target_compile_features", ["hftp_contract_headers", "INTERFACE", "cxx_std_23"]),
        ("target_link_libraries", ["hftp_contract_headers", "INTERFACE", "cxet::read_only_contracts"]),
        ("endif", []),
    ]
    if [(command.name, cmake_list_words(command.body)) for command in commands] != expected:
        errors.append("unsupported ownership model: Parser contract provider declaration changed")
        return False
    relative = "apps/hft-parser/CMakeLists.txt"
    commands = parse_commands(relative, _read(root, relative), errors)
    contexts = structural_contexts(relative, commands, cmake_list_words, errors)
    edges = [(command, context) for command, context in zip(commands, contexts)
        if command.name == "add_subdirectory" and cmake_list_words(command.body)[:1] == ["src/Contracts"]]
    if (len(edges) != 1 or edges[0][1] or
            cmake_list_words(edges[0][0].body) != ["src/Contracts", "EXCLUDE_FROM_ALL"] or
            any(command.name == "return" for command in commands)):
        errors.append("unsupported ownership model: Parser contract provider edge changed")
        return False
    return True


def source_profile_roots(graph: str, cache: dict[str, str], errors: list[str], *, root: Path | None = None):
    """Project exact root source edges and inherited values for ONE cache.

    Callers validate the CompileGraph topology first. This bounded projection
    interprets its literal sets, list writers and finite foreach bindings, not
    arbitrary CMake programs. No guard/profile fragments are combined.
    """
    relative = "cmake/CxetCompileGraph.cmake"
    commands = parse_commands(relative, graph, errors)
    contexts = structural_contexts(relative, commands, cmake_list_words, errors)
    state = {key: (value,) for key, value in cache.items()}
    state.setdefault("CMAKE_SCRIPT_MODE_FILE", ("OFF",))
    state.setdefault("CXET_OFFLINE_BENCHMARKS", ("OFF",))
    # The canonical target inventory gives this name one owner: Contracts.
    # Track only that reviewed source provider; arbitrary TARGET stays unknown.
    from Family.Targets.CxetFamilyTargetInventory import PRODUCTION_TARGETS
    provider = PRODUCTION_TARGETS.get("hftp_contract_headers")
    known_targets = {}
    if (provider is not None and provider.kind == "INTERFACE" and
            provider.owner == "apps/hft-parser/src/Contracts/CMakeLists.txt"):
        known_targets["hftp_contract_headers"] = "SOURCE_PROVED_ABSENT"
    selected_root = Path(__file__).resolve().parents[4] if root is None else root
    provider_proved = None
    result = {}
    for command, context in zip(commands, contexts):
        if _profile_context_truth(context, state, known_targets) is Truth.FALSE:
            continue
        bindings = [{}]
        for frame in context:
            if frame.kind != "foreach":
                continue
            tokens = frame.opener
            if len(tokens) < 3 or tokens[1] != "IN" or tokens[2] not in {"ITEMS", "LISTS"}:
                errors.append(f"unsupported ownership model: {relative}:{command.line}: source profile loop")
                bindings = []
                break
            items = (expand_variable_tokens(tokens[3:], state) if tokens[2] == "ITEMS" else
                     [value for key in tokens[3:] for value in state.get(key, ()) if value])
            if len(items) * len(bindings) > 64 or any("$" in value for value in items):
                errors.append(f"unsupported ownership model: {relative}:{command.line}: source profile loop values")
                bindings = []
                break
            bindings = [dict(binding, **{tokens[0]: (value,)}) for binding in bindings for value in items]
        for binding in bindings:
            local = dict(state, **binding)
            truth = _profile_context_truth(context, local, known_targets)
            if truth is Truth.FALSE:
                continue
            words = cmake_list_words(command.body)
            if command.name == "add_subdirectory":
                if truth is not Truth.TRUE:
                    errors.append(f"unsupported ownership model: {relative}:{command.line}: source edge has no exact active profile guard")
                    continue
                sources = expand_variable_tokens(words[:1], local)
                if len(sources) != 1 or any(marker in sources[0] for marker in ("$", "\\", ";")) or Path(sources[0]).is_absolute() or ".." in Path(sources[0]).parts:
                    errors.append(f"unsupported ownership model: {relative}:{command.line}: source profile edge carrier")
                    continue
                result[sources[0] + "/CMakeLists.txt"] = local
                if sources[0] in {"apps/hft-parser", "apps/hft-parser/src/Contracts"}:
                    if provider_proved is None:
                        provider_proved = _parser_contract_profile_provider(selected_root, errors)
                    known_targets["hftp_contract_headers"] = (
                        "INTERFACE" if provider_proved else "AMBIGUOUS")
            elif command.name == "return" and truth is Truth.TRUE:
                return result
            elif command.name == "set" and words:
                values = expand_variable_tokens(words[1:], local)
                if "CACHE" in words:
                    values = expand_variable_tokens(words[1:words.index("CACHE")], local)
                    if words[0] in state and "FORCE" not in words:
                        continue
                state[words[0]] = tuple(values) if truth is Truth.TRUE else ("$<CXET_UNKNOWN_SOURCE_PROFILE>",)
            elif command.name == "list" and len(words) >= 2:
                destination = expand_variable_tokens(words[1:2], local)
                if len(destination) != 1 or "$" in destination[0]:
                    errors.append(f"unsupported ownership model: {relative}:{command.line}: source profile list destination")
                    continue
                key = destination[0]
                if truth is not Truth.TRUE:
                    state[key] = ("$<CXET_UNKNOWN_SOURCE_PROFILE>",)
                    continue
                values = expand_variable_tokens(words[2:], local)
                if words[0] == "APPEND":
                    state[key] = (*state.get(key, ()), *values)
                elif words[0] == "REMOVE_ITEM":
                    state[key] = tuple(value for value in state.get(key, ()) if value not in values)
                else:
                    errors.append(f"unsupported ownership model: {relative}:{command.line}: source profile list writer")
    return result


def owner_activation(root: Path, errors: list[str]):
    """Return independent configure instances from exact driver caches.

    A physical directory may occur in several instances. Its declarations,
    cache, namespace and EOF proof must never be combined across those entries.
    Recorder production remains its actual GUI/capture profile; its corpus-only
    offline instance is separate evidence.
    """
    try:
        profiles = resolve_root_profile_caches(
            _read(root, "tools/Build/CompileTargets.py"), errors,
            offline_text=_read(root, "tools/Testing/RunOffline.py"),
            owners_text=_read(root, "tools/Build/ActiveBuild.py"), root=root)
        graph = _read(root, "cmake/CxetCompileGraph.cmake")
        graph_errors = []
        check_owner_composition(graph, graph_errors)
        errors.extend(graph_errors)
        if not profiles or graph_errors:
            return {}
        configurations = {}
        for name, cache in profiles.items():
            if (cache.get("CXET_EXCHANGES", "all") != "all" or
                    cache.get("CXET_EXCHANGE_PRESET", "")):
                raise ValueError("restricted exchange profile has no reviewed ownership projection")
            if not reviewed_file_identity("cmake/CxetExchangeSelection.cmake"):
                raise ValueError("exchange selector identity changed")
            selection = parse_commands("cmake/CxetExchangeSelection.cmake",
                _read(root, "cmake/CxetExchangeSelection.cmake"), errors)
            literals = {}
            for command in selection:
                words = cmake_list_words(command.body)
                if command.name == "set" and words[:1] in (["_cxet_exchange_names"], ["_cxet_protocol_flags"]):
                    literals[words[0]] = words[1:]
            if set(literals) != {"_cxet_exchange_names", "_cxet_protocol_flags"}:
                raise ValueError("exchange selector lost its literal profile universe")
            selected_values = {"CXET_SELECTION_ALL": ("1",), "CXET_EXCHANGE_PROFILE": ("all",),
                **{"CXET_EXCHANGE_" + exchange.upper(): ("1",) for exchange in literals["_cxet_exchange_names"]},
                **{"CXET_HAS_" + flag: ("1",) for flag in literals["_cxet_protocol_flags"]}}
            reachable = source_profile_roots(graph, cache, errors, root=root)
            roots = ("src/src/CMakeLists.txt", *reachable)
            values = {roots[0]: {key: (value,) for key, value in cache.items()},
                      **reachable}
            values[roots[0]]["CXET_BENCHHELLO_ONLY"] = ("OFF",)
            for inherited in values.values():
                inherited.update(selected_values)
            if cache["CXET_LOCAL_TESTS"] == "ON":
                owner = cache["CXET_BUILD_OWNER"]
                relative = ("src/tests/offline/CMakeLists.txt" if owner == "CXETCPP" else
                            "tools/exchange_api_probe/tests/offline/CMakeLists.txt" if owner == "TestExchangesHelper" else
                            f"apps/{owner}/tests/offline/CMakeLists.txt")
                if relative not in reachable:
                    raise ValueError(f"offline root {relative} has no reachable exact {name} source profile")
                _read(root, relative)
            configurations[name] = (roots, values)
        return configurations
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        errors.append(f"ownership activation: {exc}")
        return {}


def validate_offline_helper(text: str, errors: list[str]) -> bool:
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != _HELPER_SHA256:
        errors.append(f"unsupported ownership model: {OFFLINE_HELPER} producer identity changed; review source/link/include, cases, catalogs and labels before lowering")
        return False
    if not reviewed_file_identity("tools/Testing/CheckCaseCatalog.py"):
        errors.append("unsupported ownership model: offline executable/catalog verifier identity changed")
        return False
    if not all(reviewed_file_identity(path) for path in (
            "tools/Testing/ExtractCaseCatalog.py",
            "tools/Codex/Family/Sources/CxetFamilyCppPolicy.py")):
        errors.append("unsupported ownership model: offline source catalog extractor/lexer identity changed")
        return False
    return True


def source_cases(text: str, *, typescript: bool = False, source: Path | None = None) -> list[str]:
    """Use the configure-time producer's canonical source catalog reader."""
    path = Path(__file__).resolve().parents[4] / "tools/Testing/ExtractCaseCatalog.py"
    spec = importlib.util.spec_from_file_location("_cxet_offline_source_catalog", path)
    if spec is None or spec.loader is None:
        raise ValueError("missing canonical offline source catalog reader")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if source is not None:
        return module.extract_file_cases(source, typescript=typescript)
    return module.extract_cases(text, typescript=typescript)


def _body(values):
    return " ".join(json.dumps(value) if any(char.isspace() for char in value) or not value else value for value in values)


def _suite(root, relative, command):
    words = cmake_list_words(command.body)
    if not words or not _TARGET.fullmatch(words[0]):
        raise ValueError("invalid concrete offline target")
    target, options, index = words[0], {}, 1
    while index < len(words):
        key = words[index]
        if key not in _SINGLE | _MULTI or key in options:
            raise ValueError(f"unknown/duplicate offline keyword {key}")
        index += 1
        start = index
        while index < len(words) and words[index] not in _SINGLE | _MULTI:
            index += 1
        options[key] = words[start:index]
        if not options[key] or key in _SINGLE and len(options[key]) != 1:
            raise ValueError(f"invalid offline keyword {key}")
    owner = offline_owner(relative)
    if options.get("OWNER") != [owner] or not options.get("SOURCES"):
        raise ValueError("offline suite must bind its exact owner and concrete sources")
    allowed = ({"OWNER", "KIND", "EXPECTED", "SOURCES", "LIBRARIES", "INCLUDE_DIRECTORIES"} if command.name == "cxet_add_offline_diagnostic" else
               {"OWNER", "EXPECTED", "ENTRY", "TSCONFIG", "SOURCES", "ENVIRONMENT"} if command.name == "cxet_add_offline_typescript_suite" else
               {"OWNER", "EXPECTED", "SOURCES", "LIBRARIES", "INCLUDE_DIRECTORIES", "LABELS"})
    if set(options) - allowed:
        raise ValueError("helper receives keywords outside its canonical signature")
    if "ENVIRONMENT" in options and not (
            relative == "apps/vetron/tests/offline/CMakeLists.txt" and
            target == "vetron_offline_ranking_evidence" and options["ENVIRONMENT"] == [
                "VETRON_RANKING_MATH_WASM=${CMAKE_BINARY_DIR}/apps/vetron/wasm/trading-core-math.wasm"]):
        raise ValueError("unsupported offline environment binding")
    sources, cases = [], []
    for value in options["SOURCES"]:
        resident_fixture = value == "${CMAKE_SOURCE_DIR}/src/tests/offline/Support/ResidentMemoryFixture.cpp"
        if not resident_fixture and any(marker in value for marker in ("${", "$ENV{", "$CACHE{", "$<", ";", "\\")):
            raise ValueError(f"unsupported offline source carrier {value}")
        source = (root / "src/tests/offline/Support/ResidentMemoryFixture.cpp" if resident_fixture else
                  root / Path(relative).parent / value)
        # Resolve parent segments only after proving the resulting path and its
        # ancestry are regular project inputs, never external or generated files.
        if not unsymlinked_regular_path(source, root):
            raise ValueError(f"missing/nonregular/symlinked offline source {value}")
        source = Path(os.path.abspath(source))
        if not unsymlinked_regular_path(source, root):
            raise ValueError(f"missing/nonregular/symlinked offline source {value}")
        boundary = root / ("src" if owner == "CXETCPP" else
                           "tools/exchange_api_probe" if owner == "TestExchangesHelper" else f"apps/{owner}")
        if not source.is_relative_to(boundary):
            from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_shared_fixture_source
            if (command.name != "cxet_add_offline_suite" or not offline_shared_fixture_source(
                    relative, owner, target, source.relative_to(root).as_posix())):
                raise ValueError(f"offline source escapes its owner: {value}")
        if command.name != "cxet_add_offline_typescript_suite" and source.suffix not in {".cpp", ".cc", ".c", ".cxx"}:
            raise ValueError(f"unsupported compiled offline source {value}")
        if command.name == "cxet_add_offline_typescript_suite" and source.suffix not in {".ts", ".tsx"}:
            raise ValueError(f"unsupported TypeScript offline source {value}")
        text = source.read_text(encoding="utf-8")
        cases.extend(source_cases(text, typescript=command.name == "cxet_add_offline_typescript_suite", source=source))
        sources.append(source.relative_to(root).as_posix())
    if command.name == "cxet_add_offline_diagnostic":
        if options.get("KIND") not in (["fuzz"], ["thread"]):
            raise ValueError("invalid offline diagnostic kind")
        if "EXPECTED" in options and (not options["EXPECTED"][0].isdigit() or
                not cases or len(cases) != int(options["EXPECTED"][0]) or
                len(cases) != len(set(cases))):
            raise ValueError("offline diagnostic scenario catalog mismatch")
    elif not options.get("EXPECTED") or not options["EXPECTED"][0].isdigit() or len(cases) != int(options["EXPECTED"][0]) or not cases or len(cases) != len(set(cases)):
        raise ValueError(f"offline scenario catalog has {len(cases)} cases; expected {options.get('EXPECTED')}; duplicates are forbidden")
    return target, owner, options, sources, cases






def _workspace_loop_provenance(root: Path, commands):
    variable = "vetron_workspace_authority_cases"
    entries = [index for index, command in enumerate(commands) if command.name == "set"
               and cmake_list_words(command.body)[:1] == [variable]]
    if not entries:
        return frozenset()
    if len(entries) != 1:
        raise ValueError("duplicate workspace literal-case producer")
    block = commands[entries[0]:entries[0] + 5]
    source = "apps/vetron/tests/offline/Workspace/AuthorityCases.py"
    tree = ast.parse(_read(root, source), filename=source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "WorkspaceAuthorityCases"]
    if (len(classes) != 1 or len(classes[0].bases) != 1 or
            ast.dump(classes[0].bases[0]) != ast.dump(ast.parse("unittest.TestCase", mode="eval").body)):
        raise ValueError("workspace case catalog requires the actual unittest class")
    cases = [node.name for node in classes[0].body if isinstance(node, ast.FunctionDef)
             and node.name.startswith("test_")]
    if not 0 < len(cases) <= 64 or len(cases) != len(set(cases)):
        raise ValueError("workspace literal-case catalog is empty/duplicate/unbounded")
    declared = cmake_list_words(block[0].body)[1:]
    if len(declared) != len(set(declared)) or set(declared) != set(cases):
        raise ValueError("workspace literal-case catalog differs from actual unittest methods")
    expected = (
        ("set", [variable, *declared]),
        ("foreach", ["case", "IN", "LISTS", variable]),
        ("add_test", ["NAME", "offline.vetron.workspace.${case}", "COMMAND",
            "${Python3_EXECUTABLE}", "${CMAKE_CURRENT_SOURCE_DIR}/Workspace/AuthorityCases.py",
            "WorkspaceAuthorityCases.${case}"]),
        ("set_tests_properties", ["offline.vetron.workspace.${case}", "PROPERTIES", "LABELS",
            "owner:vetron;offline;standalone;workspace;authority", "TIMEOUT", "30", "ENVIRONMENT",
            "VETRON_FIXTURE_ROOT=${CMAKE_CURRENT_BINARY_DIR};PYTHONDONTWRITEBYTECODE=1"]),
        ("endforeach", []),
    )
    if len(block) != len(expected) or any(command.name != name or cmake_list_words(command.body) != words
            for command, (name, words) in zip(block, expected)):
        raise ValueError("unsupported workspace literal-case/loop/body provenance")
    return frozenset(block)


def _parser_entrypoint_loop_provenance(root: Path, commands):
    """Bind the one literal entrypoint loop to its actual unittest methods."""
    variable = "hftp_entrypoint_case"
    entries = [index for index, command in enumerate(commands)
        if command.name == "foreach" and cmake_list_words(command.body)[:1] == [variable]]
    if not entries:
        return frozenset()
    if len(entries) != 1:
        raise ValueError("duplicate Parser entrypoint case loop")
    block = commands[entries[0]:entries[0] + 4]
    source = "apps/hft-parser/tests/offline/Launcher/launcher-entrypoints.py"
    tree = ast.parse(_read(root, source), filename=source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Entrypoints"]
    if (len(classes) != 1 or len(classes[0].bases) != 1 or
            ast.dump(classes[0].bases[0]) != ast.dump(ast.parse("unittest.TestCase", mode="eval").body)):
        raise ValueError("Parser entrypoint catalog requires the actual unittest class")
    cases = [node.name.removeprefix("test_") for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    declared = cmake_list_words(block[0].body)[3:]
    if (not 0 < len(cases) <= 64 or len(declared) != len(set(declared)) or
            set(declared) != set(cases)):
        raise ValueError("Parser entrypoint catalog differs from actual unittest methods")
    expected = (
        ("foreach", [variable, "IN", "ITEMS", *declared]),
        ("add_test", ["NAME", "offline.hft-parser.entrypoint_${hftp_entrypoint_case}", "COMMAND",
            "${Python3_EXECUTABLE}", "${CMAKE_CURRENT_SOURCE_DIR}/Launcher/launcher-entrypoints.py",
            "--parserd", "$<TARGET_FILE:hft-parserd>", "--planner", "$<TARGET_FILE:hft-resource-planner>",
            "--artifacts-root", "${CMAKE_CURRENT_BINARY_DIR}", "Entrypoints.test_${hftp_entrypoint_case}"]),
        ("set_tests_properties", ["offline.hft-parser.entrypoint_${hftp_entrypoint_case}", "PROPERTIES",
            "LABELS", "owner:hft-parser;offline;launcher;standalone", "TIMEOUT", "30"]),
        ("endforeach", []),
    )
    if len(block) != len(expected) or any(command.name != name or cmake_list_words(command.body) != words
            for command, (name, words) in zip(block, expected)):
        raise ValueError("unsupported Parser entrypoint loop/body provenance")
    return frozenset(block)


def lower_offline_registrations(root: Path, relative: str, commands, errors: list[str]):
    """Lower exact current producer calls, retaining their physical origin."""
    if relative == _STARTUP_CMAKE:
        return _lower_startup(root, commands, errors)
    from CMake.Policy.CmakeFamilyOfflineRecipe import OfflineCommand, OfflineRegistration
    lowered, targets, registrations = [], set(), set()
    capabilities = {}
    script_producers, script_dependencies = set(), set()
    instruments = set()
    structural = frozenset()
    structural_contexts(relative, commands, cmake_list_words, errors)
    try:
        if relative == "apps/vetron/tests/offline/CMakeLists.txt":
            structural = _workspace_loop_provenance(root, commands)
        elif relative == "apps/hft-parser/tests/offline/CMakeLists.txt":
            structural = _parser_entrypoint_loop_provenance(root, commands)
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        errors.append(f"{relative}: unsupported ownership model: {exc}")
        return []
    for command in commands:
        if command.name not in _HELPERS:
            if relative == "apps/trading-core/capital/CMakeLists.txt":
                # Retain actual owner guards/return and all ordinary provider
                # commands for the generic path-aware composer.
                lowered.append(command)
                continue
            words = cmake_list_words(command.body)
            if command.name in {"if", "elseif", "else", "endif"}:
                if command.name in {"if", "elseif"} and not _offline_condition(words):
                    errors.append(f"{relative}:{command.line}: unsupported offline registration condition {words}")
                lowered.append(command)
                continue
            if command.name == "add_subdirectory":
                if (relative != "apps/trader/tests/offline/CMakeLists.txt" or words != [
                        "../startup", "${CMAKE_CURRENT_BINARY_DIR}/startup"]):
                    errors.append(f"{relative}:{command.line}: unreviewed offline registration descendant")
                else:
                    lowered.append(command)
                continue
            if command.name == "target_sources":
                if (relative != "apps/trader/tests/offline/CMakeLists.txt" or words != [
                        "trader_offline_tbank_full_path", "PRIVATE", "Execution/FinamFullPathCases.cpp"] or
                        words[0] not in targets):
                    errors.append(f"{relative}:{command.line}: unreviewed offline source attachment")
                else:
                    lowered.append(command)
                continue
            if command in structural:
                lowered.append(command)
                continue
            if command.name == "cxet_offline_instrument":
                words = cmake_list_words(command.body)
                if (len(words) != 1 or not _TARGET.fullmatch(words[0]) or
                        words[0] not in targets or words[0] in script_producers or words[0] in instruments):
                    errors.append(f"{relative}:{command.line}: unsupported ownership model: instrument requires one prior concrete owner target")
                else:
                    instruments.add(words[0])
                    lowered.append(OfflineCommand(command.name, command.body, command.line,
                                                   capabilities[words[0]]))
                continue
            if (relative == "apps/vetron/tests/offline/CMakeLists.txt" and
                    command.name == "add_dependencies" and
                    cmake_list_words(command.body) == ["vetron_offline_ranking_evidence", "vetron-math-wasm"] and
                    "vetron_offline_ranking_evidence" in script_producers):
                # The validated helper is a cold script producer, not a C++
                # target. Its exact build prerequisite creates no link facts.
                if "vetron_offline_ranking_evidence" in script_dependencies:
                    errors.append(f"{relative}:{command.line}: duplicate TypeScript build prerequisite")
                script_dependencies.add("vetron_offline_ranking_evidence")
                continue
            if command.name not in {"target_compile_options", "target_compile_definitions",
                    "target_include_directories", "target_link_options", "find_package",
                    "add_test", "set_tests_properties", "add_dependencies"}:
                errors.append(f"{relative}:{command.line}: unsupported ownership model: offline command/branch {command.name}")
            else:
                registration = capabilities.get(words[0]) if words else None
                lowered.append(OfflineCommand(command.name, command.body, command.line, registration)
                               if registration is not None and command.name.startswith("target_") else command)
            continue
        try:
            target, owner, options, sources, cases = _suite(root, relative, command)
            if target in targets:
                raise ValueError(f"duplicate offline target {target}")
            targets.add(target)
            registration = OfflineRegistration(target, relative, owner, tuple(sources),
                tuple(options.get("LIBRARIES", ())), tuple(options.get("INCLUDE_DIRECTORIES", ())))
            def add(name, values):
                lowered.append(OfflineCommand(name, _body(values), command.line, registration))
            if command.name == "cxet_add_offline_typescript_suite":
                if not options.get("ENTRY") or not options.get("TSCONFIG"):
                    raise ValueError("TypeScript suite requires concrete ENTRY/TSCONFIG")
                for key in ("ENTRY", "TSCONFIG"):
                    path = Path(options[key][0])
                    if (path.is_absolute() or ".." in path.parts or
                            any(marker in str(path) for marker in ("${", "$ENV{", "$CACHE{", "$<", ";", "\\"))):
                        raise ValueError(f"unsupported TypeScript {key} carrier")
                _read(root, (Path(relative).parent / options["TSCONFIG"][0]).as_posix())
                script_producers.add(target)
                # No C++ source/link facts exist for the cold Node bundle. Its
                # exact helper identity proves executable case/catalog commands.
                continue
            capabilities[target] = registration
            # Sources are kept relative to the original list evaluation context.
            add("add_executable", [target, *options["SOURCES"]])
            add("target_include_directories", [target, "PRIVATE", "${CMAKE_SOURCE_DIR}/tools/Testing", *options.get("INCLUDE_DIRECTORIES", [])])
            if options.get("LIBRARIES"):
                add("target_link_libraries", [target, "PRIVATE", *options["LIBRARIES"]])
            diagnostic = command.name == "cxet_add_offline_diagnostic"
            case_diagnostic = diagnostic and "EXPECTED" in options
            names = ([f"offline-diagnostic.{owner}.{target}.{case}" for case in cases] if case_diagnostic else
                     [f"offline-diagnostic.{owner}.{target}"] if diagnostic else
                     [f"offline.{owner}.{case}" for case in cases])
            for name in names:
                if name in registrations:
                    raise ValueError(f"duplicate offline registration {name}")
                registrations.add(name)
                arguments = ([] if diagnostic and not case_diagnostic else
                             ["--case", name.removeprefix(f"offline-diagnostic.{owner}.{target}." if diagnostic else f"offline.{owner}.")])
                add("add_test", ["NAME", name, "COMMAND", target, *arguments])
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{relative}:{command.line}: unsupported ownership model: {exc}")
    return lowered
