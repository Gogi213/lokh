"""Exact vendor invocation, state, and authority contracts."""

from __future__ import annotations

from pathlib import Path
from dataclasses import replace

from CMake.Syntax.CmakeFamilyContext import (
    alternate_if,
    exact_context,
    first_body,
    first_if,
    structural_contexts,
)
from CMake.Flow.CmakeFamilyExecutionIdentity import (
    reviewed_file_identity,
    reviewed_tree_identity,
)
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words


def semantic_vendor_context(context, expected) -> bool:
    """Line drift is not a new vendor authority; the whole lexical arm is."""
    if len(context) != len(expected):
        return False
    return exact_context(tuple(replace(frame, line=spec[2])
                               for frame, spec in zip(context, expected)), expected)


_CORE_LIBURING = first_if(
    "src/src/CMakeLists.txt", 101,
    ("NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
     "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"))
_CORE_LIBURING_CC_GUARD = first_if(
    "src/src/CMakeLists.txt", 103,
    ("DEFINED", "CMAKE_C_COMPILER_ID", "AND",
     "CMAKE_C_COMPILER_ID", "MATCHES", "Clang", "AND",
     "DEFINED", "CMAKE_C_COMPILER", "AND", "NOT",
     "CMAKE_C_COMPILER", "STREQUAL", ""))
_CORE_LIBURING_CC_ELSE = (
    "if", "src/src/CMakeLists.txt", 103, _CORE_LIBURING_CC_GUARD[3], "else", (),
    (("if", _CORE_LIBURING_CC_GUARD[3]),),
)
_CORE_SECP = first_if(
    "src/src/CMakeLists.txt", 192,
    ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1"))
_ROOT_ABSEIL_FUNCTION = first_body(
    "function", "CMakeLists.txt", 271,
    ("cxet_add_abseil_subdirectory",))

_SECP_VALUES = (
    ("SECP256K1_INSTALL", "OFF"),
    ("SECP256K1_ENABLE_MODULE_RECOVERY", "ON"),
    ("SECP256K1_ENABLE_MODULE_ECDH", "OFF"),
    ("SECP256K1_ENABLE_MODULE_EXTRAKEYS", "OFF"),
    ("SECP256K1_ENABLE_MODULE_SCHNORRSIG", "OFF"),
    ("SECP256K1_ENABLE_MODULE_MUSIG", "OFF"),
    ("SECP256K1_ENABLE_MODULE_ELLSWIFT", "OFF"),
    ("SECP256K1_BUILD_BENCHMARK", "OFF"),
    ("SECP256K1_BUILD_TESTS", "OFF"),
    ("SECP256K1_BUILD_EXHAUSTIVE_TESTS", "OFF"),
    ("SECP256K1_BUILD_CTIME_TESTS", "OFF"),
    ("SECP256K1_BUILD_EXAMPLES", "OFF"),
)


def _row(name, tokens, context=()):
    return name, tuple(tokens), context



def _state_record(active):
    tokens = cmake_list_words(active.command.body)
    if active.command.name == "set" and tokens:
        if tokens[0].startswith("SECP256K1_"):
            return ("cache", tokens[0], tokens[1] if len(tokens) > 1 else "",
                    tuple(value.upper() for value in tokens[2:4]),
                    tokens[-1].upper() if tokens else "")
        if tokens[0] in {
                "_CXET_BUILD_SHARED_LIBS_SAVED", "BUILD_SHARED_LIBS",
                "BUILD_TESTING", "CMAKE_POSITION_INDEPENDENT_CODE",
                "CMAKE_CXX_VISIBILITY_PRESET",
                "CMAKE_VISIBILITY_INLINES_HIDDEN",
                "ABSL_PROPAGATE_CXX_STD",
                "ABSL_USE_SYSTEM_INCLUDES",
                "ABSL_ENABLE_INSTALL"}:
            return ("set", *tokens)
    if active.command.name == "unset" and tokens[:1] == [
            "_CXET_BUILD_SHARED_LIBS_SAVED"]:
        return ("unset", *tokens)
    if active.command.name == "unset" and tokens[:1] == [
            "FETCHCONTENT_SOURCE_DIR_GOOGLETEST"]:
        return ("unset", *tokens)
    if (active.command.name == "add_subdirectory" and tokens and
            any(name in tokens[0] for name in (
                "secp256k1", "abseil-cpp"))):
        return ("edge", *tokens)
    if (active.command.name in {
            "target_compile_options", "target_link_options"} and tokens and
            tokens[0] in {
                "secp256k1", "secp256k1_precomputed", "absl_raw_hash_set", "absl_type_traits"}):
        return (active.command.name, *tokens)
    return None


def _secp_records(edge_tokens: tuple[str, ...]) -> list[tuple]:
    return [
        *(('cache', variable, value, ('CACHE', 'BOOL'), 'FORCE')
          for variable, value in _SECP_VALUES),
        ('set', '_CXET_BUILD_SHARED_LIBS_SAVED', '${BUILD_SHARED_LIBS}'),
        ('set', 'BUILD_SHARED_LIBS', 'OFF'),
        ('set', 'CMAKE_POSITION_INDEPENDENT_CODE', 'ON'),
        ('edge', *edge_tokens),
        ('target_compile_options', 'secp256k1', 'PRIVATE',
         '$<$<CONFIG:Release>:${_CXET_RELEASE_OPTIMIZATION}>',
         '$<$<CONFIG:Release>:-march=native>'),
        ('target_compile_options', 'secp256k1_precomputed', 'PRIVATE',
         '$<$<CONFIG:Release>:${_CXET_RELEASE_OPTIMIZATION}>',
         '$<$<CONFIG:Release>:-march=native>'),
        ('set', 'CMAKE_POSITION_INDEPENDENT_CODE', 'OFF'),
        ('set', 'BUILD_SHARED_LIBS', '${_CXET_BUILD_SHARED_LIBS_SAVED}'),
        ('unset', '_CXET_BUILD_SHARED_LIBS_SAVED'),
    ]


def _secp_contexts(outer: tuple, option: tuple) -> list[tuple]:
    # Twelve cache rows, three setup rows and the edge share the outer frame;
    # the two compiler mutations have one additional reviewed guard.
    return [outer] * 16 + [option, option] + [outer] * 3


def _absl_records() -> list[tuple]:
    return [
        ('set', 'ABSL_PROPAGATE_CXX_STD', 'ON'),
        ('set', 'ABSL_USE_SYSTEM_INCLUDES', 'ON'),
        ('set', 'ABSL_ENABLE_INSTALL', 'OFF'),
        ('set', '_CXET_BUILD_SHARED_LIBS_SAVED', '${BUILD_SHARED_LIBS}'),
        ('set', 'BUILD_SHARED_LIBS', 'OFF'),
        ('set', 'CMAKE_POSITION_INDEPENDENT_CODE', 'ON'),
        ('set', 'CMAKE_CXX_VISIBILITY_PRESET', 'hidden'),
        ('set', 'CMAKE_VISIBILITY_INLINES_HIDDEN', 'ON'),
        ('edge', 'extra/abseil-cpp'),
        ('target_compile_options', 'absl_type_traits', 'INTERFACE', '$<$<CXX_COMPILER_ID:Clang>:-Wno-deprecated-builtins>'),
        ('set', 'CMAKE_POSITION_INDEPENDENT_CODE', 'OFF'),
        ('set', 'BUILD_SHARED_LIBS', '${_CXET_BUILD_SHARED_LIBS_SAVED}'),
        ('unset', '_CXET_BUILD_SHARED_LIBS_SAVED'),
        ('target_compile_options', 'absl_raw_hash_set', 'PRIVATE', '-O2',
         '-g3', '-fsanitize=address,undefined',
         '-fsanitize-address-use-after-scope', '-fno-omit-frame-pointer',
         '-fno-optimize-sibling-calls', '-fno-sanitize-recover=all'),
        ('target_link_options', 'absl_raw_hash_set', 'PRIVATE',
         '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
         '-fno-sanitize-recover=all'),
        ('target_compile_options', 'absl_raw_hash_set', 'PRIVATE', '-O2',
         '-g3', '-fsanitize=thread', '-fno-omit-frame-pointer',
         '-fno-optimize-sibling-calls'),
        ('target_link_options', 'absl_raw_hash_set', 'PRIVATE',
         '-fsanitize=thread', '-fno-omit-frame-pointer'),
    ]


_ROOT_VENDOR_TARGET_MUTATIONS = frozenset(
    row
    for row in (*_secp_records(()), *_absl_records(),
                ("target_compile_options", "absl_type_traits", "INTERFACE", "$<$<CXX_COMPILER_ID:Clang>:-Wno-deprecated-builtins>"))
    if row[0] in {"target_compile_options", "target_link_options"}
)


def approved_root_vendor_target_mutation(
    name: str, tokens: list[str]
) -> bool:
    """Accept only the direct root vendor mutations pinned by the recipe."""
    return (name, *tokens) in _ROOT_VENDOR_TARGET_MUTATIONS


def _validate_vendor_state(
    commands, relative: str, expected: list[tuple], errors: list[str],
    viable: frozenset[int], expected_contexts: list[tuple],
) -> None:
    selected = [
        (active, record) for active in commands
        if (record := _state_record(active)) is not None
    ]
    if [record for _, record in selected] != expected:
        errors.append(f"{relative}: vendored build state/order changed")
    for index, (active, record) in enumerate(selected):
        # The exact family profile disables the optional native secp256k1
        # optimization. Its two guarded recipe rows remain structurally pinned
        # below, but are intentionally absent from the selected execution path.
        if (active.ordinal not in viable and
                record[0] != "target_compile_options"):
            errors.append(
                f"{relative}:{active.command.line}: vendored build state is "
                "not on a viable execution path")
        context = (
            expected_contexts[index]
            if index < len(expected_contexts) else ("<unexpected>",))
        if not semantic_vendor_context(active.structural_context, context):
            errors.append(
                f"{relative}:{active.command.line}: vendored build state "
                "structural context changed")


def _validate_liburing_producer(
    core, viable_ordinals: frozenset[int], errors: list[str]
) -> None:
    """Pin raw producer structure, not expanded program/flag provenance."""
    relative = "src/src/CMakeLists.txt"
    cc_guard = _CORE_LIBURING_CC_GUARD
    cc_else = _CORE_LIBURING_CC_ELSE
    expected_cc = (
        ("set", ("CXET_LIBURING_CC", "${CMAKE_C_COMPILER}"),
         (_CORE_LIBURING, cc_guard)),
        ("unset", ("CXET_LIBURING_CC", "CACHE"),
         (_CORE_LIBURING, cc_else)),
        ("unset", ("CXET_LIBURING_CC",), (_CORE_LIBURING, cc_else)),
        ("find_program", ("CXET_LIBURING_CC", "NAMES", "clang", "REQUIRED"),
         (_CORE_LIBURING, cc_else)),
    )
    cc_rows = [
        active for active in core
        if active.relative == relative and
        active.command.name in {"find_program", "set", "unset"} and
        cmake_list_words(active.command.body)[:1] == ["CXET_LIBURING_CC"]
    ]
    if [(active.command.name,
         tuple(cmake_list_words(active.command.body))) for active in cc_rows] != [
            (name, tokens) for name, tokens, _context in expected_cc]:
        errors.append(
            f"{relative}: exact liburing CC selection/clearance changed")
    for index, active in enumerate(cc_rows):
        expected_context = (
            expected_cc[index][2]
            if index < len(expected_cc) else ("<unexpected>",))
        if (active.scope != relative or
                active.source_base != Path("src/src") or
                active.binary_base != Path("src/src") or
                not semantic_vendor_context(
                    active.structural_context, expected_context)):
            errors.append(
                f"{relative}:{active.command.line}: liburing CC selection "
                "escaped its exact owner context")
    if not any(active.ordinal in viable_ordinals for active in cc_rows):
        errors.append(f"{relative}: selected liburing CC alternative has no viable evidence")

    expected_state = [
        ("set", ("CXET_LIBURING_VENDOR_DIR",
                 "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing")),
        ("set", ("CXET_LIBURING_CXX", "${CMAKE_CXX_COMPILER}")),
        ("file", ("GLOB_RECURSE", "CXET_LIBURING_INPUT_FILES",
                  "CONFIGURE_DEPENDS", "LIST_DIRECTORIES", "false",
                  "${CXET_LIBURING_VENDOR_DIR}/*")),
        ("list", ("FILTER", "CXET_LIBURING_INPUT_FILES", "EXCLUDE",
                  "REGEX", "(^|/)[.]git(/|$)")),
        ("list", ("SORT", "CXET_LIBURING_INPUT_FILES")),
        ("set", ("CXET_LIBURING_WORK_DIR",
                 "${CMAKE_CURRENT_BINARY_DIR}/_deps/liburing")),
        ("set", ("CXET_LIBURING_SOURCE_DIR",
                 "${CXET_LIBURING_WORK_DIR}/source")),
        ("set", ("CXET_LIBURING_INSTALL_DIR",
                 "${CXET_LIBURING_WORK_DIR}/install")),
        ("set", ("CXET_LIBURING_ARCHIVE",
                 "${CXET_LIBURING_INSTALL_DIR}/lib/liburing.a")),
        ("set", ("CXET_LIBURING_HEADER",
                 "${CXET_LIBURING_INSTALL_DIR}/include/liburing.h")),
        ("set", ("_CXET_LIBURING_CFLAGS", "${CMAKE_C_FLAGS_RELEASE}")),
        ("string", ("APPEND", "_CXET_LIBURING_CFLAGS", " -flto=full")),
        ("set", ("_CXET_LIBURING_LDFLAGS", "")),
        ("set", ("_CXET_LIBURING_LDFLAGS", "-fuse-ld=${CXET_SELECTED_LLD}")),
        ("set", (
            "_CXET_LIBURING_CLEAN_ENV",
            "PATH=/usr/bin:/bin", "LC_ALL=C",
            "CC=${CXET_LIBURING_CC}", "CXX=${CXET_LIBURING_CXX}",
            "AR=${CMAKE_AR}", "RANLIB=${CMAKE_RANLIB}",
            "CFLAGS=${_CXET_LIBURING_CFLAGS}", "CPPFLAGS=", "CXXFLAGS=",
            "LDFLAGS=${_CXET_LIBURING_LDFLAGS}",
            "LIBS=", "LIBURING_CFLAGS=", "DESTDIR=", "MAKEFLAGS=",
            "MFLAGS=", "MAKEOVERRIDES=", "SHELL=/bin/sh")),
        ("file", (
            "MAKE_DIRECTORY", "${CXET_LIBURING_INSTALL_DIR}/include")),
        ("set", ("CXET_COMPILE_JOBS", "1", "CACHE", "STRING", "Private compile driver job count")),
    ]
    lto = first_if(relative, 121, ("CXET_LTO",))
    lld = first_if(relative, 125, ("CXET_SELECTED_LLD",))
    state_contexts = [(_CORE_LIBURING,)] * len(expected_state)
    state_contexts[11] = (_CORE_LIBURING, lto)
    state_contexts[13] = (_CORE_LIBURING, lld)
    state_rows = [
        active for active in core
        if active.relative == relative and
        active.command.name in {"file", "list", "set", "unset", "string"} and
        (any((value.startswith("CXET_LIBURING_") or
             value.startswith("_CXET_LIBURING_") or
             value.startswith("${CXET_LIBURING_") or
             value.startswith("${_CXET_LIBURING_")) and
            value != "CXET_LIBURING_CC"
            for value in cmake_list_words(active.command.body)) or
         cmake_list_words(active.command.body)[:1] == ["CXET_COMPILE_JOBS"])
    ]
    actual_state = [
        (active.command.name, tuple(cmake_list_words(active.command.body)))
        for active in state_rows]
    if actual_state != expected_state:
        errors.append(
            f"{relative}: build-local liburing producer state/order changed")
    for index, active in enumerate(state_rows):
        context = state_contexts[index] if index < len(state_contexts) else ("<unexpected>",)
        if (active.scope != relative or
                active.source_base != Path("src/src") or
                active.binary_base != Path("src/src") or
                not semantic_vendor_context(
                    active.structural_context, context)):
            errors.append(
                f"{relative}:{active.command.line}: liburing producer state "
                "escaped its exact owner/context")
        if len(context) == 1 and active.ordinal not in viable_ordinals:
            errors.append(
                f"{relative}:{active.command.line}: liburing producer state "
                "is not on a viable execution path")

    if (not reviewed_tree_identity("liburing_vendor") or
            not reviewed_file_identity("cmake/SanitizeCRLF.cmake")):
        errors.append(
            f"{relative}: liburing vendor/sanitizer authority changed")

    consumer = first_if(relative, 529, ("TARGET", "liburing::uring"))
    producer_visible = first_if(relative, 534, ("TARGET", "cxet_liburing_ep"))
    missing = alternate_if(relative, 101, _CORE_LIBURING[3], ("NOT", "TARGET", "liburing::uring"))
    specs = (
        ("configure-time include directory", "file", (
            "MAKE_DIRECTORY", "${CXET_LIBURING_INSTALL_DIR}/include"),
         (_CORE_LIBURING,)),
        ("generated outputs", "add_custom_command", (
            "OUTPUT", "${CXET_LIBURING_ARCHIVE}", "${CXET_LIBURING_HEADER}", "COMMAND"), (_CORE_LIBURING,)),
        ("output producer", "add_custom_target", (
            "cxet_liburing_ep", "DEPENDS", "${CXET_LIBURING_ARCHIVE}", "${CXET_LIBURING_HEADER}"), (_CORE_LIBURING,)),
        ("producer metadata", "set_target_properties", (
            "cxet_liburing_ep", "PROPERTIES", "CXET_COMPILE_OWNER", "vendor:liburing",
            "CXET_COMPILE_INPUTS", "${CXET_LIBURING_INPUT_FILES};${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/SanitizeCRLF.cmake",
            "CXET_COMPILE_OUTPUTS", "${CXET_LIBURING_ARCHIVE};${CXET_LIBURING_HEADER}"), (_CORE_LIBURING,)),
        ("imported target", "add_library", (
            "liburing::uring", "STATIC", "IMPORTED", "GLOBAL"),
         (_CORE_LIBURING,)),
        ("producer dependency", "add_dependencies", (
            "liburing::uring", "cxet_liburing_ep"), (_CORE_LIBURING,)),
        ("imported location/include", "set_target_properties", (
            "liburing::uring", "PROPERTIES",
            "IMPORTED_LOCATION", "${CXET_LIBURING_ARCHIVE}",
            "INTERFACE_INCLUDE_DIRECTORIES",
            "${CXET_LIBURING_INSTALL_DIR}/include"), (_CORE_LIBURING,)),
        ("missing vendor refusal", "message", (
            "FATAL_ERROR", "Vendored liburing is required for the WS io_uring backend"), (missing,)),
        ("consumer link", "target_link_libraries", (
            "cxet_lib", "PRIVATE", "liburing::uring"), (consumer,)),
        ("consumer compile dependency", "add_dependencies", (
            "cxet_lib", "cxet_liburing_ep"), (consumer, producer_visible)),
    )
    matched = []
    for label, command_name, prefix, context in specs:
        candidates = []
        for active in core:
            if (active.relative != relative or
                    active.command.name != command_name):
                continue
            tokens = tuple(cmake_list_words(active.command.body))
            related = (
                (label == "configure-time include directory" and
                 tokens[:1] == ("MAKE_DIRECTORY",) and
                 any("LIBURING" in token for token in tokens[1:])) or
                (label == "generated outputs" and tokens[:1] == ("OUTPUT",) and
                 any("LIBURING" in token for token in tokens)) or
                (label in {"output producer", "producer metadata"} and
                 tokens[:1] == ("cxet_liburing_ep",)) or
                (label == "imported target" and
                 tokens[:1] == ("liburing::uring",)) or
                (label == "producer dependency" and
                 tokens[:1] == ("liburing::uring",)) or
                (label == "imported location/include" and
                 tokens[:1] == ("liburing::uring",)) or
                (label == "consumer link" and
                 tokens[:2] == ("cxet_lib", "PRIVATE") and
                 "liburing::uring" in tokens[2:]) or
                (label == "consumer compile dependency" and
                 tokens[:1] == ("cxet_lib",) and "cxet_liburing_ep" in tokens[1:]) or
                (label == "missing vendor refusal" and
                 any("liburing" in token.lower() for token in tokens))
            )
            if related:
                candidates.append(active)
        if len(candidates) != 1:
            errors.append(
                f"{relative}: required liburing {label} form count changed: "
                f"{len(candidates)}")
            continue
        active = candidates[0]
        tokens = tuple(cmake_list_words(active.command.body))
        if label == "generated outputs":
            # Terminal command/program/expanded flag authority is a separate
            # CommandPolicy gate.  Pin this producer's outputs and input edge.
            dependency_tail = (
                "DEPENDS", "${CXET_LIBURING_INPUT_FILES}",
                "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/SanitizeCRLF.cmake",
                "WORKING_DIRECTORY", "${CMAKE_CURRENT_BINARY_DIR}",
                "COMMENT", "Building vendored liburing", "VERBATIM")
            exact = (tokens[:len(prefix)] == prefix and tokens.count("OUTPUT") == 1 and
                     tokens.count("DEPENDS") == 1 and
                     tokens[tokens.index("DEPENDS"):] == dependency_tail)
        else:
            exact = tokens == prefix
        if not exact:
            errors.append(
                f"{relative}:{active.command.line}: liburing {label} "
                "arguments changed")
        matched.append(active)
        if (active.scope != relative or
                active.source_base != Path("src/src") or
                active.binary_base != Path("src/src") or
                not semantic_vendor_context(active.structural_context, context)):
            errors.append(
                f"{relative}:{active.command.line}: liburing {label} escaped "
                "its exact owner/context")
        if label != "missing vendor refusal" and active.ordinal not in viable_ordinals:
            errors.append(
                f"{relative}:{active.command.line}: liburing {label} is not "
                "on a viable execution path")
    if (len(matched) == len(specs) and
            [active.ordinal for active in matched] != sorted(
                active.ordinal for active in matched)):
        errors.append(
            f"{relative}: required liburing producer/edge order changed")


def validate_active_vendor_contract(
    commands, viable_ordinals: frozenset[int], errors: list[str]
) -> None:
    """Require the standalone core vendor recipe, never the safety graph."""
    core = [
        active for active in commands
        if active.scope == "src/src/CMakeLists.txt"]
    if not core:
        errors.append(
            "src/src/CMakeLists.txt: active core vendor scope is missing")
        return
    _validate_liburing_producer(core, viable_ordinals, errors)
    edges = [
        active for active in core
        if active.relative == "src/src/CMakeLists.txt" and
        active.command.name == "add_subdirectory" and
        "extra/secp256k1" in active.command.body]
    expected = {
        ("extra/secp256k1", _CORE_SECP),
    }
    actual = set()
    for active in edges:
        tokens = cmake_list_words(active.command.body)
        authority = (
            "extra/secp256k1" if "secp256k1" in tokens[0] else "")
        frame = _CORE_SECP
        if authority and semantic_vendor_context(active.structural_context, (frame,)):
            actual.add((authority, frame))
        if active.ordinal not in viable_ordinals:
            errors.append(
                f"{active.relative}:{active.command.line}: required external "
                "edge is not viable")
    if actual != expected or len(edges) != 1:
        errors.append(
            "src/src/CMakeLists.txt: exact active secp256k1 edge "
            "set changed")

    secp_option = first_if(
        "src/src/CMakeLists.txt", 212,
        ("CXET_SECP256K1_NATIVE_OPT",))
    core_state = [
        ('set', 'BUILD_TESTING', 'OFF'),
        *_secp_records((
            "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1",
            "${CMAKE_CURRENT_BINARY_DIR}/_deps/secp256k1",
            "EXCLUDE_FROM_ALL")),
    ]
    _validate_vendor_state(
        core, "src/src/CMakeLists.txt", core_state, errors,
        viable_ordinals,
        [(),
         *_secp_contexts((_CORE_SECP,), (_CORE_SECP, secp_option))])


def validate_root_vendor_contract(
    commands, errors: list[str], viable_offsets: frozenset[int]
) -> None:
    """Pin root native vendor state and source dependency authority."""
    contexts = structural_contexts(
        "CMakeLists.txt", commands, cmake_list_words, errors)
    active = []
    for ordinal, (command, context) in enumerate(zip(commands, contexts)):
        active.append(type("RootActive", (), {
            "relative": "CMakeLists.txt", "command": command,
            "structural_context": context, "ordinal": command.offset,
        })())
    root_secp_native = first_if(
        "CMakeLists.txt", 230, ("CXET_HAS_SECP256K1",))
    root_secp_option = first_if(
        "CMakeLists.txt", 250, ("CXET_SECP256K1_NATIVE_OPT",))
    address = first_if(
        "CMakeLists.txt", 288,
        ("CXET_SANITIZER_PROFILE", "STREQUAL", "address-undefined"))
    thread = alternate_if(
        "CMakeLists.txt", 288,
        ("CXET_SANITIZER_PROFILE", "STREQUAL", "address-undefined"),
        ("CXET_SANITIZER_PROFILE", "STREQUAL", "thread"))
    root_state = [
        ('set', 'BUILD_TESTING', 'OFF'),
        ('set', 'BUILD_SHARED_LIBS', 'OFF'),
        *_secp_records(("extra/secp256k1", "EXCLUDE_FROM_ALL")),
        *_absl_records(),
    ]
    _validate_vendor_state(
        active, "CMakeLists.txt", root_state, errors, viable_offsets,
        [(), (),
         *_secp_contexts((root_secp_native,), (root_secp_native, root_secp_option)),
         *([()] * 6), *([(_ROOT_ABSEIL_FUNCTION,)] * 3),
         *([()] * 4), (address,), (address,), (thread,), (thread,)])
