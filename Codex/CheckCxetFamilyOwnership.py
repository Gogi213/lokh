#!/usr/bin/env python3
"""Fail closed on canonical compiled ownership in the CXET family graph."""

from __future__ import annotations

import hashlib
from dataclasses import replace
import os
import re
import sys
import time
from pathlib import Path


def _bootstrap_isolated_checker_imports() -> None:
    if not (sys.flags.isolated and sys.flags.no_site):
        print(
            "cxet family checker requires /usr/bin/python3 -I -S",
            file=sys.stderr,
        )
        raise SystemExit(2)
    sys.path.append(Path(__file__).resolve(strict=True).parent.as_posix())


_bootstrap_isolated_checker_imports()

from CMake.Policy.CmakeFamilyCommandPolicy import validate_command_policies
from CMake.Syntax.CmakeFamilyDialect import (
    validate_active_dialect,
    validate_dialect_argument_microcases,
    validate_exact_active_inventory,
    validate_exact_active_inventory_microcases,
)
from CMake.Policy.CmakeFamilyEffectPolicy import validate_effect_policy_microcases
from CMake.Flow.CmakeFamilyExecutionIdentity import unsymlinked_regular_path
from CMake.Flow.CmakeFamilyFlow import (
    FlowController,
    Truth,
    bounded_merge,
    paths_cover,
    paths_intersect,
    validate_condition_evaluation_microcases,
    validate_callable_name_microcases,
)
from CMake.Flow.CmakeFamilyState import validate_callable_argument_microcases
from CMake.Flow.CmakeFamilyGraph import (
    Command,
    InstantiatedCommand,
    cmake_list_words,
    compose_active_commands,
    function_model,
    has_unresolved_cmake_carrier,
    instantiated_commands,
    normalize_project_source_path,
    parse_commands,
    strip_cmake_comments,
    variable_snapshots,
)
from CMake.Policy.CmakeFamilyIncludeDirectories import (
    validate_target_include_directory_microcases,
)
from CMake.Flow.CmakeFamilyInstances import (
    GRAPH_INSTANCE_NAMES,
    compiled_source_instances,
    directory_target_types,
)
from CMake.Policy.CmakeFamilyLoopPolicy import (
    validate_reviewed_source_folds,
    validate_loop_writer_boundary,
)
from CMake.Syntax.CmakeFamilyLexer import validate_cmake_lexer_microcases
from CMake.Policy.CmakeFamilyProperties import target_property_mutations
from CMake.Policy.CmakeFamilyRegistrationPolicy import validate_registration_policies
from CMake.Policy.CmakeFamilyScriptPolicy import validate_invoked_script_policies
from CMake.Policy.CmakeFamilyStrategyPolicy import validate_strategy_tree
from CMake.Policy.CmakeFamilyVendorPolicy import validate_active_vendor_contract
from Family.Profile.CxetFamilyActivation import (
    OFFLINE_HELPER, offline_owner, owner_activation,
    lower_offline_registrations, validate_offline_helper,
)
from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
from CMake.Policy.CmakeFamilyBenchmarkRecipe import BENCHMARK_ROOTS
from Family.Profile.CxetFamilyBenchmarkActivation import (
    BENCHMARK_HELPER, lower_benchmark_registrations, validate_benchmark_helper,
)
from Family.Targets.CxetFamilyAliasPolicy import target_aliases
from Family.Sources.CxetFamilyIncludeReachability import (
    CppIncludeSyntaxMemo,
    validate_include_reachability_microcases,
    validate_compiler_include_reachability,
)
from Family.Sources.CxetFamilyHeaderIdentity import validate_exported_header_identity
from Family.Sources.CxetFamilyAppNativeBoundary import (
    validate_app_native_boundary, validate_app_native_boundary_microcases,
)
from Family.Targets.CxetFamilyBuildPolicy import exact_liburing_import, exact_target_alias
from Family.Targets.CxetFamilyMayMustGraph import (
    build_family_graph,
    source_object_dependency,
    single_expanded_target_argument,
    validate_direct_and_transitive_contracts,
    validate_link_item_microcases,
    validate_single_target_argument_microcases,
    validate_target_source_visibility_microcases,
)
from Family.Targets.CxetFamilyOwnershipPolicy import (
    CANONICAL_COMPILED_OWNER_GROUPS,
    CANONICAL_EVALUATION_ROOTS,
    CANONICAL_EXACT_SOURCE_ATTACHMENTS,
    SHARED_COMPILED_SOURCE_TARGETS,
    reviewed_recorder_parent_source,
    OBSOLETE_TARGETS,
    SOURCE_REQUIRED_TARGETS,
    TARGET_OWNERS,
    TARGET_SOURCE_ROOTS,
    allowed_owned_source,
    generated_cmake_path,
    validate_generated_cmake_path_microcases,
)
from Family.Verification.CxetFamilyReadOnlySurface import (
    validate_read_only_physical_surfaces,
)
from Family.Sources.CxetFamilySourceAttachment import (
    compiled_attachment,
    prebuilt_attachment,
    resolve_source_attachment,
    validate_source_attachment_microcases,
)
from Family.Sources.CxetFamilySourcePolicy import (
    canonical_evaluation_context,
    typed_generated_source,
    native_crypto_owner,
    NATIVE_CRYPTO_VENDOR_SOURCES,
)
from Family.Targets.CxetFamilyTargetPolicy import (
    canonical_source_structural_error,
    declared_source_owner_error,
)
from Family.Targets.CxetFamilyTargetRegistry import (
    build_target_registry,
    covered_provider_scopes,
)
from Family.Verification.CxetFamilyVerificationFriendPolicy import (
    validate_verification_friend_contract,
    capture_verification_source_audit,
)


ROOT = Path(__file__).resolve().parents[2]

_REVIEWED_PARENT_SOURCE_TARGETS = frozenset({
    "cxet_read_only_contracts",
    "hftrec_corpus_contract",
    "trading_core_execution",
})
APPROVED_EXTERNAL_SUBDIRECTORIES = {
    "extra/secp256k1",
}


SOURCE_DECLARATION_WORDS = {
    "STATIC", "SHARED", "MODULE", "OBJECT", "INTERFACE",
    "EXCLUDE_FROM_ALL", "WIN32", "MACOSX_BUNDLE",
}
SOURCE_VISIBILITY_WORDS = {"PUBLIC", "PRIVATE", "INTERFACE"}

def read_text(path: Path, errors: list[str]) -> str:
    relative = path.relative_to(ROOT).as_posix()
    if not unsymlinked_regular_path(path, ROOT):
        errors.append(
            f"CMake input is missing, nonregular, or symlinked: {relative}")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {relative}: {exc}")
        return ""


def owned_source_commands(
    target: str,
    instances: list[InstantiatedCommand],
) -> list[tuple[InstantiatedCommand, list[str]]]:
    result: list[tuple[InstantiatedCommand, list[str]]] = []
    for instance in instances:
        command = instance.body.command
        if command.name in {"set_property", "set_target_properties"}:
            mutations, _ = target_property_mutations(instance)
            for mutation in mutations:
                if (mutation.target == target and mutation.name in {
                        "SOURCES", "INTERFACE_SOURCES"}):
                    result.append((instance, list(mutation.values)))
            continue
        first_group = (
            tuple(instance.token_groups[0])
            if instance.token_groups else ())
        raw_target, target_failure = single_expanded_target_argument(
            first_group)
        if target_failure is not None or raw_target != target:
            continue
        command_words = [
            token for group in instance.token_groups[1:] for token in group]
        if command.name in {"add_library", "add_executable"}:
            if (exact_target_alias(instance) or
                    exact_liburing_import(
                        instance, [raw_target], set(command_words))):
                continue
            source_tokens = [
                token for token in command_words
                if token not in SOURCE_DECLARATION_WORDS]
        else:
            source_tokens = [
                token for token in command_words
                if token not in SOURCE_VISIBILITY_WORDS]
        result.append((instance, source_tokens))
    return result


def validate_target_owner_arguments(
    instances: list[InstantiatedCommand],
    errors: list[str],
) -> None:
    """Reject list-expanded mutation/declaration owners before collection."""
    for instance in instances:
        command = instance.body.command.name
        if (not command.startswith("target_") and
                command not in {
                    "add_dependencies", "add_executable", "add_library",
                }):
            continue
        first_group = (
            tuple(instance.token_groups[0])
            if instance.token_groups else ())
        _, failure = single_expanded_target_argument(first_group)
        if failure is not None:
            errors.append(
                f"{instance.body.relative}:{instance.body.command.line}: "
                f"{command}: {failure}")


def contains_forbidden(body: str, token: str) -> bool:
    body = strip_cmake_comments(body)
    if token.endswith("::"):
        return re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(token)}", body, re.IGNORECASE
        ) is not None
    return token.lower() in body.lower()


def cmake_files(errors: list[str]) -> dict[str, tuple[str, list[Command]]]:
    paths: set[Path] = set()
    traversal_failed = False

    def walk_error(exc: OSError) -> None:
        nonlocal traversal_failed
        traversal_failed = True
        location = str(exc.filename) if exc.filename is not None else str(ROOT)
        errors.append(f"cannot enumerate CMake inventory at {location}: {exc}")

    for current, directory_names, file_names in os.walk(
            ROOT, followlinks=False, onerror=walk_error):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            path = current_path / name
            relative = path.relative_to(ROOT)
            if generated_cmake_path(relative.parts):
                continue
            if path.is_symlink() or not path.is_dir():
                errors.append(
                    "CMake inventory directory is nonregular/symlinked: " +
                    relative.as_posix())
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            path = current_path / name
            relative = path.relative_to(ROOT)
            if generated_cmake_path(relative.parts):
                continue
            if path.name != "CMakeLists.txt" and path.suffix != ".cmake":
                continue
            if path.is_symlink() or not path.is_file():
                errors.append(
                    "CMake inventory path is nonregular/symlinked: " +
                    relative.as_posix())
                continue
            paths.add(path)
    if traversal_failed:
        errors.append("CMake inventory traversal was incomplete")
    result: dict[str, tuple[str, list[Command]]] = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT).as_posix()
        text = read_text(path, errors)
        result[relative] = (text, parse_commands(relative, text, errors))
    return result


def check_duplicate_compiled_sources(
    source_instances: list[InstantiatedCommand],
    registry,
    errors: list[str],
) -> tuple[tuple[str, InstantiatedCommand, str], ...]:
    occurrences: list[tuple[str, InstantiatedCommand, str]] = []
    for target in sorted(registry.concrete_names()):
        for instance, source_tokens in owned_source_commands(
                target, source_instances):
            declaration = registry.context_for_use(
                target, instance, allow_same=True)
            if declaration is None:
                continue
            for token in source_tokens:
                evaluation = instance.evaluation
                body = instance.body
                generated = typed_generated_source(target, evaluation, token)
                if (has_unresolved_cmake_carrier(token) and
                        not generated):
                    errors.append(
                        f"{body.relative}:{body.command.line}: first-party "
                        f"target {target} has unresolved source carrier {token}")
                    continue
                if generated:
                    if target == "cxet_tls_certificates":
                        # This exact hash-pinned adaptation changes no includes.
                        # Still scan its upstream input in the certificate
                        # target's actual compiler environment; generated status
                        # must not hide an unproved include/dependency closure.
                        occurrences.append((target, instance,
                                            "extra/mbedtls-cold/library/x509.c"))
                    continue
                if "$<" in token:
                    _, failure = source_object_dependency(token)
                    if failure is not None:
                        errors.append(
                            f"{body.relative}:{body.command.line}: first-party "
                            f"target {target} has unsupported source generator "
                            f"expression {token}")
                    continue
                source, source_error = resolve_source_attachment(
                    evaluation, token, ROOT)
                native_vendor = (native_crypto_owner(instance) and
                                 source in NATIVE_CRYPTO_VENDOR_SOURCES.get(target, ()))
                if (".." in Path(token.strip('"')).parts and not native_vendor and
                        not reviewed_recorder_parent_source(target, instance, source) and
                        target not in _REVIEWED_PARENT_SOURCE_TARGETS and
                        offline_owner(body.relative) is None):
                    errors.append(
                        f"{body.relative}:{body.command.line}: target {target} "
                        f"has parent traversal in source {token}")
                    continue
                if source_error is not None or source is None:
                    errors.append(
                        f"{body.relative}:{body.command.line}: target "
                        f"{target}: {source_error or token}")
                    continue
                owner_error = declared_source_owner_error(
                    target, declaration, instance, source)
                if owner_error is not None:
                    errors.append(
                        f"{body.relative}:{body.command.line}: {owner_error}")
                    continue
                if compiled_attachment(source):
                    occurrences.append((target, instance, source))

    target_sources_seen: dict[
        tuple[str, str], list[InstantiatedCommand]
    ] = {}
    for target, instance, source in occurrences:
        key = (target, source)
        if any(
                paths_intersect(
                    previous.path_alternatives,
                    instance.path_alternatives)
                for previous in target_sources_seen.get(key, ())):
            errors.append(
                f"{instance.body.relative}:{instance.body.command.line}: "
                f"target {target} attaches canonical source {source} more "
                "than once on overlapping paths")
        target_sources_seen.setdefault(key, []).append(instance)

    # A concrete production TU has one compiled target owner.
    production_source_claims: dict[
        str, list[tuple[str, InstantiatedCommand]]
    ] = {}
    for target, instance, source in occurrences:
        if target not in CANONICAL_COMPILED_OWNER_GROUPS:
            continue
        for previous_target, previous_instance in production_source_claims.get(
                source, ()):
            if (previous_target == target or
                    {previous_target, target} <=
                    SHARED_COMPILED_SOURCE_TARGETS.get(source, frozenset()) or
                    not paths_intersect(
                        previous_instance.path_alternatives,
                        instance.path_alternatives)):
                continue
            errors.append(
                f"{instance.body.relative}:{instance.body.command.line}: "
                f"canonical source {source} is compiled by distinct "
                f"production targets {previous_target} and {target}")
        production_source_claims.setdefault(source, []).append(
            (target, instance))

    canonical_sources: dict[str, str] = {}
    canonical_digests: dict[str, tuple[str, str]] = {}
    for target, _, source in occurrences:
        owner_group = CANONICAL_COMPILED_OWNER_GROUPS.get(target)
        if owner_group is None:
            continue
        previous = canonical_sources.get(source)
        if previous is not None and previous != owner_group:
            errors.append(
                f"canonical source {source} is claimed by both {previous} "
                f"and {owner_group}")
        canonical_sources[source] = owner_group
        path = ROOT / source
        if not path.is_file():
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"cannot hash canonical source {source}: {exc}")
            continue
        duplicate = canonical_digests.get(digest)
        if (duplicate is not None and duplicate[0] != owner_group and
                duplicate[1] != source):
            errors.append(
                f"canonical {owner_group} source {source} is byte-identical "
                f"to canonical {duplicate[0]} source {duplicate[1]}")
        canonical_digests.setdefault(digest, (owner_group, source))

    reported: set[tuple[str, str, str]] = set()
    for target, instance, source in occurrences:
        body = instance.body
        owner = canonical_sources.get(source)
        target_group = CANONICAL_COMPILED_OWNER_GROUPS.get(target, target)
        if owner is not None and target_group != owner:
            from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_canonical_source
            if offline_canonical_source(instance, target, source):
                continue
            key = (target, owner, source)
            if key not in reported:
                errors.append(
                    f"{body.relative}:{body.command.line}: target {target} "
                    f"compiles canonical {owner} source {source}")
                reported.add(key)
            continue
        path = ROOT / source
        if not path.is_file():
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            errors.append(f"cannot hash compiled source {source}: {exc}")
            continue
        duplicate = canonical_digests.get(digest)
        if (duplicate is None or duplicate[1] == source or
                duplicate[0] == target_group):
            continue
        key = (target, duplicate[0], source)
        if key not in reported:
            errors.append(
                f"{body.relative}:{body.command.line}: target {target} "
                f"compiles byte-identical copy {source} of canonical "
                f"{duplicate[0]} source {duplicate[1]}")
            reported.add(key)
    return tuple(occurrences)


def check_target_owners(
    source_instances: list[InstantiatedCommand],
    registry,
    errors: list[str],
) -> None:
    if set(TARGET_SOURCE_ROOTS) != set(TARGET_OWNERS):
        errors.append(
            "canonical target/source-root policy is incomplete: "
            f"owners={sorted(TARGET_OWNERS)}, "
            f"source_roots={sorted(TARGET_SOURCE_ROOTS)}")
    unknown_exact_targets = (
        set(CANONICAL_EXACT_SOURCE_ATTACHMENTS) - set(TARGET_SOURCE_ROOTS))
    if unknown_exact_targets:
        errors.append(
            "exact source-attachment policy names unknown targets: "
            f"{sorted(unknown_exact_targets)}")
    for exact_target, exact_sources in (
            CANONICAL_EXACT_SOURCE_ATTACHMENTS.items()):
        if not exact_sources:
            errors.append(
                f"exact source-attachment policy for {exact_target} is empty")
        for exact_source in sorted(exact_sources):
            if not allowed_owned_source(
                    exact_source, TARGET_SOURCE_ROOTS.get(exact_target, ())):
                errors.append(
                    f"exact source-attachment policy for {exact_target} "
                    f"contains non-owner source {exact_source}")
    for target, owner in TARGET_OWNERS.items():
        declarations = [
            declaration for declaration in registry.by_name.get(target, ())
            if not declaration.alias]
        if len(declarations) != 1:
            continue
        entries = owned_source_commands(target, source_instances)
        if not entries:
            declaration = declarations[0].instance
            errors.append(
                f"{declaration.body.relative}:"
                f"{declaration.body.command.line}: target {target} has no "
                "active canonical declaration/source instance")
            continue
        source_paths = []
        exact_sources = CANONICAL_EXACT_SOURCE_ATTACHMENTS.get(target)
        exact_source_paths = {
            source: [] for source in exact_sources or ()
        }
        for instance, source_tokens in entries:
            body = instance.body
            evaluation = instance.evaluation
            context_error = canonical_source_structural_error(target, instance)
            if context_error is not None:
                errors.append(
                    f"{body.relative}:{body.command.line}: {target} "
                    f"{context_error}")
            if body.relative != owner:
                errors.append(
                    f"{body.relative}:{body.command.line}: {target} receives "
                    f"sources outside canonical owner file {owner}")
                continue
            if not canonical_evaluation_context(target, evaluation):
                expected = CANONICAL_EVALUATION_ROOTS[target]
                errors.append(
                    f"{body.relative}:{body.command.line}: {target} source "
                    "mutation is evaluated in shifted source/binary context "
                    f"{evaluation.source_base}/{evaluation.binary_base}; "
                    f"expected {expected}/{expected}")
                continue
            if not source_tokens:
                if body.command.name in {
                        "set_property", "set_target_properties",
                        "target_sources"}:
                    errors.append(
                        f"{body.relative}:{body.command.line}: target {target} "
                        "has an empty source mutation")
                continue
            entry_has_source = False
            for token in source_tokens:
                generated = typed_generated_source(target, evaluation, token)
                if prebuilt_attachment(token):
                    errors.append(
                        f"{body.relative}:{body.command.line}: {target} has "
                        f"forbidden prebuilt binary attachment {token}")
                    continue
                if (has_unresolved_cmake_carrier(token) and
                        not generated):
                    errors.append(
                        f"{body.relative}:{body.command.line}: {target} has "
                        f"unresolved source carrier {token}")
                    continue
                if generated:
                    if compiled_attachment(token):
                        entry_has_source = True
                        if exact_sources is not None:
                            errors.append(
                                f"{body.relative}:{body.command.line}: "
                                f"{target} has non-canonical generated "
                                f"source attachment {token}")
                    continue
                if "$<" in token:
                    dependency, failure = source_object_dependency(token)
                    if failure is not None or dependency is None:
                        errors.append(
                            f"{body.relative}:{body.command.line}: {target} has "
                            f"unsupported source generator expression {token}")
                    else:
                        entry_has_source = True
                        if exact_sources is not None:
                            errors.append(
                                f"{body.relative}:{body.command.line}: "
                                f"{target} has non-canonical object source "
                                f"attachment {token}")
                    continue
                source, path_error = resolve_source_attachment(
                    evaluation, token, ROOT)
                native_vendor = (native_crypto_owner(instance) and
                                 source in NATIVE_CRYPTO_VENDOR_SOURCES.get(target, ()))
                if (".." in Path(token.strip('"')).parts and not native_vendor and
                        not reviewed_recorder_parent_source(target, instance, source) and
                        target not in _REVIEWED_PARENT_SOURCE_TARGETS):
                    errors.append(
                        f"{body.relative}:{body.command.line}: {target} has "
                        f"forbidden parent traversal in owned source {token}")
                    continue
                if path_error is not None or source is None:
                    errors.append(
                        f"{body.relative}:{body.command.line}: {target} has "
                        f"invalid source path {path_error or token}")
                    continue
                if not allowed_owned_source(
                        source, TARGET_SOURCE_ROOTS[target]):
                    errors.append(
                        f"{body.relative}:{body.command.line}: {target} "
                        f"compiles non-owner source {token}")
                    continue
                if compiled_attachment(source):
                    entry_has_source = True
                    if exact_sources is not None:
                        if source not in exact_sources:
                            errors.append(
                                f"{body.relative}:{body.command.line}: "
                                f"{target} compiles source outside its exact "
                                f"canonical attachment set: {source}")
                        else:
                            exact_source_paths[source].append(
                                instance.path_alternatives)
            if entry_has_source:
                source_paths.append(instance.path_alternatives)
        if exact_sources is not None:
            declaration_paths = registry.declaration_paths(target)
            for source in sorted(exact_sources):
                attachment_coverage = bounded_merge(
                    errors,
                    f"exact source coverage for {target}:{source}",
                    *exact_source_paths[source],
                )
                if not paths_cover(
                        universe=declaration_paths,
                        evidence=attachment_coverage):
                    declaration = declarations[0].instance
                    errors.append(
                        f"{declaration.body.relative}:"
                        f"{declaration.body.command.line}: {target} misses "
                        f"required exact source {source} on at least one "
                        "declaration path")
        coverage = bounded_merge(
            errors, f"canonical source coverage for {target}", *source_paths)
        if (target in SOURCE_REQUIRED_TARGETS and not paths_cover(
                universe=registry.declaration_paths(target),
                evidence=coverage)):
            declaration = declarations[0].instance
            errors.append(
                f"{declaration.body.relative}:"
                f"{declaration.body.command.line}: compiled target {target} "
                "has no concrete/typed source on every declaration path")


def check_reverse_dependencies(
    files: dict[str, tuple[str, list[Command]]], errors: list[str]
) -> None:
    forbidden_by_owner = {
        "apps/trading-core/": (
            "hft_parser", "hft_trader", "trader::", "vetron::"),
        "apps/hft-parser/": (
            "trading_core", "hft_trader", "trader::", "vetron::"),
    }
    for relative, (_, commands) in files.items():
        forbidden: tuple[str, ...] = ()
        for prefix, tokens in forbidden_by_owner.items():
            if relative.startswith(prefix):
                forbidden = tokens
                break
        if not forbidden:
            continue
        for command in commands:
            if command.name not in {
                    "target_link_libraries", "add_subdirectory",
                    "find_package", "find_library"}:
                continue
            for token in forbidden:
                if contains_forbidden(command.body, token):
                    errors.append(
                        f"{relative}:{command.line}: forbidden reverse "
                        f"dependency token {token}")


def check_obsolete_references(
    files: dict[str, tuple[str, list[Command]]], errors: list[str]
) -> None:
    active_commands = {
        "add_library", "add_executable", "add_custom_target",
        "add_dependencies", "target_link_libraries", "install",
    }
    for relative, (_, commands) in files.items():
        for command in commands:
            if command.name not in active_commands:
                continue
            for target in OBSOLETE_TARGETS:
                if re.search(
                    rf"(?<![A-Za-z0-9_.-]){re.escape(target)}"
                    rf"(?![A-Za-z0-9_.-])",
                    strip_cmake_comments(command.body),
                ):
                    errors.append(
                        f"{relative}:{command.line}: obsolete target {target} "
                        "remains in active CMake")


def validate_path_contract_microcases(errors: list[str]) -> None:
    """Self-check the directional path algebra before reading the project."""
    all_paths = ((),)
    no_paths = ()
    a0 = ((('A', 0),),)
    a1 = ((('A', 1),),)
    a_both = (a0[0], a1[0])
    directional_cases = (
        ("unconditional evidence", all_paths, all_paths, True),
        ("conditional evidence cannot prove unconditional universe",
         all_paths, a0, False),
        ("unconditional evidence proves conditional universe",
         a0, all_paths, True),
        ("matching conditional evidence", a0, a0, True),
        ("opposite conditional evidence", a0, a1, False),
        ("two-arm union", a_both, a_both, True),
        ("partial two-arm evidence", a_both, a0, False),
        ("empty universe", no_paths, all_paths, False),
        ("empty evidence", all_paths, no_paths, False),
    )
    for label, universe, evidence, expected in directional_cases:
        actual = paths_cover(universe=universe, evidence=evidence)
        if actual != expected:
            errors.append(
                f"path-contract self-check {label}: expected {expected}, "
                f"got {actual}")

    for semantic in ("source", "test registration", "MUST edge"):
        if (not paths_cover(universe=a_both, evidence=a_both) or
                paths_cover(universe=a_both, evidence=a0)):
            errors.append(
                f"path-contract self-check {semantic}: declaration universe "
                "is not governed by directional full/partial evidence")

    provider_live = (
        (("provider-choice", 0),),
        (("provider-choice", 1),),
    )
    consumer_paths = ((("consumer-choice", 0),),)
    cross_cases = (
        ("cross-root guaranteed", {
            "provider": provider_live,
        }, {"provider": provider_live}, ("provider",)),
        ("cross-root partial", {
            "provider": (provider_live[0],),
        }, {"provider": provider_live}, ()),
        ("cross-root missing live scope", {
            "provider": provider_live,
        }, {}, ()),
    )
    for label, evidence_by_scope, live_eof_paths, expected in cross_cases:
        actual = covered_provider_scopes(
            use_scope="consumer",
            use_paths=consumer_paths,
            evidence_by_scope=evidence_by_scope,
            live_eof_paths=live_eof_paths,
        )
        if actual != expected:
            errors.append(
                f"path-contract self-check {label}: expected {expected}, "
                f"got {actual}")

    same_scope = covered_provider_scopes(
        use_scope="provider",
        use_paths=provider_live,
        evidence_by_scope={"provider": provider_live},
        live_eof_paths={},
    )
    if same_scope != ("provider",):
        errors.append(
            "path-contract self-check same-scope fragments: one-scope union "
            "did not cover its use universe")
    split_scopes = covered_provider_scopes(
        use_scope="consumer",
        use_paths=consumer_paths,
        evidence_by_scope={
            "provider-left": ((('left-choice', 0),),),
            "provider-right": ((('right-choice', 1),),),
        },
        live_eof_paths={
            "provider-left": (
                (("left-choice", 0),), (("left-choice", 1),)),
            "provider-right": (
                (("right-choice", 0),), (("right-choice", 1),)),
        },
    )
    if split_scopes:
        errors.append(
            "path-contract self-check split-scope fragments: evidence from "
            "different provider scopes was combined")

    nested_errors: list[str] = []
    nested_if = FlowController(errors=nested_errors, context="nested-if case")
    nested_if.open_if("A", Truth.UNKNOWN)
    nested_if.open_if("B", Truth.UNKNOWN)
    nested_if.fatal_current()
    nested_if.alternate_if(None)
    nested_if.close_if()
    nested_if.alternate_if(None)
    nested_if.close_if()
    expected_nested_if = (
        (("A", 0), ("B", 1)),
        (("A", 1),),
    )
    if nested_if.current_paths() != expected_nested_if:
        errors.append(
            "path-contract self-check nested fatal if: successful A0/B1,A1 "
            f"paths changed to {nested_if.current_paths()}")
    if paths_intersect(nested_if.fatal, nested_if.current_paths()):
        errors.append(
            "path-contract self-check nested fatal if: fatal A0/B0 "
            "intersects successful A0/B1,A1")

    nested_loop = FlowController(
        errors=nested_errors, context="nested-loop case")
    nested_loop.open_loop("L", has_values=True, zero_possible=True)
    nested_loop.open_if("B", Truth.UNKNOWN)
    nested_loop.fatal_current()
    nested_loop.alternate_if(None)
    nested_loop.close_if()
    nested_loop.close_loop()
    expected_nested_loop = (
        (("B", 1), ("L", 0)),
        (("L", 1),),
    )
    if nested_loop.current_paths() != expected_nested_loop:
        errors.append(
            "path-contract self-check nested fatal loop: successful "
            f"L0/B1,L1 paths changed to {nested_loop.current_paths()}")
    if paths_intersect(nested_loop.fatal, nested_loop.current_paths()):
        errors.append(
            "path-contract self-check nested fatal loop: fatal L0/B0 "
            "intersects successful L0/B1,L1")
    if nested_errors:
        errors.extend(
            f"path-contract flow self-check: {failure}"
            for failure in nested_errors)


def owner_local_provider_test_instances(
    files, initial_values, scope_values, baseline_instances, errors,
):
    """Instantiate extra math/Execution targets in ONE actual ON profile.

    Common production declarations remain in their product-profile roots.
    Only newly declared test targets and their actual mutations/registrations
    enter this independent profile scope; its EOF/path evidence is never merged
    into production declaration evidence.
    """
    physical_root = "apps/trading-core/CMakeLists.txt"
    selected = scope_values.get("apps/trading-core/tests/offline/CMakeLists.txt")
    if selected is None or selected.get("CXET_LOCAL_TESTS") != ("ON",):
        errors.append("unsupported ownership model: missing exact trading-core offline provider profile")
        return [], [], {}
    scope = "offline-provider:trading-core:release"
    stage = compose_active_commands(ROOT, files, (physical_root,),
        APPROVED_EXTERNAL_SUBDIRECTORIES, errors,
        initial_values_by_scope={physical_root: selected})
    stage = [replace(command, scope=scope,
        execution_chain=((command.execution_chain[0][0], scope), *command.execution_chain[1:]))
        for command in stage]
    model = function_model(stage, errors)
    bootstrap = variable_snapshots(stage, model, [], initial_values,
        initial_values_by_scope={scope: selected})
    bootstrap_instances = instantiated_commands(stage, model, bootstrap,
        GRAPH_INSTANCE_NAMES, [])
    types = directory_target_types(bootstrap_instances)
    snapshots = variable_snapshots(stage, model, errors, initial_values, types,
        initial_values_by_scope={scope: selected})
    instances = instantiated_commands(stage, model, snapshots,
        GRAPH_INSTANCE_NAMES, errors, types)
    def names(surface, only_local_tests=False):
        return {instance.token_groups[0][0] for instance in surface
                if (instance.body.command.name in {"add_library", "add_executable", "add_custom_target"}
                    and instance.token_groups and len(instance.token_groups[0]) == 1 and
                    (not only_local_tests or any("CXET_LOCAL_TESTS" in frame.opener
                        for frame in instance.evaluation.structural_context)))}
    added = names(instances, only_local_tests=True)
    if added & names(baseline_instances):
        errors.append("provider-local test stage shadows product targets: " +
            ", ".join(sorted(added & names(baseline_instances))))
    selected_instances = []
    for instance in instances:
        tokens = [value for group in instance.token_groups for value in group]
        command = instance.body.command.name
        if not tokens:
            continue
        if (tokens[0] in added or command == "add_test" and "COMMAND" in tokens and
                tokens[tokens.index("COMMAND") + 1] in added or
                command == "set_property" and len(tokens) > 1 and tokens[1] in added or
                command == "add_dependencies" and any(token in added for token in tokens)):
            selected_instances.append(instance)
    return stage, selected_instances, snapshots.live_eof_paths


def validate_configuration(files, active_roots, scope_initial_values, errors,
                           *, syntax_memo=None, phase_reporter=None, source_audit=None):
    """Validate one configure; no namespace/EOF facts cross this call."""
    phase_started = time.monotonic() if phase_reporter is not None else 0.0
    def phase(name):
        nonlocal phase_started
        if phase_reporter is not None:
            current = time.monotonic()
            phase_reporter(name, current - phase_started)
            phase_started = current

    files, scope_initial_values = lower_selector_modules(
        ROOT, files, scope_initial_values, errors)
    if errors:
        return
    active_commands = compose_active_commands(
        ROOT,
        files,
        active_roots,
        APPROVED_EXTERNAL_SUBDIRECTORIES,
        errors,
        initial_values_by_scope=scope_initial_values,
    )
    validate_loop_writer_boundary(active_commands, errors)
    validate_reviewed_source_folds(active_commands, errors)
    functions = function_model(active_commands, errors)
    validate_active_dialect(
        active_commands,
        set(functions.global_definitions),
        cmake_list_words,
        errors,
    )
    validate_exact_active_inventory(
        active_commands,
        cmake_list_words,
        errors,
        active_origins=frozenset(command.relative for command in active_commands),
    )
    phase("compose-model")
    if errors:
        # Unknown syntax/topology is a failed prerequisite. Do not create a
        # graph or produce cascaded include diagnostics from rejected facts.
        return
    initial_values = {
        # The exact family profile is configured with clang/clang++.  Bind the
        # compiler identity used by each app's fail-closed root guard without
        # turning this static graph check into a host compiler probe.
        "CMAKE_C_COMPILER_ID": ("Clang",),
        "CMAKE_CXX_COMPILER_ID": ("Clang",),
        "CMAKE_SYSTEM_NAME": ("Linux",),
        "CMAKE_SYSTEM_PROCESSOR": ("x86_64",),
        "CXET_LIB_INCLUDE_DIR": (
            (ROOT / "src/src/Core/include").as_posix(),
            (ROOT / "src/src/Contracts/include").as_posix(),
        ),
    }
    bootstrap_snapshots = variable_snapshots(
        active_commands, functions, [], initial_values,
        initial_values_by_scope=scope_initial_values)
    bootstrap_instances = instantiated_commands(
        active_commands, functions, bootstrap_snapshots,
        GRAPH_INSTANCE_NAMES, [])
    # Current owner production/offline lanes do not activate the retired
    # full-or-safety duplicate declaration pair. Ordinary registry collision
    # checks still reject every unproved duplicate.
    target_types = directory_target_types(bootstrap_instances,
        shared_namespace=True, live_eof_paths=bootstrap_snapshots.live_eof_paths,
        active_commands=active_commands, snapshots=bootstrap_snapshots)
    phase("flow-bootstrap")
    snapshots = variable_snapshots(
        active_commands, functions, errors, initial_values, target_types,
        initial_values_by_scope=scope_initial_values)
    validate_active_vendor_contract(
        active_commands, snapshots.viable_ordinals, errors)
    graph_instances = instantiated_commands(
        active_commands,
        functions,
        snapshots,
        GRAPH_INSTANCE_NAMES,
        errors,
        target_types,
    )
    phase("flow-base")
    if errors:
        return
    # One bounded refinement exposes only independently grounded native
    # declarations. Symbolic TARGET/fatal self-grounding remains excluded by
    # directory_target_types' ALL_PATHS requirement; no general fixed point.
    target_types = directory_target_types(
        graph_instances, shared_namespace=True,
        live_eof_paths=snapshots.live_eof_paths,
        active_commands=active_commands, snapshots=snapshots)
    snapshots = variable_snapshots(
        active_commands, functions, errors, initial_values, target_types,
        initial_values_by_scope=scope_initial_values)
    graph_instances = instantiated_commands(
        active_commands, functions, snapshots, GRAPH_INSTANCE_NAMES, errors,
        target_types)
    phase("flow-refined")
    if errors:
        return
    combined_instances = graph_instances
    verification_friend_proof = validate_verification_friend_contract(
        active_commands, graph_instances, errors,
        check_include_boundaries=False, syntax_memo=syntax_memo, source_audit=source_audit)
    validate_command_policies(
        combined_instances, cmake_list_words, errors, target_types,
        active_origins=frozenset(command.relative for command in active_commands),
        snapshots=snapshots)
    validate_invoked_script_policies(
        combined_instances, files, cmake_list_words, errors,
        active_origins=frozenset(command.relative for command in active_commands))
    validate_target_owner_arguments(combined_instances, errors)
    combined_live_eof_paths = snapshots.live_eof_paths
    registry = build_target_registry(
        combined_instances,
        errors,
        live_eof_paths=combined_live_eof_paths,
        active_origins=frozenset(command.relative for command in active_commands),
        active_commands=active_commands,
        snapshots=snapshots,
    )
    aliases = target_aliases(combined_instances, errors, registry)
    validate_registration_policies(
        combined_instances,
        registry,
        errors,
        verification_friend_proof,
        snapshots=snapshots,
    )
    combined_graph_instances = combined_instances
    source_instances = compiled_source_instances(combined_instances)
    check_target_owners(source_instances, registry, errors)
    source_occurrences = check_duplicate_compiled_sources(
        source_instances, registry, errors)
    graphs = build_family_graph(
        combined_graph_instances,
        registry,
        aliases,
        errors,
        verification_friend_proof=verification_friend_proof,
    )
    validate_direct_and_transitive_contracts(graphs, errors,
        active_origins=frozenset(command.relative for command in active_commands),
        disabled_contract_targets=registry.disabled_contract_targets())
    active_target_names = frozenset(
        instance.token_groups[0][0]
        for instance in graph_instances
        if (instance.body.command.name in {
                "add_executable", "add_library", "add_custom_target"} and
            instance.token_groups and len(instance.token_groups[0]) == 1)
    )
    phase("graph")
    exported_headers = validate_compiler_include_reachability(
        ROOT, combined_instances, registry, aliases, source_occurrences,
        active_target_names, errors,
        active_origins=frozenset(command.relative for command in active_commands),
        syntax_memo=syntax_memo)
    phase("include")
    validate_exported_header_identity(ROOT, exported_headers, errors)
    phase("header-identity")


def main() -> int:
    errors: list[str] = []
    validate_read_only_physical_surfaces(ROOT, errors)
    validate_generated_cmake_path_microcases(errors)
    validate_effect_policy_microcases(errors)
    validate_exact_active_inventory_microcases(errors)
    validate_cmake_lexer_microcases(errors)
    validate_dialect_argument_microcases(errors)
    validate_callable_name_microcases(errors)
    validate_condition_evaluation_microcases(errors)
    validate_callable_argument_microcases(errors)
    validate_target_include_directory_microcases(errors)
    validate_source_attachment_microcases(errors)
    validate_path_contract_microcases(errors)
    validate_link_item_microcases(errors)
    validate_single_target_argument_microcases(errors)
    validate_target_source_visibility_microcases(errors)
    validate_include_reachability_microcases(errors)
    validate_app_native_boundary_microcases(errors)
    validate_app_native_boundary(ROOT, errors)
    files = cmake_files(errors)
    trading_core = files.get("apps/trading-core/CMakeLists.txt")
    if trading_core is None:
        errors.append("missing active strategy owner CMakeLists.txt")
    else:
        validate_strategy_tree(trading_core[1], cmake_list_words, errors)
    configurations = owner_activation(ROOT, errors)
    helper = files.get(OFFLINE_HELPER)
    helper_proven = helper is not None and validate_offline_helper(helper[0], errors)
    if helper is None:
        errors.append(f"missing offline registration producer {OFFLINE_HELPER}")
    benchmark_helper = files.get(BENCHMARK_HELPER)
    benchmarks_proven = benchmark_helper is not None and validate_benchmark_helper(
        ROOT, errors, text=benchmark_helper[0])
    if benchmark_helper is None:
        errors.append(f"missing benchmark registration producer {BENCHMARK_HELPER}")
    for relative, (source, commands) in tuple(files.items()):
        if offline_owner(relative) is not None:
            files[relative] = (source, lower_offline_registrations(
                ROOT, relative, commands, errors) if helper_proven else [])
        elif relative in BENCHMARK_ROOTS:
            files[relative] = (source, lower_benchmark_registrations(
                ROOT, relative, commands, errors) if benchmarks_proven else [])
    syntax_memo = CppIncludeSyntaxMemo()
    source_audit = None
    if not errors:
        started = time.monotonic()
        print("CXET ownership physical source audit START", file=sys.stderr, flush=True)
        source_audit = capture_verification_source_audit(errors,
            check_include_boundaries=False, syntax_memo=syntax_memo)
        print(f"CXET ownership physical source audit END elapsed={time.monotonic() - started:.3f}s",
              file=sys.stderr, flush=True)
    # One rejected configure decides FAIL. Report the exact failed profile
    # and every remaining profile as NOTRUN; PASS requires the entire mapping.
    if errors:
        errors.append("configure ownership proofs not run: activation/lowering prerequisites failed")
    else:
        profile_names = tuple(configurations)
        for index, (name, (roots, values)) in enumerate(configurations.items()):
            profile_errors = []
            started = time.monotonic()
            print(f"CXET ownership profile {index + 1}/{len(profile_names)} START {name}",
                  file=sys.stderr, flush=True)
            def report_phase(phase, elapsed):
                print(f"CXET ownership profile {index + 1}/{len(profile_names)} "
                      f"PHASE {name} {phase} elapsed={elapsed:.3f}s", file=sys.stderr, flush=True)
            validate_configuration(files, roots, values, profile_errors,
                                   syntax_memo=syntax_memo, phase_reporter=report_phase,
                                   source_audit=source_audit)
            elapsed = time.monotonic() - started
            status = "FAIL" if profile_errors else "OK"
            print(f"CXET ownership profile {index + 1}/{len(profile_names)} "
                  f"END {name} {status} elapsed={elapsed:.3f}s", file=sys.stderr, flush=True)
            for failure in dict.fromkeys(profile_errors):
                errors.append(f"{failure} [profiles: {name}]")
            if profile_errors:
                remaining = profile_names[index + 1:]
                if remaining:
                    errors.append("configure ownership proofs NOTRUN: " + ", ".join(remaining))
                break
    check_reverse_dependencies(files, errors)
    check_obsolete_references(files, errors)
    if not errors and source_audit is not None:
        source_audit.validate(errors)
    if errors:
        print("CXET family ownership check: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "CXET family ownership check: PASS "
        "(path-aware namespace, canonical owners, may/must edges)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
