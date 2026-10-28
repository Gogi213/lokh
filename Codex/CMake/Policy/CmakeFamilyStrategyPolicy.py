"""Canonical trading-core strategy and generated-registry identities."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import (
    exact_context,
    alternate_if,
    StructuralTracker,
    first_body,
    first_if,
    structural_contexts,
)


ROOT = Path(__file__).resolve().parents[4]
BINARY_ROOT = "__CXET_CMAKE_BINARY__"
CANONICAL_STRATEGY_NAMES = ("delivery_sum_signal", "pair_api_probe")
REPLAY_STRATEGY_NAMES: tuple[str, ...] = ()


def canonical_strategy_names() -> tuple[str, ...]:
    return CANONICAL_STRATEGY_NAMES


def strategy_folder(name: str) -> str:
    """Physical folder spelling; descriptor and serialized names stay stable."""
    return "".join(part[:1].upper() + part[1:] for part in name.split("_"))


def strategy_name(folder: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", folder).lower()


def actual_strategy_names() -> tuple[str, ...]:
    return tuple(sorted(
        strategy_name(path.parent.name)
        for path in (ROOT / "apps/trading-core/src/Strategy/include/strategy").glob(
            "*/*/Strategy.hpp")
        if path.is_file()
    ))


def actual_registered_strategy_names() -> tuple[str, ...]:
    """Mirror the CMake Strategy.hpp plus optional Descriptor.hpp predicate."""
    result: list[str] = []
    root = ROOT / "apps/trading-core/src/Strategy/include/strategy"
    for header in sorted(root.glob("*/*/Strategy.hpp")):
        if not header.is_file():
            continue
        name = strategy_name(header.parent.name)
        descriptor = header.parent / "Descriptor.hpp"
        try:
            payload = header.read_bytes()
            if descriptor.is_file():
                payload += b"\n" + descriptor.read_bytes()
        except OSError:
            continue
        pattern = (
            re.escape(name.encode("utf-8")) +
            rb"StrategyDescriptor[ \t\r\n]*\("
        )
        if re.search(pattern, payload) is not None:
            result.append(name)
    return tuple(result)


def proven_strategy_names() -> tuple[str, ...]:
    """Expose no generated authority until the real CMake predicate is exact."""
    candidates = actual_strategy_names()
    registered = actual_registered_strategy_names()
    if not (
            candidates == CANONICAL_STRATEGY_NAMES and
            registered == CANONICAL_STRATEGY_NAMES):
        return ()
    return CANONICAL_STRATEGY_NAMES


def proven_strategy_headers() -> frozenset[str]:
    return frozenset(
        (ROOT / "apps/trading-core/src/Strategy/include/strategy/trader" / strategy_folder(name) /
         "Strategy.hpp").resolve().as_posix()
        for name in proven_strategy_names()
    )


def proven_replay_strategy_names() -> tuple[str, ...]:
    """Only explicit Backtest adapters grant replay metadata authority."""
    return REPLAY_STRATEGY_NAMES


def registry_outputs() -> frozenset[str]:
    prefix = (
        BINARY_ROOT + "/apps/trading-core/generated/"
        "trading_core/Strategy/GeneratedStrategyRegistry")
    return frozenset({prefix + ".hpp", prefix + ".cpp"} | {
        prefix + f"_{name}.cpp" for name in proven_strategy_names()
    })


def registry_sources() -> frozenset[str]:
    return frozenset(
        value for value in registry_outputs() if value.endswith(".cpp"))


@lru_cache(maxsize=1)
def _selection_records():
    """Pin the bounded selection, owner-only discovery and unknown-name refusal."""
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words, scan_commands
    errors = []
    records = scan_commands('reviewed-strategy-selection', r'''set(TRADING_CORE_STRATEGY_SELECTION "all" CACHE STRING
  "Strategy descriptors: all or comma-separated canonical strategy names")
set(TRADING_CORE_SELECTED_STRATEGY_NAMES)
if(NOT TRADING_CORE_STRATEGY_SELECTION STREQUAL "all")
  if(NOT TRADING_CORE_STRATEGY_SELECTION MATCHES "^[a-z0-9_]+(,[a-z0-9_]+)*$")
    message(FATAL_ERROR
      "TRADING_CORE_STRATEGY_SELECTION must be all or a non-empty comma-separated list of canonical strategy names")
  endif()
  string(REPLACE "," ";" TRADING_CORE_SELECTED_STRATEGY_NAMES
    "${TRADING_CORE_STRATEGY_SELECTION}")
  set(TRADING_CORE_UNIQUE_SELECTED_STRATEGY_NAMES "${TRADING_CORE_SELECTED_STRATEGY_NAMES}")
  list(REMOVE_DUPLICATES TRADING_CORE_UNIQUE_SELECTED_STRATEGY_NAMES)
  if(NOT "${TRADING_CORE_SELECTED_STRATEGY_NAMES}" STREQUAL
         "${TRADING_CORE_UNIQUE_SELECTED_STRATEGY_NAMES}")
    message(FATAL_ERROR "TRADING_CORE_STRATEGY_SELECTION contains duplicate strategy names")
  endif()
endif()
file(GLOB TRADING_CORE_ALL_STRATEGY_HEADERS CONFIGURE_DEPENDS
  "${CMAKE_CURRENT_SOURCE_DIR}/src/Strategy/include/strategy/hft-trader/*/Strategy.hpp"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/Strategy/include/strategy/trader/*/Strategy.hpp")
set(TRADING_CORE_STRATEGY_HEADERS)
set(TRADING_CORE_STRATEGY_DEPENDENCY_HEADERS)
set(TRADING_CORE_AVAILABLE_STRATEGY_NAMES)
foreach(strategy_header IN LISTS TRADING_CORE_ALL_STRATEGY_HEADERS)
  get_filename_component(strategy_dir "${strategy_header}" DIRECTORY)
  get_filename_component(strategy_folder "${strategy_dir}" NAME)
  # Use the same canonical descriptor names as the generated provider wrappers.
  string(REGEX REPLACE "([a-z0-9])([A-Z])" "\\1_\\2" strategy_name "${strategy_folder}")
  string(TOLOWER "${strategy_name}" strategy_name)
  list(APPEND TRADING_CORE_AVAILABLE_STRATEGY_NAMES "${strategy_name}")
  if(TRADING_CORE_STRATEGY_SELECTION STREQUAL "all" OR
     strategy_name IN_LIST TRADING_CORE_SELECTED_STRATEGY_NAMES)
    list(APPEND TRADING_CORE_STRATEGY_HEADERS "${strategy_header}")
    file(GLOB_RECURSE strategy_dependency_headers CONFIGURE_DEPENDS
      "${strategy_dir}/*.hpp" "${strategy_dir}/*.ipp")
    list(APPEND TRADING_CORE_STRATEGY_DEPENDENCY_HEADERS ${strategy_dependency_headers})
  endif()
endforeach()
foreach(strategy_name IN LISTS TRADING_CORE_SELECTED_STRATEGY_NAMES)
  if(NOT strategy_name IN_LIST TRADING_CORE_AVAILABLE_STRATEGY_NAMES)
    message(FATAL_ERROR "Unknown TRADING_CORE_STRATEGY_SELECTION strategy: ${strategy_name}")
  endif()
endforeach()''', errors,
        lambda name, body, line, offset: (name, tuple(cmake_list_words(body))))
    if errors:
        raise ValueError('invalid reviewed strategy selection recipe')
    return tuple(records)


def _exact_record_block(commands, records, contexts, expected):
    relative = 'apps/trading-core/CMakeLists.txt'
    matches = [index for index in range(max(0, len(records) - len(expected) + 1))
               if tuple(records[index:index + len(expected)]) == expected]
    if len(matches) != 1:
        return None
    start = matches[0]
    errors = []
    tracker = StructuralTracker(relative, (), errors)
    for offset, (name, tokens) in enumerate(expected):
        index = start + offset
        if contexts[index] != tracker.context():
            return None
        tracker.advance(name, tokens, commands[index].line, index)
    tracker.finish()
    return start if not errors else None


def _registration_records():
    """One semantic owner for the exact ordered registry fold grammar."""
    return (
        ("set", ("TRADING_CORE_REGISTERED_STRATEGY_NAMES",)),
        ("foreach", (
            "strategy_header", "IN", "LISTS",
            "TRADING_CORE_STRATEGY_HEADERS")),
        ("get_filename_component", (
            "strategy_dir", "${strategy_header}", "DIRECTORY")),
        ("get_filename_component", (
            "strategy_folder", "${strategy_dir}", "NAME")),
        ("string", ("REGEX", "REPLACE", "([a-z0-9])([A-Z])",
                    r"\\1_\\2", "strategy_name", "${strategy_folder}")),
        ("string", ("TOLOWER", "${strategy_name}", "strategy_name")),
        ("file", ("READ", "${strategy_header}", "strategy_header_text")),
        ("set", ("strategy_descriptor_text", "${strategy_header_text}")),
        ("if", ("EXISTS", "${strategy_dir}/Descriptor.hpp")),
        ("file", (
            "READ", "${strategy_dir}/Descriptor.hpp",
            "strategy_descriptor_header_text")),
        ("string", (
            "APPEND", "strategy_descriptor_text", r"\n",
            "${strategy_descriptor_header_text}")),
        ("endif", ()),
        ("if", (
            "strategy_descriptor_text", "MATCHES",
            r"${strategy_name}StrategyDescriptor[ \t\r\n]*\\(")),
        ("list", (
            "APPEND", "TRADING_CORE_REGISTERED_STRATEGY_NAMES",
            "${strategy_name}")),
        ("list", (
            "APPEND", "TRADING_CORE_GENERATED_STRATEGY_REGISTRY_SOURCES",
            "${TRADING_CORE_GENERATED_DIR}/trading_core/Strategy/"
            "GeneratedStrategyRegistry_${strategy_name}.cpp")),
        ("elseif", ("NOT", "TRADING_CORE_STRATEGY_SELECTION", "STREQUAL", "all")),
        ("message", ("FATAL_ERROR", "Selected strategy has no canonical descriptor: ${strategy_name}")),
        ("endif", ()),
        ("endforeach", ()),
    )


def validate_registration_predicate(
    commands,
    tokenize,
    errors: list[str],
) -> tuple:
    """Return only the exact parsed fold after discovery and context proof."""
    relative = "apps/trading-core/CMakeLists.txt"
    prior_errors = len(errors)
    contexts = structural_contexts(relative, commands, tokenize, errors)
    records = [
        (command.name, tuple(tokenize(command.body)))
        for command in commands
    ]
    discovery = _selection_records()
    discovery_start = _exact_record_block(commands, records, contexts, discovery)
    if discovery_start is None:
        errors.append(
            relative + ': Strategy.hpp selection/discovery predicate changed '
            'or escaped top-level context')
    expected = _registration_records()
    start = _exact_record_block(commands, records, contexts, expected)
    if start is None:
        errors.append(
            relative + ': parsed strategy registration block changed '
            'or escaped its exact structural context')
    if (len(errors) == prior_errors and discovery_start is not None and
            start is not None and discovery_start + len(discovery) < start):
        proven_indexes = set(range(discovery_start, discovery_start + len(discovery)))
        proven_indexes.update(range(start, start + len(expected)))
        protected = {'TRADING_CORE_STRATEGY_SELECTION', 'TRADING_CORE_SELECTED_STRATEGY_NAMES',
                     'TRADING_CORE_UNIQUE_SELECTED_STRATEGY_NAMES', 'TRADING_CORE_ALL_STRATEGY_HEADERS',
                     'TRADING_CORE_STRATEGY_HEADERS', 'TRADING_CORE_STRATEGY_DEPENDENCY_HEADERS',
                     'TRADING_CORE_AVAILABLE_STRATEGY_NAMES', 'TRADING_CORE_REGISTERED_STRATEGY_NAMES'}
        for index, (name, tokens) in enumerate(records):
            if index in proven_indexes or not tokens:
                continue
            output = (tokens[0] if name in {'set', 'unset'} else
                      tokens[1] if name == 'list' and len(tokens) > 1 else
                      tokens[1] if name == 'file' and len(tokens) > 1 and
                          tokens[0] in {'GLOB', 'GLOB_RECURSE'} else
                      tokens[2] if name == 'file' and len(tokens) > 2 and
                          tokens[0] in {'READ', 'STRINGS', 'SIZE', 'REAL_PATH', 'TIMESTAMP'} else
                      tokens[0] if name == 'get_filename_component' else None)
            if output in protected or (name == 'string' and any(token in protected for token in tokens)):
                errors.append(relative + ': strategy selection/discovery has an unreviewed writer')
        if len(errors) == prior_errors:
            return (tuple(commands[discovery_start:discovery_start + len(discovery)]) +
                    tuple(commands[start:start + len(expected)]))
    if len(errors) == prior_errors:
        errors.append(relative + ': strategy discovery must precede registration')
    return ()


def reviewed_strategy_fold_member(active) -> bool:
    """Recognize a literal scalar recipe in its exact canonical loop arm.

    The caller must also validate the complete contiguous producer through
    validate_registration_predicate before interpreting any profile.
    """
    relative = "apps/trading-core/CMakeLists.txt"
    if (active.relative != relative or active.source_base != Path("apps/trading-core") or
            active.binary_base != active.source_base or not active.structural_context):
        return False
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    frames = active.structural_context
    record = (active.command.name, tuple(cmake_list_words(active.command.body)))
    # Discovery and registration are independently bounded by their exact
    # input lists. Identical scalar transforms do not confer another loop's
    # authority, nor can a registration arm move outside its descriptor guard.
    discovery_loop = first_body('foreach', relative, frames[0].line,
        ('strategy_header', 'IN', 'LISTS', 'TRADING_CORE_ALL_STRATEGY_HEADERS'))
    discovery_guard = ('TRADING_CORE_STRATEGY_SELECTION', 'STREQUAL', 'all', 'OR',
                       'strategy_name', 'IN_LIST', 'TRADING_CORE_SELECTED_STRATEGY_NAMES')
    discovery = _selection_records()
    opener = discovery.index(('foreach', discovery_loop[3]))
    closer = discovery.index(('endforeach', ()), opener)
    guard = discovery.index(('if', discovery_guard), opener)
    for index in range(opener + 1, closer + 1):
        if record != discovery[index]:
            continue
        context = (discovery_loop,)
        if index > guard and index < closer:
            if len(frames) != 2:
                continue
            context += (first_if(relative, frames[1].line, discovery_guard),)
        if exact_context(frames, context):
            return True
    records = _registration_records()
    loop = first_body('foreach', relative, frames[0].line, records[1][1])
    for index, expected in enumerate(records):
        if index < 2 or record != expected:
            continue
        context = (loop,)
        if 9 <= index <= 11 or 13 <= index <= 17:
            if len(frames) != 2:
                continue
            if index <= 11:
                arm = first_if(relative, frames[1].line, records[8][1])
            elif index <= 15:
                arm = first_if(relative, frames[1].line, records[12][1])
            else:
                arm = alternate_if(relative, frames[1].line, records[12][1], records[15][1])
            context += (arm,)
        if exact_context(frames, context):
            return True
    return False


def validate_strategy_tree(commands, tokenize, errors: list[str]) -> None:
    """Prove the single owner and fixed registered strategy set."""
    headers = sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "apps").rglob("Strategy.hpp")
        if path.is_file()
    )
    offenders = [
        path for path in headers
        if not path.startswith("apps/trading-core/src/Strategy/include/strategy/")
    ]
    if offenders:
        errors.append(
            "concrete Strategy.hpp sources exist outside canonical "
            "trading-core owner: " + ", ".join(offenders))
    expected = canonical_strategy_names()
    for description, actual in (
        ("Strategy.hpp directory", actual_strategy_names()),
        ("CMake registered", actual_registered_strategy_names()),
    ):
        if actual != expected:
            errors.append(
                "apps/trading-core/src/Strategy/include/strategy: " + description +
                " strategy set changed; expected " + str(list(expected)) +
                ", found " + str(list(actual)))
    validate_registration_predicate(commands, tokenize, errors)
    validate_strategy_manifest_producer(commands, tokenize, errors)


def validate_strategy_manifest_producer(commands, tokenize, errors: list[str]) -> None:
    relative = "apps/trading-core/CMakeLists.txt"
    expected = (
        ("set", ("TRADING_CORE_STRATEGY_HEADERS_MANIFEST",
                 "${TRADING_CORE_GENERATED_DIR}/trading_core/Strategy/StrategyHeaders.manifest")),
        ("set", ("TRADING_CORE_STRATEGY_HEADERS_MANIFEST_CONTENT", "${TRADING_CORE_STRATEGY_HEADERS_ARG}\\n")),
        ("if", ("EXISTS", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}")),
        ("file", ("READ", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}",
                  "TRADING_CORE_PREVIOUS_STRATEGY_HEADERS_MANIFEST_CONTENT")),
        ("endif", ()),
        ("if", ("NOT", "EXISTS", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}", "OR", "NOT",
                "${TRADING_CORE_PREVIOUS_STRATEGY_HEADERS_MANIFEST_CONTENT}", "STREQUAL",
                "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST_CONTENT}")),
        ("file", ("WRITE", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}",
                  "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST_CONTENT}")),
        ("endif", ()),
    )
    records = [(command.name, tuple(tokenize(command.body))) for command in commands]
    matches = [index for index in range(max(0, len(records) - len(expected) + 1))
               if tuple(records[index:index + len(expected)]) == expected]
    contexts = structural_contexts(relative, commands, tokenize, errors)
    if len(matches) != 1:
        errors.append(f"{relative}: strategy header manifest producer changed or duplicated")
        return
    start = matches[0]
    read = first_if(relative, commands[start + 2].line, expected[2][1])
    write = first_if(relative, commands[start + 5].line, expected[5][1])
    expected_contexts = ((), (), (), (read,), (read,), (), (write,), (write,))
    if not all(exact_context(contexts[start + offset], context)
               for offset, context in enumerate(expected_contexts)):
        errors.append(f"{relative}: strategy header manifest producer escaped its exact context")
