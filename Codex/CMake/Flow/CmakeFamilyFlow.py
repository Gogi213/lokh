"""Fail-closed path and control-flow primitives for bounded CMake modeling."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from CMake.Syntax.CmakeFamilyBindings import (
    expand_foreach_values,
    invalid_binding,
    invalid_formals,
    parse_foreach_binding,
)
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words, words
from CMake.Flow.CmakeFamilyState import (
    UNCERTAIN_BRANCH_ALTERNATIVE,
    argument_overrides,
    expand_variable_tokens,
)


class Truth(Enum):
    FALSE = 0
    UNKNOWN = 1
    TRUE = 2


Decision = str
PathChoice = tuple[Decision, int]
ExecutionPath = tuple[PathChoice, ...]
PathSet = tuple[ExecutionPath, ...]
VariableState = dict[str, tuple[str, ...]]

_REVIEWED_EFFECT_FORMALS = frozenset()

ALL_PATHS: PathSet = ((),)
NO_PATHS: PathSet = ()
MAX_EXECUTION_PATHS = 256
MAX_PATH_CHOICES = 512

_FALSE_CONSTANTS = frozenset({
    "", "0", "FALSE", "IGNORE", "N", "NO", "NOTFOUND", "OFF",
})
_TRUE_CONSTANTS = frozenset({"1", "ON", "Y", "YES", "TRUE"})
_NUMBER = re.compile(
    r"[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?")
_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_EXACT_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REVIEWED_SOURCE_CONDITIONS = frozenset({
    ("NOT", "EXISTS", "${_hft_compressor_toolchain}"),
    ("VETRON_EMXX_EXECUTABLE", "AND", "NOT", "IS_ABSOLUTE", "${VETRON_EMXX_EXECUTABLE}"),
    ("VETRON_EMXX_EXECUTABLE", "AND", "EXISTS", "${VETRON_EMXX_EXECUTABLE}"),
    ("NOT", "VETRON_EMXX_EXECUTABLE", "OR", "NOT", "EXISTS", "${VETRON_EMXX_EXECUTABLE}",
     "OR", "IS_DIRECTORY", "${VETRON_EMXX_EXECUTABLE}"),
    ("DEFINED", "CXET_BUILD_OWNER"),
    ("NOT", "DEFINED", "CXET_BUILD_OWNER"),
    ("CMAKE_SOURCE_DIR", "STREQUAL", "CMAKE_CURRENT_SOURCE_DIR", "OR",
     "NOT", "TARGET", "cxet::read_only_contracts"),
    ("CMAKE_SOURCE_DIR", "STREQUAL", "CMAKE_CURRENT_SOURCE_DIR", "OR",
     "NOT", "CXET_ROOT_SOURCE_GRAPH", "OR", "NOT", "TARGET", "cxet::read_only_contracts"),
    ("TARGET", "trading-core-math-tests"),
    ("CMAKE_C_COMPILER_VERSION", "VERSION_LESS", "23", "OR",
     "CMAKE_CXX_COMPILER_VERSION", "VERSION_LESS", "23"),
    ("TARGET", "cxet_liburing_ep"),
    ("NOT", "TARGET", "cxet::read_only_contracts"),
    ("NOT", "CXET_ROOT_SOURCE_GRAPH", "OR", "NOT", "TARGET",
     "trading_core::algorithm"),
    ("_hftp_finam_metadata_helper_source", "MATCHES",
     "storeFinamArchiveCatalogLastGood"),
    ("NOT", "CMAKE_C_COMPILER_ID", "MATCHES", "Clang", "OR",
     "NOT", "CMAKE_CXX_COMPILER_ID", "MATCHES", "Clang"),
    ("NOT", "CMAKE_CXX_COMPILER_ID", "MATCHES", "Clang"),
    ("CMAKE_CXX_COMPILER_ID", "MATCHES", "GNU|Clang"),
    ("strategy_descriptor_text", "MATCHES",
     r"${strategy_name}StrategyDescriptor[ \t\r\n]*\\("),
    ("NOT", "strategy_descriptor_text", "MATCHES",
     r"${strategy_name}StrategyDescriptor[ \\t\\r\\n]*\\("),
    ("DEFINED", "CXET_PORTABLE_BUILD", "AND", "CXET_PORTABLE_BUILD"),
    ("TARGET", "cxet_replay_core"),
    ("TARGET", "hft_compressor_core"),
    ("NOT", "EXISTS",
     "${CMAKE_SOURCE_DIR}/extra/secp256k1/CMakeLists.txt"),
    ("EXISTS", "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}", "AND",
     "NOT", "IS_DIRECTORY",
     "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}"),
    ("NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
     "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"),
    ("NOT", "TARGET", "liburing::uring"),
    ("NOT", "TARGET", "cxet_crypto"),
    ("NOT", "TARGET", "secp256k1"),
    ("NOT", "EXISTS",
     "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1/CMakeLists.txt"),
    ("TARGET", "secp256k1"),
    ("TARGET", "liburing::uring"),
    ("NOT", "TARGET", "${vetron_required_target}"),
    ("TARGET", "${vetron_forbidden_target}"),
    ("NOT", "TARGET", "${hftp_required_root_target}"),
    ("NOT", "TARGET", "absl::flat_hash_set"),
    ("NOT", "TARGET", "${hftp_required_client_target}"),
    ("EXISTS", "${CMAKE_CURRENT_SOURCE_DIR}/benchmarks/CMakeLists.txt"),
    ("NOT", "TARGET", "cxet_market_ingress_bench_support"),
    ("EXISTS",
     '${CMAKE_CURRENT_SOURCE_DIR}/benchmarks/Fuzz/CMakeLists.txt'),
    ("TARGET", "${hftp_auxiliary_target}"),
    ("NOT", "TARGET", "${cxet_family_required_target}"),
    ("NOT", "TARGET", "${cxet_family_friend_target}"),
    ("NOT", "TARGET", "${trader_required_target}"),
    ("NOT", "TARGET", "${required_target}"),
    ("NOT", "TARGET", "cxet::cxet_lib", "OR", "NOT", "TARGET",
     "trading_core::algorithm", "OR", "NOT", "TARGET",
     "trading_core::execution", "OR", "NOT", "TARGET",
     "trading_core::strategy"),
    ("NOT", "TARGET", "cxet::cxet_lib"),
    ("EXISTS", "${strategy_dir}/Descriptor.hpp"),
    ("EXISTS", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}"),
    ("NOT", "EXISTS", "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST}", "OR",
     "NOT", "${TRADING_CORE_PREVIOUS_STRATEGY_HEADERS_MANIFEST_CONTENT}", "STREQUAL",
     "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST_CONTENT}"),
    ("NOT", "DEFINED", "CXET_LTO"),
    ("NOT", "DEFINED", "CXET_NO_EXCEPTIONS_RTTI"),
    ("NOT", "DEFINED", "CXET_SECP256K1_NATIVE_OPT"),
    ("DEFINED", "CMAKE_C_COMPILER_ID", "AND",
     "CMAKE_C_COMPILER_ID", "MATCHES", "Clang", "AND",
     "DEFINED", "CMAKE_C_COMPILER", "AND", "NOT",
     "CMAKE_C_COMPILER", "STREQUAL", ""),
    ("NOT", "DEFINED", "CXET_ROOT_SOURCE_GRAPH", "OR", "NOT",
     "CXET_ROOT_SOURCE_GRAPH"),
    ("NOT", "DEFINED", "STRATEGY_HEADERS"),
})
_REVIEWED_STRATEGY_NAMES = frozenset({"delivery_sum_signal", "pair_api_probe"})
_SAFE_COMPARISONS = frozenset({"STREQUAL", "EQUAL", "LESS", "GREATER",
                               "LESS_EQUAL", "GREATER_EQUAL"})
_UNSUPPORTED_CONDITION_WORDS = frozenset({
    "COMMAND", "POLICY", "TARGET", "TEST", "DEFINED", "EXISTS",
    "IS_READABLE", "IS_WRITABLE", "IS_EXECUTABLE", "IS_DIRECTORY",
    "IS_SYMLINK", "IS_ABSOLUTE", "IS_NEWER_THAN", "MATCHES", "IN_LIST",
    "STRLESS", "STRGREATER", "STRLESS_EQUAL", "STRGREATER_EQUAL",
    "VERSION_LESS", "VERSION_GREATER", "VERSION_EQUAL",
    "VERSION_LESS_EQUAL", "VERSION_GREATER_EQUAL", "PATH_EQUAL",
})


def _safe_condition_grammar(tokens: tuple[str, ...]) -> bool:
    """Accept only the bounded boolean/scalar grammar the tracer evaluates."""
    index = 0

    def parse_primary() -> bool:
        nonlocal index
        if index >= len(tokens):
            return False
        token = tokens[index]
        if token == "(":
            index += 1
            if not parse_or() or index >= len(tokens) or tokens[index] != ")":
                return False
            index += 1
            return True
        upper = token.upper()
        if upper == "TARGET":
            index += 1
            if index >= len(tokens):
                return False
            name = tokens[index]
            literal = _condition_literal(name)
            if literal is not None:
                name = literal[0]
            if (name.upper() in {"NOT", "AND", "OR", "TARGET"} or
                    not (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:+-]*", name) or
                         _EXACT_REFERENCE.fullmatch(name))):
                return False
            index += 1
            return True
        if (token == ")" or upper in {"NOT", "AND", "OR"} or
                upper in _SAFE_COMPARISONS or
                upper in _UNSUPPORTED_CONDITION_WORDS or
                upper.startswith("IS_") or upper.startswith("VERSION_")):
            return False
        index += 1
        if index < len(tokens) and tokens[index].upper() in _SAFE_COMPARISONS:
            index += 1
            if index >= len(tokens):
                return False
            operand = tokens[index]
            operand_upper = operand.upper()
            if (operand in {"(", ")"} or
                    operand_upper in {"NOT", "AND", "OR"} or
                    operand_upper in _SAFE_COMPARISONS or
                    operand_upper in _UNSUPPORTED_CONDITION_WORDS or
                    operand_upper.startswith("IS_") or
                    operand_upper.startswith("VERSION_")):
                return False
            index += 1
        return True

    def parse_not() -> bool:
        nonlocal index
        if index < len(tokens) and tokens[index].upper() == "NOT":
            index += 1
            return parse_not()
        return parse_primary()

    def parse_and() -> bool:
        nonlocal index
        if not parse_not():
            return False
        while index < len(tokens) and tokens[index].upper() == "AND":
            index += 1
            if not parse_not():
                return False
        return True

    def parse_or() -> bool:
        nonlocal index
        if not parse_and():
            return False
        while index < len(tokens) and tokens[index].upper() == "OR":
            index += 1
            if not parse_and():
                return False
        return True

    return bool(tokens) and parse_or() and index == len(tokens)


def reviewed_evidence_condition(tokens, expanded_tokens=None) -> bool:
    values = tuple(tokens)
    expanded = tuple(expanded_tokens if expanded_tokens is not None else values)
    canonical_values = tuple(
        value[1:-1]
        if len(value) >= 2 and value[0] == value[-1] == '"' else value
        for value in values)
    canonical_expanded = tuple(
        value[1:-1]
        if len(value) >= 2 and value[0] == value[-1] == '"' else value
        for value in expanded)
    if canonical_values in _REVIEWED_SOURCE_CONDITIONS:
        structural = (
            _UNSUPPORTED_CONDITION_WORDS | _SAFE_COMPARISONS |
            {"NOT", "AND", "OR", "(", ")"})
        raw_structure = tuple(
            token.upper() for token in canonical_values
            if (token.upper() in structural or
                token.upper().startswith("IS_") or
                token.upper().startswith("VERSION_")))
        expanded_structure = tuple(
            token.upper() for token in canonical_expanded
            if (token.upper() in structural or
                token.upper().startswith("IS_") or
                token.upper().startswith("VERSION_")))
        return (
            len(values) == len(expanded) and
            raw_structure == expanded_structure
        )
    return (
        _safe_condition_grammar(values) and
        _safe_condition_grammar(expanded)
    )


def _condition_literal(token: str) -> tuple[str, bool] | None:
    """Return quoted/bracket condition data and whether CMake expands it."""
    if len(token) >= 2 and token[0] == token[-1] == '"':
        return token[1:-1], True
    bracket = re.fullmatch(r"\[(=*)\[(.*)\]\1\]", token, re.DOTALL)
    if bracket is not None:
        return bracket.group(2), False
    return None


@dataclass
class ConditionalStateFrame:
    base: VariableState
    branches: list[VariableState]
    has_else: bool = False
    current_viable: bool = True


@dataclass
class LoopStateFrame:
    variable: str
    previous: tuple[str, ...] | None
    base: VariableState
    values: tuple[str, ...] = ()
    zero_possible: bool = False
    current_viable: bool = True
    terminal: bool = False
    continued_states: list[VariableState] | None = None
    completed_boundaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class VariableSnapshots:
    """State plus may/must path evidence for commands reaching live EOF.

    ``loop_overrides`` and ``loop_path_overrides`` are index-aligned concrete
    occurrences.  ``path_alternatives`` is their may-union; ``live_eof_paths``
    is the successful path universe and ``guaranteed_ordinals`` is its
    all-live-path ordinal intersection.
    """

    values: dict[int, VariableState]
    viable_ordinals: frozenset[int]
    loop_overrides: dict[int, tuple[VariableState, ...]]
    path_alternatives: dict[int, PathSet]
    live_eof_paths: dict[str, PathSet]
    guaranteed_ordinals: frozenset[int]
    loop_path_overrides: dict[int, tuple[PathSet, ...]] = field(
        default_factory=dict)
    source_independent_ordinals: frozenset[int] = frozenset()


@dataclass(frozen=True)
class InstantiatedCommand:
    body: object
    evaluation: object
    token_groups: tuple[tuple[str, ...], ...]
    emission_ordinal: int
    path_alternatives: PathSet = ALL_PATHS


@dataclass(frozen=True)
class FunctionModel:
    members: dict[int, tuple[str, str]]
    definitions: dict[tuple[str, str], tuple[str, ...]]
    kinds: dict[tuple[str, str], str]
    global_definitions: dict[str, tuple[str, str]]
    bodies: dict[tuple[str, str], tuple[object, ...]]


def function_model(commands: list, errors: list[str]) -> FunctionModel:
    """Index active callable declarations without executing their bodies."""
    stacks: dict[tuple[str, tuple[str, ...], str], list[str]] = {}
    members: dict[int, tuple[str, str]] = {}
    definitions: dict[tuple[str, str], tuple[str, ...]] = {}
    kinds: dict[tuple[str, str], str] = {}
    global_definitions: dict[str, tuple[str, str]] = {}
    bodies: dict[tuple[str, str], list[object]] = {}
    for active in commands:
        command = active.command
        stack = stacks.setdefault(
            (active.scope, active.directory, active.relative), [])
        command_words = cmake_list_words(command.body)
        if command.name in {"function", "macro"}:
            if not command_words:
                errors.append(
                    f"{active.relative}:{command.line}: empty CMake callable "
                    "declaration")
                continue
            raw_name = command_words[0]
            name = raw_name.lower()
            if invalid_binding(raw_name):
                errors.append(
                    f"{active.relative}:{command.line}: callable name must "
                    f"be one exact literal identifier: {raw_name}")
            invalid_parameters = invalid_formals(command_words[1:])
            if (active.relative, name, tuple(command_words[1:])) in (
                    _REVIEWED_EFFECT_FORMALS):
                invalid_parameters = []
            if invalid_parameters:
                errors.append(
                    f"{active.relative}:{command.line}: callable {name} has "
                    "unresolved/build-effect formal bindings "
                    f"{invalid_parameters}")
            key = (active.scope, name)
            global_previous = global_definitions.get(name)
            if global_previous is not None and global_previous != key:
                errors.append(
                    f"{active.relative}:{command.line}: cross-family CMake "
                    f"callable collision {name}; first owned by "
                    f"{global_previous[0]}")
            if key in definitions:
                errors.append(
                    f"{active.relative}:{command.line}: duplicate "
                    f"active-family CMake callable {name}")
            definitions[key] = tuple(command_words[1:])
            kinds[key] = command.name
            global_definitions.setdefault(name, key)
            stack.append(name)
            continue
        if command.name in {"endfunction", "endmacro"}:
            if stack:
                stack.pop()
            else:
                errors.append(
                    f"{active.relative}:{command.line}: unmatched "
                    f"{command.name}")
            continue
        if stack:
            owner = (active.scope, stack[-1])
            members[active.ordinal] = owner
            bodies.setdefault(owner, []).append(active)
    return FunctionModel(
        members, definitions, kinds, global_definitions,
        {owner: tuple(body) for owner, body in bodies.items()})


def validate_callable_name_microcases(errors: list[str]) -> None:
    if invalid_binding("reviewed_helper"):
        errors.append("callable-name self-check rejected literal baseline")
    for value in ("target\\_sources", "${FN}", "$<IF:1,foo,bar>"):
        if not invalid_binding(value):
            errors.append(
                f"callable-name self-check accepted dynamic/escaped {value}")


def validate_condition_evaluation_microcases(errors: list[str]) -> None:
    """Keep CMP0054 quote provenance visible to the flow evaluator."""
    state = {"SWITCH": ("TRUE",)}

    def expand(raw, _preserve):
        return [
            "TRUE" if value == "${SWITCH}" else value
            for value in raw
        ]

    if evaluate_condition(words("SWITCH"), state, expand) is not Truth.TRUE:
        errors.append("condition self-check rejected unquoted variable lookup")
    for label, body in (
        ("quoted variable name", '"SWITCH"'),
        ("bracket variable name", "[=[SWITCH]=]"),
    ):
        if evaluate_condition(words(body), state, expand) is not Truth.FALSE:
            errors.append(
                f"condition self-check dereferenced {label}")
    if evaluate_condition(
            words('"${SWITCH}"'), state, expand) is not Truth.TRUE:
        errors.append("condition self-check rejected quoted explicit expansion")


def truth_not(value: Truth) -> Truth:
    if value is Truth.TRUE:
        return Truth.FALSE
    if value is Truth.FALSE:
        return Truth.TRUE
    return Truth.UNKNOWN


def truth_and(left: Truth, right: Truth) -> Truth:
    if left is Truth.FALSE or right is Truth.FALSE:
        return Truth.FALSE
    if left is Truth.TRUE and right is Truth.TRUE:
        return Truth.TRUE
    return Truth.UNKNOWN


def truth_or(left: Truth, right: Truth) -> Truth:
    if left is Truth.TRUE or right is Truth.TRUE:
        return Truth.TRUE
    if left is Truth.FALSE and right is Truth.FALSE:
        return Truth.FALSE
    return Truth.UNKNOWN


def _constant_truth(value: str) -> Truth:
    upper = value.upper()
    if upper in _FALSE_CONSTANTS or upper.endswith("-NOTFOUND"):
        return Truth.FALSE
    if upper in _TRUE_CONSTANTS:
        return Truth.TRUE
    if _NUMBER.fullmatch(value):
        try:
            return Truth.FALSE if float(value) == 0.0 else Truth.TRUE
        except ValueError:
            return Truth.UNKNOWN
    return Truth.UNKNOWN


def evaluate_condition(
    tokens: list[str] | tuple[str, ...],
    state: dict[str, tuple[str, ...]],
    expand,
    reviewed_source: list[str] | tuple[str, ...] | None = None,
    *,
    known_targets: dict[str, str] | None = None,
) -> Truth:
    """Evaluate the safe boolean subset; unsupported atoms stay UNKNOWN.

    The supported grammar is constants/numbers, normal-variable truth,
    bounded scalar comparisons, parentheses, NOT, AND and OR.  Filesystem,
    regex, policy and command predicates deliberately remain UNKNOWN,
    so both arms stay feasible instead of consulting the host environment.
    TARGET is TRUE only for an earlier independently proved declaration in
    this configure namespace; an omitted/conditional name remains UNKNOWN
    unless a complete source catalog proves its earlier declarations inactive.
    """

    raw = tuple(tokens)
    if raw == ("NOT", "DEFINED", "CXET_ROOT_SOURCE_GRAPH", "OR", "NOT", "CXET_ROOT_SOURCE_GRAPH"):
        # The source-profile projection binds this normal variable before the
        # owner root is entered. Missing/merged-absent state is not evidence
        # about an ambient cache, and must not manufacture a successful guard.
        if ("CXET_ROOT_SOURCE_GRAPH" not in state or
                UNCERTAIN_BRANCH_ALTERNATIVE in state["CXET_ROOT_SOURCE_GRAPH"]):
            return Truth.UNKNOWN
        return evaluate_condition(("NOT", "CXET_ROOT_SOURCE_GRAPH"), state, expand)
    if raw in {("DEFINED", "CXET_BUILD_OWNER"),
               ("NOT", "DEFINED", "CXET_BUILD_OWNER")}:
        # The actual driver-selected owner is a presence predicate. OFF/empty
        # still means DEFINED; a merged absent branch is not definite evidence.
        if UNCERTAIN_BRANCH_ALTERNATIVE in state.get("CXET_BUILD_OWNER", ()):
            return Truth.UNKNOWN
        defined = "CXET_BUILD_OWNER" in state
        accepted = defined if raw[0] == "DEFINED" else not defined
        return Truth.TRUE if accepted else Truth.FALSE
    canonical_source = tuple(
        value[1:-1]
        if len(value) >= 2 and value[0] == value[-1] == '"' else value
        for value in (reviewed_source or ()))
    index = 0

    def quoted_truth(token: str) -> Truth | None:
        literal = _condition_literal(token)
        if literal is None:
            return None
        value, expands = literal
        values = tuple(expand((value,), True)) if expands else (value,)
        if not values:
            return Truth.FALSE
        truths: set[Truth] = set()
        for item in values:
            if any(marker in item for marker in (
                    "${", "$ENV{", "$CACHE{", "$<", "\x00")):
                truths.add(Truth.UNKNOWN)
                continue
            constant = _constant_truth(item)
            truths.add(
                Truth.FALSE if constant is Truth.UNKNOWN else constant)
        return truths.pop() if len(truths) == 1 else Truth.UNKNOWN

    def atom_truth(token: str, seen: frozenset[str] = frozenset()) -> Truth:
        quoted = quoted_truth(token)
        if quoted is not None:
            return quoted
        constant = _constant_truth(token)
        if constant is not Truth.UNKNOWN:
            return constant
        exact = _EXACT_REFERENCE.fullmatch(token)
        variable = exact.group(1) if exact is not None else (
            token if _VARIABLE.fullmatch(token) and token in state else None)
        if variable is not None:
            if variable in seen:
                return Truth.UNKNOWN
            values = state.get(variable)
            if values is None:
                expanded = tuple(expand((token,), True))
            else:
                expanded = values
            if not expanded:
                return Truth.FALSE
            truths = {
                atom_truth(value, seen | {variable})
                for value in expanded
            }
            return truths.pop() if len(truths) == 1 else Truth.UNKNOWN
        expanded = tuple(expand((token,), True))
        if expanded != (token,):
            if not expanded:
                return Truth.FALSE
            truths = {atom_truth(value, seen) for value in expanded}
            return truths.pop() if len(truths) == 1 else Truth.UNKNOWN
        return Truth.UNKNOWN

    def operand(token: str) -> tuple[str, ...] | None:
        literal = _condition_literal(token)
        if literal is not None:
            value, expands = literal
            expanded = tuple(expand((value,), True)) if expands else (value,)
            if any(
                    "${" in item or "$ENV{" in item or "$CACHE{" in item or
                    "$<" in item or "\x00" in item for item in expanded):
                return None
            return expanded or ("",)
        exact = _EXACT_REFERENCE.fullmatch(token)
        variable = exact.group(1) if exact is not None else (
            token if _VARIABLE.fullmatch(token) and token in state else None)
        values = state.get(variable) if variable is not None else None
        expanded = tuple(expand((token,), True)) if values is None else values
        expanded = expanded or ("",)
        if any(
                "${" in value or "$ENV{" in value or "$CACHE{" in value or
                "$<" in value or "\x00" in value
                for value in expanded):
            return None
        return expanded

    def comparison_truth(left: str, operator: str, right: str) -> Truth:
        left_values = operand(left)
        right_values = operand(right)
        if (left_values is None or right_values is None or
                len(left_values) != 1 or len(right_values) != 1):
            return Truth.UNKNOWN
        a, b = left_values[0], right_values[0]
        if operator == "STREQUAL":
            return Truth.TRUE if a == b else Truth.FALSE
        # The root profile tracer knows the compiler IDs selected by the exact
        # clang/clang++ presets.  Model only the literal Clang regex used by
        # the pinned root rejection guard; every other regex remains unknown.
        if operator == "MATCHES":
            if b == "Clang":
                return Truth.TRUE if "Clang" in a else Truth.FALSE
            if canonical_source == (
                    "strategy_descriptor_text", "MATCHES",
                    r"${strategy_name}StrategyDescriptor[ \t\r\n]*\\("):
                for name in _REVIEWED_STRATEGY_NAMES:
                    if b == (
                            f"{name}StrategyDescriptor"
                            r"[ \t\r\n]*\\("):
                        found = re.search(
                            re.escape(name) +
                            r"StrategyDescriptor[ \t\r\n]*\(", a)
                        return Truth.TRUE if found else Truth.FALSE
            return Truth.UNKNOWN
        if _NUMBER.fullmatch(a) is None or _NUMBER.fullmatch(b) is None:
            return Truth.UNKNOWN
        try:
            numbers = float(a), float(b)
        except ValueError:
            return Truth.UNKNOWN
        comparisons = {
            "EQUAL": numbers[0] == numbers[1],
            "LESS": numbers[0] < numbers[1],
            "GREATER": numbers[0] > numbers[1],
            "LESS_EQUAL": numbers[0] <= numbers[1],
            "GREATER_EQUAL": numbers[0] >= numbers[1],
        }
        return Truth.TRUE if comparisons[operator] else Truth.FALSE

    def parse_primary() -> Truth:
        nonlocal index
        if index >= len(raw):
            return Truth.UNKNOWN
        token = raw[index]
        if token == "(":
            index += 1
            value = parse_or()
            if index >= len(raw) or raw[index] != ")":
                index = len(raw)
                return Truth.UNKNOWN
            index += 1
            return value
        if token == ")":
            return Truth.UNKNOWN
        if token.upper() == "TARGET":
            if index + 1 >= len(raw):
                index = len(raw)
                return Truth.UNKNOWN
            values = operand(raw[index + 1])
            index += 2
            if (values is not None and len(values) == 1 and known_targets is not None and
                    known_targets.get(values[0]) == "SOURCE_PROVED_ABSENT"):
                return Truth.FALSE
            if (values is not None and len(values) == 1 and known_targets is not None and
                    known_targets.get(values[0]) == "PROVED_ABSENT" and
                    canonical_source in {
                        ("NOT", "TARGET", "cxet_crypto"),
                        ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1"),
                        ("NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
                         "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"),
                    }):
                return Truth.FALSE
            if (values is not None and len(values) == 1 and
                    known_targets is not None and
                    known_targets.get(values[0]) not in {
                        None, "AMBIGUOUS", "PROVED_ABSENT", "SOURCE_PROVED_ABSENT"}):
                return Truth.TRUE
            return Truth.UNKNOWN
        if token.upper() == "EXISTS" and index + 1 < len(raw):
            path = raw[index + 1]
            literal = _condition_literal(path)
            path = literal[0] if literal is not None else path
            index += 2
            return (Truth.TRUE if known_targets is not None and
                    known_targets.get("EXISTS:" + path) == "PROVED_PRESENT" else Truth.UNKNOWN)
        if index + 2 < len(raw) and raw[index + 1].upper() in {
                "STREQUAL", "EQUAL", "LESS", "GREATER", "LESS_EQUAL",
                "GREATER_EQUAL", "MATCHES"}:
            operator = raw[index + 1].upper()
            index += 3
            return comparison_truth(token, operator, raw[index - 1])
        index += 1
        return atom_truth(token)

    def parse_not() -> Truth:
        nonlocal index
        if index < len(raw) and raw[index].upper() == "NOT":
            index += 1
            return truth_not(parse_not())
        return parse_primary()

    def parse_and() -> Truth:
        nonlocal index
        value = parse_not()
        while index < len(raw) and raw[index].upper() == "AND":
            index += 1
            value = truth_and(value, parse_not())
        return value

    def parse_or() -> Truth:
        nonlocal index
        value = parse_and()
        while index < len(raw) and raw[index].upper() == "OR":
            index += 1
            value = truth_or(value, parse_and())
        return value

    if not raw:
        return Truth.FALSE
    result = parse_or()
    return result if index == len(raw) else Truth.UNKNOWN


def evaluate_message_fatality(tokens, state: VariableState, expand) -> Truth:
    """Classify exact message() modes that make configure unsuccessful."""
    if not tokens:
        return Truth.FALSE
    values = tuple(expand((tokens[0],), True))
    if not values or any(
            "${" in value or "$ENV{" in value or "$CACHE{" in value or
            "$<" in value or "\x00" in value
            for value in values):
        return Truth.UNKNOWN
    results = {
        Truth.TRUE if value in {"FATAL_ERROR", "SEND_ERROR"} else Truth.FALSE
        for value in values
    }
    return results.pop() if len(results) == 1 else Truth.UNKNOWN


def structural_context_possible(context, initial_values=None, *, known_targets=None) -> bool:
    """Reject only arms proven impossible by constants/exact owner inputs."""
    state = initial_values or {}
    identity = lambda values, preserve: expand_variable_tokens(
        values, state, preserve_empty=preserve)
    for frame in context:
        if frame.kind != "if":
            continue
        remaining = True
        for prior in frame.prior_arms:
            if not remaining:
                break
            truth = evaluate_condition(prior.tokens, state, identity, known_targets=known_targets)
            if truth is Truth.TRUE or prior.kind == "else":
                remaining = False
        if not remaining:
            return False
        if frame.arm.kind != "else" and evaluate_condition(
                frame.arm.tokens, state, identity, known_targets=known_targets) is Truth.FALSE:
            return False
    return True


class PathOverflowError(RuntimeError):
    pass


def _check_path_budget(paths: list[ExecutionPath]) -> None:
    if len(paths) > MAX_EXECUTION_PATHS or any(
            len(path) > MAX_PATH_CHOICES for path in paths):
        raise PathOverflowError(
            "symbolic CMake path budget exceeded "
            f"({MAX_EXECUTION_PATHS} alternatives, "
            f"{MAX_PATH_CHOICES} choices per path)")


def merge_paths(*groups: PathSet) -> PathSet:
    result: list[ExecutionPath] = []
    for group in groups:
        for path in group:
            normalized = tuple(sorted(path))
            if normalized not in result:
                result.append(normalized)
                _check_path_budget(result)
    return tuple(result)


def choose_paths(paths: PathSet, decision: Decision, arm: int) -> PathSet:
    result: list[ExecutionPath] = []
    for path in paths:
        prior = dict(path).get(decision)
        if prior is not None and prior != arm:
            continue
        candidate = path if prior == arm else tuple(
            sorted((*path, (decision, arm))))
        if candidate not in result:
            result.append(candidate)
            _check_path_budget(result)
    return tuple(result)


def path_compatible(left: ExecutionPath, right: ExecutionPath) -> bool:
    right_choices = dict(right)
    return all(
        decision not in right_choices or right_choices[decision] == arm
        for decision, arm in left
    )


def paths_intersect(left: PathSet, right: PathSet) -> bool:
    return any(path_compatible(a, b) for a in left for b in right)


def intersect_paths(left: PathSet, right: PathSet) -> PathSet:
    result: list[ExecutionPath] = []
    for a in left:
        for b in right:
            if not path_compatible(a, b):
                continue
            candidate = tuple(sorted({*a, *b}))
            if candidate not in result:
                result.append(candidate)
                _check_path_budget(result)
    return tuple(result)


def bounded_intersection(
    left: PathSet,
    right: PathSet,
    errors: list[str],
    context: str,
) -> PathSet:
    try:
        return intersect_paths(left, right)
    except PathOverflowError as failure:
        errors.append(f"{context}: {failure}")
        return NO_PATHS


def bounded_merge(
    errors: list[str], context: str, *groups: PathSet
) -> PathSet:
    try:
        return merge_paths(*groups)
    except PathOverflowError as failure:
        errors.append(f"{context}: {failure}")
        return NO_PATHS


def bounded_choice(
    paths: PathSet,
    decision: Decision,
    arm: int,
    errors: list[str],
    context: str,
) -> PathSet:
    try:
        return choose_paths(paths, decision, arm)
    except PathOverflowError as failure:
        errors.append(f"{context}: {failure}")
        return NO_PATHS


def _strip_decision(paths: PathSet, decision: Decision) -> PathSet:
    return tuple(dict.fromkeys(
        tuple(choice for choice in path if choice[0] != decision)
        for path in paths))


def path_implies(path: ExecutionPath, requirement: ExecutionPath) -> bool:
    choices = dict(path)
    return all(choices.get(decision) == arm for decision, arm in requirement)


def paths_cover(*, universe: PathSet, evidence: PathSet) -> bool:
    """Return whether evidence is present on every universe path.

    The direction is intentional: every path whose behavior must be proven is
    in ``universe``; each path in ``evidence`` is a sufficient condition for
    the modeled effect.  Both sets are fail-closed when empty.
    """
    return bool(universe) and bool(evidence) and all(
        any(path_implies(path, requirement) for requirement in evidence)
        for path in universe
    )


@dataclass
class _IfFlow:
    decision: Decision
    base: PathSet
    remaining: PathSet
    current: PathSet
    completed: PathSet = NO_PATHS
    feasible: PathSet = NO_PATHS
    arm: int = 0
    has_else: bool = False
    branched: bool = False
    inherited_decision: bool = False


@dataclass
class _LoopFlow:
    decision: Decision
    feasible: PathSet
    current: PathSet
    zero: PathSet
    continued: PathSet = NO_PATHS


class FlowController:
    """Track feasible paths through nested if/foreach and terminal commands."""

    def __init__(
        self,
        initial: PathSet = ALL_PATHS,
        errors: list[str] | None = None,
        context: str = "active CMake flow",
    ) -> None:
        self._current = initial
        self._blocks: list[_IfFlow | _LoopFlow] = []
        self.returned: PathSet = NO_PATHS
        self.fatal: PathSet = NO_PATHS
        self.errors = errors
        self.context = context

    def _bounded(self, operation, *args) -> PathSet:
        try:
            return operation(*args)
        except PathOverflowError as failure:
            if self.errors is not None:
                self.errors.append(f"{self.context}: {failure}")
            return NO_PATHS

    def current_paths(self) -> PathSet:
        if self._blocks:
            return self._blocks[-1].current
        return self._current

    def _replace_current(self, paths: PathSet) -> None:
        if self._blocks:
            self._blocks[-1].current = paths
        else:
            self._current = paths

    def absorb_child(self, successful: PathSet) -> None:
        self._replace_current(successful)

    def open_if(self, decision: Decision, truth: Truth) -> None:
        base = self.current_paths()
        inherited_decision = any(
            decision in dict(path) for path in base)
        branched = truth is Truth.UNKNOWN or inherited_decision
        current = (
            NO_PATHS if truth is Truth.FALSE else
            self._bounded(choose_paths, base, decision, 0)
            if branched else base)
        remaining = NO_PATHS if truth is Truth.TRUE else base
        self._blocks.append(_IfFlow(
            decision, base, remaining, current, feasible=current,
            branched=branched, inherited_decision=inherited_decision))

    def alternate_if(self, truth: Truth | None) -> None:
        frame = self._blocks[-1]
        if not isinstance(frame, _IfFlow):
            return
        frame.completed = self._bounded(
            merge_paths, frame.completed, frame.current)
        frame.arm += 1
        if truth is None:
            frame.current = (
                self._bounded(choose_paths, frame.remaining,
                              frame.decision, frame.arm)
                if frame.branched else frame.remaining)
            frame.remaining = NO_PATHS
            frame.has_else = True
        else:
            if truth is Truth.UNKNOWN:
                frame.branched = True
            frame.current = (
                NO_PATHS if truth is Truth.FALSE else
                self._bounded(
                    choose_paths, frame.remaining, frame.decision, frame.arm)
                if frame.branched else frame.remaining)
            if truth is Truth.TRUE:
                frame.remaining = NO_PATHS
        frame.feasible = self._bounded(
            merge_paths, frame.feasible, frame.current)

    def implicit_if_paths(self) -> PathSet:
        frame = self._blocks[-1]
        if not isinstance(frame, _IfFlow) or frame.has_else:
            return NO_PATHS
        return (
            self._bounded(choose_paths, frame.remaining,
                          frame.decision, frame.arm + 1)
            if frame.branched else frame.remaining)

    def close_if(self, preserve_decision: bool = False) -> PathSet:
        frame = self._blocks.pop()
        if not isinstance(frame, _IfFlow):
            return self.current_paths()
        implicit = NO_PATHS if frame.has_else else (
            self._bounded(choose_paths, frame.remaining,
                          frame.decision, frame.arm + 1)
            if frame.branched else frame.remaining)
        feasible = self._bounded(merge_paths, frame.feasible, implicit)
        paths = self._bounded(merge_paths,
            frame.completed,
            frame.current,
            implicit,
        )
        if (frame.branched and not frame.inherited_decision and
                not preserve_decision and paths_cover(
                    universe=feasible, evidence=paths)):
            paths = _strip_decision(paths, frame.decision)
        self._replace_current(paths)
        return paths

    def open_loop(
        self,
        decision: Decision,
        has_values: bool,
        zero_possible: bool,
    ) -> None:
        base = self.current_paths()
        if has_values and zero_possible:
            current = self._bounded(choose_paths, base, decision, 0)
            zero = self._bounded(choose_paths, base, decision, 1)
        elif has_values:
            current, zero = base, NO_PATHS
        else:
            current, zero = NO_PATHS, base
        feasible = self._bounded(merge_paths, current, zero)
        self._blocks.append(_LoopFlow(decision, feasible, current, zero))

    def close_loop(self) -> PathSet:
        frame = self._blocks.pop()
        if not isinstance(frame, _LoopFlow):
            return self.current_paths()
        paths = self._bounded(
            merge_paths, frame.current, frame.continued, frame.zero)
        if paths_cover(universe=frame.feasible, evidence=paths):
            paths = _strip_decision(paths, frame.decision)
        self._replace_current(paths)
        return paths

    def continue_current(self) -> bool:
        paths = self.current_paths()
        for block in reversed(self._blocks):
            if isinstance(block, _LoopFlow):
                block.continued = self._bounded(
                    merge_paths, block.continued, paths)
                self._replace_current(NO_PATHS)
                return True
        return False

    def return_current(self) -> PathSet:
        paths = self.current_paths()
        self.returned = self._bounded(merge_paths, self.returned, paths)
        self._replace_current(NO_PATHS)
        return paths

    def fatal_current(self) -> PathSet:
        paths = self.current_paths()
        self.fatal = self._bounded(merge_paths, self.fatal, paths)
        self._replace_current(NO_PATHS)
        return paths

    def successful_paths(self) -> PathSet:
        return self._bounded(merge_paths, self._current, self.returned)

    def normal_paths(self) -> PathSet:
        return self._current

    def add_returned(self, paths: PathSet) -> None:
        self.returned = self._bounded(merge_paths, self.returned, paths)

    def has_open_blocks(self) -> bool:
        return bool(self._blocks)


@dataclass
class _IterationLane:
    controller: FlowController
    binding: VariableState
    identity: tuple[int, ...]
    continued: PathSet = NO_PATHS


@dataclass
class _IterationFrame:
    decision: Decision
    parents: list[_IterationLane]
    children: list[list[_IterationLane]]


class IteratingFlowController:
    """Execute bounded foreach iterations as sequential symbolic lanes."""

    def __init__(
        self,
        initial: PathSet = ALL_PATHS,
        errors: list[str] | None = None,
        context: str = "active iterating CMake flow",
    ) -> None:
        self.errors = errors if errors is not None else []
        self.context = context
        self._base_lanes = [_IterationLane(
            FlowController(initial, self.errors, context), {}, ())]
        self._iterations: list[_IterationFrame] = []

    @classmethod
    def from_lanes(cls, contexts, errors: list[str], context: str):
        contexts = tuple(contexts)
        if len(contexts) > MAX_EXECUTION_PATHS:
            errors.append(
                f"{context}: inherited iteration lane budget exceeded "
                f"({MAX_EXECUTION_PATHS})")
            return cls(NO_PATHS, errors, context)
        result = cls(NO_PATHS, errors, context)
        result._base_lanes = [
            _IterationLane(
                FlowController(paths, errors, context), dict(binding), identity)
            for binding, paths, identity in contexts]
        return result

    def _lanes(self) -> list[_IterationLane]:
        if not self._iterations:
            return self._base_lanes
        return [
            lane for group in self._iterations[-1].children for lane in group]

    def bindings(self) -> tuple[VariableState, ...]:
        return tuple(dict(lane.binding) for lane in self._lanes())

    def lane_contexts(
        self,
    ) -> tuple[tuple[VariableState, PathSet, tuple[int, ...]], ...]:
        return tuple(
            (dict(lane.binding), lane.controller.current_paths(), lane.identity)
            for lane in self._lanes())

    def condition_truths(
        self,
        tokens,
        state: VariableState,
        expand,
        refine=None,
        *,
        known_targets=None,
    ):
        truths: list[Truth] = []
        for binding in self.bindings():
            bound = {**state, **binding}
            if refine is not None:
                bound = refine(bound)
            expand_bound = lambda raw, preserve, current=bound: expand(
                raw, current, preserve)
            expanded = tuple(expand_bound(tokens, True))
            if not reviewed_evidence_condition(tokens, expanded):
                self.errors.append(
                    f"{self.context}: unreviewed/dynamic evidence condition "
                    f"{list(tokens)} -> {list(expanded)}")
                truths.append(Truth.TRUE)
            else:
                truths.append(evaluate_condition(
                    tokens, bound, expand_bound, tokens, known_targets=known_targets))
        return tuple(truths)

    def message_fatalities(self, tokens, state: VariableState, expand):
        return tuple(
            evaluate_message_fatality(
                tokens, {**state, **binding},
                lambda raw, preserve, bound={**state, **binding}: expand(
                    raw, bound, preserve))
            for binding in self.bindings())

    def current_paths(self) -> PathSet:
        return bounded_merge(
            self.errors, f"{self.context} current iteration paths",
            *(lane.controller.current_paths() for lane in self._lanes()))

    def _truths(self, truths) -> tuple[Truth, ...]:
        lanes = self._lanes()
        if isinstance(truths, Truth):
            return (truths,) * len(lanes)
        values = tuple(truths)
        if len(values) != len(lanes):
            self.errors.append(
                f"{self.context}: iteration truth/binding cardinality mismatch")
            return (Truth.UNKNOWN,) * len(lanes)
        return values

    def open_if(self, decision: Decision, truths) -> None:
        for lane, truth in zip(self._lanes(), self._truths(truths)):
            suffix = ".".join(map(str, lane.identity)) or "root"
            lane.controller.open_if(f"{decision}:iteration:{suffix}", truth)

    def alternate_if(self, truths) -> None:
        values = (None,) * len(self._lanes()) if truths is None else self._truths(
            truths)
        for lane, truth in zip(self._lanes(), values):
            lane.controller.alternate_if(truth)

    def implicit_if_paths(self) -> PathSet:
        return bounded_merge(
            self.errors, f"{self.context} implicit iteration paths",
            *(lane.controller.implicit_if_paths() for lane in self._lanes()))

    def close_if(self, preserve_decision: bool = False) -> PathSet:
        for lane in self._lanes():
            lane.controller.close_if(preserve_decision)
        return self.current_paths()

    def open_iterations(
        self,
        decision: Decision,
        bindings: tuple[VariableState, ...],
    ) -> None:
        parents = self._lanes()
        if bindings and (
                len(bindings) > MAX_EXECUTION_PATHS or
                len(parents) > MAX_EXECUTION_PATHS // len(bindings)):
            self.errors.append(
                f"{self.context}: foreach iteration lane budget exceeded "
                f"({MAX_EXECUTION_PATHS})")
            for parent in parents:
                parent.controller.fatal_current()
            bindings = ()
        children: list[list[_IterationLane]] = []
        for parent in parents:
            group: list[_IterationLane] = []
            for index, binding in enumerate(bindings):
                identity = (*parent.identity, index)
                suffix = ".".join(map(str, identity))
                initial = parent.controller.current_paths()
                parent_suffix = (
                    ".".join(map(str, parent.identity)) or "root")
                for prior in range(index):
                    initial = bounded_choice(
                        initial,
                        f"{decision}:boundary:{parent_suffix}:{prior}", 1,
                        self.errors,
                        f"{self.context} foreach reachability")
                controller = FlowController(
                    initial, self.errors,
                    f"{self.context} foreach {decision} iteration {suffix}")
                group.append(_IterationLane(
                    controller, {**parent.binding, **binding}, identity))
            children.append(group)
        self._iterations.append(_IterationFrame(decision, parents, children))

    def close_iterations(self) -> PathSet:
        frame = self._iterations.pop()
        for parent, children in zip(frame.parents, frame.children):
            normal = parent.controller.current_paths()
            returned = NO_PATHS
            parent_suffix = (
                ".".join(map(str, parent.identity)) or "root")
            for index, child in enumerate(children):
                if child.controller.has_open_blocks():
                    self.errors.append(
                        f"{self.context}: iteration reaches EOF with open blocks")
                    normal = NO_PATHS
                    returned = NO_PATHS
                    break
                child_normal = bounded_merge(
                    self.errors, f"{self.context} continued iteration paths",
                    child.controller.normal_paths(), child.continued)
                boundary = (
                    f"{frame.decision}:boundary:{parent_suffix}:{index}")
                returned = bounded_merge(
                    self.errors, f"{self.context} iteration return paths",
                    returned,
                    bounded_intersection(
                        normal, bounded_choice(
                            child.controller.returned, boundary, 0,
                            self.errors, f"{self.context} iteration return"),
                        self.errors,
                        f"{self.context} sequential iteration return"))
                normal = bounded_intersection(
                    normal, bounded_choice(
                        child_normal, boundary, 1, self.errors,
                        f"{self.context} iteration continuation"), self.errors,
                    f"{self.context} sequential iteration success")
            parent.controller.absorb_child(normal)
            parent.controller.add_returned(returned)
        return self.current_paths()

    def continue_current(self) -> bool:
        if not self._iterations:
            return False
        for lane in self._lanes():
            paths = lane.controller.current_paths()
            lane.continued = bounded_merge(
                self.errors, f"{self.context} continue paths",
                lane.continued, paths)
            lane.controller.absorb_child(NO_PATHS)
        return True

    def return_current(self) -> PathSet:
        paths = self.current_paths()
        for lane in self._lanes():
            lane.controller.return_current()
        return paths

    def fatal_current(self) -> PathSet:
        paths = self.current_paths()
        for lane in self._lanes():
            lane.controller.fatal_current()
        return paths

    def terminate_message(self, truths, source: str) -> None:
        for lane, truth in zip(self._lanes(), self._truths(truths)):
            if not lane.controller.current_paths():
                continue
            if truth is Truth.UNKNOWN:
                suffix = ".".join(map(str, lane.identity)) or "root"
                self.errors.append(
                    f"{source}: unresolved/mixed message() severity in "
                    f"iteration {suffix}")
            if truth is not Truth.FALSE:
                lane.controller.fatal_current()

    def absorb_child(self, successful: PathSet) -> None:
        for lane in self._lanes():
            live = bounded_intersection(
                lane.controller.current_paths(), successful, self.errors,
                f"{self.context} child success paths")
            lane.controller.absorb_child(live)

    def absorb_lane(
        self, identity: tuple[int, ...], successful: PathSet
    ) -> None:
        matches = [lane for lane in self._lanes() if lane.identity == identity]
        if len(matches) != 1:
            self.errors.append(
                f"{self.context}: missing/ambiguous iteration lane {identity}")
            return
        lane = matches[0]
        lane.controller.absorb_child(bounded_intersection(
            lane.controller.current_paths(), successful, self.errors,
            f"{self.context} lane child success paths"))

    def successful_paths(self) -> PathSet:
        if self._iterations:
            self.errors.append(
                f"{self.context}: successful_paths with open iterations")
            return NO_PATHS
        return bounded_merge(
            self.errors, f"{self.context} successful base lanes",
            *(lane.controller.successful_paths()
              for lane in self._base_lanes))

    def normal_paths(self) -> PathSet:
        return bounded_merge(
            self.errors, f"{self.context} normal base lanes",
            *(lane.controller.normal_paths() for lane in self._base_lanes))

    @property
    def returned(self) -> PathSet:
        return bounded_merge(
            self.errors, f"{self.context} returned base lanes",
            *(lane.controller.returned for lane in self._base_lanes))

    def add_returned(self, paths: PathSet) -> None:
        for lane in self._base_lanes:
            lane.controller.add_returned(bounded_intersection(
                lane.controller.current_paths(), paths, self.errors,
                f"{self.context} added return paths"))

    def has_open_blocks(self) -> bool:
        return bool(self._iterations) or any(
            lane.controller.has_open_blocks() for lane in self._lanes())


class ExecutionChainManager:
    """Propagate local returns and global fatals across include/subdir scopes."""

    def __init__(self, errors: list[str], on_close) -> None:
        self.errors = errors
        self.on_close = on_close
        self.flows: dict[tuple, IteratingFlowController] = {}
        self.previous: tuple = ()
        self.live_eof: dict[str, PathSet] = {}

    def _finish(self, chain: tuple, keep: int) -> None:
        for depth in range(len(chain), keep, -1):
            key = chain[:depth]
            flow = self.flows.pop(key)
            if flow.has_open_blocks():
                self.errors.append(
                    f"{key[-1][1]}: active control blocks reach scope EOF")
                successful = NO_PATHS
            else:
                successful = flow.successful_paths()
            self.on_close(key, flow)
            parent = key[:-1]
            if parent:
                self.flows[parent].absorb_child(successful)
            else:
                scope = key[0][1]
                self.live_eof[scope] = bounded_merge(
                    self.errors, f"{scope} EOF paths",
                    self.live_eof.get(scope, NO_PATHS), successful)

    def enter(self, chain: tuple) -> IteratingFlowController:
        common = 0
        while (common < len(self.previous) and common < len(chain) and
               self.previous[common] == chain[common]):
            common += 1
        if self.previous:
            self._finish(self.previous, common)
        for depth in range(common + 1, len(chain) + 1):
            key = chain[:depth]
            context = f"{key[-1][1]} active flow"
            self.flows[key] = (
                IteratingFlowController.from_lanes(
                    self.flows[key[:-1]].lane_contexts(),
                    self.errors, context)
                if depth > 1 else
                IteratingFlowController(ALL_PATHS, self.errors, context))
        self.previous = chain
        return self.flows[chain]

    def finish(self) -> None:
        if self.previous:
            self._finish(self.previous, 0)
            self.previous = ()


def trace_callable_success(
    owner,
    commands,
    model,
    initial_paths: PathSet,
    inherited: VariableState,
    arguments: list[str],
    tokenize,
    expand,
    expand_call,
    errors: list[str],
    call_trace: tuple[int, ...],
    stack: tuple = (),
    *,
    known_targets=None,
) -> PathSet:
    """Trace only callable termination so nested FATAL cannot be swallowed."""
    if owner in stack:
        errors.append(
            "active callable flow cycle: " +
            " -> ".join(name for _, name in (*stack, owner)))
        return NO_PATHS
    local = dict(inherited)
    definition = model.definitions.get(owner, ())
    local.update(argument_overrides(definition, arguments))
    bodies = model.bodies.get(owner, ())
    flow = IteratingFlowController(
        initial_paths, errors, f"callable termination {owner[1]}")
    state_frames: list[tuple[VariableState, list[VariableState]]] = []
    loop_depth = 0
    next_stack = (*stack, owner)

    def merge_locals(states: list[VariableState]) -> VariableState:
        if not states:
            return dict(local)
        result: VariableState = {}
        for variable in dict.fromkeys(
                name for state in states for name in state):
            variants = [state.get(variable) for state in states]
            values: list[str] = []
            for variant in variants:
                for value in variant or (f"${{{variable}}}",):
                    if value not in values:
                        values.append(value)
            if len(set(variants)) > 1:
                values.append(UNCERTAIN_BRANCH_ALTERNATIVE)
            result[variable] = tuple(values)
        return result

    for member in bodies:
        command = member.command
        raw = (
            words(command.body)
            if command.name in {"if", "elseif"} else
            tokenize(command.body)
        )
        decision = (
            f"call:{owner[0]}:{'/'.join(map(str, call_trace))}:"
            f"{member.ordinal}")
        if command.name == "if":
            flow.open_if(decision, flow.condition_truths(
                raw, local, expand, known_targets=known_targets))
            state_frames.append((dict(local), []))
            continue
        if command.name in {"elseif", "else"} and state_frames:
            base, branches = state_frames[-1]
            if flow.current_paths():
                branches.append(dict(local))
            local = dict(base)
            flow.alternate_if(None if command.name == "else" else
                flow.condition_truths(raw, local, expand, known_targets=known_targets))
            continue
        if command.name == "endif" and state_frames:
            base, branches = state_frames.pop()
            if flow.current_paths():
                branches.append(dict(local))
            if flow.implicit_if_paths():
                branches.append(base)
            flow.close_if()
            local = merge_locals(branches) if branches else base
            continue
        if command.name == "foreach":
            binding, binding_error = parse_foreach_binding(list(raw))
            if binding is None:
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    f"uses {binding_error or 'unsupported foreach grammar'}")
                flow.fatal_current()
                flow.open_iterations(decision, ())
                loop_depth += 1
                continue
            values, zero_possible = expand_foreach_values(
                binding, local,
                lambda values, preserve: expand(values, local, preserve))
            uncertain = ((bool(values) and zero_possible) or any(
                "${" in value or "$ENV{" in value or "$CACHE{" in value or
                "$<" in value or "\x00" in value for value in values))
            if uncertain:
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "has non-exact foreach iteration values")
                flow.fatal_current()
                values = ()
            flow.open_iterations(decision, tuple(
                {binding.variable: (value,)} for value in values))
            loop_depth += 1
            continue
        if command.name == "endforeach":
            if loop_depth:
                flow.close_iterations()
                loop_depth -= 1
            continue
        if not flow.current_paths():
            continue
        if command.name == "continue":
            if raw:
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "uses continue() arguments")
                flow.fatal_current()
            elif not flow.continue_current():
                errors.append(
                    f"{member.relative}:{command.line}: continue() outside "
                    f"foreach in callable {owner[1]}")
                flow.fatal_current()
            continue
        if command.name == "return":
            if raw:
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "uses unsupported return propagation")
                flow.fatal_current()
            else:
                flow.return_current()
            continue
        if command.name == "message":
            flow.terminate_message(
                flow.message_fatalities(raw, local, expand),
                f"{member.relative}:{command.line}")
            continue
        if command.name == "set" and raw and _VARIABLE.fullmatch(raw[0]):
            tail = {value.upper() for value in raw[1:]}
            if not tail.intersection({"CACHE", "PARENT_SCOPE", "FORCE"}):
                local[raw[0]] = tuple(expand(raw[1:], local, True))
            continue
        if command.name == "unset" and raw and _VARIABLE.fullmatch(raw[0]):
            local.pop(raw[0], None)
            continue
        nested = model.global_definitions.get(command.name)
        if nested is not None and nested[0] == owner[0]:
            for binding, paths, identity in flow.lane_contexts():
                if not paths:
                    continue
                bound = {**local, **binding}
                nested_arguments = expand_call(member, bound)
                successful = trace_callable_success(
                    nested, commands, model, paths, bound,
                    nested_arguments, tokenize, expand, expand_call, errors,
                    (*call_trace, member.ordinal, len(identity), *identity),
                    next_stack, known_targets=known_targets)
                flow.absorb_lane(identity, successful)
    if flow.has_open_blocks():
        errors.append(f"callable {owner[1]} reaches EOF with open flow blocks")
        return NO_PATHS
    return flow.successful_paths()
