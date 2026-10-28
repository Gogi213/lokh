"""Positive active-command dialect for the repository root CMake graph."""

from __future__ import annotations

from dataclasses import dataclass
import re
import posixpath

from CMake.Policy.CmakeFamilyCommandPolicy import safe_compile_option
from CMake.Policy.CmakeFamilyConditionPolicy import exact_command_contexts
from CMake.Syntax.CmakeFamilyLexer import scan_commands, words as cmake_words
from CMake.Flow.CmakeFamilyFlow import (
    ALL_PATHS,
    NO_PATHS,
    FlowController,
    PathSet,
    Truth,
    evaluate_condition,
    paths_cover,
    reviewed_evidence_condition,
)
from CMake.Policy.CmakeFamilyLinkOptions import safe_link_option
from CMake.Policy.CmakeFamilyIncludeDirectories import target_include_items
from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity
from CMake.Policy.CmakeFamilySetPolicy import parse_variable_signature
from CMake.Root.CmakeFamilyRootTargets import validate_root_target_inventory
from CMake.Policy.CmakeFamilyVendorPolicy import approved_root_vendor_target_mutation
from CMake.Flow.CmakeFamilyState import (
    SYNTHETIC_BINARY_ROOT,
    expand_variable_tokens,
    expand_callable_arguments,
)


_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_STRUCTURAL = frozenset({
    "else", "elseif", "endfunction", "endforeach", "endif", "foreach",
    "function", "if",
})
_STATE = frozenset({"list", "option", "set", "string", "unset"})
_TARGET = frozenset({
    "add_dependencies", "add_executable", "add_library",
    "set_target_properties", "target_compile_definitions",
    "target_compile_features", "target_compile_options",
    "target_include_directories", "target_link_libraries",
    "target_link_options",
})
_EXPLICIT = frozenset({
    "add_compile_options", "add_link_options", "add_custom_target", "add_subdirectory",
    "add_test", "cmake_minimum_required",
    "cxet_add_abseil_subdirectory", "enable_testing",
    "execute_process", "file", "find_package", "include",
    "message", "pkg_check_modules", "project", "set_property",
})
_APPROVED_SUBDIRECTORIES = frozenset({
    "extra/abseil-cpp", "extra/secp256k1", "src/src",
    "src/replay", "src/tests", "src/benchmarks/MarketIngress",
    "src/benchmarks/AbseilRegistry",
    "src/tests/Family", "apps/hft-parser", "apps/trading-core",
    "apps/hft-compressor",
    "apps/hft-recorder/src/Contracts",
    "apps/hft-backtest", "apps/trader", "apps/vetron", "apps/hft-recorder",
    "tools/Checks/tests/prepared_orders", "tools/Diagnostic",
    "apps/diagnostic",
})
_OPTIONAL_ROOT_EDGES = {
    "tools/Diagnostic": (
        ("if", ("CXET_SELECTION_ALL", "OR", "CXET_EXCHANGE_FINAM")),
    ),
    "apps/diagnostic": (
        ("elseif", ("CXET_FAMILY_SOURCE_GRAPH",)),
        ("if", ("CXET_FAMILY_PROFILE", "STREQUAL", '"full"')),
    ),
    "apps/hft-compressor": (
        ("elseif", ("CXET_FAMILY_SOURCE_GRAPH",)),
        ("if", ("CXET_FAMILY_PROFILE", "STREQUAL", '"full"')),
    ),
    "apps/hft-recorder/src/Contracts": (
        ("elseif", ("CXET_FAMILY_SOURCE_GRAPH",)),
        ("if", ("CXET_FAMILY_PROFILE", "STREQUAL", '"full"')),
    ),
    "apps/hft-backtest": (
        ("elseif", ("CXET_FAMILY_SOURCE_GRAPH",)),
        ("if", ("CXET_FAMILY_PROFILE", "STREQUAL", '"full"')),
    ),
    "src/benchmarks/AbseilRegistry": (
        ("if", ("CXET_ENABLE_ABSEIL_REGISTRY_BENCH",)),
    ),
    "src/benchmarks/FamilyStrategyCycle": (
        ("elseif", ("CXET_FAMILY_SOURCE_GRAPH",)),
        ("if", ("CXET_ENABLE_FAMILY_STRATEGY_BENCH",)),
    ),
    "tools/exchange_api_probe": (
        ("if", ("CXET_EXCHANGE_FEED_RACE_BUILD",)),
    ),
}
_ROOT_TESTS = {
    "cxet_sort_contract": ("cxet_sort_contract_tests",),
    "cxet_ranking_cache_contract": ("cxet_ranking_cache_contract_tests",),
    "cxet_sort_benchmark_contract": (
        "cxet_sort_benchmark_contract_tests",
        "$<TARGET_FILE:cxet_sort_memory_bench>",
    ),
    "cxet_sort_memory_tracker_contract": (
        "cxet_sort_memory_tracker_contract_tests",),
}
_SIGNATURE_WORDS = frozenset({
    "BOOL", "CACHE", "FILEPATH", "FORCE", "INTERNAL", "PARENT_SCOPE",
    "PATH", "STRING",
})

_ROOT_INCLUDE_PATHS = frozenset({
    "src/benchmarks/Sort",
    "src/benchmarks/MarketIngressRps",
    "src/benchmarks/PrimitivesParse",
    "src/java/include",
})
_ROOT_COMPILE_DEFINITION_FORMS = frozenset({
    (
        "cxet_sort_bench", "PRIVATE",
        'CXET_SORT_BUILD_PROFILE="${CMAKE_CXX_COMPILER_ID}-'
        '${CMAKE_CXX_COMPILER_VERSION},build_type=${CMAKE_BUILD_TYPE},'
        'portable=${CXET_PORTABLE_BUILD},hft_magic=${CXET_ENABLE_HFT_MAGIC}"',
    ),
    (
        "cxet_primitives_parse_bench", "PRIVATE",
        'CXET_BENCH_SOURCE_ID="${_CXET_PRIMITIVES_PARSE_SOURCE_ID}"',
        'CXET_BENCH_BUILD_PROFILE_ID="'
        '${_CXET_PRIMITIVES_PARSE_BUILD_PROFILE_ID}"',
        'CXET_BENCH_CMAKE_CACHE_PATH="${CMAKE_BINARY_DIR}/CMakeCache.txt"',
    ),
})

_ROOT_FOREACH = (
    "_CXET_PRIMITIVES_PARSE_UNTRACKED_FILE", "IN", "LISTS",
    "_CXET_PRIMITIVES_PARSE_UNTRACKED_FILES",
)
_ROOT_FOREACH_IF = (
    "EXISTS", "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}", "AND",
    "NOT", "IS_DIRECTORY", "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}",
)
_ROOT_EXISTS_CONDITIONS = frozenset({
    ("NOT", "EXISTS",
     "${CMAKE_SOURCE_DIR}/extra/secp256k1/CMakeLists.txt"),
    _ROOT_FOREACH_IF,
})
_ROOT_CLANG24_VERSION_CONDITION = (
    "CMAKE_C_COMPILER_VERSION", "VERSION_LESS", "24", "OR",
    "CMAKE_CXX_COMPILER_VERSION", "VERSION_LESS", "24",
)
_PINNED_TOOLCHAIN_INCLUDE = (
    "${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake",
)
_EXCHANGE_SELECTION_INCLUDE = (
    "${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake",
)
_PINNED_TOOLCHAIN_MARKER = "__CXET_REVIEWED_PINNED_TOOLCHAIN__"
_BENCHHELLO_GUARD = ("if", ("CXET_BENCHHELLO_ONLY",))
_ABSEIL_FUNCTION = ("function", ("cxet_add_abseil_subdirectory",))


# These two cold, top-level blocks are indivisible exceptions. Pin commands,
# arguments (including quote provenance), order and structural context; do not
# extend the general variable, path, foreach or filesystem dialect for deploy.
_DIAGNOSTIC_DEPLOY_BLOCKS = (
    """if(CXET_DIAGNOSTIC_DEPLOY)
  if(NOT CXET_BUILD_OWNER STREQUAL "diagnostic" OR
     NOT CXET_TOOLCHAIN_PROFILE STREQUAL "pinned" OR
     NOT CXET_FAMILY_PROFILE STREQUAL "essential" OR
     NOT CMAKE_BUILD_TYPE STREQUAL "Release" OR NOT CXET_PORTABLE_BUILD OR
     CXET_FULL_BUILD OR CXET_FAMILY_SOURCE_GRAPH OR CXET_BUILD_REPLAY OR
     CXET_LOCAL_TESTS OR CXET_LOCAL_BENCHMARKS OR
     CXET_ENABLE_PREPARED_ORDER_CHECKS OR
     CXET_MACHINE_SAFETY_AUDIT OR CXET_SAFETY_BUILD OR
     NOT CXET_SANITIZER_PROFILE STREQUAL "none" OR
     NOT CXET_CLANG24_LIFETIME_PROFILE STREQUAL "off" OR
     CXET_ENABLE_HFT_MAGIC OR CXET_DISABLE_HFT_MAGIC OR
     NOT CXET_HOT_FEATURE_PROFILE STREQUAL "none" OR CXET_SECP256K1_NATIVE_OPT)
    message(FATAL_ERROR "Diagnostic deployment requires the pinned essential portable Release product, without tests, benchmarks, hot features or extended build modes")
  endif()
  foreach(_cxet_deploy_hot_feature IN ITEMS
      CXET_HFT_SIMD_IDENTITY_TAGS CXET_HFT_PMADD_DIGITS CXET_HFT_PCLMUL_JSON
      CXET_HFT_SHUFFLE_CLASSIFY CXET_HFT_RECIPROCAL_DIVISION
      CXET_HFT_IDENTITY_HASH_SPECIALIZED CXET_HFT_IDENTITY_HASH_XXH3
      CXET_ENABLE_NAPI_BUSY_POLL)
    if(${_cxet_deploy_hot_feature})
      message(FATAL_ERROR "Diagnostic deployment forbids hot feature ${_cxet_deploy_hot_feature}")
    endif()
  endforeach()
  unset(_cxet_deploy_hot_feature)
endif()
""",
    """file(REAL_PATH "${CMAKE_BINARY_DIR}" _cxet_deploy_binary)
set(_cxet_deploy_root "${CMAKE_SOURCE_DIR}/build/deploy/diagnostic")
cmake_path(IS_PREFIX _cxet_deploy_root "${_cxet_deploy_binary}" NORMALIZE _cxet_in_deploy_tree)
if(CXET_DIAGNOSTIC_DEPLOY)
  set(_cxet_deploy_lto off)
  if(CXET_LTO)
    set(_cxet_deploy_lto full)
  endif()
  set(_cxet_expected_deploy_binary "${_cxet_deploy_root}/${_cxet_deploy_lto}")
  if(NOT CXET_EXCHANGE_PROFILE STREQUAL "all")
    string(APPEND _cxet_expected_deploy_binary "/exchanges/${CXET_EXCHANGE_PROFILE}")
  endif()
  if(NOT _cxet_in_deploy_tree OR NOT _cxet_deploy_binary STREQUAL _cxet_expected_deploy_binary)
    message(FATAL_ERROR "Diagnostic deployment requires its exact isolated build/deploy/diagnostic/{off,full} exchange profile directory")
  endif()
elseif(_cxet_in_deploy_tree)
  message(FATAL_ERROR "The Diagnostic deployment namespace requires CXET_DIAGNOSTIC_DEPLOY=ON")
endif()
unset(_cxet_deploy_binary)
unset(_cxet_deploy_root)
unset(_cxet_in_deploy_tree)
unset(_cxet_deploy_lto)
unset(_cxet_expected_deploy_binary)
""",
)


def _reviewed_deploy_offsets(commands, tokenize, errors: list[str]) -> frozenset[int]:
    scopes = dict((command.offset, scope)
                  for command, scope in exact_command_contexts(commands))

    def signature(command):
        return command.name, tuple(tokenize(command.body))

    reviewed: set[int] = set()
    actual = [signature(command) for command in commands]
    for block in _DIAGNOSTIC_DEPLOY_BLOCKS:
        expected_commands = scan_commands(
            "<reviewed-diagnostic-deploy>", block, errors, _RootMicroCommand)
        expected = [signature(command) for command in expected_commands]
        starts = [index for index, value in enumerate(actual)
                  if value == expected[0] and
                  actual[index:index + len(expected)] == expected and
                  scopes.get(commands[index].offset) == ()]
        if len(starts) != 1:
            errors.append(
                "CMakeLists.txt: exact isolated Diagnostic deployment block changed")
            continue
        reviewed.update(command.offset for command in
                        commands[starts[0]:starts[0] + len(expected)])
    return frozenset(reviewed)


def _optional_root_edge(directory: str, tokens: list[str], scope) -> bool:
    excluded = {
        "apps/hft-compressor", "apps/diagnostic", "tools/Diagnostic",
        "src/benchmarks/AbseilRegistry", "src/benchmarks/FamilyStrategyCycle",
        "tools/exchange_api_probe",
    }
    return (
        directory in _OPTIONAL_ROOT_EDGES and
        tokens == ([directory, "EXCLUDE_FROM_ALL"]
                   if directory in excluded else [directory]) and
        scope == _OPTIONAL_ROOT_EDGES[directory]
    )


def _apply_deploy_state(name: str, tokens: list[str], state) -> None:
    """Model only commands already admitted by the complete block inventory."""
    if name == "file":
        # Root profile evidence uses an abstract private binary directory;
        # this is an identity fact, never a real filesystem path probe.
        state["_cxet_deploy_binary"] = state["CMAKE_BINARY_DIR"]
    elif name == "cmake_path":
        prefix = state.get("_cxet_deploy_root", ())
        binary = state.get("_cxet_deploy_binary", ())
        if (len(prefix) == len(binary) == 1 and
                not _opaque(prefix[0]) and not _opaque(binary[0])):
            root = posixpath.normpath(prefix[0])
            path = posixpath.normpath(binary[0])
            state["_cxet_in_deploy_tree"] = (
                "ON" if path == root or path.startswith(root + "/") else "OFF",)
        else:
            state["_cxet_in_deploy_tree"] = ("${_cxet_in_deploy_tree}",)
    elif name == "set":
        state[tokens[0]] = tuple(expand_variable_tokens(
            tokens[1:], state, preserve_empty=True))
    elif name == "unset":
        state.pop(tokens[0], None)
    elif name == "string":
        variable = tokens[1]
        previous = state.get(variable, ("",))
        suffix = expand_variable_tokens(tokens[2:], state, preserve_empty=True)
        state[variable] = tuple(value + "".join(suffix) for value in previous)


def _reviewed_pinned_toolchain_include(tokens: list[str]) -> bool:
    return (tuple(tokens) == _PINNED_TOOLCHAIN_INCLUDE and
            reviewed_file_identity("cmake/CxetToolchain.cmake"))


def _reviewed_exchange_selection_include(tokens: list[str]) -> bool:
    return (tuple(tokens) == _EXCHANGE_SELECTION_INCLUDE and
            reviewed_file_identity("cmake/CxetExchangeSelection.cmake"))


def _reviewed_source_predicates(tokens: list[str]) -> bool:
    if tuple(tokens) in (("DEFINED", "CXET_BUILD_OWNER"),
                         ("NOT", "DEFINED", "CXET_BUILD_OWNER"),
                         ("CXET_FAMILY_SOURCE_GRAPH", "AND", "(NOT", "DEFINED", "CXET_BUILD_OWNER", "OR", "CXET_BUILD_OWNER", "STREQUAL", '"hft-parser")')):
        return True
    if tuple(tokens) == _ROOT_CLANG24_VERSION_CONDITION:
        return True
    if not reviewed_evidence_condition(tokens, tokens):
        return False
    upper = tuple(token.upper() for token in tokens)
    if "TARGET" in upper:
        return False
    if "EXISTS" in upper and tuple(tokens) not in _ROOT_EXISTS_CONDITIONS:
        return False
    return True


def _root_foreach_body(name: str, tokens: list[str]) -> bool:
    """Allow only the reviewed, ownership-neutral primitives hash fold."""
    if name == "set":
        return tokens == [
            "_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH",
            "${CMAKE_SOURCE_DIR}/${_CXET_PRIMITIVES_PARSE_UNTRACKED_FILE}",
        ]
    if name == "file":
        return tokens == [
            "SHA256", "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}",
            "_CXET_PRIMITIVES_PARSE_UNTRACKED_HASH",
        ]
    return name == "string" and tokens == [
        "APPEND", "_CXET_PRIMITIVES_PARSE_SOURCE_STATE",
        "\\n${_CXET_PRIMITIVES_PARSE_UNTRACKED_FILE}:",
        "${_CXET_PRIMITIVES_PARSE_UNTRACKED_HASH}",
    ]


def _root_include_carrier(value: str) -> bool:
    if value in {"${CXET_LIB_INCLUDE_DIR}", "${RDKAFKA_INCLUDE_DIRS}"}:
        return True
    source_prefix = "${CMAKE_SOURCE_DIR}/"
    if value.startswith(source_prefix):
        payload = value[len(source_prefix):]
        if any(marker in payload for marker in _CARRIERS):
            return False
        return (".." not in payload.replace("\\", "/").split("/") and
                posixpath.normpath(payload.replace("\\", "/")) in
                _ROOT_INCLUDE_PATHS)
    if any(marker in value for marker in _CARRIERS):
        return False
    return (".." not in value.replace("\\", "/").split("/") and
            posixpath.normpath(value.replace("\\", "/")) in
            _ROOT_INCLUDE_PATHS)
_VENDOR_TARGETS = {
    "extra/secp256k1": frozenset({
        "secp256k1", "secp256k1_precomputed"}),
    "extra/abseil-cpp": frozenset({"absl_raw_hash_set", "absl_type_traits"}),
}


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _tokens(command, tokenize) -> list[str]:
    return [_unquote(value) for value in tokenize(command.body)]


def _opaque(value: str) -> bool:
    return any(marker in value for marker in _CARRIERS)


def _literal_truth(tokens: list[str]) -> bool | None:
    """Return only an unambiguous one-token CMake truth constant."""
    if len(tokens) != 1:
        return None
    value = tokens[0].upper()
    if value in {
            "", "0", "FALSE", "IGNORE", "N", "NO", "NOTFOUND", "OFF"} or (
            value.endswith("-NOTFOUND")):
        return False
    if value in {"1", "ON", "TRUE", "Y", "YES"}:
        return True
    if re.fullmatch(
            r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:E[+-]?\d+)?", value):
        return float(value) != 0.0
    return None


@dataclass(frozen=True)
class _RootFlow:
    state: dict[str, tuple[str, ...]]
    composed: bool
    vendor_targets: frozenset[str]


@dataclass
class _RootConditional:
    base: _RootFlow
    parent_viable: bool
    remaining_possible: bool
    current_viable: bool
    branches: list[_RootFlow]
    has_else: bool = False


@dataclass(frozen=True)
class RootProfileEvidence:
    """Commands that reach successful EOF paths for one exact cache profile."""

    name: str
    command_paths: dict[int, PathSet]
    live_eof_paths: PathSet

    def covers(self, offset: int) -> bool:
        return paths_cover(
            universe=self.live_eof_paths,
            evidence=self.command_paths.get(offset, NO_PATHS),
        )

    def covers_all(self, offsets) -> bool:
        offsets = tuple(offsets)
        return bool(offsets) and all(self.covers(offset) for offset in offsets)


@dataclass(frozen=True)
class RootDialectEvidence:
    """Generic may-viability plus non-combinable exact-profile evidence."""

    viable_offsets: frozenset[int]
    profiles: dict[str, RootProfileEvidence]

    def profile_covers_all(self, name: str, offsets) -> bool:
        profile = self.profiles.get(name)
        return profile is not None and profile.covers_all(offsets)


@dataclass
class _ProfileConditional:
    base: dict[str, tuple[str, ...]]
    branches: list[dict[str, tuple[str, ...]]]


def _flow_snapshot(state, composed: bool, vendor_targets) -> _RootFlow:
    return _RootFlow(dict(state), composed, frozenset(vendor_targets))


def _merge_flows(flows: list[_RootFlow]) -> _RootFlow:
    """Keep only branch-invariant facts; poison every ambiguous variable."""
    keys = set().union(*(flow.state for flow in flows))
    state: dict[str, tuple[str, ...]] = {}
    missing = object()
    for variable in keys:
        alternatives = [flow.state.get(variable, missing) for flow in flows]
        first = alternatives[0]
        if first is not missing and all(value == first for value in alternatives):
            state[variable] = first
        else:
            state[variable] = (f"${{{variable}}}",)
    vendor_targets = set(flows[0].vendor_targets)
    for flow in flows[1:]:
        vendor_targets.intersection_update(flow.vendor_targets)
    return _RootFlow(
        state,
        all(flow.composed for flow in flows),
        frozenset(vendor_targets),
    )


def _include(tokens: list[str], composed: bool) -> bool:
    if composed and tokens in (["${CMAKE_SOURCE_DIR}/cmake/CxetCompileGraph.cmake"],
                               ["${CMAKE_SOURCE_DIR}/cmake/CxetCompileMetadata.cmake"],
                               ["${CMAKE_SOURCE_DIR}/src/src/cmake/Sources/CxetContractGates.cmake"]):
        return True
    return not composed and (
        _reviewed_pinned_toolchain_include(tokens) or
        _reviewed_exchange_selection_include(tokens))



def _file(tokens: list[str], composed: bool) -> bool:
    if not composed:
        return tokens == [
            "WRITE", "${CMAKE_BINARY_DIR}/.cxet_sanitizer_profile",
            "${CXET_SANITIZER_PROFILE}\\n",
        ]
    return tokens == [
        "SHA256", "${_CXET_PRIMITIVES_PARSE_UNTRACKED_PATH}",
        "_CXET_PRIMITIVES_PARSE_UNTRACKED_HASH",
    ]


def _execute_process(tokens: list[str], composed: bool) -> bool:
    if not composed:
        return False
    exact = ((
        "COMMAND", "git", "rev-parse", "--short=12", "HEAD",
        "WORKING_DIRECTORY", "${CMAKE_SOURCE_DIR}", "OUTPUT_VARIABLE",
        "_CXET_PRIMITIVES_PARSE_SOURCE_ID",
        "OUTPUT_STRIP_TRAILING_WHITESPACE", "ERROR_QUIET",
    ), (
        "COMMAND", "git", "diff", "--binary", "--no-ext-diff", "HEAD",
        "--", ".", "WORKING_DIRECTORY", "${CMAKE_SOURCE_DIR}",
        "OUTPUT_VARIABLE", "_CXET_PRIMITIVES_PARSE_SOURCE_DIFF",
        "ERROR_QUIET",
    ), (
        "COMMAND", "git", "ls-files", "--others", "--exclude-standard",
        "--", ".", "WORKING_DIRECTORY", "${CMAKE_SOURCE_DIR}",
        "OUTPUT_VARIABLE", "_CXET_PRIMITIVES_PARSE_UNTRACKED",
        "OUTPUT_STRIP_TRAILING_WHITESPACE", "ERROR_QUIET",
    ))
    return tuple(tokens) in exact


def _custom_target(tokens: list[str], composed: bool) -> bool:
    scripts = (
        "tools/Codex/CheckNativeBoundaries.sh",
        "tools/Codex/CheckExchangeStructure.sh",
        "tools/Codex/CheckVersionNaming.sh",
    )
    return (composed and all(
        reviewed_file_identity(script) for script in scripts) and
        reviewed_file_identity("tools/Codex/VersionNamingAllowlist.txt") and
        tokens == [
        "cxet_native_boundary_check",
        "COMMAND", "bash",
        "${CMAKE_SOURCE_DIR}/tools/Codex/CheckNativeBoundaries.sh",
        "COMMAND", "bash",
        "${CMAKE_SOURCE_DIR}/tools/Codex/CheckExchangeStructure.sh",
        "COMMAND", "bash",
        "${CMAKE_SOURCE_DIR}/tools/Codex/CheckVersionNaming.sh",
        "WORKING_DIRECTORY", "${CMAKE_SOURCE_DIR}", "COMMENT",
        "Checking native, exchange ownership and version naming boundaries",
        "VERBATIM",
    ])


def _add_test(tokens: list[str], composed: bool) -> bool:
    if not composed or len(tokens) < 4 or tokens[:1] != ["NAME"]:
        return False
    try:
        command_index = tokens.index("COMMAND")
    except ValueError:
        return False
    return (
        command_index == 2 and
        tuple(tokens[command_index + 1:]) == _ROOT_TESTS.get(tokens[1])
    )


def _directory_compile_options(tokens: list[str], composed: bool) -> bool:
    lifetime_profiles = ({
        "$<$<COMPILE_LANGUAGE:CXX>:-Wlifetime-safety-permissive>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wno-error=lifetime-safety-permissive>",
    }, {
        "$<$<COMPILE_LANGUAGE:CXX>:-Wlifetime-safety-permissive>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wlifetime-safety-strict>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wlifetime-safety-validations>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wlifetime-safety-suggestions>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wno-error=lifetime-safety-permissive>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wno-error=lifetime-safety-strict>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wno-error=lifetime-safety-validations>",
        "$<$<COMPILE_LANGUAGE:CXX>:-Wno-error=lifetime-safety-suggestions>",
    })
    return (
        not composed and (tokens in ([
            "$<$<CONFIG:Release>:${_CXET_RELEASE_OPTIMIZATION}>",
            "$<$<CONFIG:Release>:-march=native>",
        ], ["$<$<CONFIG:Release>:${_CXET_RELEASE_OPTIMIZATION}>"]) or set(tokens) in lifetime_profiles)
    )


def _normal_set_destination(variable: str) -> bool:
    return (
        variable.startswith("_CXET_") or
        variable in {
            "ABSL_ENABLE_INSTALL", "ABSL_PROPAGATE_CXX_STD", "ABSL_USE_SYSTEM_INCLUDES",
            "BUILD_SHARED_LIBS", "BUILD_TESTING", "CXET_LIB_INCLUDE_DIR",
            "CXET_ROOT_SOURCE_GRAPH",
            "CMAKE_CXX_VISIBILITY_PRESET",
            "CMAKE_VISIBILITY_INLINES_HIDDEN",
        }
    )


def _approved_unresolved_scalar(variable: str, raw: str) -> bool:
    return (variable, raw) in {
        ("_CXET_BUILD_SHARED_LIBS_SAVED", "${BUILD_SHARED_LIBS}"),
        ("BUILD_SHARED_LIBS", "${_CXET_BUILD_SHARED_LIBS_SAVED}"),
        ("_CXET_PRIMITIVES_PARSE_SOURCE_STATE",
         "${_CXET_PRIMITIVES_PARSE_SOURCE_DIFF}"),
    }


def _root_set(
    name: str,
    tokens: list[str],
    state: dict[str, tuple[str, ...]],
    origin: str,
    errors: list[str],
    raw_tokens: list[str],
) -> bool:
    def expand(raw):
        return expand_callable_arguments(raw, state, errors=errors, context=origin)

    signature = parse_variable_signature(name, raw_tokens, expand, errors, origin)
    if signature is None:
        return False
    variable = signature.variable
    if name == "unset":
        if (variable == "FETCHCONTENT_SOURCE_DIR_GOOGLETEST" and
                tokens in ([variable, "CACHE"], [variable])):
            state.pop(variable, None)
            return True
        if signature.cache_removal or signature.parent_scope:
            return False
        return (
            variable.startswith("_CXET_"))
    for raw in tokens[1:]:
        if re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", raw):
            values = expand([raw])
            if (any(_opaque(value) for value in values) and
                    not _approved_unresolved_scalar(variable, raw) and
                    signature.cache_type is None):
                errors.append(
                    f"{origin}: unresolved token can change root set signature")
                return False
            if any(value.upper() in _SIGNATURE_WORDS for value in values):
                errors.append(f"{origin}: expanded token changes root set signature")
                return False
    exact_normal = {
        "ABSL_ENABLE_INSTALL": ("OFF",),
        "ABSL_PROPAGATE_CXX_STD": ("ON",),
        "ABSL_USE_SYSTEM_INCLUDES": ("ON",),
        "BUILD_SHARED_LIBS": ("OFF", "${_CXET_BUILD_SHARED_LIBS_SAVED}"),
        "BUILD_TESTING": ("OFF",),
        "CMAKE_BUILD_TYPE": ("Release",),
        "CMAKE_CXX_EXTENSIONS": ("OFF",),
        "CMAKE_CXX_STANDARD": ("23",),
        "CMAKE_CXX_STANDARD_REQUIRED": ("ON",),
        "CMAKE_CXX_VISIBILITY_PRESET": ("hidden",),
        "CMAKE_EXPORT_COMPILE_COMMANDS": ("ON",),
        "CMAKE_POSITION_INDEPENDENT_CODE": ("ON", "OFF"),
        "CMAKE_VISIBILITY_INLINES_HIDDEN": ("ON",),
        "CXET_LIB_INCLUDE_DIR": (
            "${CMAKE_SOURCE_DIR}/src/src/Core/include",
            "${CMAKE_SOURCE_DIR}/src/src/Contracts/include",
        ),
        "CXET_ROOT_SOURCE_GRAPH": ("ON",),
        "_CXET_RELEASE_OPTIMIZATION": ("-O3", "-O1", "-O2"),
        "_CXET_RELEASE_FLAGS": ("${_CXET_RELEASE_OPTIMIZATION} -DNDEBUG -ffunction-sections -fdata-sections",),
    }
    if signature.cache_type is None and not (
            _normal_set_destination(variable) or variable in exact_normal):
        errors.append(f"{origin}: unapproved root normal variable {variable}")
        return False
    exact_values = (
        {exact_normal[variable]}
        if variable == "CXET_LIB_INCLUDE_DIR" else
        {(value,) for value in exact_normal.get(variable, ())}
    )
    if (signature.cache_type is None and variable in exact_normal and
            tuple(tokens[1:]) not in exact_values):
        errors.append(f"{origin}: unapproved root value for {variable}")
        return False
    if signature.cache_type is None:
        state[variable] = signature.values
    else:
        state.setdefault(variable, signature.values)
    return True


def _root_list(tokens: list[str], state, origin: str, errors: list[str]) -> bool:
    approved_forms = {
        ("FIND", "_CXET_VALID_SANITIZER_PROFILES",
         "${CXET_SANITIZER_PROFILE}", "_CXET_SANITIZER_PROFILE_INDEX"):
            "_CXET_SANITIZER_PROFILE_INDEX",
        ("FIND", "_CXET_VALID_CLANG24_LIFETIME_PROFILES",
         "${CXET_CLANG24_LIFETIME_PROFILE}",
         "_CXET_CLANG24_LIFETIME_PROFILE_INDEX"):
            "_CXET_CLANG24_LIFETIME_PROFILE_INDEX",
    }
    output = approved_forms.get(tuple(tokens))
    if output is not None:
        state[output] = (f"${{{output}}}",)
        return True
    return False


def _root_string(tokens: list[str], state) -> bool:
    if tokens == ["APPEND", "_CXET_RELEASE_FLAGS", " -march=native -mtune=native"]:
        previous = state.get("_CXET_RELEASE_FLAGS", ("-O3 -DNDEBUG -ffunction-sections -fdata-sections",))
        state["_CXET_RELEASE_FLAGS"] = tuple(
            value + " -march=native -mtune=native" for value in previous)
        return True
    approved = (
        len(tokens) == 5 and tokens[:3] == ["REPLACE", "\\n", ";"] and
        tokens[3:] == ["_CXET_PRIMITIVES_PARSE_UNTRACKED_FILES",
                       "${_CXET_PRIMITIVES_PARSE_UNTRACKED}"]
    ) or (
        len(tokens) == 4 and tokens[:2] == [
            "APPEND", "_CXET_PRIMITIVES_PARSE_SOURCE_STATE"]
    ) or (
        len(tokens) == 3 and tokens[0] == "SHA256" and tokens[1] in {
            "_CXET_PRIMITIVES_PARSE_SOURCE_STATE_HASH",
            "_CXET_PRIMITIVES_PARSE_BUILD_PROFILE_ID",
        }
    ) or tokens == [
        "SUBSTRING", "${_CXET_PRIMITIVES_PARSE_SOURCE_STATE_HASH}", "0",
        "12", "_CXET_PRIMITIVES_PARSE_SOURCE_STATE_SHORT",
    ] or (
        len(tokens) == 3 and tokens[:2] == [
            "APPEND", "_CXET_PRIMITIVES_PARSE_SOURCE_ID"]
    )
    if approved:
        if tokens[0] == "REPLACE":
            destination = tokens[3]
        elif tokens[0] == "SUBSTRING":
            destination = tokens[4]
        else:
            destination = tokens[1]
        state[destination] = (f"${{{destination}}}",)
    return approved


def _pre_core_vendor_target(
    name: str,
    tokens: list[str],
    vendor_targets: set[str],
) -> bool:
    target = tokens[0] if tokens else ""
    return (
        target in vendor_targets and
        approved_root_vendor_target_mutation(name, tokens)
    )


def _target_command(
    name: str,
    tokens: list[str],
    composed: bool,
    vendor_targets: set[str],
) -> bool:
    if not tokens or _opaque(tokens[0]) or "$<" in tokens[0]:
        return False
    whole_carriers = [
        value for value in tokens[1:]
        if re.fullmatch(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", value)]
    approved_carriers = {
            "${CXET_LIB_INCLUDE_DIR}", "${RDKAFKA_INCLUDE_DIRS}",
            "${RDKAFKA_LDFLAGS}",
    }
    if name == "set_target_properties":
        approved_carriers.add("${CMAKE_BINARY_DIR}")
    if any(value not in approved_carriers for value in whole_carriers):
        return False
    if not composed:
        return _pre_core_vendor_target(name, tokens, vendor_targets)
    if name in {"add_executable", "add_library"}:
        controls = {"EXCLUDE_FROM_ALL", "MODULE", "OBJECT", "SHARED", "STATIC"}
        sources = [value for value in tokens[1:] if value.upper() not in controls]
        return (
            composed and bool(sources) and
            all(not _opaque(value) and "$<" not in value and
                not value.startswith("/") and ".." not in value.split("/") and
                value.startswith("src/") for value in sources)
        )
    if name == "target_include_directories":
        values, failure = target_include_items(tokens)
        return composed and failure is None and bool(values) and all(
            _root_include_carrier(value) for value in values)
    if name == "target_link_libraries":
        values = [value for value in tokens[1:] if value.upper() not in {
            "INTERFACE", "PRIVATE", "PUBLIC"}]
        return composed and bool(values) and all(
            not _opaque(value) or value == "${RDKAFKA_LDFLAGS}"
            for value in values)
    if name == "add_dependencies":
        return composed and len(tokens) > 1 and all(
            not _opaque(value) and "$<" not in value for value in tokens[1:])
    if name == "target_compile_features":
        return len(tokens) == 3 and tokens[1].upper() in {
            "PRIVATE", "PUBLIC", "INTERFACE"} and tokens[2] == "cxx_std_23"
    if name == "target_compile_definitions":
        return tuple(tokens) in _ROOT_COMPILE_DEFINITION_FORMS
    if name == "target_compile_options":
        values = [value for value in tokens[1:] if value.upper() not in {
            "BEFORE", "PRIVATE", "PUBLIC", "INTERFACE"}]
        return bool(values) and all(safe_compile_option(value) for value in values)
    if name == "target_link_options":
        values = [value for value in tokens[1:] if value.upper() not in {
            "BEFORE", "PRIVATE", "PUBLIC", "INTERFACE"}]
        return (
            tokens == [
                "cxet_kafka_service", "PRIVATE", "-Wl,-rpath,$ORIGIN"] or
            bool(values) and all(safe_link_option(value) for value in values)
        )
    # Ownership of all remaining target mutations/declarations is checked by
    # validate_root_ownership_effects; the positive dialect still requires a
    # literal target and forbids these commands before root target ownership.
    return composed or name in {"target_compile_options", "target_link_options"}


def _merge_profile_states(
    states: list[dict[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    """Retain only state facts shared by every live branch."""
    if not states:
        return {}
    keys = set().union(*states)
    missing = object()
    result: dict[str, tuple[str, ...]] = {}
    for variable in keys:
        alternatives = [state.get(variable, missing) for state in states]
        first = alternatives[0]
        if first is not missing and all(value == first for value in alternatives):
            result[variable] = first
        else:
            result[variable] = (f"${{{variable}}}",)
    return result


def _trace_root_profile(
    commands,
    tokenize,
    profile_name: str,
    cache: dict[str, str],
    errors: list[str],
    deploy_offsets: frozenset[int] = frozenset(),
) -> RootProfileEvidence:
    """Trace one exact cache profile without borrowing paths from another."""
    # These exact CI profiles target the repository-required Linux/x86-64
    # platform. Compiler identity is inferred only after the exact reviewed
    # pinned include and project() are processed below; no host probe occurs.
    state: dict[str, tuple[str, ...]] = {
        "CMAKE_SYSTEM_NAME": ("Linux",),
        "CMAKE_SYSTEM_PROCESSOR": ("x86_64",),
        "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        "CMAKE_CURRENT_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        "CMAKE_SOURCE_DIR": ("__CXET_REPOSITORY_ROOT__",),
        **{variable: (str(value),) for variable, value in cache.items()},
    }
    profile_cache = set(cache)
    conditionals: list[_ProfileConditional] = []
    flow = FlowController(
        ALL_PATHS, errors,
        f"CMakeLists.txt exact root profile {profile_name}")
    command_paths: dict[int, PathSet] = {}

    def expand(raw, preserve_empty: bool = True):
        return expand_variable_tokens(
            raw, state, preserve_empty=preserve_empty)

    def condition_truth(
        raw_tokens: list[str],
        tokens: list[str],
        origin: str,
    ) -> Truth:
        # The owner is selected and validated by the canonical Python driver.
        # CMake DEFINED must use presence, never its variable's truth value.
        if tuple(tokens) == ("DEFINED", "CXET_BUILD_OWNER"):
            return Truth.TRUE if "CXET_BUILD_OWNER" in state else Truth.FALSE
        if tuple(tokens) == ("NOT", "DEFINED", "CXET_BUILD_OWNER"):
            return Truth.FALSE if "CXET_BUILD_OWNER" in state else Truth.TRUE
        if tuple(tokens) == ("CXET_FAMILY_SOURCE_GRAPH", "AND", "(NOT", "DEFINED", "CXET_BUILD_OWNER", "OR", "CXET_BUILD_OWNER", "STREQUAL", '"hft-parser")'):
            selected = state.get("CXET_FAMILY_SOURCE_GRAPH") == ("ON",) and (
                "CXET_BUILD_OWNER" not in state or state.get("CXET_BUILD_OWNER") == ("hft-parser",))
            return Truth.TRUE if selected else Truth.FALSE
        retired_modes = ("CXET_HFT_TRADER_FULL_BUILD", "OR", "HFT_TRADER_FULL_BUILD",
                         "OR", "HFT_TRADER_HOT_MONO_CLOCK_CANDIDATE")
        if tuple(tokens) == retired_modes:
            false = {"", "OFF", "NO", "FALSE", "N", "0", "IGNORE", "NOTFOUND"}
            enabled = any(state.get(name, ("OFF",))[0].upper() not in false
                          for name in retired_modes if name != "OR")
            return Truth.TRUE if enabled else Truth.FALSE
        expanded = tuple(expand(raw_tokens, True))
        if (tuple(tokens) != _ROOT_CLANG24_VERSION_CONDITION and
                expanded != _ROOT_CLANG24_VERSION_CONDITION and
                not reviewed_evidence_condition(tokens, expanded)):
            errors.append(
                f"{origin} [{profile_name}]: unreviewed/dynamic root "
                f"evidence condition {tokens} -> {list(expanded)}")
            return Truth.TRUE
        return evaluate_condition(raw_tokens, state, expand)

    def apply_state(command_name: str, tokens: list[str], origin: str,
                    raw_tokens: list[str]) -> None:
        if (command_name == "include" and
                _reviewed_exchange_selection_include(tokens)):
            # The bounded source-profile universe selects all exchanges. The
            # reviewed selector enables secp256k1 for Aster/Hyperliquid; this is
            # the only selector output consumed by the root commands below.
            # This fact describes source selection, never native readiness.
            if (state.get("CXET_EXCHANGES", ("all",)) != ("all",) or
                    state.get("CXET_EXCHANGE_PRESET", ("",)) != ("",)):
                errors.append(
                    f"{origin} [{profile_name}]: restricted exchange selection "
                    "is outside the reviewed root profile model")
                return
            state["CXET_HAS_SECP256K1"] = ("1",)
            state["CXET_SELECTION_ALL"] = ("ON",)
            state["CXET_EXCHANGE_FINAM"] = ("ON",)
            state["CXET_EXCHANGE_PROFILE"] = ("all",)
            return
        if command_name == "include" and tokens == ["${CMAKE_SOURCE_DIR}/cmake/CxetCompileGraph.cmake"]:
            # Its complete owner/list/edge inventory is checked independently
            # by check_owner_composition before an overall PASS is possible.
            state["CXET_ROOT_SOURCE_GRAPH"] = ("ON",)
            if state.get("CXET_BUILD_OWNER") == ("hft-parser",) and state.get("CXET_LOCAL_TESTS") == ("OFF",):
                state["CXET_FAMILY_SOURCE_GRAPH"] = ("ON",)
            return
        if (command_name == "include" and
                _reviewed_pinned_toolchain_include(tokens) and
                state.get("CXET_TOOLCHAIN_PROFILE") == ("pinned",)):
            # The reviewed bytes prove selection semantics only. Sentinels are
            # static graph facts and never represent a compiler execution.
            state["CMAKE_C_COMPILER"] = (
                "__CXET_REVIEWED_PINNED_CLANG__",)
            state["CMAKE_CXX_COMPILER"] = (
                "__CXET_REVIEWED_PINNED_CLANGXX__",)
            state[_PINNED_TOOLCHAIN_MARKER] = ("selected",)
            return
        if (command_name == "project" and
                state.get(_PINNED_TOOLCHAIN_MARKER) == ("selected",)):
            state["CMAKE_C_COMPILER_ID"] = ("Clang",)
            state["CMAKE_CXX_COMPILER_ID"] = ("Clang",)
            return
        if command_name in {"set", "unset"}:
            signature = parse_variable_signature(
                command_name, raw_tokens,
                lambda raw: expand_callable_arguments(
                    raw, state, errors=errors, context=origin), errors,
                f"{origin} [{profile_name}]",
            )
            if signature is None:
                return
            if command_name == "unset":
                state.pop(signature.variable, None)
                if signature.cache_removal:
                    profile_cache.discard(signature.variable)
                return
            if signature.cache_type is None:
                state[signature.variable] = signature.values
                return
            if signature.force or signature.variable not in profile_cache:
                state[signature.variable] = signature.values
            profile_cache.add(signature.variable)
            return
        if command_name == "option" and tokens:
            variable = tokens[0]
            if variable not in profile_cache and len(tokens) >= 3:
                state[variable] = (tokens[-1],)
                profile_cache.add(variable)
            return
        if command_name == "list":
            _root_list(tokens, state, f"{origin} [{profile_name}]", errors)
            return
        if command_name == "string":
            _root_string(tokens, state)
            return
        if command_name == "execute_process":
            try:
                output = tokens[tokens.index("OUTPUT_VARIABLE") + 1]
            except (ValueError, IndexError):
                return
            state[output] = (f"${{{output}}}",)

    for command in commands:
        raw_tokens = list(tokenize(command.body))
        tokens = [_unquote(value) for value in raw_tokens]
        origin = f"CMakeLists.txt:{command.line}"
        current = flow.current_paths()
        if current:
            command_paths[command.offset] = current

        if command.name == "if":
            if (command.offset in deploy_offsets and
                    tokens == ["${_cxet_deploy_hot_feature}"]):
                # The root profile universe does not select deployment. Do
                # not interpret an unbound foreach variable as evidence.
                if current:
                    errors.append(
                        f"{origin} [{profile_name}]: deployment hot-feature "
                        "loop is outside the reviewed root profile universe")
                truth = Truth.FALSE
            else:
                truth = condition_truth(raw_tokens, tokens, origin)
            conditionals.append(_ProfileConditional(
                base=dict(state), branches=[]))
            flow.open_if(
                f"{profile_name}:if@{command.offset}", truth)
            continue
        if command.name in {"elseif", "else"}:
            if not conditionals or not flow.has_open_blocks():
                continue
            frame = conditionals[-1]
            if flow.current_paths():
                frame.branches.append(dict(state))
            state.clear()
            state.update(frame.base)
            if command.name == "else":
                flow.alternate_if(None)
            else:
                flow.alternate_if(condition_truth(
                    raw_tokens, tokens, origin))
            continue
        if command.name == "endif":
            if not conditionals or not flow.has_open_blocks():
                continue
            frame = conditionals.pop()
            if flow.current_paths():
                frame.branches.append(dict(state))
            if flow.implicit_if_paths():
                frame.branches.append(dict(frame.base))
            flow.close_if()
            merged = _merge_profile_states(frame.branches)
            state.clear()
            state.update(merged or frame.base)
            continue
        if not current:
            continue
        if (command.offset in deploy_offsets and command.name in {
                "file", "cmake_path", "set", "unset", "string"}):
            _apply_deploy_state(command.name, tokens, state)
        else:
            apply_state(command.name, tokens, origin, raw_tokens)
        if (command.name == "message" and tokens and
                tokens[0] in {"FATAL_ERROR", "SEND_ERROR"}):
            flow.fatal_current()

    if conditionals or flow.has_open_blocks():
        errors.append(
            f"CMakeLists.txt: exact root profile {profile_name} ended with "
            "open conditionals")
        live_eof_paths = NO_PATHS
    else:
        live_eof_paths = flow.normal_paths()
    return RootProfileEvidence(
        profile_name, command_paths, live_eof_paths)


@dataclass(frozen=True)
class _RootMicroCommand:
    name: str
    body: str
    line: int
    offset: int


def validate_root_dialect_microcases(errors: list[str]) -> None:
    deploy_source = "\n".join(_DIAGNOSTIC_DEPLOY_BLOCKS)
    deploy_errors: list[str] = []
    deploy_commands = scan_commands(
        "<deploy-microcase>", deploy_source, deploy_errors, _RootMicroCommand)
    deploy_offsets = _reviewed_deploy_offsets(
        deploy_commands, cmake_words, deploy_errors)
    if deploy_errors or len(deploy_offsets) != len(deploy_commands):
        errors.append("root dialect self-check rejected exact deployment blocks")
    for label, source in (
        ("portable guard", deploy_source.replace("OR NOT CXET_PORTABLE_BUILD", "")),
        ("hot-feature inventory", deploy_source.replace(" CXET_HFT_PMADD_DIGITS", "")),
        ("namespace", deploy_source.replace("/build/deploy/diagnostic", "/build")),
        ("path guard", deploy_source.replace(
            "NOT _cxet_in_deploy_tree OR NOT", "NOT _cxet_in_deploy_tree AND NOT")),
        ("injected effect", deploy_source.replace(
            "  unset(_cxet_deploy_hot_feature)",
            "  add_subdirectory(apps/trader)\n  unset(_cxet_deploy_hot_feature)")),
        ("relocated blocks", "if(UNREVIEWED)\n" + deploy_source + "endif()\n"),
        ("duplicate blocks", deploy_source + deploy_source),
    ):
        mutation_errors: list[str] = []
        commands = scan_commands(
            "<deploy-mutation>", source, mutation_errors, _RootMicroCommand)
        _reviewed_deploy_offsets(commands, cmake_words, mutation_errors)
        if not mutation_errors:
            errors.append(
                "root dialect self-check accepted deployment mutation " + label)

    diagnostic = ["tools/Diagnostic", "EXCLUDE_FROM_ALL"]
    diagnostic_scope = _OPTIONAL_ROOT_EDGES[diagnostic[0]]
    if not _optional_root_edge(diagnostic[0], diagnostic, diagnostic_scope):
        errors.append("root dialect self-check rejected exact Diagnostic edge")
    for tokens, scope in (
        (["tools/Diagnostic"], diagnostic_scope),
        (diagnostic, ()),
        (diagnostic, (("if", ("CXET_SELECTION_ALL",)),)),
        (diagnostic, (("if", ("CXET_SELECTION_ALL", "AND", "CXET_EXCHANGE_FINAM")),)),
    ):
        if _optional_root_edge(diagnostic[0], tokens, scope):
            errors.append("root dialect self-check accepted unguarded Diagnostic edge")

    if not _include(list(_PINNED_TOOLCHAIN_INCLUDE), False):
        errors.append(
            "root-profile self-check rejected reviewed pinned toolchain "
            "include")
    for tokens in (
        ["${CMAKE_SOURCE_DIR}/cmake/Other.cmake"],
        ["${CMAKE_SOURCE_DIR}/${TOOLCHAIN_MODULE}"],
        ["cmake/CxetToolchain.cmake"],
    ):
        if _include(tokens, False):
            errors.append(
                "root-profile self-check accepted unreviewed toolchain "
                f"include {tokens}")
    cache = {"CMAKE_EXPORT_COMPILE_COMMANDS": "ON"}
    quoted = (
        _RootMicroCommand(
            "if", '"CMAKE_EXPORT_COMPILE_COMMANDS"', 1, 1),
        _RootMicroCommand("else", "", 2, 2),
        _RootMicroCommand("message", "FATAL_ERROR late", 3, 3),
        _RootMicroCommand("endif", "", 4, 4),
    )
    quoted_evidence = _trace_root_profile(
        quoted, cmake_words, "quoted-condition", cache, errors)
    if quoted_evidence.live_eof_paths:
        errors.append(
            "root-profile self-check quoted variable atom manufactured a "
            "successful EOF path")

    lowercase = (_RootMicroCommand(
        "message", "fatal_error not-terminal", 1, 1),)
    lowercase_evidence = _trace_root_profile(
        lowercase, cmake_words, "lowercase-message", {}, errors)
    if not lowercase_evidence.live_eof_paths:
        errors.append(
            "root-profile self-check treated lowercase fatal_error as "
            "terminal")

    fatal = (_RootMicroCommand(
        "message", "FATAL_ERROR terminal", 1, 1),)
    if _trace_root_profile(
            fatal, cmake_words, "exact-fatal", {}, errors).live_eof_paths:
        errors.append(
            "root-profile self-check retained EOF after exact FATAL_ERROR")

    pinned_compiler_guard = (
        _RootMicroCommand(
            "include",
            '"${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake"', 1, 1),
        _RootMicroCommand(
            "project", "CXET LANGUAGES C CXX ASM", 2, 2),
        _RootMicroCommand(
            "if", 'NOT CMAKE_C_COMPILER_ID MATCHES "Clang" OR NOT '
            'CMAKE_CXX_COMPILER_ID MATCHES "Clang"', 3, 3),
        _RootMicroCommand("message", "FATAL_ERROR clang-only", 4, 4),
        _RootMicroCommand("endif", "", 5, 5),
    )
    if not _trace_root_profile(
            pinned_compiler_guard, cmake_words, "pinned-compiler",
            {"CXET_TOOLCHAIN_PROFILE": "pinned"}, errors).live_eof_paths:
        errors.append(
            "root-profile self-check did not infer Clang from the reviewed "
            "pinned toolchain include")
    for label, commands, cache in (
        ("missing include", pinned_compiler_guard[1:],
         {"CXET_TOOLCHAIN_PROFILE": "pinned"}),
        ("baseline profile", pinned_compiler_guard,
         {"CXET_TOOLCHAIN_PROFILE": "baseline"}),
        ("unreviewed include", (
            _RootMicroCommand(
                "include", '"${CMAKE_SOURCE_DIR}/cmake/Other.cmake"', 1, 1),
            *pinned_compiler_guard[1:]),
         {"CXET_TOOLCHAIN_PROFILE": "pinned"}),
    ):
        if _trace_root_profile(
                commands, cmake_words, label, cache,
                errors).live_eof_paths:
            errors.append(
                "root-profile self-check inferred Clang from " + label)

    for label, tokens in (
        ("late TARGET fatal", ["TARGET", "cxet_lib"]),
        ("late EXISTS fatal", [
            "EXISTS", "${CMAKE_SOURCE_DIR}/CMakeLists.txt"]),
        ("late COMMAND fatal", ["COMMAND", "message"]),
    ):
        if _reviewed_source_predicates(tokens):
            errors.append(
                f"root-profile self-check accepted unmodeled {label} "
                "predicate")

    dynamic_commands = (
        _RootMicroCommand("set", "_CXET_LATE_PREDICATE TARGET", 1, 1),
        _RootMicroCommand("if", "${_CXET_LATE_PREDICATE} cxet_lib", 2, 2),
        _RootMicroCommand("message", "FATAL_ERROR late", 3, 3),
        _RootMicroCommand("endif", "", 4, 4),
    )
    dynamic_errors: list[str] = []
    dynamic_evidence = _trace_root_profile(
        dynamic_commands, cmake_words, "dynamic-predicate", {},
        dynamic_errors)
    if not dynamic_errors or dynamic_evidence.live_eof_paths:
        errors.append(
            "root-profile self-check accepted variable-generated TARGET "
            "with successful EOF")

    matches_commands = (
        _RootMicroCommand("if", '"x" MATCHES "^x$"', 1, 1),
        _RootMicroCommand("message", "FATAL_ERROR late", 2, 2),
        _RootMicroCommand("endif", "", 3, 3),
    )
    matches_errors: list[str] = []
    matches_evidence = _trace_root_profile(
        matches_commands, cmake_words, "unreviewed-matches", {},
        matches_errors)
    if not matches_errors or matches_evidence.live_eof_paths:
        errors.append(
            "root-profile self-check accepted unreviewed late MATCHES fatal "
            "with successful EOF")

    platform_guards = (
        _RootMicroCommand("if", 'NOT CMAKE_SYSTEM_NAME STREQUAL "Linux"', 1, 1),
        _RootMicroCommand("message", "FATAL_ERROR platform", 2, 2),
        _RootMicroCommand("endif", "", 3, 3),
        _RootMicroCommand("if", 'NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64"', 4, 4),
        _RootMicroCommand("message", "FATAL_ERROR architecture", 5, 5),
        _RootMicroCommand("endif", "", 6, 6),
    )
    if not _trace_root_profile(
            platform_guards, cmake_words, "linux-x86-ci", {}, errors).live_eof_paths:
        errors.append("root-profile self-check rejected required CI platform")
    for override in ({"CMAKE_SYSTEM_NAME": "Darwin"},
                     {"CMAKE_SYSTEM_PROCESSOR": "aarch64"}):
        if _trace_root_profile(
                platform_guards, cmake_words, "wrong-platform", override,
                errors).live_eof_paths:
            errors.append("root-profile self-check accepted unsupported platform")

    # CACHE documentation is one quoted argument even when it contains lists.
    quoted_body = 'CXET_LTO OFF CACHE BOOL "Build slower; measure separately."'
    quoted_errors: list[str] = []
    if not _root_set(
            "set", [_unquote(value) for value in cmake_words(quoted_body)],
            {}, 'quoted-cache-docs', quoted_errors, cmake_words(quoted_body)) or quoted_errors:
        errors.append('root dialect self-check rejected quoted CACHE docsumentation')
    injection_body = "CXET_LTO OFF ${TAIL}"
    injection_errors: list[str] = []
    if _root_set(
            "set", cmake_words(injection_body),
            {"TAIL": ("CACHE", "BOOL", 'docsumentation')},
            "dynamic-cache-signature", injection_errors, cmake_words(injection_body)):
        errors.append("root dialect self-check accepted dynamic CACHE signature")

    baseline_definition = next(iter(_ROOT_COMPILE_DEFINITION_FORMS))
    if not _target_command(
            "target_compile_definitions", list(baseline_definition),
            True, set()):
        errors.append(
            "root-profile self-check rejected a pinned compile definition")
    for dangerous in ("private=public", "protected=public", "friend=public"):
        if _target_command(
                "target_compile_definitions",
                ["cxet_sort_bench", "PRIVATE", dangerous], True, set()):
            errors.append(
                "root-profile self-check accepted access-rewrite definition "
                f"{dangerous}")


def validate_root_dialect(
    commands,
    tokenize,
    errors: list[str],
    profiles: dict[str, dict[str, str]] | None = None,
) -> RootDialectEvidence:
    """Reject every viable root command outside the reviewed root grammar."""
    bootstrap = [
        (command.line, command.name, tuple(_tokens(command, tokenize)))
        for command in commands
        if (command.name in {"cmake_minimum_required", "project"} or
            (command.name == "include" and
             tuple(_tokens(command, tokenize)) in (
                 _PINNED_TOOLCHAIN_INCLUDE, _EXCHANGE_SELECTION_INCLUDE)))
    ]
    expected_bootstrap = [
        ("cmake_minimum_required", ("VERSION", "3.22")),
        ("include", _PINNED_TOOLCHAIN_INCLUDE),
        ("project", ("CXET", "LANGUAGES", "C", "CXX", "ASM")),
        ("include", _EXCHANGE_SELECTION_INCLUDE),
    ]
    if [(name, tokens) for _, name, tokens in bootstrap] != expected_bootstrap:
        errors.append(
            "CMakeLists.txt: root project/minimum bootstrap inventory changed")
    if [command.name for command in commands[:4]] != [
            "cmake_minimum_required", "include", "project", "include"]:
        errors.append(
            "CMakeLists.txt: root project/minimum bootstrap is not first")
    deploy_offsets = _reviewed_deploy_offsets(commands, tokenize, errors)
    conditionals: list[_RootConditional] = []
    composed = False
    vendor_targets: set[str] = set()
    state: dict[str, tuple[str, ...]] = {
        "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        "CMAKE_CURRENT_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        "CMAKE_SOURCE_DIR": ("__CXET_REPOSITORY_ROOT__",),
    }
    allowed = _STRUCTURAL | _STATE | _TARGET | _EXPLICIT
    viable_commands = []
    directory_terminal = False
    loop_condition_depths: list[int] = []
    foreach_count = 0

    def current_viable() -> bool:
        return (
            not directory_terminal and
            (not conditionals or conditionals[-1].current_viable)
        )

    def restore(flow: _RootFlow) -> None:
        nonlocal composed, vendor_targets
        state.clear()
        state.update(flow.state)
        composed = flow.composed
        vendor_targets = set(flow.vendor_targets)

    scopes = {command.offset: scope
              for command, scope in exact_command_contexts(commands)}
    optimization_producers = [
        (tuple(_tokens(command, tokenize)), scopes.get(command.offset))
        for command in commands if command.name == 'set' and
        _tokens(command, tokenize)[:1] == ['_CXET_RELEASE_OPTIMIZATION']]
    system_scope = (("if", ("CXET_TOOLCHAIN_PROFILE", "STREQUAL", '"system-diagnostic"')),)
    deploy_optimization_scope = (("elseif", ("CXET_DIAGNOSTIC_DEPLOY",)),)
    if optimization_producers != [
            (('_CXET_RELEASE_OPTIMIZATION', '-O3'), ()),
            (('_CXET_RELEASE_OPTIMIZATION', '-O1'), system_scope),
            (('_CXET_RELEASE_OPTIMIZATION', '-O2'), deploy_optimization_scope)]:
        errors.append('CMakeLists.txt: exact pinned/system-diagnostic/deploy optimization producers changed')
    system_restrictions = tuple(cmake_words('''
CXET_FULL_BUILD OR CXET_FAMILY_SOURCE_GRAPH OR CXET_BUILD_REPLAY OR
CXET_LOCAL_BENCHMARKS OR CXET_ENABLE_PREPARED_ORDER_CHECKS OR
CXET_MACHINE_SAFETY_AUDIT OR
NOT CXET_FAMILY_PROFILE STREQUAL "essential" OR
NOT CXET_CLANG24_LIFETIME_PROFILE STREQUAL "off" OR
NOT CXET_SANITIZER_PROFILE STREQUAL "none" OR
NOT CMAKE_BUILD_TYPE STREQUAL "Release"
'''))
    system_refusals = [scopes.get(command.offset) for command in commands
        if command.name == 'message' and _tokens(command, tokenize) == [
            'FATAL_ERROR', 'system-diagnostic permits only isolated Release Diagnostic/dependency tests, without benchmarks, replay or extended family profiles']]
    if system_refusals != [system_scope + (("if", system_restrictions),)]:
        errors.append('CMakeLists.txt: exact system-diagnostic composition restriction changed')
    bench_commands = [
        (command.line, command.name, tuple(_tokens(command, tokenize)),
         scopes.get(command.offset))
        for command in commands
        if scopes.get(command.offset) == (_BENCHHELLO_GUARD,)
    ]
    if bench_commands and bench_commands != [
            (27, "set", ("CXET_PORTABLE_BUILD", "ON", "CACHE", "BOOL",
                         "Portable CPU target", "FORCE"),
             (_BENCHHELLO_GUARD,)),
            (28, "set", ("CMAKE_EXPORT_COMPILE_COMMANDS", "ON"),
             (_BENCHHELLO_GUARD,)),
            (29, "add_subdirectory", ("src/src",),
             (_BENCHHELLO_GUARD,)),
            (30, "add_subdirectory", ("apps/BENCHHELLO",),
             (_BENCHHELLO_GUARD,)),
            (31, "return", (), (_BENCHHELLO_GUARD,)),
    ]:
        errors.append("CMakeLists.txt: exact BENCHHELLO-only branch changed")
    for command in commands:
        tokens = _tokens(command, tokenize)
        origin = f"CMakeLists.txt:{command.line}"
        if command.name == "if":
            if (command.offset not in deploy_offsets and
                    not _reviewed_source_predicates(tokens)):
                errors.append(
                    f"{origin}: unreviewed source-determined root predicate")
            if loop_condition_depths and tuple(tokens) != _ROOT_FOREACH_IF:
                errors.append(
                    f"{origin}: unreviewed conditional inside root foreach")
            parent_viable = current_viable()
            truth = (False if tuple(tokens) == ("CXET_BENCHHELLO_ONLY",)
                     and command.line == 26 and not conditionals
                     else _literal_truth(tokens))
            conditionals.append(_RootConditional(
                base=_flow_snapshot(state, composed, vendor_targets),
                parent_viable=parent_viable,
                remaining_possible=parent_viable and truth is not True,
                current_viable=parent_viable and truth is not False,
                branches=[],
            ))
            continue
        if command.name in {"elseif", "else"}:
            if not conditionals:
                errors.append(f"{origin}: unmatched root {command.name}()")
                continue
            frame = conditionals[-1]
            if loop_condition_depths:
                errors.append(
                    f"{origin}: sibling conditional arm inside root foreach")
            if frame.has_else:
                errors.append(
                    f"{origin}: root {command.name}() follows else()")
                frame.current_viable = False
                continue
            if frame.current_viable:
                frame.branches.append(
                    _flow_snapshot(state, composed, vendor_targets))
            restore(frame.base)
            if command.name == "else":
                frame.current_viable = frame.remaining_possible
                frame.remaining_possible = False
                frame.has_else = True
            else:
                if not _reviewed_source_predicates(tokens):
                    errors.append(
                        f"{origin}: unreviewed source-determined root "
                        "predicate")
                truth = _literal_truth(tokens)
                frame.current_viable = (
                    frame.remaining_possible and truth is not False)
                frame.remaining_possible = (
                    frame.remaining_possible and truth is not True)
            continue
        if command.name == "endif":
            if not conditionals:
                errors.append(f"{origin}: unmatched root endif()")
                continue
            if (loop_condition_depths and
                    len(conditionals) <= loop_condition_depths[-1]):
                errors.append(
                    f"{origin}: root endif() crosses foreach boundary")
            frame = conditionals.pop()
            if frame.current_viable:
                frame.branches.append(
                    _flow_snapshot(state, composed, vendor_targets))
            if frame.remaining_possible:
                frame.branches.append(frame.base)
            if frame.branches:
                restore(_merge_flows(frame.branches))
            else:
                restore(frame.base)
                if frame.parent_viable:
                    if conditionals:
                        conditionals[-1].current_viable = False
                    else:
                        directory_terminal = True
            continue
        if (command.offset in deploy_offsets and
                command.name in {"foreach", "endforeach"}):
            if current_viable():
                viable_commands.append(command)
            continue
        if command.name == "foreach":
            foreach_count += 1
            if loop_condition_depths:
                errors.append(f"{origin}: nested root foreach is unsupported")
            if tuple(tokens) != _ROOT_FOREACH:
                errors.append(f"{origin}: unreviewed root foreach grammar")
            loop_condition_depths.append(len(conditionals))
            if current_viable():
                viable_commands.append(command)
            continue
        if command.name == "endforeach":
            if tokens:
                errors.append(f"{origin}: root endforeach arguments changed")
            if not loop_condition_depths:
                errors.append(f"{origin}: unmatched root endforeach()")
            else:
                condition_depth = loop_condition_depths.pop()
                if len(conditionals) != condition_depth:
                    errors.append(
                        f"{origin}: root foreach closes with an open "
                        "conditional")
            if current_viable():
                viable_commands.append(command)
            continue
        if not current_viable():
            continue
        if loop_condition_depths and not _root_foreach_body(
                command.name, tokens):
            errors.append(
                f"{origin}: ownership/effect command {command.name}() is "
                "forbidden inside root foreach")
            continue
        viable_commands.append(command)
        if (command.offset in deploy_offsets and command.name in {
                "file", "cmake_path", "set", "unset", "string"}):
            _apply_deploy_state(command.name, tokens, state)
            continue
        if command.name not in allowed:
            errors.append(f"{origin}: command {command.name}() is outside the root dialect")
            continue
        approved = True
        if command.name == "cmake_minimum_required":
            approved = tokens == ["VERSION", "3.22"]
        elif command.name == "project":
            approved = tokens == ["CXET", "LANGUAGES", "C", "CXX", "ASM"]
        elif command.name == "message":
            approved = bool(tokens) and tokens[0] == "FATAL_ERROR"
        elif command.name in {"function", "endfunction"}:
            approved = (command.name, tokens) in (
                ("function", ["cxet_add_abseil_subdirectory"]),
                ("endfunction", []))
        elif command.name == "include":
            approved = _include(tokens, composed)
        elif command.name.startswith("cxet_"):
            approved = (
                command.name == "cxet_add_abseil_subdirectory" and
                not tokens and
                scopes.get(command.offset) == ())
        elif command.name == "file":
            approved = _file(tokens, composed)
        elif command.name == "execute_process":
            approved = _execute_process(tokens, composed)
        elif command.name == "add_custom_target":
            approved = _custom_target(tokens, composed)
        elif command.name == "add_test":
            approved = _add_test(tokens, composed)
        elif command.name == "add_compile_options":
            approved = _directory_compile_options(tokens, composed) or tokens == [
                "$<$<AND:$<CONFIG:Release>,$<OR:$<COMPILE_LANGUAGE:C>,$<COMPILE_LANGUAGE:CXX>>>:-flto=full>"]
        elif command.name == "add_link_options":
            approved = tokens in (["$<$<CONFIG:Release>:-flto=full>"],
                ["$<$<CONFIG:Release>:-fuse-ld=${CXET_SELECTED_LLD}>", "$<$<CONFIG:Release>:-Wl,--gc-sections>"])
            if tokens == ["-L/usr/lib/gcc/x86_64-linux-gnu/12"]:
                approved = scopes.get(command.offset) == (
                    ("if", ("CXET_TOOLCHAIN_PROFILE", "STREQUAL", '"system-diagnostic"')),)

        elif command.name == "add_subdirectory":
            directory = tokens[0].rstrip("/") if tokens else ""
            approved = (
                directory in _APPROVED_SUBDIRECTORIES and
                tokens[1:] in ([], ["EXCLUDE_FROM_ALL"]) and
                (not tokens[1:] or directory in {
                    "extra/secp256k1",
                    "src/benchmarks/MarketIngress",
                    "src/benchmarks/AbseilRegistry", "apps/hft-compressor", "apps/hft-recorder", "apps/diagnostic",
                })
            )
            if directory in _OPTIONAL_ROOT_EDGES:
                approved = _optional_root_edge(
                    directory, tokens, scopes.get(command.offset))
            if directory == "tools/Checks/tests/prepared_orders":
                approved = tokens == [directory] and scopes.get(command.offset) == (("if", ("CXET_ENABLE_PREPARED_ORDER_CHECKS",)),)
        elif command.name == "find_package":
            approved = tokens in (["OpenSSL", "REQUIRED"], ["PkgConfig", "REQUIRED"])
        elif command.name == "pkg_check_modules":
            approved = composed and tokens == ["RDKAFKA", "REQUIRED", "rdkafka"]
        elif command.name == "enable_testing":
            approved = not tokens
        elif command.name in {"set", "unset"}:
            approved = _root_set(
                command.name, tokens, state, origin, errors,
                list(tokenize(command.body)))
            if command.name == "set" and tokens[:1] == ["_CXET_RELEASE_OPTIMIZATION"]:
                expected_scope = {
                    ("-O3",): (),
                    ("-O1",): system_scope,
                    ("-O2",): deploy_optimization_scope,
                }.get(tuple(tokens[1:]))
                approved = approved and scopes.get(command.offset) == expected_scope
            if command.name == "set" and tokens[:2] == ["CXET_LTO", "OFF"]:
                approved = approved and scopes.get(command.offset) == (
                    ("if", ("CXET_TOOLCHAIN_PROFILE", "STREQUAL", '"system-diagnostic"',
                            "OR", "CXET_DIAGNOSTIC_DEPLOY")),)
        elif command.name == "list":
            approved = _root_list(tokens, state, origin, errors)
        elif command.name == "string":
            approved = _root_string(tokens, state)
        elif command.name in _TARGET:
            approved = _target_command(
                command.name, tokens, composed, vendor_targets)
        if not approved:
            errors.append(f"{origin}: unapproved root {command.name} form {tokens}")
        if (approved and command.name == "message" and
                tokens[:1] == ["FATAL_ERROR"]):
            if conditionals:
                conditionals[-1].current_viable = False
            else:
                directory_terminal = True
        if command.name == "execute_process" and approved:
            try:
                output = tokens[tokens.index("OUTPUT_VARIABLE") + 1]
                state[output] = (f"${{{output}}}",)
            except (ValueError, IndexError):
                pass
        if (command.name == "add_subdirectory" and tokens and
                tokens[0].rstrip("/") == "src/src"):
            composed = True
        if command.name == "add_subdirectory" and approved and tokens:
            vendor_targets.update(
                _VENDOR_TARGETS.get(tokens[0].rstrip("/"), ()))
    if conditionals:
        errors.append("CMakeLists.txt: unterminated root conditional blocks")
    if loop_condition_depths:
        errors.append("CMakeLists.txt: unterminated root foreach block")
    if foreach_count not in (0, 1):
        errors.append(
            "CMakeLists.txt: expected one exact primitives foreach, found "
            f"{foreach_count}")
    validate_root_target_inventory(viable_commands, tokenize, errors)
    profile_evidence = {
        name: _trace_root_profile(
            commands, tokenize, name, dict(cache), errors, deploy_offsets)
        for name, cache in (profiles or {}).items()
    }
    return RootDialectEvidence(
        frozenset(command.offset for command in viable_commands),
        profile_evidence,
    )
