"""Selected instantiated-command surfaces for family ownership checks."""

from __future__ import annotations

from CMake.Policy.CmakeFamilyCommandPolicy import COMMAND_POLICY_NAMES
from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, NO_PATHS, paths_cover, paths_intersect
from CMake.Flow.CmakeFamilyState import SHARED_TARGET_NAMESPACE, NATIVE_PREREQUISITE_NAMESPACE
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Flow.CmakeFamilyExecutionIdentity import (
    ROOT, reviewed_external_authority, unsymlinked_regular_path,
)
from pathlib import Path
from CMake.Policy.CmakeFamilyRegistrationPolicy import REGISTRATION_POLICY_NAMES
from CMake.Syntax.CmakeFamilyContext import exact_context, first_if
from CMake.Syntax.CmakeFamilyDialect import TRUSTED_FIND_PACKAGE_FORMS
from Family.Targets.CxetFamilyTargetInventory import APPROVED_EXTERNAL_LINK_ITEMS


GRAPH_INSTANCE_NAMES = frozenset({
    "add_dependencies", "add_executable", "add_library", "add_link_options",
    "link_libraries", "set_directory_properties", "set_property",
    "set_target_properties", "set_tests_properties",
    "target_include_directories", "target_link_libraries",
    "target_link_options", "target_precompile_headers", "target_sources",
}) | COMMAND_POLICY_NAMES | REGISTRATION_POLICY_NAMES

SOURCE_INSTANCE_NAMES = frozenset({
    "add_executable", "add_library", "set_property",
    "set_target_properties", "target_sources",
})


def compiled_source_instances(instances):
    return [
        instance for instance in instances
        if instance.body.command.name in SOURCE_INSTANCE_NAMES]


def directory_target_types(
    instances,
    *,
    shared_namespace: bool = False,
    live_eof_paths=None,
    active_commands=None,
    snapshots=None,
):
    """Return local catalogs, optionally definite targets in ONE configure.

    The caller must separate configure instances before opting into shared
    visibility. Shared declarations require either an independent unconditional
    direct execution snapshot or a nonsymbolic provider EOF universe.
    Declaration/path fragments never combine to manufacture presence.
    """
    declarations = {}
    namespace_declarations = {}
    for instance in instances:
        command = instance.body.command.name
        if command not in {
                "add_executable", "add_library", "add_custom_target"}:
            continue
        if not instance.token_groups or len(instance.token_groups[0]) != 1:
            continue
        target = instance.token_groups[0][0]
        tail = {
            value for group in instance.token_groups[1:] for value in group}
        if not target or any(marker in target for marker in (
                "${", "$ENV{", "$CACHE{", "$<")):
            continue
        if shared_namespace:
            namespace_declarations.setdefault(target, []).append(instance)
        if "ALIAS" in tail or "IMPORTED" in tail:
            continue
        kind = {
            "add_executable": "EXECUTABLE",
            "add_library": "LIBRARY",
            "add_custom_target": "UTILITY",
        }[command]
        key = (instance.evaluation.scope, instance.evaluation.directory)
        value = (kind, instance.evaluation.ordinal)
        declarations.setdefault((key, target), []).append((instance, value))
    result = {}
    for (key, target), entries in declarations.items():
        kind_mismatch = any(
            left[1][0] != right[1][0]
            for index, left in enumerate(entries)
            for right in entries[index + 1:]
        )
        overlapping = any(
            paths_intersect(
                left[0].path_alternatives, right[0].path_alternatives)
            for index, left in enumerate(entries)
            for right in entries[index + 1:]
        )
        ambiguous = kind_mismatch or overlapping
        kind = "AMBIGUOUS" if ambiguous else entries[0][1][0]
        ordinal = min(entry[1][1] for entry in entries)
        result.setdefault(key, {})[target] = (kind, ordinal)
    if shared_namespace:
        namespace = result[SHARED_TARGET_NAMESPACE] = {}
        source_absences = (_source_target_absences(active_commands, snapshots)
                          if active_commands is not None and snapshots is not None else {})

        def source_independent(ordinal):
            return (snapshots is not None and (
                ordinal in snapshots.source_independent_ordinals or
                snapshots.path_alternatives.get(ordinal) == ALL_PATHS))

        def causal_guard_presence(target, instance):
            # Resolve only one direct lexical TARGET guard in source order.
            # Its raw arm must carry no additional unknown termination/path
            # choice, and its prerequisite must already have independent proof.
            frames = getattr(instance.body, "structural_context", ())
            if (snapshots is None or instance.body != instance.evaluation or len(frames) != 1 or
                    frames[0].kind != "if" or frames[0].arm.kind != "if" or
                    frames[0].prior_arms or
                    cmake_list_words(instance.body.command.body)[:1] != [target]):
                return False
            guard = frames[0]
            if (not source_independent(guard.ordinal) or
                    snapshots.path_alternatives.get(instance.evaluation.ordinal) != (
                        tuple(tuple(sorted((*path, (f"direct:{instance.evaluation.scope}:{guard.ordinal}:iteration:root", 0))))
                              for path in snapshots.path_alternatives.get(guard.ordinal, ())))):
                return False
            if guard.opener == ("NOT", "TARGET", target):
                return source_absences.get(guard.ordinal, {}).get(target) == "SOURCE_PROVED_ABSENT"
            if len(guard.opener) == 2 and guard.opener[0] == "TARGET":
                provider = namespace.get(guard.opener[1])
                return provider is not None and provider[1] < guard.ordinal
            return False
        candidates = [
            (target, entries[0])
            for target, entries in namespace_declarations.items()
            if len(entries) == 1
        ]
        candidates.sort(key=lambda item: (
            item[1].evaluation.ordinal,
            getattr(item[1], "emission_ordinal", item[1].evaluation.ordinal)))
        for target, instance in candidates:
            universe = (live_eof_paths or {}).get(instance.evaluation.scope, ())
            # A direct literal declaration reached on every starting path is
            # independent of later symbolic/fatal ISA guards. Its raw snapshot
            # must precede EOF clipping. Callable/body and variable-generated
            # declarations cannot borrow the caller's unconditional snapshot.
            causal = causal_guard_presence(target, instance)
            independent = causal or bool(snapshots is not None and
                instance.body == instance.evaluation and
                cmake_list_words(instance.body.command.body)[:1] == [target] and
                source_independent(instance.evaluation.ordinal))
            # In particular TARGET ghost / decl / fatal else has a symbolic
            # declaration snapshot, so successful EOF cannot self-ground it.
            if (not universe or (universe != ALL_PATHS and not independent) or
                    not causal and not paths_cover(universe=universe, evidence=instance.path_alternatives)):
                continue
            command = instance.body.command.name
            kind = {"add_executable": "EXECUTABLE", "add_library": "LIBRARY",
                    "add_custom_target": "UTILITY"}[command]
            tokens = [value for group in instance.token_groups for value in group]
            if "ALIAS" in tokens[1:]:
                if (len(tokens) != 3 or tokens[1] != "ALIAS" or
                        command == "add_custom_target" or
                        namespace.get(tokens[2], (None,))[0] != kind):
                    continue
            elif "IMPORTED" in tokens[1:]:
                valid = (
                    command == "add_executable" and tokens[1:] == ["IMPORTED", "GLOBAL"] or
                    command == "add_library" and len(tokens) == 4 and
                    tokens[1] in {"STATIC", "SHARED", "MODULE", "UNKNOWN", "INTERFACE"} and
                    tokens[2:] == ["IMPORTED", "GLOBAL"])
                if not valid:
                    continue
            namespace[target] = (kind, instance.evaluation.ordinal)
        if active_commands is not None:
            result[NATIVE_PREREQUISITE_NAMESPACE] = _native_prerequisites(active_commands, instances)
            if snapshots is not None:
                for ordinal, facts in source_absences.items():
                    result[NATIVE_PREREQUISITE_NAMESPACE].setdefault(ordinal, {}).update(facts)
                _native_external_targets(result, active_commands, snapshots)
    return result


def _source_target_absences(active_commands, snapshots):
    """Prove literal source-target absence before one direct TARGET guard.

    Unlike a missing emitted target, a raw inactive declaration snapshot proves
    the selected configure skipped that declaration. Unknown/conditional earlier
    declarations, callable bodies and opaque names veto the fact. Only names
    present in the complete source catalog qualify; arbitrary missing targets
    remain unknown and cannot turn a fatal branch into namespace authority.
    """
    declarations = []
    for active in active_commands:
        if active.command.name not in {"add_library", "add_executable", "add_custom_target"}:
            continue
        tokens = cmake_list_words(active.command.body)
        declarations.append((tokens[0] if tokens else "", active))
    catalog = {name for name, _ in declarations if name and not any(
        marker in name for marker in ("${", "$ENV{", "$CACHE{", "$<"))}
    result = {}
    for active in active_commands:
        if active.command.name != "if" or any(
                frame.kind in {"function", "macro", "foreach"}
                for frame in active.structural_context):
            continue
        tokens = tuple(cmake_list_words(active.command.body))
        operand = (tokens[1] if len(tokens) == 2 and tokens[0] == "TARGET" else
                   tokens[2] if len(tokens) == 3 and tokens[:2] == ("NOT", "TARGET") else None)
        # Package/native providers have namespaces outside the source catalog.
        # Only the canonical corpus alias has a reviewed first-party producer;
        # a later arbitrary source alias cannot prove a package name absent.
        from Family.Targets.CxetFamilyAliasPolicy import source_owned_recorder_alias
        if (operand not in catalog or
                ("::" in operand and not source_owned_recorder_alias(operand, active_commands)) or
                operand in APPROVED_EXTERNAL_LINK_ITEMS):
            continue
        clean = True
        for name, declaration in declarations:
            if declaration.ordinal >= active.ordinal:
                continue
            if snapshots.path_alternatives.get(declaration.ordinal) == NO_PATHS:
                continue
            if name == operand or not name or any(
                    marker in name for marker in ("${", "$ENV{", "$CACHE{", "$<")):
                clean = False
                break
        # Skipped third-party directories have no general declaration model.
        # The pinned secp catalog alone has a reviewed finite namespace.
        for earlier in active_commands:
            if earlier.ordinal >= active.ordinal:
                continue
            if earlier.command.name in {"find_package", "pkg_check_modules"}:
                if snapshots.path_alternatives.get(earlier.ordinal) == NO_PATHS:
                    continue
                # Only the dialect's reviewed package forms have a bounded
                # external namespace. Unknown providers may declare even an
                # ordinary first-party-looking target name.
                clean = clean and (earlier.command.name == "find_package" and
                    tuple(cmake_list_words(earlier.command.body)) in TRUSTED_FIND_PACKAGE_FORMS)
                continue
            if earlier.command.name != "add_subdirectory":
                continue
            source = cmake_list_words(earlier.command.body)[:1]
            if source and "extra/" in source[0]:
                clean = clean and operand not in {"secp256k1", "secp256k1_precomputed"} and (
                    source[0] == "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1" and
                    reviewed_external_authority("secp256k1"))
        if clean:
            result[active.ordinal] = {operand: "SOURCE_PROVED_ABSENT"}
    return result


def _native_external_targets(result, active_commands, snapshots):
    """Ground only the pinned secp catalog reached on every independent path.

    Skipped vendor dialect cannot declare arbitrary shared targets. Its two
    reviewed library names become visible only after the real external edge,
    independently reached using the fresh-namespace absence fact.
    """
    native = result.get(NATIVE_PREREQUISITE_NAMESPACE, {})
    guards = [active for active in active_commands if
              active.relative == "src/src/CMakeLists.txt" and
              active.command.name == "if" and active.command.line == 192 and
              native.get(active.ordinal, {}).get("secp256k1") == "PROVED_ABSENT"]
    if len(guards) != 1 or not reviewed_external_authority("secp256k1"):
        return
    edges = [active for active in active_commands if
             active.relative == "src/src/CMakeLists.txt" and
             active.source_base == Path("src/src") and active.binary_base == Path("src/src") and
             active.command.name == "add_subdirectory" and
             tuple(cmake_list_words(active.command.body)) == (
                 "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1",
                 "${CMAKE_CURRENT_BINARY_DIR}/_deps/secp256k1", "EXCLUDE_FROM_ALL") and
             exact_context(active.structural_context, (first_if(
                 "src/src/CMakeLists.txt", 192,
                 ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1")),))]
    if len(edges) != 1:
        return
    edge = edges[0]
    # The upstream catalog declares both names. An earlier possible local
    # declaration of either name would collide, even when it is not definite
    # enough to enter the shared positive namespace itself.
    for active in active_commands:
        if (active.ordinal >= edge.ordinal or active.command.name not in {
                "add_library", "add_executable", "add_custom_target"}):
            continue
        tokens = cmake_list_words(active.command.body)
        name = tokens[0] if tokens else ""
        if (name in {"secp256k1", "secp256k1_precomputed"} or not name or
                any(marker in name for marker in ("${", "$ENV{", "$CACHE{", "$<"))):
            return
    universe = snapshots.live_eof_paths.get(edge.scope, ())
    evidence = snapshots.path_alternatives.get(edge.ordinal, ())
    if (not universe or evidence != ALL_PATHS or
            not paths_cover(universe=universe, evidence=evidence)):
        return
    namespace = result[SHARED_TARGET_NAMESPACE]
    for target in ("secp256k1", "secp256k1_precomputed"):
        if target not in namespace:
            namespace[target] = ("LIBRARY", edge.ordinal)


def _native_prerequisites(active_commands, instances):
    """Prove fresh native bootstrap prerequisites in one complete configure.

    Every earlier possible declaration, including unresolved names, vetoes an
    absence fact. The one skipped earlier vendor catalog is pinned secp256k1;
    its reviewed namespace cannot introduce cxet_crypto or liburing::uring.
    """
    guards = {
        ("NOT", "TARGET", "cxet_crypto"): ("cxet_crypto", 234),
        ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1"): ("secp256k1", 192),
        ("NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
         "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"): ("liburing::uring", 101),
    }
    files = {
        "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure": "extra/liburing/configure",
        "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1/CMakeLists.txt": "extra/secp256k1/CMakeLists.txt",
    }
    declarations = []
    for active in active_commands:
        if active.command.name in {"add_library", "add_executable", "add_custom_target"}:
            tokens = cmake_list_words(active.command.body)
            declarations.append((tokens[0] if tokens else "", active.ordinal))
    for instance in instances:
        if instance.body.command.name in {"add_library", "add_executable", "add_custom_target"}:
            names = instance.token_groups[0] if instance.token_groups else ()
            declarations.extend((name, instance.evaluation.ordinal) for name in names)
    result = {}
    for active in active_commands:
        if (active.relative != "src/src/CMakeLists.txt" or
                active.source_base != Path("src/src") or active.binary_base != Path("src/src") or
                active.command.name != "if"):
            continue
        tokens = tuple(cmake_list_words(active.command.body))
        facts = {}
        for raw, relative in files.items():
            reviewed_exists = (
                tokens in guards and active.command.line == guards[tokens][1] or
                tokens == ("NOT", "EXISTS", raw) and active.command.line == 193 and
                raw.endswith("/extra/secp256k1/CMakeLists.txt"))
            if reviewed_exists and raw in tokens and unsymlinked_regular_path(ROOT / relative, ROOT):
                facts["EXISTS:" + raw] = "PROVED_PRESENT"
        guard = guards.get(tokens)
        target = guard[0] if guard is not None else None
        if target is not None and active.command.line == guard[1] and not active.structural_context:
            earlier = [(name, ordinal) for name, ordinal in declarations if ordinal < active.ordinal]
            clean = not any(name == target or not name or any(
                marker in name for marker in ("${", "$ENV{", "$CACHE{", "$<"))
                for name, _ in earlier)
            for command in active_commands:
                if command.ordinal >= active.ordinal or command.command.name != "add_subdirectory":
                    continue
                source = cmake_list_words(command.command.body)[:1]
                if source and "extra/" in source[0]:
                    clean = clean and target not in {"secp256k1", "secp256k1_precomputed"} and (
                        source[0] == "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1" and
                        reviewed_external_authority("secp256k1"))
            if clean:
                facts[target] = "PROVED_ABSENT"
        if facts:
            result[active.ordinal] = facts
    return result
