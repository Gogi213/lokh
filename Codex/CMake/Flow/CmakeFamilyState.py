"""Small state operations shared by the bounded CMake interpreter."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

from CMake.Syntax.CmakeFamilyLexer import cmake_argument_value, split_top_level


SYNTHETIC_BINARY_ROOT = "__CXET_CMAKE_BINARY__"
# Opt-in target visibility for one exact configure.  This key cannot be a
# source scope and must never be read as a directory's BUILDSYSTEM_TARGETS.
SHARED_TARGET_NAMESPACE = ("\x00CXET_CONFIGURE_TARGET_NAMESPACE\x00", ())
NATIVE_PREREQUISITE_NAMESPACE = ("\x00CXET_NATIVE_PREREQUISITES\x00", ())
# Internal branch marker.  CMake source cannot contain NUL, so this cannot be
# confused with an explicit empty list element.  It records a *defined-empty*
# branch without turning that branch into one foreach iteration.
ZERO_LIST_ALTERNATIVE = "\x00CXET_DEFINED_EMPTY_LIST\x00"
# A mixed live-path union containing both an empty and a non-empty value must
# not silently collapse to the non-empty value when it reaches a proof-bearing
# command (notably target sources and links).  Keep an unresolved carrier in
# that expansion so downstream exact policies fail closed.
UNCERTAIN_EMPTY_ALTERNATIVE = "$<CXET_INTERNAL_UNCERTAIN_EMPTY>"
UNCERTAIN_BRANCH_ALTERNATIVE = "$<CXET_INTERNAL_UNCERTAIN_BRANCH_VALUE>"
UNSUPPORTED_CALL_ARGUMENT = "$<CXET_INTERNAL_UNSUPPORTED_CALL_ARGUMENT>"
_PATH_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_BRACKET_ARGUMENT = re.compile(r"\[(=*)\[([\s\S]*)\]\1\]")
_QUOTED_ARGUMENT = re.compile(r'"(?:\\[\s\S]|[^"\\])*"')


def reviewed_source_probe_decisions(commands, repository_root):
    """Identify only fresh, complete canonical lowered ISA-probe recipes.

    These decisions remain in every raw execution path. Their identities can
    classify an unconditional source declaration independently of whether the
    selected compiler passes its prerequisite probes; they never prove support.
    """
    from CMake.Flow.CmakeFamilyGraph import parse_commands
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    from CMake.Syntax.CmakeFamilyContext import StructuralTracker
    from Family.Profile.CxetFamilySelectorActivation import (
        _verified, _literal, _hot_projection,
    )
    relative = "cmake/CxetHotOptions.cmake"
    try:
        source = (repository_root / relative).read_text()
        errors = []
        parsed = parse_commands(relative, source, errors)
        _verified(repository_root, relative, source, parsed, errors)
        probes = tuple(tuple(pair.split("|")) for pair in _literal(parsed, "_CXET_HOT_PROBES"))
        if errors or any(len(pair) != 2 for pair in probes):
            return frozenset()
        expected = _hot_projection(parsed, probes, _literal(parsed, "_CXET_OPTIONAL_HOT_SWITCHES"))
    except (OSError, ValueError):
        return frozenset()
    groups = {}
    for active in commands:
        if active.relative == relative:
            groups.setdefault((active.scope, active.directory, active.execution_chain), []).append(active)
    result = set()
    probe_tokens = {(feature, "AND", "NOT", "_CXET_HOT_SUPPORTED_" + feature) for feature, _ in probes}
    for members in groups.values():
        if [active.command for active in members] != expected:
            continue
        errors = []
        tracker = StructuralTracker(relative, (), errors)
        coherent = True
        for active in members:
            coherent = coherent and active.structural_context == tracker.context()
            tracker.advance(active.command.name, tuple(cmake_list_words(active.command.body)),
                            active.command.line, active.ordinal)
        tracker.finish()
        if errors or not coherent:
            continue
        for active in members:
            if (active.command.name == "if" and active.command.line == 88 and
                    tuple(cmake_list_words(active.command.body)) in probe_tokens):
                result.add(f"direct:{active.scope}:{active.ordinal}:iteration:root")
    return frozenset(result)


def source_prefix_is_independent(paths, probes, completed_boundaries):
    """Classify prefixes without changing raw path or successful-EOF evidence."""
    return bool(paths) and all(all(
        arm == 1 and (decision in probes or decision in completed_boundaries)
        for decision, arm in path) for path in paths)


def reviewed_root_absl_target(commands, scope_values, repository_root):
    """Prove the one prerequisite supplied by the actual reviewed root vendor."""
    from CMake.Flow.CmakeFamilyExecutionIdentity import ROOT as authority_root
    # The reviewed external-tree authority below is rooted in this checkout.
    # A copied root recipe must not borrow another directory's vendor proof.
    if repository_root != authority_root:
        return {}
    core = "src/src/CMakeLists.txt"
    selected = (scope_values or {}).get(core, {})
    if (not any(active.scope == core and active.relative == core for active in commands) or
            len(selected.get("CXET_BUILD_OWNER", ())) != 1 or
            len(selected.get("CXET_FAMILY_PROFILE", ())) != 1):
        return {}
    from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_external_authority, unsymlinked_regular_path
    from CMake.Root.CmakeFamilyRootGraphCommon import parse_commands, words
    from CMake.Root.CmakeFamilyRootDialect import validate_root_dialect
    from CMake.Root.CmakeFamilyRootPolicy import validate_root_ownership_effects
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    root_file = repository_root / "CMakeLists.txt"
    if not unsymlinked_regular_path(root_file, repository_root):
        return {}
    try:
        errors = []
        parsed = parse_commands("CMakeLists.txt", root_file.read_text(), errors)
        recipe = [(command.name, tuple(cmake_list_words(command.body))) for command in parsed]
        expected = [
            ("function", ("cxet_add_abseil_subdirectory",)),
            ("set", ("CMAKE_CXX_VISIBILITY_PRESET", "hidden")),
            ("set", ("CMAKE_VISIBILITY_INLINES_HIDDEN", "ON")),
            ("add_subdirectory", ("extra/abseil-cpp",)),
            ("endfunction", ()),
        ]
        definitions = [index for index, item in enumerate(recipe) if item == expected[0]]
        calls = [command for command in parsed if command.name == "cxet_add_abseil_subdirectory"]
        core_edges = [command for command in parsed if command.name == "add_subdirectory" and
                      cmake_list_words(command.body) == ["src/src"]]
        if (len(definitions) != 1 or recipe[definitions[0]:definitions[0] + len(expected)] != expected or
                len(calls) != 1 or calls[0].body.strip() or len(core_edges) != 1 or
                not parsed[definitions[0] + len(expected) - 1].offset < calls[0].offset < core_edges[0].offset):
            return {}
        cache = {name: values[0] for name, values in selected.items()
                 if len(values) == 1 and not any(marker in values[0] for marker in ("${", "$<", "$CACHE{", "$ENV{"))}
        evidence = validate_root_dialect(parsed, words, errors, profiles={"source-presence": cache})
        validate_root_ownership_effects(parsed, words, errors, evidence.viable_offsets)
        profile = evidence.profiles.get("source-presence")
        if (errors or profile is None or not profile.live_eof_paths or
                not profile.covers_all((calls[0].offset, core_edges[0].offset)) or
                not reviewed_external_authority("abseil-cpp")):
            return {}
    except (OSError, ValueError):
        return {}
    return {"absl::flat_hash_set": "LIBRARY"}


def active_binary_dir(active) -> str:
    """Return the non-filesystem stand-in for an active CMake binary dir."""
    relative = active.binary_base.as_posix()
    if relative == ".":
        return SYNTHETIC_BINARY_ROOT
    return f"{SYNTHETIC_BINARY_ROOT}/{relative}"


def directory_targets_before(targets, active):
    entries = targets.get((active.scope, active.directory), {})
    return {
        target: kind for target, (kind, ordinal) in entries.items()
        if ordinal < active.ordinal
    }


def configure_targets_before(targets, active):
    """Return only earlier independently definite shared target declarations.

    An omitted target remains unknown, not proven absent.  Independent-root
    tables have no shared namespace and therefore expose no configure facts.
    """
    known = {
        target: kind
        for target, (kind, ordinal) in targets.get(SHARED_TARGET_NAMESPACE, {}).items()
        if ordinal < active.ordinal
    }
    # Absence/filesystem facts are issued only by the complete source catalog
    # for this exact native prerequisite command, never for an arbitrary name.
    known.update(targets.get(NATIVE_PREREQUISITE_NAMESPACE, {}).get(active.ordinal, {}))
    return known


def expand_active_tokens(
    active,
    tokens: list[str] | tuple[str, ...],
    snapshots,
    repository_root: Path,
    overrides: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    state = dict(snapshots.values.get(active.ordinal, {}))
    state.update({
        "CMAKE_CURRENT_SOURCE_DIR": (active.source_base.as_posix(),),
        "CMAKE_CURRENT_LIST_DIR": (Path(active.relative).parent.as_posix(),),
        "CMAKE_CURRENT_BINARY_DIR": (active_binary_dir(active),),
        "CMAKE_SOURCE_DIR": (repository_root.as_posix(),),
        "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
    })
    state.setdefault("PROJECT_SOURCE_DIR", (repository_root.as_posix(),))
    state.setdefault("PROJECT_BINARY_DIR", (SYNTHETIC_BINARY_ROOT,))
    return expand_variable_tokens(tokens, state, overrides)


def expand_context_tokens(
    active,
    tokens: list[str] | tuple[str, ...],
    state: dict[str, tuple[str, ...]],
    repository_root: Path,
    preserve_empty: bool = False,
) -> list[str]:
    contextual = dict(state)
    contextual.update({
        "CMAKE_CURRENT_SOURCE_DIR": (
            (repository_root / active.source_base).as_posix(),),
        "CMAKE_CURRENT_LIST_DIR": (
            (repository_root / Path(active.relative).parent).as_posix(),),
        "CMAKE_CURRENT_BINARY_DIR": (active_binary_dir(active),),
        "CMAKE_SOURCE_DIR": (repository_root.as_posix(),),
        "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
    })
    contextual.setdefault("PROJECT_SOURCE_DIR", (repository_root.as_posix(),))
    contextual.setdefault("PROJECT_BINARY_DIR", (SYNTHETIC_BINARY_ROOT,))
    return expand_variable_tokens(
        tokens, contextual, preserve_empty=preserve_empty)


def expand_context_callable_arguments(
    active,
    tokens: list[str] | tuple[str, ...],
    state: dict[str, tuple[str, ...]],
    repository_root: Path,
    errors: list[str] | None = None,
    context: str = "active CMake callable",
) -> list[str]:
    """Contextualize and bind a call without losing argument positions."""
    contextual = dict(state)
    contextual.update({
        "CMAKE_CURRENT_SOURCE_DIR": (
            (repository_root / active.source_base).as_posix(),),
        "CMAKE_CURRENT_LIST_DIR": (
            (repository_root / Path(active.relative).parent).as_posix(),),
        "CMAKE_CURRENT_BINARY_DIR": (active_binary_dir(active),),
        "CMAKE_SOURCE_DIR": (repository_root.as_posix(),),
        "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
    })
    contextual.setdefault("PROJECT_SOURCE_DIR", (repository_root.as_posix(),))
    contextual.setdefault("PROJECT_BINARY_DIR", (SYNTHETIC_BINARY_ROOT,))
    return expand_callable_arguments(
        tokens, contextual, errors=errors, context=context)


def normalize_synthetic_binary_path(value: str) -> str | None:
    """Normalize a modeled binary path and reject lexical root escape."""
    if any(marker in value for marker in _PATH_CARRIERS):
        return None
    normalized = posixpath.normpath(value.replace("\\", "/"))
    if (normalized == SYNTHETIC_BINARY_ROOT or
            normalized.startswith(SYNTHETIC_BINARY_ROOT + "/")):
        return normalized
    return None


def expand_variable_tokens(
    tokens: list[str] | tuple[str, ...],
    state: dict[str, tuple[str, ...]],
    overrides: dict[str, tuple[str, ...]] | None = None,
    expanding: frozenset[str] = frozenset(),
    preserve_empty: bool = False,
) -> list[str]:
    """Expand bounded normal-variable alternatives without evaluating genex."""
    result: list[str] = []
    overrides = overrides or {}
    for raw in tokens:
        if raw == ZERO_LIST_ALTERNATIVE:
            continue
        value = cmake_argument_value(raw)
        exact = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
        if exact is not None:
            variable = exact.group(1)
            values = overrides.get(variable, state.get(variable))
            if values is None or variable in expanding:
                result.append(value)
            else:
                concrete = tuple(
                    item for item in values
                    if item != ZERO_LIST_ALTERNATIVE)
                result.extend(expand_variable_tokens(
                    concrete, state, overrides, expanding | {variable},
                    preserve_empty))
                if ZERO_LIST_ALTERNATIVE in values and concrete:
                    result.append(UNCERTAIN_EMPTY_ALTERNATIVE)
            continue

        variants = [""]
        cursor = 0
        for reference in re.finditer(
                r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value):
            literal = value[cursor:reference.start()]
            variable = reference.group(1)
            values = overrides.get(variable, state.get(variable))
            if values is None or variable in expanding:
                replacements = [reference.group(0)]
            else:
                replacements = []
                alternatives = values or (ZERO_LIST_ALTERNATIVE,)
                mixed_empty = (
                    ZERO_LIST_ALTERNATIVE in alternatives and
                    any(item != ZERO_LIST_ALTERNATIVE
                        for item in alternatives))
                for item in alternatives:
                    if item == ZERO_LIST_ALTERNATIVE:
                        replacements.append(
                            UNCERTAIN_EMPTY_ALTERNATIVE
                            if mixed_empty else "")
                        continue
                    if not item:
                        replacements.append("")
                    else:
                        replacements.extend(expand_variable_tokens(
                            (item,), state, overrides,
                            expanding | {variable}, preserve_empty) or ("",))
            variants = [
                prefix + literal + replacement
                for prefix in variants for replacement in replacements]
            cursor = reference.end()
        for variant in (item + value[cursor:] for item in variants):
            split = split_top_level(variant, ";")
            parts = split if preserve_empty else [part for part in split if part]
            if parts:
                result.extend(parts)
            elif variant or preserve_empty:
                result.append(variant)
    return result


def expand_callable_arguments(
    tokens: list[str] | tuple[str, ...],
    state: dict[str, tuple[str, ...]],
    overrides: dict[str, tuple[str, ...]] | None = None,
    errors: list[str] | None = None,
    context: str = "active CMake callable",
) -> list[str]:
    """Expand one CMake call while retaining scalar argument boundaries.

    A quoted or bracket argument occupies exactly one formal position even if
    its value contains a semicolon or is empty.  Its formal may later be
    expanded unquoted by the callable body, where CMake list splitting applies.
    """
    result: list[str] = []
    for raw in tokens:
        bracket = _BRACKET_ARGUMENT.fullmatch(raw)
        if bracket is not None:
            result.append(bracket.group(2))
            continue
        if '"' in raw:
            if _QUOTED_ARGUMENT.fullmatch(raw) is None:
                if errors is not None:
                    errors.append(
                        f"{context}: mixed quoted/unquoted callable argument "
                        "is unsupported")
                result.append(UNSUPPORTED_CALL_ARGUMENT)
                continue
            expanded = expand_variable_tokens(
                (raw,), state, overrides, preserve_empty=True)
            result.append(";".join(expanded))
            continue
        result.extend(expand_variable_tokens(
            (raw,), state, overrides, preserve_empty=True))
    return result


def validate_callable_argument_microcases(errors: list[str]) -> None:
    """Pin CMake's call-position/list behavior used by source ownership."""
    state = {"LIST": ("safe.cpp", "/tmp/foreign.cpp")}
    quoted = expand_callable_arguments(('"${LIST}"',), state)
    bound = argument_overrides(("sources",), quoted)
    exposed = expand_variable_tokens(("${sources}",), state, bound)
    if quoted != ["safe.cpp;/tmp/foreign.cpp"] or exposed != [
            "safe.cpp", "/tmp/foreign.cpp"]:
        errors.append(
            "callable argument self-check lost quoted list provenance")

    positional = expand_callable_arguments(
        ('""', "/tmp/foreign.cpp", "safe.cpp"), {})
    bound = argument_overrides(("unused", "source"), positional)
    if (positional != ["", "/tmp/foreign.cpp", "safe.cpp"] or
            bound.get("source") != ("/tmp/foreign.cpp",)):
        errors.append(
            "callable argument self-check shifted an explicit empty argument")

    bracket = expand_callable_arguments(("[[${LIST};literal]]",), state)
    if bracket != ["${LIST};literal"]:
        errors.append(
            "callable argument self-check expanded a bracket argument")


def merge_variable_states(
    states: list[dict[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    """Union branches, preserving absent and explicitly empty alternatives."""
    if len(states) == 1:
        # This is one concrete sequential path, not a branch union.  Repeated
        # list elements (for example repeated --required-strategy keywords)
        # are semantically observable and must retain order/multiplicity.
        return dict(states[0])
    keys: list[str] = []
    for state in states:
        for variable in state:
            if variable not in keys:
                keys.append(variable)
    result: dict[str, tuple[str, ...]] = {}
    for variable in keys:
        first = states[0].get(variable)
        if first is not None and all(state.get(variable) == first for state in states[1:]):
            # An unrelated branch may leave an exact list unchanged. Preserve
            # its empty value, order and duplicates instead of inventing an
            # empty alternative that survives a later guaranteed APPEND.
            result[variable] = first
            continue
        values: list[str] = []
        branch_signatures: list[tuple[str, ...]] = []
        for state in states:
            branch_values = state.get(variable)
            if branch_values is None:
                branch_values = (f"${{{variable}}}",)
            elif not branch_values:
                branch_values = (ZERO_LIST_ALTERNATIVE,)
            branch_signatures.append(branch_values)
            for value in branch_values:
                if value not in values:
                    values.append(value)
        if (len(set(branch_signatures)) > 1 and
                UNCERTAIN_BRANCH_ALTERNATIVE not in values):
            values.append(UNCERTAIN_BRANCH_ALTERNATIVE)
        result[variable] = tuple(values)
    return result


def iteration_bindings(loop_frames) -> tuple[dict[str, tuple[str, ...]], ...]:
    """Return one scalar override map per statically modeled loop iteration."""
    bindings: list[dict[str, tuple[str, ...]]] = [{}]
    for frame in loop_frames:
        if not frame.current_viable or not frame.values:
            return ()
        bindings = [
            {**binding, frame.variable: (value,)}
            for binding in bindings
            for value in frame.values
        ]
    return tuple(bindings)


def argument_overrides(
    definition: tuple[str, ...],
    arguments: list[str],
) -> dict[str, tuple[str, ...]]:
    result = {
        parameter: ((arguments[index],) if index < len(arguments) else ())
        for index, parameter in enumerate(definition)
    }
    result["ARGN"] = tuple(arguments[len(definition):])
    result["ARGV"] = tuple(arguments)
    result["ARGC"] = (str(len(arguments)),)
    for index, argument in enumerate(arguments):
        result[f"ARGV{index}"] = (argument,)
    return result
