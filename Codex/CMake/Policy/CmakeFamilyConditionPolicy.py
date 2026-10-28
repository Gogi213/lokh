"""Exact token/context guards for the CXET family CMake graph."""

from __future__ import annotations

from dataclasses import dataclass

from CMake.Syntax.CmakeFamilyLexer import scan_commands, words


ConditionTokens = tuple[str, ...]
ContextFrame = tuple[str, ConditionTokens]
CommandContext = tuple[ContextFrame, ...]

ROOT_PROFILE_EXCLUSION = (
    "CXET_FAMILY_SOURCE_GRAPH", "AND", "(",
    "CXET_SAFETY_BUILD", "OR", "CXET_ENABLE_SRC_TESTS", ")",
)
ROOT_COMPILER_CONDITION = (
    "NOT", "CMAKE_C_COMPILER_ID", "MATCHES", '"Clang"', "OR",
    "NOT", "CMAKE_CXX_COMPILER_ID", "MATCHES", '"Clang"',
)
ROOT_SYSTEM_CONDITION = (
    "NOT", "CMAKE_SYSTEM_NAME", "STREQUAL", '"Linux"',
)
ROOT_PROCESSOR_CONDITION = (
    "NOT", "CMAKE_SYSTEM_PROCESSOR", "STREQUAL", '"x86_64"',
)
_STANDALONE_CONDITION = (
    "CMAKE_SOURCE_DIR", "STREQUAL", "CMAKE_CURRENT_SOURCE_DIR",
)
_ROOT_MARKER_CONDITION = (
    "NOT", "DEFINED", "CXET_ROOT_SOURCE_GRAPH", "OR",
    "NOT", "CXET_ROOT_SOURCE_GRAPH",
)
_ROOT_FAMILY_CONDITION = (
    "CXET_FAMILY_SOURCE_GRAPH", "OR", "CXET_FULL_BUILD",
)
_ROOT_FULL_FAMILY_CONDITION = (
    "CXET_FULL_BUILD", "AND", "CXET_FAMILY_SOURCE_GRAPH",
)
_ROOT_SAFETY_CONDITION = (
    "CXET_ENABLE_SRC_TESTS", "OR", "CXET_SAFETY_BUILD",
)
_ROOT_PRE_GUARD_EFFECTS = frozenset({
    "add_compile_definitions", "add_compile_options",
    "add_custom_command", "add_custom_target",
    "add_executable", "add_library", "add_link_options",
    "add_subdirectory", "aux_source_directory", "build_command",
    "cmake_language", "configure_file", "execute_process", "export",
    "file", "find_file", "find_library", "find_package", "find_path",
    "find_program", "include", "install", "link_libraries", "return",
    "target_compile_definitions", "target_compile_features",
    "target_compile_options", "target_include_directories",
    "target_link_libraries", "target_link_options", "target_sources",
})


def exact_condition_tokens(body: str) -> ConditionTokens:
    """Retain CMake token boundaries, spelling and quote provenance."""
    return tuple(words(body))


def exact_command_contexts(commands) -> list[tuple[object, CommandContext]]:
    """Return structural contexts without case-folding or token joining."""
    contexts: list[tuple[object, CommandContext]] = []
    stack: list[ContextFrame] = []
    openers = {"if", "foreach", "function", "macro", "while", "block"}
    closers = {
        "endif": "if",
        "endforeach": "foreach",
        "endfunction": "function",
        "endmacro": "macro",
        "endwhile": "while",
        "endblock": "block",
    }
    for command in commands:
        if command.name in closers:
            expected = closers[command.name]
            active_kind = stack[-1][0] if stack else ""
            if stack and (
                    active_kind == expected or
                    expected == "if" and
                    active_kind in {"elseif", "else"}):
                stack.pop()
            continue
        if command.name in {"else", "elseif"}:
            if stack and stack[-1][0] in {"if", "elseif", "else"}:
                stack[-1] = (
                    command.name,
                    exact_condition_tokens(command.body),
                )
            continue
        contexts.append((command, tuple(stack)))
        if command.name in openers:
            stack.append((
                command.name,
                exact_condition_tokens(command.body),
            ))
    return contexts


def _fatal_scopes(commands) -> tuple[CommandContext, ...]:
    return tuple(
        scope for command, scope in exact_command_contexts(commands)
        if command.name == "message"
        and exact_condition_tokens(command.body)[:1] == ("FATAL_ERROR",)
    )


def _exact_top_level_fatal_block(
    commands,
    condition: ConditionTokens,
) -> bool:
    contexts = exact_command_contexts(commands)
    scopes = {command.offset: scope for command, scope in contexts}
    openers = [
        index for index, command in enumerate(commands)
        if command.name == "if"
        and scopes.get(command.offset) == ()
        and exact_condition_tokens(command.body) == condition
    ]
    if len(openers) != 1:
        return False
    block = commands[openers[0]:openers[0] + 3]
    return (
        len(block) == 3 and
        [command.name for command in block] == [
            "if", "message", "endif"] and
        exact_condition_tokens(block[1].body)[:1] == ("FATAL_ERROR",) and
        scopes.get(block[1].offset) == (("if", condition),)
    )


def _exact_if_elseif_fatal_chain(
    commands,
    opening: ConditionTokens,
    fallback: ConditionTokens,
) -> bool:
    contexts = exact_command_contexts(commands)
    scopes = {command.offset: scope for command, scope in contexts}
    openers = [
        index for index, command in enumerate(commands)
        if command.name == "if"
        and scopes.get(command.offset) == ()
        and exact_condition_tokens(command.body) == opening
    ]
    if len(openers) != 1:
        return False
    depth = 0
    branches: list[tuple[int, str, ConditionTokens]] = []
    closing_index: int | None = None
    for index in range(openers[0], len(commands)):
        command = commands[index]
        if command.name == "if":
            depth += 1
            continue
        if command.name == "endif":
            depth -= 1
            if depth == 0:
                closing_index = index
                break
            continue
        if depth == 1 and command.name in {"else", "elseif"}:
            branches.append((
                index, command.name,
                exact_condition_tokens(command.body)))
    if closing_index is None or len(branches) != 1:
        return False
    if branches[0][1:] != ("elseif", fallback):
        return False
    branch_index = branches[0][0]
    block = commands[branch_index:closing_index + 1]
    return (
        len(block) == 3 and
        [command.name for command in block] == [
            "elseif", "message", "endif"] and
        exact_condition_tokens(block[1].body)[:1] == ("FATAL_ERROR",) and
        scopes.get(block[1].offset) == (("elseif", fallback),)
    )


def validate_root_exclusion_guard(commands, errors: list[str]) -> None:
    if not _exact_top_level_fatal_block(
            commands, ROOT_PROFILE_EXCLUSION):
        errors.append(
            "CMakeLists.txt: family and safety/test graphs need one exact "
            "top-level one-member fail-closed exclusion guard")


def validate_root_full_family_guard(commands, errors: list[str]) -> None:
    if not _exact_top_level_fatal_block(
            commands, _ROOT_FULL_FAMILY_CONDITION):
        errors.append(
            "CMakeLists.txt: full/family profiles need one exact top-level "
            "one-member fail-closed guard")


def validate_root_compiler_guard(commands, errors: list[str]) -> None:
    """Pin the only root compiler predicate used to reject a preset."""
    compiler_predicates = [
        exact_condition_tokens(command.body)
        for command in commands
        if command.name in {"if", "elseif"}
        and any(token in {
            "CMAKE_C_COMPILER_ID", "CMAKE_CXX_COMPILER_ID"
        } for token in exact_condition_tokens(command.body))
    ]
    if (not _exact_top_level_fatal_block(
            commands, ROOT_COMPILER_CONDITION) or
            compiler_predicates != [ROOT_COMPILER_CONDITION]):
        errors.append(
            "CMakeLists.txt: exact top-level Clang compiler rejection guard "
            "changed")


def validate_root_platform_guards(commands, errors: list[str]) -> None:
    """Pin the complete root target-platform rejection inventory."""
    platform_predicates = [
        exact_condition_tokens(command.body)
        for command in commands
        if command.name in {"if", "elseif"}
        and any(token in {
            "CMAKE_SYSTEM_NAME", "CMAKE_SYSTEM_PROCESSOR"
        } for token in exact_condition_tokens(command.body))
    ]
    expected = [ROOT_SYSTEM_CONDITION, ROOT_PROCESSOR_CONDITION]
    if (platform_predicates != expected or any(
            not _exact_top_level_fatal_block(commands, condition)
            for condition in expected)):
        errors.append(
            "CMakeLists.txt: exact top-level Linux/x86_64 rejection guards "
            "changed")


def validate_root_guard_order(commands, errors: list[str]) -> None:
    """Require all root rejection guards before executable graph effects."""
    contexts = exact_command_contexts(commands)
    scopes = {command.offset: scope for command, scope in contexts}
    bootstrap = tuple(command.name for command in commands[:4])
    if (bootstrap != ("cmake_minimum_required", "include", "project", "include") or
            exact_condition_tokens(commands[1].body) != (
                '"${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake"',) or
            exact_condition_tokens(commands[2].body) != (
                "CXET", "LANGUAGES", "C", "CXX", "ASM") or
            exact_condition_tokens(commands[3].body) != (
                '"${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake"',)):
        errors.append("CMakeLists.txt: exact toolchain/project/exchange-selection bootstrap must be first")
        return
    cursor = 4
    if cursor < len(commands) and commands[cursor].name == "if" and exact_condition_tokens(commands[cursor].body) == ("DEFINED", "CXET_BUILD_OWNER"):
        block = commands[cursor:cursor + 4]
        expected_names = ("if", "set", "set", "endif")
        if tuple(command.name for command in block) != expected_names or any(
                exact_condition_tokens(command.body)[:4] != (variable, "OFF", "CACHE", "BOOL")
                or exact_condition_tokens(command.body)[-1:] != ("FORCE",)
                for command, variable in zip(block[1:3], (
                    "CMAKE_INTERPROCEDURAL_OPTIMIZATION", "CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE"))):
            errors.append("CMakeLists.txt: owner-only IPO reset contract changed")
            return
        cursor += 4
    indices = []
    for condition in (ROOT_COMPILER_CONDITION, ROOT_SYSTEM_CONDITION, ROOT_PROCESSOR_CONDITION):
        block = commands[cursor:cursor + 3]
        if (len(block) != 3 or tuple(command.name for command in block) != ("if", "message", "endif")
                or exact_condition_tokens(block[0].body) != condition
                or exact_condition_tokens(block[1].body)[:1] != ("FATAL_ERROR",)
                or scopes.get(block[0].offset) != ()):
            errors.append("CMakeLists.txt: compiler/platform rejection guards must follow bootstrap before effects")
            return
        indices.append(cursor)
        cursor += 3
    full_guard = [index for index, command in enumerate(commands)
                  if command.name == "if" and scopes.get(command.offset) == ()
                  and exact_condition_tokens(command.body) == _ROOT_FULL_FAMILY_CONDITION]
    effects = [index for index, command in enumerate(commands)
               if index >= cursor and command.name in _ROOT_PRE_GUARD_EFFECTS]
    if len(full_guard) != 1 or not effects or full_guard[0] >= effects[0]:
        errors.append("CMakeLists.txt: full/family rejection must precede every source/build effect")


def validate_app_guard_contract(
    relative: str,
    commands,
    errors: list[str],
) -> None:
    contexts = exact_command_contexts(commands)
    scopes = {command.offset: scope for command, scope in contexts}
    guard_indices: dict[ConditionTokens, int] = {}
    for condition, description in (
        (_STANDALONE_CONDITION, "standalone configure rejection"),
        (_ROOT_MARKER_CONDITION, "fail-closed CXET_ROOT_SOURCE_GRAPH guard"),
    ):
        expected_scope = (("if", condition),)
        openers = [
            index for index, command in enumerate(commands)
            if command.name == "if"
            and scopes.get(command.offset) == ()
            and exact_condition_tokens(command.body) == condition
        ]
        if len(openers) != 1:
            errors.append(
                f"{relative}: missing one exact top-level {description}")
            continue
        index = openers[0]
        guard_indices[condition] = index
        block = commands[index:index + 3]
        if (len(block) != 3 or
                [command.name for command in block] != [
                    "if", "message", "endif"] or
                exact_condition_tokens(block[1].body)[:1] !=
                ("FATAL_ERROR",) or
                scopes.get(block[1].offset) != expected_scope):
            errors.append(
                f"{relative}: {description} must be an exact one-member "
                "FATAL_ERROR block")

    standalone_index = guard_indices.get(_STANDALONE_CONDITION)
    marker_index = guard_indices.get(_ROOT_MARKER_CONDITION)
    if standalone_index is None or marker_index is None:
        return
    prelude = commands[:standalone_index]
    if (any(command.name != "cmake_minimum_required"
            for command in prelude) or
            marker_index != standalone_index + 3):
        errors.append(
            f"{relative}: standalone/root-marker guards must be the first "
            "executable app contract with no transfer or mutation between "
            "them")


def _target_guard_inventory(
    condition: ConditionTokens,
) -> tuple[str, ...] | None:
    """Parse only an OR-list of exact `NOT TARGET <literal>` clauses."""
    if not condition:
        return None
    providers: list[str] = []
    index = 0
    while index < len(condition):
        if (condition[index:index + 2] != ("NOT", "TARGET") or
                index + 2 >= len(condition)):
            return None
        provider = condition[index + 2]
        if (not provider or provider in {"AND", "OR", "(", ")"} or
                "${" in provider or "$<" in provider):
            return None
        providers.append(provider)
        index += 3
        if index == len(condition):
            break
        if condition[index] != "OR":
            return None
        index += 1
    return tuple(providers)


def provider_guard_is_fatal(prelude: str, provider: str) -> bool:
    commands = _parse("<provider-prelude>", prelude, [])
    if any(
            command.name in {"break", "continue", "return"}
            for command in commands):
        return False
    contexts = exact_command_contexts(commands)
    for command, scope in contexts:
        if (command.name != "message" or
                exact_condition_tokens(command.body)[:1] !=
                ("FATAL_ERROR",) or not scope):
            continue
        kind, condition = scope[-1]
        inventory = _target_guard_inventory(condition)
        if (kind == "if" and scope == (("if", condition),) and
                inventory is not None and provider in inventory):
            frame = ("if", condition)
            members = [
                (candidate, candidate_scope)
                for candidate, candidate_scope in contexts
                if candidate_scope[:1] == (frame,)
            ]
            if members == [(command, scope)]:
                return True
        if len(scope) != 2 or kind != "if":
            continue
        frame_kind, loop_tokens = scope[0]
        if (frame_kind != "foreach" or len(loop_tokens) < 4 or
                loop_tokens[1:3] != ("IN", "ITEMS")):
            continue
        variable = loop_tokens[0]
        items = tuple(loop_tokens[3:])
        if (provider in items and
                condition == ("NOT", "TARGET", f"${{{variable}}}")):
            loop_frame = (frame_kind, loop_tokens)
            members = [
                (candidate, candidate_scope)
                for candidate, candidate_scope in contexts
                if candidate_scope[:1] == (loop_frame,)
            ]
            expected_if_scope = (loop_frame,)
            if (len(members) == 2 and
                    members[0][0].name == "if" and
                    exact_condition_tokens(members[0][0].body) == condition and
                    members[0][1] == expected_if_scope and
                    members[1] == (command, scope)):
                return True
    return False


def exact_provider_guard_inventory(
    prelude: str,
    *,
    conditional_guards: tuple[
        tuple[ConditionTokens, tuple[str, ...]], ...] = (),
) -> tuple[str, ...] | None:
    """Prove one unconditional inventory plus explicitly scoped guard blocks."""
    parse_errors: list[str] = []
    commands = _parse("<provider-prelude>", prelude, parse_errors)
    if parse_errors or any(
            command.name in {"break", "continue", "return"}
            for command in commands):
        return None
    contexts = exact_command_contexts(commands)
    scopes = {command.offset: scope for command, scope in contexts}
    structures: list[tuple[tuple[str, ...], int]] = []
    conditional_structures: list[
        tuple[ConditionTokens, tuple[str, ...], int]] = []

    for index, command in enumerate(commands):
        scope = scopes.get(command.offset)
        if scope and command.name == "if":
            condition = exact_condition_tokens(command.body)
            inventory = _target_guard_inventory(condition)
            block = commands[index:index + 3]
            if (len(scope) == 1 and scope[0][0] == "if" and
                    inventory is not None and len(block) == 3 and
                    [member.name for member in block] == [
                        "if", "message", "endif"] and
                    exact_condition_tokens(block[1].body)[:1] ==
                    ("FATAL_ERROR",) and
                    scopes.get(block[1].offset) == scope + (("if", condition),)):
                conditional_structures.append((
                    scope[0][1], inventory, block[1].offset))
        if scope != ():
            continue
        if command.name == "if":
            condition = exact_condition_tokens(command.body)
            inventory = _target_guard_inventory(condition)
            block = commands[index:index + 3]
            if (inventory is not None and len(block) == 3 and
                    [member.name for member in block] == [
                        "if", "message", "endif"] and
                    exact_condition_tokens(block[1].body)[:1] ==
                    ("FATAL_ERROR",) and
                    scopes.get(block[1].offset) == (("if", condition),)):
                structures.append((inventory, block[1].offset))
            continue
        if command.name != "foreach":
            continue
        loop_tokens = exact_condition_tokens(command.body)
        if (len(loop_tokens) < 4 or loop_tokens[1:3] !=
                ("IN", "ITEMS")):
            continue
        variable = loop_tokens[0]
        inventory = tuple(loop_tokens[3:])
        condition = ("NOT", "TARGET", f"${{{variable}}}")
        block = commands[index:index + 5]
        loop_scope = (("foreach", loop_tokens),)
        fatal_scope = loop_scope + (("if", condition),)
        if (inventory and len(block) == 5 and
                [member.name for member in block] == [
                    "foreach", "if", "message", "endif", "endforeach"] and
                exact_condition_tokens(block[1].body) == condition and
                scopes.get(block[1].offset) == loop_scope and
                exact_condition_tokens(block[2].body)[:1] ==
                ("FATAL_ERROR",) and
                scopes.get(block[2].offset) == fatal_scope):
            structures.append((inventory, block[2].offset))

    if tuple((condition, inventory)
             for condition, inventory, _ in conditional_structures) != conditional_guards:
        return None
    covered_fatals = {
        *(offset for _, offset in structures),
        *(offset for _, _, offset in conditional_structures),
    }
    for command, scope in contexts:
        if (command.name != "message" or
                exact_condition_tokens(command.body)[:1] !=
                ("FATAL_ERROR",)):
            continue
        negative_target_scope = any(
            "NOT" in condition and "TARGET" in condition
            for _, condition in scope)
        if negative_target_scope and command.offset not in covered_fatals:
            return None
    if len(structures) != 1:
        return None
    return structures[0][0]


def _find_inventory(commands) -> tuple[tuple[ConditionTokens, CommandContext], ...]:
    return tuple(
        (exact_condition_tokens(command.body), scope)
        for command, scope in exact_command_contexts(commands)
        if command.name == "find_package"
    )


def validate_root_provider_contract(
    root_commands,
    core_commands,
    errors: list[str],
) -> None:
    """Prove imported providers exist before the root-composed core uses them."""
    expected_root = ()
    if _find_inventory(root_commands) != expected_root:
        errors.append(
            "CMakeLists.txt: exact root find_package provider inventory "
            "changed")

    standalone = (("if", _STANDALONE_CONDITION),)
    expected_core = (
        (("absl", "REQUIRED"), standalone),
        (("Threads", "REQUIRED"), ()),
    )
    if _find_inventory(core_commands) != expected_core:
        errors.append(
            "src/src/CMakeLists.txt: exact standalone/unconditional "
            "find_package provider inventory changed")

    root_core = [
        command for command, scope in exact_command_contexts(root_commands)
        if command.name == "add_subdirectory"
        and scope == ()
        and exact_condition_tokens(command.body) == ("src/src",)
    ]
    root_absl = [
        command for command in root_commands
        if command.name == "add_subdirectory"
        and exact_condition_tokens(command.body) == ("extra/abseil-cpp",)
    ]
    if (len(root_core) != 1 or len(root_absl) != 1 or
            not root_absl[0].offset < root_core[0].offset):
        errors.append(
            "CMakeLists.txt: direct-source Abseil provider must "
            "precede the root src/src edge")

    core_target = [
        command for command in core_commands
        if command.name == "add_library"
        and exact_condition_tokens(command.body)[:1] == ("cxet_lib",)
    ]
    core_threads = [
        command for command, scope in exact_command_contexts(core_commands)
        if command.name == "find_package" and not scope
        and exact_condition_tokens(command.body) == ("Threads", "REQUIRED")
    ]
    liburing_condition = (
        "NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
        '"${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"',
    )
    liburing = [
        command for command, scope in exact_command_contexts(core_commands)
        if command.name == "add_library"
        and exact_condition_tokens(command.body) ==
            ("liburing::uring", "STATIC", "IMPORTED", "GLOBAL")
        and scope == (("if", liburing_condition),)
    ]
    thread_links = [command for command in core_commands
                    if command.name == "target_link_libraries" and "Threads::Threads" in exact_condition_tokens(command.body)]
    target_inventory = [(exact_condition_tokens(command.body), context)
                        for command, context in exact_command_contexts(core_commands)
                        if command in core_target]
    core_declaration_valid = target_inventory == [
        (("cxet_lib", "STATIC", "${CXET_LIB_SOURCES}"), ()),
    ]
    if not core_declaration_valid:
        errors.append(
            "src/src/CMakeLists.txt: cxet_lib must have one unconditional "
            "STATIC declaration")
    if (not core_declaration_valid or len(core_threads) != 1 or not thread_links or
            any(core_threads[0].offset > command.offset for command in thread_links)):
        errors.append("src/src/CMakeLists.txt: Threads provider must precede every actual Threads::Threads link")
    if (len(liburing) != 1 or
            not _exact_if_elseif_fatal_chain(
                core_commands, liburing_condition,
                ("NOT", "TARGET", "liburing::uring"))):
        errors.append(
            "src/src/CMakeLists.txt: build-local liburing imported-provider "
            "fallback must remain an exact one-member FATAL_ERROR branch")


@dataclass(frozen=True)
class _Command:
    name: str
    body: str
    line: int
    offset: int


def _parse(relative: str, text: str, errors: list[str]) -> list[_Command]:
    return scan_commands(relative, text, errors, _Command)


def validate_condition_policy_microcases(errors: list[str]) -> None:
    expected = _ROOT_FULL_FAMILY_CONDITION
    for label, body in (
        ("lowercase", "cxet_full_build AND CXET_FAMILY_SOURCE_GRAPH"),
        ("quoted", '"CXET_FULL_BUILD" AND CXET_FAMILY_SOURCE_GRAPH'),
        ("concatenated", "CXET_FULL_BUILDANDCXET_FAMILY_SOURCE_GRAPH"),
    ):
        if exact_condition_tokens(body) == expected:
            errors.append(
                f"condition-policy self-check accepted {label} root guard")
    if exact_condition_tokens(
            "CXET_FULL_BUILD AND CXET_FAMILY_SOURCE_GRAPH") != expected:
        errors.append("condition-policy self-check rejected baseline root guard")

    full_family_text = (
        "if(CXET_FULL_BUILD AND CXET_FAMILY_SOURCE_GRAPH)\n"
        "  message(FATAL_ERROR incompatible)\nendif()\n")
    full_family_errors: list[str] = []
    validate_root_full_family_guard(
        _parse("<root-full-family>", full_family_text, []),
        full_family_errors)
    if full_family_errors:
        errors.append(
            "condition-policy full/family baseline failed: " +
            "; ".join(full_family_errors))
    early_full_family_errors: list[str] = []
    validate_root_full_family_guard(
        _parse("<root-full-family>", full_family_text.replace(
            "  message", "  return()\n  message"), []),
        early_full_family_errors)
    if not early_full_family_errors:
        errors.append(
            "condition-policy self-check accepted early full/family return")

    compiler_commands = _parse("<root-compiler>", (
        'if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang" OR NOT '
        'CMAKE_CXX_COMPILER_ID MATCHES "Clang")\n'
        "  message(FATAL_ERROR clang-only)\nendif()\n"), [])
    compiler_errors: list[str] = []
    validate_root_compiler_guard(compiler_commands, compiler_errors)
    if compiler_errors:
        errors.append(
            "condition-policy compiler baseline failed: " +
            "; ".join(compiler_errors))
    mutated_compiler = _parse("<root-compiler>", (
        'if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")\n'
        "  message(FATAL_ERROR inverted)\nendif()\n"), [])
    mutation_errors: list[str] = []
    validate_root_compiler_guard(mutated_compiler, mutation_errors)
    if not mutation_errors:
        errors.append(
            "condition-policy self-check accepted substituted compiler guard")
    early_compiler_return = _parse("<root-compiler>", (
        'if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang" OR NOT '
        'CMAKE_CXX_COMPILER_ID MATCHES "Clang")\n'
        "  return()\n"
        "  message(FATAL_ERROR clang-only)\nendif()\n"), [])
    early_compiler_errors: list[str] = []
    validate_root_compiler_guard(
        early_compiler_return, early_compiler_errors)
    if not early_compiler_errors:
        errors.append(
            "condition-policy self-check accepted early compiler return")

    platform_text = (
        'if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")\n'
        "  message(FATAL_ERROR linux-only)\nendif()\n"
        'if(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")\n'
        "  message(FATAL_ERROR x86-only)\nendif()\n")
    platform_errors: list[str] = []
    validate_root_platform_guards(
        _parse("<root-platform>", platform_text, []), platform_errors)
    if platform_errors:
        errors.append(
            "condition-policy platform baseline failed: " +
            "; ".join(platform_errors))
    for label, mutation in (
        ("early return", platform_text.replace(
            "  message(FATAL_ERROR linux-only)",
            "  return()\n  message(FATAL_ERROR linux-only)")),
        ("system substitution", platform_text.replace(
            'CMAKE_SYSTEM_NAME STREQUAL "Linux"',
            'CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux"')),
        ("processor substitution", platform_text.replace(
            'CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64"',
            'CMAKE_SYSTEM_PROCESSOR MATCHES "x86_64|amd64"')),
    ):
        mutation_errors: list[str] = []
        validate_root_platform_guards(
            _parse("<root-platform>", mutation, []), mutation_errors)
        if not mutation_errors:
            errors.append(
                f"condition-policy self-check accepted platform {label}")

    ordered_root = (
        "cmake_minimum_required(VERSION 3.22)\n"
        'include("${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake")\n'
        "project(CXET LANGUAGES C CXX ASM)\n"
        'include("${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake")\n'
        'if(NOT CMAKE_C_COMPILER_ID MATCHES "Clang" OR NOT '
        'CMAKE_CXX_COMPILER_ID MATCHES "Clang")\n'
        "  message(FATAL_ERROR compiler)\nendif()\n"
        'if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")\n'
        "  message(FATAL_ERROR system)\nendif()\n"
        'if(NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64")\n'
        "  message(FATAL_ERROR processor)\nendif()\n"
        "set(CXET_FULL_BUILD ON)\n"
        "set(CXET_FAMILY_SOURCE_GRAPH OFF)\n"
        "if(CXET_FULL_BUILD AND CXET_FAMILY_SOURCE_GRAPH)\n"
        "  message(FATAL_ERROR profiles)\nendif()\n"
        "set(CXET_SAFETY_BUILD OFF)\n"
        "if(CXET_FAMILY_SOURCE_GRAPH AND ( CXET_SAFETY_BUILD OR "
        "CXET_ENABLE_SRC_TESTS ))\n"
        "  message(FATAL_ERROR exclusion)\nendif()\n"
        "file(WRITE output value)\n")
    ordered_errors: list[str] = []
    validate_root_guard_order(
        _parse("<root-order>", ordered_root, []), ordered_errors)
    if ordered_errors:
        errors.append(
            "condition-policy guard-order baseline failed: " +
            "; ".join(ordered_errors))
    for label, mutation in (
        ("effect before profiles", ordered_root.replace(
            "set(CXET_FULL_BUILD ON)",
            "file(WRITE poison value)\nset(CXET_FULL_BUILD ON)", 1)),
        ("transfer before compiler", ordered_root.replace(
            'include("${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake")\n',
            'include("${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake")\nreturn()\n', 1)),
        ("exchange selector substitution", ordered_root.replace(
            "cmake/CxetExchangeSelection.cmake", "cmake/Unreviewed.cmake", 1)),
        ("exchange selector removal", ordered_root.replace(
            'include("${CMAKE_SOURCE_DIR}/cmake/CxetExchangeSelection.cmake")\n', "", 1)),
    ):
        mutation_errors = []
        validate_root_guard_order(
            _parse("<root-order>", mutation, []), mutation_errors)
        if not mutation_errors:
            errors.append(
                f"condition-policy self-check accepted root {label}")

    exclusion_text = (
        "if(CXET_FAMILY_SOURCE_GRAPH AND ( CXET_SAFETY_BUILD OR "
        "CXET_ENABLE_SRC_TESTS ))\n"
        "  message(FATAL_ERROR incompatible)\nendif()\n")
    exclusion_errors: list[str] = []
    validate_root_exclusion_guard(
        _parse("<root-exclusion>", exclusion_text, []), exclusion_errors)
    if exclusion_errors:
        errors.append(
            "condition-policy exclusion baseline failed: " +
            "; ".join(exclusion_errors))
    early_exclusion_errors: list[str] = []
    validate_root_exclusion_guard(
        _parse("<root-exclusion>", exclusion_text.replace(
            "  message", "  return()\n  message"), []),
        early_exclusion_errors)
    if not early_exclusion_errors:
        errors.append(
            "condition-policy self-check accepted early exclusion return")

    provider = "cxet::cxet_lib"
    if not provider_guard_is_fatal(
            f"if(NOT TARGET {provider})\n"
            "  message(FATAL_ERROR missing)\nendif()\n", provider):
        errors.append("condition-policy self-check rejected provider guard")
    aggregate = (
        f"if(NOT TARGET {provider} OR NOT TARGET trading_core::strategy)\n"
        "  message(FATAL_ERROR missing)\nendif()\n")
    if not provider_guard_is_fatal(aggregate, provider):
        errors.append(
            "condition-policy self-check rejected provider OR inventory")
    loop = (
        f"foreach(required_target IN ITEMS {provider} trading_core::strategy)\n"
        "  if(NOT TARGET ${required_target})\n"
        "    message(FATAL_ERROR missing)\n"
        "  endif()\n"
        "endforeach()\n")
    if not provider_guard_is_fatal(loop, provider):
        errors.append(
            "condition-policy self-check rejected provider loop inventory")
    expected_provider_inventory = (
        provider, "trading_core::strategy")
    for label, text in (("aggregate", aggregate), ("loop", loop)):
        if exact_provider_guard_inventory(text) != expected_provider_inventory:
            errors.append(
                f"condition-policy self-check rejected exact {label} "
                "provider inventory")
    for label, mutation in (
        ("extra aggregate member", aggregate.replace(
            "trading_core::strategy)",
            "trading_core::strategy OR NOT TARGET poison::missing)")),
        ("extra loop member", loop.replace(
            "trading_core::strategy)",
            "trading_core::strategy poison::missing)")),
    ):
        if (exact_provider_guard_inventory(mutation) ==
                expected_provider_inventory):
            errors.append(
                f"condition-policy self-check accepted {label}")
    separate_guard = (
        aggregate + "if(NOT TARGET poison::missing)\n"
        "  message(FATAL_ERROR poison)\nendif()\n")
    if exact_provider_guard_inventory(separate_guard) is not None:
        errors.append(
            "condition-policy self-check accepted extra separate guard")
    conditional_provider = "hft-finam-metadata-store"
    reviewed_conditional = (
        (("CXET_EXCHANGE_FINAM",), (conditional_provider,)),)
    conditional_block = (
        "if(CXET_EXCHANGE_FINAM)\n"
        f"  if(NOT TARGET {conditional_provider})\n"
        "    message(FATAL_ERROR missing)\n"
        "  endif()\n"
        "  set(VETRON_FINAM_DEPENDENCY hft-finam-metadata-store)\n"
        "endif()\n")
    conditional_prelude = loop + conditional_block
    if exact_provider_guard_inventory(
            conditional_prelude, conditional_guards=reviewed_conditional) != expected_provider_inventory:
        errors.append(
            "condition-policy self-check rejected reviewed conditional provider")
    if exact_provider_guard_inventory(conditional_prelude) is not None:
        errors.append(
            "condition-policy self-check accepted unselected conditional provider")
    for label, mutation in (
        ("missing guard", loop),
        ("predicate substitution", conditional_prelude.replace(
            "if(CXET_EXCHANGE_FINAM)", "if(FALSE)")),
        ("extra member", conditional_prelude.replace(
            f"if(NOT TARGET {conditional_provider})",
            f"if(NOT TARGET {conditional_provider} OR NOT TARGET poison::missing)")),
        ("early return", conditional_prelude.replace(
            "    message", "    return()\n    message")),
        ("nonfatal block", conditional_prelude.replace(
            "    message(FATAL_ERROR", "    message(STATUS")),
        ("duplicate block", conditional_prelude + conditional_block),
    ):
        if exact_provider_guard_inventory(
                mutation, conditional_guards=reviewed_conditional) is not None:
            errors.append(
                f"condition-policy self-check accepted conditional provider {label}")
    for label, mutation in (
        ("lowercase fatal", "message(fatal_error missing)"),
        ("joined target", f"if(NOTTARGET{provider})"),
    ):
        text = (
            f"if(NOT TARGET {provider})\n"
            "  message(FATAL_ERROR missing)\nendif()\n")
        text = (
            text.replace("message(FATAL_ERROR missing)", mutation)
            if label == "lowercase fatal" else
            text.replace(f"if(NOT TARGET {provider})", mutation)
        )
        if provider_guard_is_fatal(text, provider):
            errors.append(
                f"condition-policy self-check accepted provider {label}")
    for label, mutation in (
        ("unreachable conjunction",
         f"if(FALSE AND NOT TARGET {provider})\n"
         "  message(FATAL_ERROR missing)\nendif()\n"),
        ("conditional outer scope",
         f"if(FALSE)\n  if(NOT TARGET {provider})\n"
         "    message(FATAL_ERROR missing)\n  endif()\nendif()\n"),
        ("mixed OR predicate",
         f"if(NOT TARGET {provider} OR FALSE)\n"
         "  message(FATAL_ERROR missing)\nendif()\n"),
        ("early return",
         f"if(NOT TARGET {provider})\n"
         "  return()\n  message(FATAL_ERROR missing)\nendif()\n"),
        ("loop continue",
         f"foreach(required_target IN ITEMS {provider})\n"
         "  continue()\n  if(NOT TARGET ${required_target})\n"
         "    message(FATAL_ERROR missing)\n  endif()\nendforeach()\n"),
        ("loop target rewrite",
         f"foreach(required_target IN ITEMS {provider})\n"
         "  set(required_target trading_core::strategy)\n"
         "  if(NOT TARGET ${required_target})\n"
         "    message(FATAL_ERROR missing)\n  endif()\nendforeach()\n"),
    ):
        if provider_guard_is_fatal(mutation, provider):
            errors.append(
                f"condition-policy self-check accepted provider {label}")

    app_commands = _parse("<app-guard>", (
        "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
        "  message(FATAL_ERROR standalone)\nendif()\n"
        "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
        "NOT CXET_ROOT_SOURCE_GRAPH)\n"
        "  message(FATAL_ERROR root)\nendif()\n"), [])
    app_errors: list[str] = []
    validate_app_guard_contract("<app-guard>", app_commands, app_errors)
    if app_errors:
        errors.append(
            "condition-policy app baseline failed: " + "; ".join(app_errors))
    joined = _parse("<app-guard>", (
        "if(CMAKE_SOURCE_DIRSTREQUALCMAKE_CURRENT_SOURCE_DIR)\n"
        "  message(FATAL_ERROR standalone)\nendif()\n"
        "if(NOTDEFINEDCXET_ROOT_SOURCE_GRAPH OR "
        "NOTCXET_ROOT_SOURCE_GRAPH)\n"
        "  message(FATAL_ERROR root)\nendif()\n"), [])
    joined_errors: list[str] = []
    validate_app_guard_contract("<app-guard>", joined, joined_errors)
    if not joined_errors:
        errors.append("condition-policy self-check accepted joined app guards")

    for label, mutation in (
        ("early return", (
            "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
            "  return()\n"
            "  message(FATAL_ERROR standalone)\nendif()\n"
            "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
            "NOT CXET_ROOT_SOURCE_GRAPH)\n"
            "  message(FATAL_ERROR root)\nendif()\n")),
        ("preseeded root marker", (
            "set(CXET_ROOT_SOURCE_GRAPH ON)\n"
            "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
            "  message(FATAL_ERROR standalone)\nendif()\n"
            "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
            "NOT CXET_ROOT_SOURCE_GRAPH)\n"
            "  message(FATAL_ERROR root)\nendif()\n")),
        ("rewritten source evidence", (
            "set(CMAKE_SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/parent)\n"
            "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
            "  message(FATAL_ERROR standalone)\nendif()\n"
            "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
            "NOT CXET_ROOT_SOURCE_GRAPH)\n"
            "  message(FATAL_ERROR root)\nendif()\n")),
        ("between-guard marker write", (
            "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
            "  message(FATAL_ERROR standalone)\nendif()\n"
            "set(CXET_ROOT_SOURCE_GRAPH ON)\n"
            "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
            "NOT CXET_ROOT_SOURCE_GRAPH)\n"
            "  message(FATAL_ERROR root)\nendif()\n")),
        ("project hook before guards", (
            "project(untrusted LANGUAGES CXX)\n"
            "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
            "  message(FATAL_ERROR standalone)\nendif()\n"
            "if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR "
            "NOT CXET_ROOT_SOURCE_GRAPH)\n"
            "  message(FATAL_ERROR root)\nendif()\n")),
    ):
        mutation_errors: list[str] = []
        validate_app_guard_contract(
            "<app-guard>", _parse("<app-guard>", mutation, []),
            mutation_errors)
        if not mutation_errors:
            errors.append(
                f"condition-policy self-check accepted app {label}")

    root_text = (
        "add_subdirectory(extra/abseil-cpp)\n"
        "add_subdirectory(src/src)\n")
    core_text = (
        "if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)\n"
        "  find_package(absl REQUIRED)\nendif()\n"
        "find_package(Threads REQUIRED)\n"
        "if(NOT TARGET liburing::uring AND EXISTS "
        "\"${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure\")\n"
        "  add_library(liburing::uring STATIC IMPORTED GLOBAL)\n"
        "elseif(NOT TARGET liburing::uring)\n"
        "  message(FATAL_ERROR missing)\nendif()\n"
        "add_library(cxet_lib STATIC ${CXET_LIB_SOURCES})\n"
        "target_link_libraries(cxet_lib PRIVATE Threads::Threads)\n")
    root_commands = _parse("<root-provider>", root_text, [])
    core_commands = _parse("<core-provider>", core_text, [])
    provider_errors: list[str] = []
    validate_root_provider_contract(
        root_commands, core_commands, provider_errors)
    if provider_errors:
        errors.append(
            "condition-policy provider baseline failed: " +
            "; ".join(provider_errors))
    for label, mutation in (
        ("shared core", core_text.replace("cxet_lib STATIC", "cxet_lib SHARED")),
        ("untyped core", core_text.replace("cxet_lib STATIC", "cxet_lib")),
        ("conditional core", core_text.replace(
            "add_library(cxet_lib STATIC ${CXET_LIB_SOURCES})\n",
            "if(DEFINED CXET_BUILD_OWNER)\n"
            "add_library(cxet_lib STATIC ${CXET_LIB_SOURCES})\nendif()\n")),
    ):
        mutation_errors: list[str] = []
        validate_root_provider_contract(
            root_commands, _parse("<core-provider>", mutation, []),
            mutation_errors)
        if not mutation_errors:
            errors.append(f"condition-policy self-check accepted {label}")
    early_liburing_errors: list[str] = []
    validate_root_provider_contract(
        root_commands,
        _parse("<core-provider>", core_text.replace(
            "elseif(NOT TARGET liburing::uring)\n"
            "  message(FATAL_ERROR missing)",
            "elseif(NOT TARGET liburing::uring)\n"
            "  return()\n"
            "  message(FATAL_ERROR missing)"), []),
        early_liburing_errors)
    if not early_liburing_errors:
        errors.append(
            "condition-policy self-check accepted early liburing return")
    relocated_liburing_errors: list[str] = []
    validate_root_provider_contract(
        root_commands,
        _parse("<core-provider>", core_text.replace(
            "elseif(NOT TARGET liburing::uring)\n"
            "  message(FATAL_ERROR missing)\nendif()",
            "endif()\nif(FALSE)\n"
            "elseif(NOT TARGET liburing::uring)\n"
            "  message(FATAL_ERROR missing)\nendif()"), []),
        relocated_liburing_errors)
    if not relocated_liburing_errors:
        errors.append(
            "condition-policy self-check accepted relocated liburing "
            "fallback")
    for label, mutation in (
        ("production OpenSSL", "find_package(OpenSSL REQUIRED)\n" + root_text),
        ("production SSL oracle", "find_package(OpenSSL REQUIRED COMPONENTS SSL)\n" + root_text),
        ("Abseil removal", root_text.replace(
            "add_subdirectory(extra/abseil-cpp)\n", "", 1)),
        ("Abseil after core", "add_subdirectory(src/src)\n"
            "add_subdirectory(extra/abseil-cpp)\n"),
    ):
        mutation_errors: list[str] = []
        validate_root_provider_contract(
            _parse("<root-provider>", mutation, []),
            core_commands, mutation_errors)
        if not mutation_errors:
            errors.append(
                f"condition-policy self-check accepted provider {label}")
