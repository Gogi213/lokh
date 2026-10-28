#!/usr/bin/env python3
"""Small deterministic CMake lexer/scope helpers for family static checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from CMake.Flow.CmakeFamilyMutations import (
    apply_list_command,
    apply_string_command,
    has_unresolved_cmake_carrier,
)
from CMake.Policy.CmakeFamilyCachePolicy import (
    approved_direct_cache_set,
    approved_direct_option,
)
from CMake.Syntax.CmakeFamilyBindings import (
    expand_foreach_values,
    parse_foreach_binding,
)
from CMake.Policy.CmakeFamilyEffectPolicy import (
    approved_effect_set,
    effect_variable,
    selector_variable,
)
from CMake.Syntax.CmakeFamilyDialect import (
    TRUSTED_BUILTIN_INCLUDES as APPROVED_SYSTEM_MODULE_INCLUDES,
)
from CMake.Policy.CmakeFamilyExternalEdges import validate_active_external_edge
from CMake.Syntax.CmakeFamilyLexer import (
    cmake_list_words,
    scan_commands,
    split_top_level,
    strip_cmake_comments,
    words,
)
from CMake.Flow.CmakeFamilyState import (
    SYNTHETIC_BINARY_ROOT,
    SHARED_TARGET_NAMESPACE,
    active_binary_dir,
    argument_overrides,
    directory_targets_before as _directory_targets_before,
    configure_targets_before as _configure_targets_before,
    expand_callable_arguments,
    expand_context_callable_arguments as _expand_context_callable_arguments,
    expand_context_tokens as _expand_context_tokens,
    expand_variable_tokens,
    merge_variable_states,
    reviewed_source_probe_decisions,
    reviewed_root_absl_target,
    source_prefix_is_independent,
)
from CMake.Flow.CmakeFamilyFlow import (
    NO_PATHS,
    ExecutionChainManager,
    FunctionModel,
    IteratingFlowController,
    InstantiatedCommand,
    PathSet,
    ConditionalStateFrame as _ConditionalFrame,
    LoopStateFrame as _LoopFrame,
    VariableSnapshots,
    bounded_intersection,
    function_model,
    paths_cover,
    paths_intersect,
    structural_context_possible,
    trace_callable_success,
)
from CMake.Policy.CmakeFamilySetPolicy import (
    approved_vetron_wasm_parent_scope,
    expanded_variable_name,
    parse_variable_signature,
)
from CMake.Flow.CmakeFamilyWriters import apply_output_writer
from CMake.Policy.CmakeFamilyProgramPolicy import ProgramClearance
from CMake.Syntax.CmakeFamilyPaths import logical_relative_path, normalize_project_source_path
from CMake.Safety.CmakeFamilySafetyPolicy import approved_safety_parent_scope
from CMake.Policy.CmakeFamilyLoopPolicy import reviewed_scalar_iteration_locals
from CMake.Syntax.CmakeFamilyContext import (
    StructuralContext,
    StructuralTracker,
    require_project_edges,
    reviewed_source_return,
    validate_project_edge,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class Command:
    name: str
    body: str
    line: int


@dataclass(frozen=True)
class ActiveCommand:
    scope: str
    relative: str
    source_base: Path
    binary_base: Path
    directory: tuple[str, ...]
    command: Command
    ordinal: int
    structural_context: StructuralContext = ()
    execution_chain: tuple[
        tuple[tuple[str, ...], str], ...
    ] = ()


def parse_commands(relative: str, text: str, errors: list[str]) -> list[Command]:
    return scan_commands(
        relative,
        text,
        errors,
        lambda name, body, line, _offset: Command(name, body, line),
    )


def compose_active_commands(
    root: Path,
    files: dict[str, tuple[str, list[Command]]],
    family_roots: tuple[str, ...],
    approved_external_subdirectories: set[str],
    errors: list[str],
    *,
    initial_values_by_scope: dict[
        str, dict[str, tuple[str, ...]]
    ] | None = None,
) -> list[ActiveCommand]:
    """Compose includes and first-party subdirectories in CMake execution order."""
    result: list[ActiveCommand] = []
    seen_directories: dict[str, tuple[str, Path, Path]] = {}
    seen_external_sources: set[str] = set()
    seen_project_edges: set[tuple[str, int, str, str]] = set()

    def completed_source_targets():
        # A guarded reuse edge may refer to a previously composed independent
        # provider root. Only direct unconditional literal source declarations
        # from a root with no possible early termination grant presence here.
        # No absence, callable, imported or branch-derived fact is inferred.
        terminated_roots = {item.scope for item in result if item.command.name in {
            "message", "return", "break", "continue"}}
        known = {}
        for item in result:
            if (item.scope in terminated_roots or item.structural_context or
                    item.relative != item.scope or item.command.name not in {
                        "add_library", "add_executable", "add_custom_target"}):
                continue
            tokens = cmake_list_words(item.command.body)
            if not tokens or any(marker in tokens[0] for marker in ("$", "\\", ";")) or "IMPORTED" in tokens:
                continue
            if "ALIAS" in tokens[1:]:
                if len(tokens) != 3 or tokens[1] != "ALIAS" or tokens[2] not in known:
                    continue
            known[tokens[0]] = "SOURCE_DECLARED"
        return known

    def source_candidates(
        raw: str,
        active: ActiveCommand,
        include: bool,
    ) -> list[Path]:
        if "\\" in raw:
            return []
        value = raw
        replacements = {
            "${CMAKE_CURRENT_SOURCE_DIR}": active.source_base.as_posix(),
            "${CMAKE_CURRENT_LIST_DIR}": Path(active.relative).parent.as_posix(),
            "${CMAKE_SOURCE_DIR}": ".",
        }
        rooted = any(marker in raw for marker in replacements)
        for marker, replacement in replacements.items():
            value = value.replace(marker, replacement)
        if has_unresolved_cmake_carrier(value) or "$<" in value:
            return []
        path = Path(value)
        if path.is_absolute():
            return [path]
        if rooted:
            return [root / path]
        bases = (
            (Path(active.relative).parent, active.source_base)
            if include else (active.source_base,)
        )
        return [root / base / path for base in bases]

    def repo_relative(candidate: Path) -> str | None:
        try:
            return candidate.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return None

    def resolve_include(active: ActiveCommand) -> str | None:
        command_words = cmake_list_words(active.command.body)
        if len(command_words) != 1:
            errors.append(
                f"{active.relative}:{active.command.line}: include() must "
                "have one exact module/path and no RESULT_VARIABLE")
            return None
        raw = command_words[0]
        candidates = source_candidates(raw, active, True)
        for candidate in candidates:
            relative = repo_relative(candidate)
            if relative in files:
                return relative
        if raw in APPROVED_SYSTEM_MODULE_INCLUDES:
            return None
        errors.append(
            f"{active.relative}:{active.command.line}: unresolved/unapproved "
            f"include carrier {raw}"
        )
        return None

    def resolve_binary_base(
        active: ActiveCommand,
        raw: str | None,
        child_source: Path,
    ) -> Path | None:
        if raw is None:
            try:
                suffix = child_source.relative_to(active.source_base)
            except ValueError:
                return None
            return logical_relative_path(suffix.as_posix(), active.binary_base)
        value = raw
        replacements = {
            "${CMAKE_CURRENT_BINARY_DIR}": active.binary_base.as_posix(),
            "${CMAKE_BINARY_DIR}": ".",
        }
        rooted = any(marker in raw for marker in replacements)
        for marker, replacement in replacements.items():
            value = value.replace(marker, replacement)
        if has_unresolved_cmake_carrier(value) or "$<" in value:
            return None
        return logical_relative_path(
            value, Path() if rooted else active.binary_base)

    def resolve_subdirectory(
        active: ActiveCommand,
    ) -> tuple[str, Path, Path] | None:
        command_words = cmake_list_words(active.command.body)
        if not command_words:
            errors.append(
                f"{active.relative}:{active.command.line}: empty add_subdirectory")
            return None
        raw_source = command_words[0]
        candidates = source_candidates(raw_source, active, False)
        if not candidates:
            errors.append(
                f"{active.relative}:{active.command.line}: unresolved first-party "
                f"add_subdirectory source {raw_source}"
            )
            return None
        source_relative = repo_relative(candidates[0])
        if source_relative is None:
            errors.append(
                f"{active.relative}:{active.command.line}: add_subdirectory "
                f"escapes repository root: {raw_source}"
            )
            return None
        source_base = Path(source_relative)
        if source_relative in approved_external_subdirectories:
            validate_active_external_edge(
                active, source_relative, seen_external_sources, errors)
            return None
        child_relative = (source_base / "CMakeLists.txt").as_posix()
        if child_relative not in files:
            errors.append(
                f"{active.relative}:{active.command.line}: first-party "
                f"add_subdirectory has no CMakeLists.txt: {raw_source}"
            )
            return None
        binary_raw = (
            command_words[1]
            if len(command_words) > 1 and command_words[1] not in {
                "EXCLUDE_FROM_ALL", "SYSTEM"}
            else None
        )
        binary_base = resolve_binary_base(active, binary_raw, source_base)
        if binary_base is None:
            errors.append(
                f"{active.relative}:{active.command.line}: unresolved/escaping "
                f"add_subdirectory binary scope {binary_raw or raw_source}"
            )
            return None
        return child_relative, source_base, binary_base

    def append_list(
        scope: str,
        relative: str,
        source_base: Path,
        binary_base: Path,
        directory: tuple[str, ...],
        include_stack: tuple[str, ...],
        directory_stack: tuple[str, ...],
        inherited_context: StructuralContext,
        execution_chain: tuple[
            tuple[tuple[str, ...], str], ...
        ],
    ) -> None:
        if relative in include_stack:
            errors.append(
                f"active family include cycle in {scope}: "
                + " -> ".join(include_stack + (relative,))
            )
            return
        entry = files.get(relative)
        if entry is None:
            errors.append(f"active family CMake file is missing: {relative}")
            return
        callable_stack: list[str] = []
        returned = False
        tracker = StructuralTracker(relative, inherited_context, errors)
        for command in entry[1]:
            active = ActiveCommand(
                scope,
                relative,
                source_base,
                binary_base,
                directory,
                command,
                len(result),
                tracker.context(),
                execution_chain,
            )
            result.append(active)
            if command.name in {"function", "macro"}:
                callable_stack.append(command.name)
                tracker.advance(
                    command.name, tuple(cmake_list_words(command.body)),
                    command.line, active.ordinal)
                continue
            if command.name in {"endfunction", "endmacro"}:
                if callable_stack:
                    callable_stack.pop()
                tracker.advance(
                    command.name, tuple(cmake_list_words(command.body)),
                    command.line, active.ordinal)
                continue
            if callable_stack:
                # Definition bodies execute only when called. Traversing an
                # include/subdirectory here would shift it to parse time.
                tracker.advance(
                    command.name, tuple(cmake_list_words(command.body)),
                    command.line, active.ordinal)
                continue
            if command.name == "return" and reviewed_source_return(
                    active, entry[0], entry[1], (initial_values_by_scope or {}).get(scope)):
                returned = True
            if command.name == "include":
                if not structural_context_possible(
                        active.structural_context,
                        (initial_values_by_scope or {}).get(scope)):
                    tracker.advance(
                        command.name, tuple(cmake_list_words(command.body)),
                        command.line, active.ordinal)
                    continue
                included = resolve_include(active)
                if included is not None:
                    validate_project_edge(
                        active, included, seen_project_edges, errors)
                    if returned:
                        tracker.advance(command.name, tuple(cmake_list_words(command.body)),
                                        command.line, active.ordinal)
                        continue
                    append_list(
                        scope, included, source_base, binary_base, directory,
                        include_stack + (relative,), directory_stack,
                        active.structural_context,
                        execution_chain + ((directory, included),))
            elif command.name == "add_subdirectory":
                if not structural_context_possible(
                        active.structural_context,
                        (initial_values_by_scope or {}).get(scope)):
                    tracker.advance(
                        command.name, tuple(cmake_list_words(command.body)),
                        command.line, active.ordinal)
                    continue
                child = resolve_subdirectory(active)
                if child is None:
                    tracker.advance(
                        command.name, tuple(cmake_list_words(command.body)),
                        command.line, active.ordinal)
                    continue
                child_relative, child_source, child_binary = child
                validate_project_edge(
                    active, child_relative, seen_project_edges, errors)
                if returned:
                    tracker.advance(command.name, tuple(cmake_list_words(command.body)),
                                    command.line, active.ordinal)
                    continue
                if not structural_context_possible(
                        active.structural_context,
                        (initial_values_by_scope or {}).get(scope),
                        known_targets=completed_source_targets()):
                    tracker.advance(command.name, tuple(cmake_list_words(command.body)),
                                    command.line, active.ordinal)
                    continue
                if child_relative in directory_stack:
                    errors.append(
                        f"active family add_subdirectory cycle in {scope}: "
                        + " -> ".join(directory_stack + (child_relative,))
                    )
                    tracker.advance(
                        command.name, tuple(cmake_list_words(command.body)),
                        command.line, active.ordinal)
                    continue
                context = (scope, child_source, child_binary)
                previous = seen_directories.get(child_relative)
                if previous is not None:
                    detail = (
                        "conflicting scopes"
                        if previous[1:] != context[1:] else
                        "duplicate active invocation"
                    )
                    errors.append(
                        f"{active.relative}:{command.line}: first-party "
                        f"subdirectory {child_relative} has {detail}; already "
                        f"owned by active scope {previous[0]}"
                    )
                    tracker.advance(
                        command.name, tuple(cmake_list_words(command.body)),
                        command.line, active.ordinal)
                    continue
                seen_directories[child_relative] = context
                append_list(
                    scope,
                    child_relative,
                    child_source,
                    child_binary,
                    directory + (child_relative,),
                    (),
                    directory_stack + (child_relative,),
                    active.structural_context,
                    execution_chain + ((
                        directory + (child_relative,), child_relative),),
                )
            tracker.advance(
                command.name, tuple(cmake_list_words(command.body)),
                command.line, active.ordinal)
        tracker.finish()

    seeded_roots: list[str] = []
    for family_root in family_roots:
        base = Path(family_root).parent
        previous = seen_directories.get(family_root)
        if previous is not None:
            errors.append(
                f"active family source directory {family_root} is listed twice"
            )
            continue
        seen_directories[family_root] = (family_root, base, base)
        seeded_roots.append(family_root)
    for family_root in seeded_roots:
        base = Path(family_root).parent
        append_list(
            family_root,
            family_root,
            base,
            base,
            (family_root,),
            (),
            (family_root,),
            (),
            (((family_root,), family_root),),
        )
    require_project_edges(family_roots, seen_project_edges, errors,
                          initial_values_by_scope=initial_values_by_scope,
                          active_origins=frozenset(item.relative for item in result))
    return result


def variable_snapshots(
    commands: list[ActiveCommand],
    model: FunctionModel,
    errors: list[str],
    initial_values: dict[str, tuple[str, ...]] | None = None,
    directory_target_types: dict[
        tuple[str, tuple[str, ...]], dict[str, tuple[str, int]]
    ] | None = None,
    *,
    initial_values_by_scope: dict[
        str, dict[str, tuple[str, ...]]
    ] | None = None,
) -> VariableSnapshots:
    direct_cache_mutations: dict[tuple[str, str], set[str]] = {}
    callable_edges: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for member in commands:
        owner = model.members.get(member.ordinal)
        if owner is None:
            continue
        member_words = cmake_list_words(member.command.body)
        if member_words:
            nested = model.global_definitions.get(member.command.name)
            if nested is not None:
                callable_edges.setdefault(owner, set()).add(nested)
            tail = [value.upper() for value in member_words[1:]]
            if ((member.command.name in {"set", "unset"} and
                    "CACHE" in tail or member.command.name == "option") and
                    re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_]*", member_words[0])):
                direct_cache_mutations.setdefault(owner, set()).add(
                    member_words[0])


    def cache_mutations(
        owner: tuple[str, str],
        stack: frozenset[tuple[str, str]] = frozenset(),
    ) -> set[str]:
        if owner in stack:
            return set()
        result = set(direct_cache_mutations.get(owner, ()))
        for nested in callable_edges.get(owner, ()):
            result.update(cache_mutations(nested, stack | {owner}))
        return result

    states: dict[
        tuple[str, tuple[str, ...]], dict[str, tuple[str, ...]]
    ] = {}
    loop_stacks: dict[
        tuple[tuple[tuple[str, ...], str], ...], list[_LoopFrame]
    ] = {}
    conditional_stacks: dict[
        tuple[tuple[tuple[str, ...], str], ...], list[_ConditionalFrame]
    ] = {}
    snapshot_values: dict[int, dict[str, tuple[str, ...]]] = {}
    snapshot_loop_overrides: dict[
        int, tuple[dict[str, tuple[str, ...]], ...]
    ] = {}
    snapshot_loop_paths: dict[int, tuple[PathSet, ...]] = {}
    candidate_ordinals: set[int] = set()
    snapshot_paths: dict[int, PathSet] = {}
    direct_target_presence: dict[str, dict[str, tuple[str, PathSet]]] = {}
    source_probes = reviewed_source_probe_decisions(commands, REPOSITORY_ROOT)
    root_package_targets = (reviewed_root_absl_target(commands, initial_values_by_scope, REPOSITORY_ROOT)
        if directory_target_types is not None and SHARED_TARGET_NAMESPACE in directory_target_types else {})
    completed_boundaries: set[str] = set()
    source_independent_ordinals: set[int] = set()
    cache_states: dict[str, dict[str, tuple[str, ...]]] = {}
    program_clearance = ProgramClearance()
    returned_states: dict[
        tuple[tuple[tuple[str, ...], str], ...],
        list[dict[str, tuple[str, ...]]],
    ] = {}

    def directory_state(active: ActiveCommand) -> dict[str, tuple[str, ...]]:
        key = (active.scope, active.directory)
        state = states.get(key)
        if state is not None:
            return state
        parent_key = (active.scope, active.directory[:-1])
        seed = dict(initial_values or {})
        seed.update((initial_values_by_scope or {}).get(active.scope, {}))
        state = dict(states.get(parent_key, seed))
        states[key] = state
        return state

    def active_chain(active: ActiveCommand):
        return active.execution_chain or ((active.directory, active.relative),)

    def known_targets_before(active):
        known = ({} if directory_target_types is None else
                 _configure_targets_before(directory_target_types, active))
        known.update(root_package_targets)
        for scope, targets in direct_target_presence.items():
            if scope == active.scope:
                known.update({name: kind for name, (kind, _paths) in targets.items()})
            elif directory_target_types is not None and SHARED_TARGET_NAMESPACE in directory_target_types:
                universe = flow_chains.live_eof.get(scope, NO_PATHS)
                if universe:
                    known.update({name: kind for name, (kind, paths) in targets.items()
                                  if paths_cover(universe=universe, evidence=paths)})
        return known

    def close_scope(key, flow: IteratingFlowController) -> None:
        state = states.get((key[0][1], key[-1][0]))
        return_branches = returned_states.pop(key, [])
        if state is not None and return_branches:
            live_states = [dict(state)] if flow.current_paths() else []
            state.clear()
            state.update(merge_variable_states(
                [*live_states, *return_branches]))

    flow_chains = ExecutionChainManager(errors, close_scope)

    def expand_here(
        active: ActiveCommand,
        raw: list[str] | tuple[str, ...],
        state: dict[str, tuple[str, ...]],
        preserve_empty: bool = False,
    ) -> list[str]:
        return _expand_context_tokens(
            active, raw, state, REPOSITORY_ROOT, preserve_empty)

    preceding = {
        current.ordinal: previous
        for previous, current in zip(commands, commands[1:])
    }

    def direct_literal_find(active, raw, state):
        # The general state preserves possible source membership, not list
        # order. FIND may use an exact index only immediately after its literal
        # set producer, before any mutation, alias, branch merge or call.
        previous = preceding.get(active.ordinal)
        if (len(raw) != 4 or raw[0].upper() != "FIND" or
                previous is None or previous.command.name != "set" or
                model.members.get(previous.ordinal) is not None or
                model.members.get(active.ordinal) is not None or
                any(getattr(previous, name) != getattr(active, name) for name in (
                    "scope", "relative", "source_base", "binary_base",
                    "directory", "structural_context", "execution_chain"))):
            return None
        producer = cmake_list_words(previous.command.body)
        if (len(producer) < 2 or producer[0] != raw[1] or
                len(producer) > 257 or any(
                    re.fullmatch(r"[A-Za-z0-9_./+-]{1,4096}", value) is None
                    for value in producer[1:]) or
                any(value.upper() in {"CACHE", "PARENT_SCOPE"}
                    for value in producer[1:])):
            return None
        values = tuple(producer[1:])
        return values if state.get(raw[1]) == values else None

    for active in commands:
        flow = flow_chains.enter(active_chain(active))
        chain = active_chain(active)
        state = directory_state(active)
        # Each root represents an independent owner configure. CACHE writes
        # propagate inside that configure, never into a different owner cache.
        global_cache_state = cache_states.setdefault(active.scope, {})
        # CMake cache writes are visible across add_subdirectory scopes and
        # when execution returns to a parent directory. A cache value may also
        # pre-exist, so keep it deliberately unresolved for later carriers.
        for variable, values in global_cache_state.items():
            state.setdefault(variable, values)
        snapshot_values[active.ordinal] = dict(state)
        lane_contexts = flow.lane_contexts()
        overrides = tuple(binding for binding, _, _ in lane_contexts)
        snapshot_loop_overrides[active.ordinal] = overrides
        snapshot_loop_paths[active.ordinal] = tuple(
            paths for _, paths, _ in lane_contexts)
        snapshot_paths[active.ordinal] = flow.current_paths()
        if source_prefix_is_independent(flow.current_paths(), source_probes, completed_boundaries):
            source_independent_ordinals.add(active.ordinal)
        if flow.current_paths() and overrides:
            candidate_ordinals.add(active.ordinal)
        if active.ordinal in model.members:
            continue
        command = active.command
        command_words = cmake_list_words(command.body)
        condition_words = words(command.body)
        conditionals = conditional_stacks.setdefault(chain, [])
        if command.name == "if":
            flow.open_if(f"direct:{active.scope}:{active.ordinal}",
                flow.condition_truths(
                    condition_words, state,
                    lambda raw, bound, preserve: expand_here(
                        active, raw, bound, preserve),
                    lambda bound: reviewed_scalar_iteration_locals(
                        active, bound),
                    known_targets=known_targets_before(active)))
            conditionals.append(_ConditionalFrame(dict(state), []))
            continue
        if command.name in {"elseif", "else"}:
            if conditionals:
                frame = conditionals[-1]
                if flow.current_paths():
                    frame.branches.append(dict(state))
                state.clear()
                state.update(frame.base)
                if command.name == "else":
                    frame.has_else = True
                    flow.alternate_if(None)
                else:
                    flow.alternate_if(flow.condition_truths(
                        condition_words, state,
                        lambda raw, bound, preserve: expand_here(
                            active, raw, bound, preserve),
                        lambda bound: reviewed_scalar_iteration_locals(
                            active, bound),
                        known_targets=known_targets_before(active)))
            continue
        if command.name == "endif":
            if conditionals:
                frame = conditionals.pop()
                if flow.current_paths():
                    frame.branches.append(dict(state))
                if flow.implicit_if_paths():
                    frame.branches.append(frame.base)
                flow.close_if()
                state.clear()
                if frame.branches:
                    state.update(merge_variable_states(frame.branches))
                else:
                    state.update(frame.base)
            continue
        if command.name == "endforeach":
            stack = loop_stacks.get(chain, [])
            if stack:
                frame = stack.pop()
                states_to_merge = list(frame.continued_states or [])
                if frame.zero_possible or not frame.values:
                    states_to_merge.append(frame.base)
                if flow.current_paths() and frame.values:
                    iteration = dict(state)
                    if not frame.variable:
                        pass
                    elif frame.previous is None:
                        iteration.pop(frame.variable, None)
                    else:
                        iteration[frame.variable] = frame.previous
                    states_to_merge.append(iteration)
                flow.close_iterations()
                completed_boundaries.update(frame.completed_boundaries)
                state.clear()
                if states_to_merge:
                    state.update(merge_variable_states(states_to_merge))
                else:
                    state.update(frame.base)
            continue
        if command.name == "continue":
            if flow.current_paths():
                if command_words:
                    errors.append(
                        f"{active.relative}:{command.line}: continue() "
                        "arguments are unsupported")
                    flow.fatal_current()
                    continue
                stack = loop_stacks.get(chain, [])
                if not stack or not flow.continue_current():
                    errors.append(
                        f"{active.relative}:{command.line}: continue() "
                        "outside an active foreach")
                    flow.fatal_current()
                else:
                    if stack[-1].continued_states is None:
                        stack[-1].continued_states = []
                    stack[-1].continued_states.append(dict(state))
            continue
        if command.name == "return":
            if flow.current_paths():
                if command_words:
                    errors.append(
                        f"{active.relative}:{command.line}: direct return() "
                        "propagation is unsupported")
                    flow.fatal_current()
                else:
                    returned_states.setdefault(chain, []).append(dict(state))
                    flow.return_current()
            continue
        callable_owner = model.global_definitions.get(command.name)
        if (callable_owner is not None and flow.current_paths() and
                callable_owner[0] != active.scope):
            errors.append(
                f"{active.relative}:{command.line}: cross-family call to "
                f"{command.name} owned by {callable_owner[0]}"
            )
        elif callable_owner is not None and flow.current_paths():
            for variable in cache_mutations(callable_owner):
                poison = (f"$CACHE{{{variable}}}",)
                global_cache_state[variable] = poison
                state.setdefault(variable, poison)
            for call_index, (bound, paths, identity) in enumerate(
                    flow.lane_contexts()):
                if not paths:
                    continue
                call_state = {**state, **bound}
                call_arguments = _expand_context_callable_arguments(
                    active, words(command.body), call_state, REPOSITORY_ROOT,
                    errors,
                    f"{active.relative}:{command.line} callable flow")
                successful = trace_callable_success(
                    callable_owner, commands, model, paths,
                    call_state, call_arguments,
                    cmake_list_words, lambda raw, local, preserve: expand_here(
                        active, raw, local, preserve),
                    lambda member, local: _expand_context_callable_arguments(
                        active, words(member.command.body), local,
                        REPOSITORY_ROOT, errors,
                        f"{member.relative}:{member.command.line} nested "
                        "callable flow"),
                    errors,
                    (active.ordinal, call_index),
                    known_targets=known_targets_before(active))
                flow.absorb_lane(identity, successful)
        if not command_words:
            continue
        if command.name == "foreach":
            stack = loop_stacks.setdefault(chain, [])
            if not flow.current_paths():
                stack.append(_LoopFrame(
                    "", None, dict(state), current_viable=False))
                flow.open_iterations(
                    f"loop:{active.scope}:{active.ordinal}", ())
                continue
            binding, binding_error = parse_foreach_binding(command_words)
            if binding is None:
                errors.append(
                    f"{active.relative}:{command.line}: "
                    f"{binding_error or 'unsupported foreach grammar'}")
                stack.append(_LoopFrame(
                    "", None, dict(state), current_viable=False))
                flow.fatal_current()
                flow.open_iterations(
                    f"loop:{active.scope}:{active.ordinal}", ())
                continue
            variable = binding.variable
            expanded_values, zero_possible = expand_foreach_values(
                binding,
                state,
                lambda raw, preserve: expand_here(
                    active, raw, state, preserve),
            )
            possible_zero = zero_possible or any(
                has_unresolved_cmake_carrier(value) or "$<" in value
                for value in expanded_values)
            if expanded_values and possible_zero:
                errors.append(
                    f"{active.relative}:{command.line}: non-exact foreach "
                    "iteration values")
                flow.fatal_current()
                expanded_values = ()
            stack.append(_LoopFrame(
                variable=variable,
                previous=state.get(variable),
                base=dict(state),
                values=expanded_values,
                zero_possible=possible_zero,
                current_viable=bool(expanded_values),
                completed_boundaries=tuple(
                    f"loop:{active.scope}:{active.ordinal}:boundary:{'.'.join(map(str, identity)) or 'root'}:{index}"
                    for _binding, _paths, identity in flow.lane_contexts()
                    for index in range(len(expanded_values))) if not possible_zero else (),
            ))
            flow.open_iterations(
                f"loop:{active.scope}:{active.ordinal}", tuple(
                    {variable: (value,)} for value in expanded_values))
            state[variable] = expanded_values
            continue
        if not flow.current_paths():
            continue
        if (command.name in {"add_library", "add_executable", "add_custom_target"} and
                active.ordinal in source_independent_ordinals and
                not any(frame.kind in {"foreach", "function", "macro"} for frame in active.structural_context)):
            # Source declarations reached on every current path are visible to
            # later same-configure TARGET guards immediately. This only records
            # literal direct names; unknown/callable/conditional declarations
            # cannot ground themselves or turn a fatal guard into authority.
            tokens = cmake_list_words(command.body)
            kind = {"add_library": "LIBRARY", "add_executable": "EXECUTABLE", "add_custom_target": "UTILITY"}[command.name]
            valid_import = (command.name == "add_executable" and tokens[1:] == ["IMPORTED", "GLOBAL"] or
                command.name == "add_library" and len(tokens) == 4 and tokens[1] in {
                    "STATIC", "SHARED", "MODULE", "UNKNOWN", "INTERFACE"} and tokens[2:] == ["IMPORTED", "GLOBAL"])
            if (tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.:+-]*", tokens[0]) and
                    ("IMPORTED" not in tokens[1:] or valid_import) and ("ALIAS" not in tokens[1:] or
                    len(tokens) == 3 and tokens[1] == "ALIAS" and
                    known_targets_before(active).get(tokens[2]) == kind)):
                direct_target_presence.setdefault(active.scope, {})[tokens[0]] = (kind, flow.current_paths())
        if command.name == "cmake_language":
            errors.append(
                f"{active.relative}:{command.line}: active cmake_language() "
                "metaprogramming is unsupported"
            )
            continue
        if command.name == "message":
            flow.terminate_message(flow.message_fatalities(
                command_words, state,
                lambda raw, bound, preserve: expand_here(
                    active, raw, bound, preserve)),
                f"{active.relative}:{command.line}")
            continue
        if command.name == "project":
            if (len(active.directory) != 1 or
                    active.relative != active.directory[0]):
                errors.append(
                    f"{active.relative}:{command.line}: nested/include "
                    "project() is unsupported in the active-family model"
                )
                state["PROJECT_SOURCE_DIR"] = ("${PROJECT_SOURCE_DIR}",)
                state["PROJECT_BINARY_DIR"] = ("${PROJECT_BINARY_DIR}",)
                continue
            state["PROJECT_SOURCE_DIR"] = (
                (REPOSITORY_ROOT / active.source_base).as_posix(),
            )
            state["PROJECT_BINARY_DIR"] = (active_binary_dir(active),)
            continue
        if command.name == "option":
            origin = f"{active.relative}:{command.line}"
            variable = expanded_variable_name(
                command_words[0],
                lambda raw: expand_here(active, raw, state),
                errors,
                origin,
            )
            if variable is None:
                continue
            if not approved_direct_option(
                    active.relative, variable, command_words):
                errors.append(
                    f"{active.relative}:{command.line}: unapproved option "
                    f"CACHE producer {variable}")
                continue
            if effect_variable(variable) and not selector_variable(variable):
                errors.append(
                    f"{active.relative}:{command.line}: build-effect "
                    f"option mutation is forbidden: {variable}"
                )
                continue
            poison = (f"$CACHE{{{variable}}}",)
            global_cache_state[variable] = poison
            state.setdefault(variable, poison)
            continue
        if command.name in {"set", "unset"}:
            signature = parse_variable_signature(
                command.name,
                command_words,
                lambda raw: expand_here(
                    active, raw, state, preserve_empty=True),
                errors,
                f"{active.relative}:{command.line}",
            )
            if signature is None:
                continue
            variable = signature.variable
            if effect_variable(variable):
                if not approved_effect_set(
                        active.relative, variable, command_words,
                        list(signature.values)):
                    errors.append(
                        f"{active.relative}:{command.line}: build-effect "
                        f"mutation is forbidden: {variable}"
                    )
                    continue
        if command.name == "set":
            if signature.parent_scope:
                parent_state = states.get((active.scope, active.directory[:-1]))
                if (parent_state is not None and command_words == [
                        "VETRON_MATH_WASM_OUTPUT", "${VETRON_MATH_WASM_OUTPUT}", "PARENT_SCOPE"] and
                        approved_vetron_wasm_parent_scope(
                            active, signature, state, REPOSITORY_ROOT, SYNTHETIC_BINARY_ROOT)):
                    parent_state[variable] = signature.values
                    continue
                errors.append(
                    f"{active.relative}:{command.line}: unsupported active "
                    f"PARENT_SCOPE mutation of {variable}"
                )
                continue
            if signature.cache_type is not None:
                if not approved_direct_cache_set(
                        active.relative, signature):
                    errors.append(
                        f"{active.relative}:{command.line}: unapproved direct "
                        f"CACHE producer {variable}")
                    continue
                poison = (f"$CACHE{{{variable}}}",)
                global_cache_state[variable] = poison
                state.setdefault(variable, poison)
            else:
                state[variable] = signature.values
        elif command.name == "unset":
            if signature.parent_scope:
                errors.append(
                    f"{active.relative}:{command.line}: unsupported active "
                    f"PARENT_SCOPE removal of {command_words[0]}"
                )
                continue
            if signature.cache_removal:
                if not program_clearance.cache_clear(
                        active, variable, state, global_cache_state, errors):
                    errors.append(
                        f"{active.relative}:{command.line}: direct CACHE "
                        f"removal is unsupported for {variable}")
            else:
                if not program_clearance.normal_clear(
                        active, variable, state, errors):
                    state.pop(variable, None)
        elif command.name == "list":
            apply_list_command(
                command_words,
                state,
                lambda raw: expand_here(active, raw, state),
                errors,
                f"{active.relative}:{command.line}",
                direct_literal_find=direct_literal_find(
                    active, command_words, state),
            )
        elif command.name == "string":
            apply_string_command(
                command_words,
                state,
                lambda raw: expand_here(active, raw, state),
                errors,
                f"{active.relative}:{command.line}",
                strategy_context=active,
            )
        else:
            target_types = (
                None if directory_target_types is None else
                _directory_targets_before(directory_target_types, active))
            program_variable = command_words[0] if command_words else ""
            cleared = (
                command.name == "find_program" and
                program_clearance.ready(active, program_variable))
            apply_output_writer(
                command.name,
                command_words,
                REPOSITORY_ROOT,
                REPOSITORY_ROOT / active.source_base,
                state,
                lambda raw: expand_here(active, raw, state),
                errors,
                f"{active.relative}:{command.line}",
                target_types,
                cleared,
            )
            if command.name == "find_program":
                program_clearance.consume(active, program_variable)
    flow_chains.finish()
    live_eof_paths = flow_chains.live_eof
    command_scopes = {active.ordinal: active.scope for active in commands}
    for scope in sorted(set(command_scopes.values())):
        if not live_eof_paths.get(scope):
            errors.append(
                f"{scope}: no feasible LIVE path reaches composed root EOF")
    viable_ordinals = frozenset(
        ordinal for ordinal in candidate_ordinals
        if paths_intersect(
            snapshot_paths.get(ordinal, NO_PATHS),
            live_eof_paths.get(command_scopes[ordinal], NO_PATHS)))
    guaranteed_ordinals = frozenset(
        ordinal for ordinal in viable_ordinals
        if paths_cover(
            universe=live_eof_paths.get(
                command_scopes[ordinal], NO_PATHS),
            evidence=snapshot_paths.get(ordinal, NO_PATHS)))
    return VariableSnapshots(
        snapshot_values,
        viable_ordinals,
        snapshot_loop_overrides,
        snapshot_paths,
        live_eof_paths,
        guaranteed_ordinals,
        snapshot_loop_paths,
        frozenset(source_independent_ordinals),
    )


def instantiated_commands(
    commands: list[ActiveCommand],
    model: FunctionModel,
    snapshots: VariableSnapshots,
    selected_names: set[str],
    errors: list[str],
    directory_target_types: dict[
        tuple[str, tuple[str, ...]], dict[str, tuple[str, int]]
    ] | None = None,
) -> list[InstantiatedCommand]:
    """Expand selected direct and recursively wrapped CMake commands."""
    bodies = model.bodies

    result: list[InstantiatedCommand] = []
    reported_cycles: set[tuple[tuple[str, str], ...]] = set()
    emission_counter = 0

    def occurrences(active: ActiveCommand, fallback: PathSet):
        overrides = snapshots.loop_overrides.get(active.ordinal, ({},))
        paths = snapshots.loop_path_overrides.get(active.ordinal)
        return zip(overrides, paths if paths is not None else
                   (fallback,) * len(overrides))

    def expand_values(
        evaluation: ActiveCommand,
        raw: list[str] | tuple[str, ...],
        local: dict[str, tuple[str, ...]],
        preserve_empty: bool = False,
    ) -> list[str]:
        state = dict(snapshots.values.get(evaluation.ordinal, {}))
        state.update({
            "CMAKE_CURRENT_SOURCE_DIR": (
                evaluation.source_base.as_posix(),),
            "CMAKE_CURRENT_LIST_DIR": (
                Path(evaluation.relative).parent.as_posix(),),
            "CMAKE_CURRENT_BINARY_DIR": (active_binary_dir(evaluation),),
            "CMAKE_SOURCE_DIR": (REPOSITORY_ROOT.as_posix(),),
            "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        })
        state.setdefault("PROJECT_SOURCE_DIR", (REPOSITORY_ROOT.as_posix(),))
        state.setdefault("PROJECT_BINARY_DIR", (SYNTHETIC_BINARY_ROOT,))
        return expand_variable_tokens(
            raw, state, local, preserve_empty=preserve_empty)

    def call_arguments(
        evaluation: ActiveCommand,
        raw: list[str] | tuple[str, ...],
        local: dict[str, tuple[str, ...]],
        context: str,
    ) -> list[str]:
        state = dict(snapshots.values.get(evaluation.ordinal, {}))
        state.update({
            "CMAKE_CURRENT_SOURCE_DIR": (evaluation.source_base.as_posix(),),
            "CMAKE_CURRENT_LIST_DIR": (
                Path(evaluation.relative).parent.as_posix(),),
            "CMAKE_CURRENT_BINARY_DIR": (active_binary_dir(evaluation),),
            "CMAKE_SOURCE_DIR": (REPOSITORY_ROOT.as_posix(),),
            "CMAKE_BINARY_DIR": (SYNTHETIC_BINARY_ROOT,),
        })
        state.setdefault("PROJECT_SOURCE_DIR", (REPOSITORY_ROOT.as_posix(),))
        state.setdefault("PROJECT_BINARY_DIR", (SYNTHETIC_BINARY_ROOT,))
        return expand_callable_arguments(
            raw, state, local, errors, context)

    def emit(
        body: ActiveCommand,
        evaluation: ActiveCommand,
        local: dict[str, tuple[str, ...]],
        paths: PathSet,
    ) -> None:
        nonlocal emission_counter
        local = reviewed_scalar_iteration_locals(body, local)
        groups = tuple(
            tuple(expand_values(
                evaluation, [token], local,
                preserve_empty='"' in token))
            for token in words(body.command.body)
        )
        result.append(InstantiatedCommand(
            body, evaluation, groups, emission_counter, paths))
        emission_counter += 1

    def execute(
        owner: tuple[str, str],
        evaluation: ActiveCommand,
        arguments: list[str],
        inherited: dict[str, tuple[str, ...]],
        stack: tuple[tuple[str, str], ...],
        origin: ActiveCommand,
        initial_paths: PathSet,
        call_trace: tuple[int, ...],
    ) -> PathSet:
        if model.kinds.get(owner) == "macro":
            errors.append(
                f"{origin.relative}:{origin.command.line}: active-family "
                f"macro invocation {owner[1]} is unsupported; caller-scope "
                "mutation cannot be approximated safely"
            )
            return NO_PATHS
        if owner in stack:
            cycle = stack[stack.index(owner):] + (owner,)
            if cycle not in reported_cycles:
                errors.append(
                    f"{origin.relative}:{origin.command.line}: recursive "
                    "active-family CMake callable cycle: "
                    + " -> ".join(name for _, name in cycle)
                )
                reported_cycles.add(cycle)
            return NO_PATHS

        local = dict(inherited)
        local.update(argument_overrides(model.definitions[owner], arguments))
        loop_stack: list[_LoopFrame] = []
        conditionals: list[_ConditionalFrame] = []
        next_stack = stack + (owner,)
        flow = IteratingFlowController(
            initial_paths, errors,
            f"{origin.relative}:{origin.command.line} callable {owner[1]}")
        result_start = len(result)

        def callable_viable() -> bool:
            return bool(flow.current_paths())

        def bound_contexts():
            return tuple(
                ({**local, **binding}, paths, identity)
                for binding, paths, identity in flow.lane_contexts()
                if paths)

        def finish(paths: PathSet | None = None) -> PathSet:
            open_blocks = flow.has_open_blocks()
            if open_blocks:
                errors.append(
                    f"{origin.relative}:{origin.command.line}: callable "
                    f"{owner[1]} reaches EOF with open control blocks")
            successful = (
                NO_PATHS if open_blocks else
                flow.successful_paths() if paths is None else paths)
            survivors = []
            for instance in result[result_start:]:
                live = bounded_intersection(
                    instance.path_alternatives, successful, errors,
                    f"{instance.body.relative}:"
                    f"{instance.body.command.line} callable paths")
                if live:
                    survivors.append(replace(
                        instance, path_alternatives=live))
            result[result_start:] = survivors
            return successful

        for member in bodies.get(owner, ()):
            command = member.command
            raw_words = cmake_list_words(command.body)
            condition_words = words(command.body)
            if command.name == "if":
                decision = (
                    f"call:{owner[0]}:{'/'.join(map(str, call_trace))}:"
                    f"{member.ordinal}")
                flow.open_if(decision, flow.condition_truths(
                    condition_words, local,
                    lambda raw, bound, preserve: expand_values(
                        evaluation, raw, bound, preserve),
                    known_targets=(None if directory_target_types is None else
                        _configure_targets_before(directory_target_types, evaluation))))
                conditionals.append(_ConditionalFrame(dict(local), []))
                continue
            if command.name in {"elseif", "else"}:
                if conditionals:
                    frame = conditionals[-1]
                    if flow.current_paths():
                        frame.branches.append(dict(local))
                    local.clear()
                    local.update(frame.base)
                    if command.name == "else":
                        frame.has_else = True
                        flow.alternate_if(None)
                    else:
                        flow.alternate_if(flow.condition_truths(
                            condition_words, local,
                            lambda raw, bound, preserve: expand_values(
                                evaluation, raw, bound, preserve),
                            known_targets=(None if directory_target_types is None else
                                _configure_targets_before(directory_target_types, evaluation))))
                continue
            if command.name == "endif":
                if conditionals:
                    frame = conditionals.pop()
                    if flow.current_paths():
                        frame.branches.append(dict(local))
                    if flow.implicit_if_paths():
                        frame.branches.append(frame.base)
                    flow.close_if()
                    local.clear()
                    if frame.branches:
                        local.update(merge_variable_states(frame.branches))
                    else:
                        local.update(frame.base)
                continue
            if command.name == "endforeach":
                if loop_stack:
                    frame = loop_stack.pop()
                    iteration = dict(local)
                    if not frame.variable:
                        pass
                    elif frame.previous is None:
                        iteration.pop(frame.variable, None)
                    else:
                        iteration[frame.variable] = frame.previous
                    states = list(frame.continued_states or [])
                    if frame.zero_possible or not frame.values:
                        states.append(frame.base)
                    if flow.current_paths() and frame.values:
                        states.append(iteration)
                    flow.close_iterations()
                    local.clear()
                    if states:
                        local.update(merge_variable_states(states))
                    else:
                        local.update(frame.base)
                continue
            if command.name == "continue":
                if callable_viable():
                    if raw_words:
                        errors.append(
                            f"{member.relative}:{command.line}: callable "
                            f"{owner[1]} uses continue() arguments")
                        flow.fatal_current()
                    elif not loop_stack or not flow.continue_current():
                        errors.append(
                            f"{member.relative}:{command.line}: callable "
                            f"{owner[1]} uses continue() outside foreach")
                        flow.fatal_current()
                    else:
                        if loop_stack[-1].continued_states is None:
                            loop_stack[-1].continued_states = []
                        loop_stack[-1].continued_states.append(dict(local))
                continue
            if command.name == "return":
                if not callable_viable():
                    continue
                if raw_words:
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} uses unsupported return propagation"
                    )
                    flow.fatal_current()
                else:
                    flow.return_current()
                continue
            if not raw_words:
                continue
            if command.name == "foreach":
                if not callable_viable():
                    loop_stack.append(_LoopFrame(
                        "", None, dict(local), current_viable=False))
                    flow.open_iterations(
                        f"call-loop:{owner[0]}:{'/'.join(map(str, call_trace))}:"
                        f"{member.ordinal}", ())
                    continue
                binding, binding_error = parse_foreach_binding(raw_words)
                if binding is None:
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} uses "
                        f"{binding_error or 'unsupported foreach grammar'}")
                    loop_stack.append(_LoopFrame(
                        "", None, dict(local), current_viable=False))
                    flow.fatal_current()
                    flow.open_iterations(
                        f"call-loop:{owner[0]}:{'/'.join(map(str, call_trace))}:"
                        f"{member.ordinal}", ())
                    continue
                variable = binding.variable
                expanded_values, zero_possible = expand_foreach_values(
                    binding,
                    local,
                    lambda raw, preserve: expand_values(
                        evaluation, raw, local, preserve),
                )
                possible_zero = zero_possible or any(
                    has_unresolved_cmake_carrier(value) or "$<" in value
                    for value in expanded_values)
                if expanded_values and possible_zero:
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} has non-exact foreach iteration values")
                    flow.fatal_current()
                    expanded_values = ()
                loop_stack.append(_LoopFrame(
                    variable=variable,
                    previous=local.get(variable),
                    base=dict(local),
                    values=expanded_values,
                    zero_possible=possible_zero,
                    current_viable=bool(expanded_values),
                ))
                flow.open_iterations(
                    f"call-loop:{owner[0]}:{'/'.join(map(str, call_trace))}:"
                    f"{member.ordinal}", tuple(
                        {variable: (value,)} for value in expanded_values))
                local[variable] = expanded_values
                continue
            if not callable_viable():
                continue
            if command.name == "message":
                flow.terminate_message(flow.message_fatalities(
                    raw_words, local,
                    lambda raw, bound, preserve: expand_values(
                        evaluation, raw, bound, preserve)),
                    f"{member.relative}:{command.line}")
                continue
            if command.name == "project":
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "uses unsupported nested project()"
                )
                return finish(NO_PATHS)
            if command.name == "cmake_language":
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "uses unsupported cmake_language() metaprogramming"
                )
                return finish(NO_PATHS)
            if command.name == "add_subdirectory":
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    "uses unsupported deferred add_subdirectory()"
                )
                return finish(NO_PATHS)
            if command.name == "include":
                if len(raw_words) != 1:
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} uses unsupported include output/options")
                    return finish(NO_PATHS)
                included = expand_values(evaluation, [raw_words[0]], local)
                if (len(included) == 1 and
                        included[0] in APPROVED_SYSTEM_MODULE_INCLUDES):
                    continue
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    f"uses unresolved/project include {included}"
                )
                return finish(NO_PATHS)
            if command.name == "option":
                variable = expanded_variable_name(
                    raw_words[0],
                    lambda raw: expand_values(evaluation, raw, local),
                    errors,
                    f"{member.relative}:{command.line}: callable {owner[1]}",
                )
                if variable is None:
                    return finish(NO_PATHS)
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    f"has an unsupported option CACHE producer {variable}")
                return finish(NO_PATHS)
            if command.name in {"set", "unset"}:
                signatures = [
                    parse_variable_signature(
                        command.name,
                        raw_words,
                        lambda raw, bound=bound: expand_values(
                            evaluation, raw, bound, preserve_empty=True),
                        errors,
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]}",
                    )
                    for bound, _, _ in bound_contexts()
                ]
                if not signatures or any(
                        signature is None for signature in signatures):
                    return finish(NO_PATHS)
                concrete = [
                    signature for signature in signatures
                    if signature is not None]
                if any(signature.cache_type is not None or
                       signature.cache_removal for signature in concrete):
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} performs unsupported CACHE mutation of "
                        f"{raw_words[0]}"
                    )
                    return finish(NO_PATHS)
                variables = {
                    signature.variable for signature in concrete}
                if len(variables) != 1:
                    errors.append(
                        f"{member.relative}:{command.line}: ambiguous local "
                        f"variable owner in {owner[1]}: {variables}"
                    )
                    continue
                variable = next(iter(variables))
                if effect_variable(variable):
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} mutates build-effect variable "
                        f"{variable}"
                    )
                    return finish(NO_PATHS)
                if command.name == "unset":
                    if any(signature.parent_scope for signature in concrete):
                        errors.append(
                            f"{member.relative}:{command.line}: callable "
                            f"{owner[1]} uses unsupported PARENT_SCOPE removal "
                            f"of {variable}"
                        )
                        return finish(NO_PATHS)
                    local.pop(variable, None)
                    continue
                if any(signature.parent_scope for signature in concrete):
                    if (owner[1] == "cxet_select_sources" and
                            member.relative == "cmake/CxetExchangeSelection.cmake" and
                            raw_words == ["${result}", "${ARGN}", "PARENT_SCOPE"] and
                            all(signature.parent_scope and signature.cache_type is None and
                                tuple(signature.values) == local.get(signature.variable)
                                for signature in concrete)):
                        # The byte-pinned all-exchange selector is identity.
                        # Approve only an actual no-op return: changing caller
                        # sources through different ARGN is still unsupported.
                        continue
                    if approved_safety_parent_scope(
                            owner, member.relative, raw_words, concrete):
                        continue
                    errors.append(
                        f"{member.relative}:{command.line}: callable "
                        f"{owner[1]} uses unsupported PARENT_SCOPE mutation "
                        f"of {variable}"
                    )
                    return finish(NO_PATHS)
                local[variable] = tuple(
                    value
                    for signature in concrete
                    for value in signature.values
                )
                continue
            if command.name == "list":
                apply_list_command(
                    raw_words,
                    local,
                    lambda raw: expand_values(evaluation, raw, local),
                    errors,
                    f"{member.relative}:{command.line}: callable {owner[1]}",
                )
                continue
            if command.name == "string":
                apply_string_command(
                    raw_words,
                    local,
                    lambda raw: expand_values(evaluation, raw, local),
                    errors,
                    f"{member.relative}:{command.line}: callable {owner[1]}",
                )
                continue

            if apply_output_writer(
                    command.name,
                    raw_words,
                    REPOSITORY_ROOT,
                    REPOSITORY_ROOT / evaluation.source_base,
                    local,
                    lambda raw: expand_values(evaluation, raw, local),
                    errors,
                    f"{member.relative}:{command.line}: callable {owner[1]}",
                    None if directory_target_types is None else
                    _directory_targets_before(
                        directory_target_types, evaluation)):
                continue

            nested_owner = model.global_definitions.get(command.name)
            if (nested_owner is not None and
                    nested_owner[0] != member.scope):
                errors.append(
                    f"{member.relative}:{command.line}: callable {owner[1]} "
                    f"cross-calls {command.name} owned by {nested_owner[0]}"
                )
                return finish(NO_PATHS)
            if nested_owner is not None:
                for bound, paths, identity in bound_contexts():
                    nested_arguments = call_arguments(
                        evaluation, words(command.body), bound,
                        f"{member.relative}:{command.line} nested callable")
                    successful = execute(
                        nested_owner,
                        evaluation,
                        nested_arguments,
                        bound,
                        next_stack,
                        member,
                        paths,
                        call_trace + (
                            member.ordinal, len(identity), *identity),
                    )
                    flow.absorb_lane(identity, successful)
            elif command.name in selected_names:
                for bound, paths, _ in bound_contexts():
                    emit(member, evaluation, bound, paths)

        return finish()

    for active in commands:
        if active.ordinal not in snapshots.viable_ordinals:
            continue
        if active.ordinal in model.members:
            continue
        owner = model.global_definitions.get(active.command.name)
        active_live_paths = bounded_intersection(
            snapshots.path_alternatives.get(active.ordinal, NO_PATHS),
            snapshots.live_eof_paths.get(active.scope, NO_PATHS), errors,
            f"{active.relative}:{active.command.line} live paths")
        if owner is not None and owner[0] != active.scope:
            errors.append(
                f"{active.relative}:{active.command.line}: cross-family call "
                f"to {active.command.name} owned by {owner[0]}"
            )
        elif owner is not None:
            for override_index, (overrides, occurrence_paths) in enumerate(
                    occurrences(active, active_live_paths)):
                live_paths = bounded_intersection(
                    occurrence_paths,
                    snapshots.live_eof_paths.get(active.scope, NO_PATHS),
                    errors, f"{active.relative}:{active.command.line} "
                    "iteration live paths")
                if not live_paths:
                    continue
                arguments = call_arguments(
                    active, words(active.command.body), overrides,
                    f"{active.relative}:{active.command.line} callable")
                inherited = dict(
                    snapshots.values.get(active.ordinal, {}))
                inherited.update(overrides)
                execute(
                    owner,
                    active,
                    arguments,
                    inherited,
                    (),
                    active,
                    live_paths,
                    (active.ordinal, override_index),
                )
        elif active.command.name in selected_names:
            for overrides, occurrence_paths in occurrences(
                    active, active_live_paths):
                live_paths = bounded_intersection(
                    occurrence_paths,
                    snapshots.live_eof_paths.get(active.scope, NO_PATHS),
                    errors, f"{active.relative}:{active.command.line} "
                    "iteration live paths")
                if live_paths:
                    emit(active, active, overrides, live_paths)
    return result
