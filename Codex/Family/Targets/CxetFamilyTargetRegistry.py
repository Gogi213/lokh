"""Path-aware global target namespace for the active CXET family graph."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import exact_context, first_if, recorder_contract_context
from CMake.Flow.CmakeFamilyFlow import (
    NO_PATHS,
    PathSet,
    bounded_intersection,
    bounded_merge,
    paths_cover,
    paths_intersect,
)
from CMake.Syntax.CmakeFamilyPaths import normalize_project_source_path
from Family.Targets.CxetFamilyBuildPolicy import exact_liburing_import
from Family.Targets.CxetFamilyOwnershipPolicy import (
    CANONICAL_EVALUATION_ROOTS,
    TARGET_OWNERS,
)
from Family.Targets.CxetFamilyProductPolicy import product_root
from Family.Targets.CxetFamilyTargetInventory import (
    CANONICAL_KINDS,
    EXCLUDED_LOCAL_TARGETS,
    CUSTOM_TARGETS,
    IMPORTED_TARGETS,
    LIBRARY_KINDS,
    PRODUCTION_TARGETS,
    ROLE_ALIAS,
    ROLE_BENCH,
    ROLE_CUSTOM,
    ROLE_FUZZ,
    ROLE_IMPORTED,
    ROLE_PRODUCTION,
    ROLE_SOURCE_EXCEPTIONS,
    ROLE_SOURCE_ROOTS,
    ROLE_TEST,
    TEST_REGISTRATION_DEPENDENCIES,
    TargetSpec,
    target_spec,
)


ROOT = Path(__file__).resolve().parents[4]
_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_EXECUTABLE_CONTROLS = frozenset({
    "ALIAS", "IMPORTED", "GLOBAL", "WIN32", "MACOSX_BUNDLE",
    "EXCLUDE_FROM_ALL",
})
_LIBRARY_CONTROLS = frozenset({
    "ALIAS", "IMPORTED", "GLOBAL", "UNKNOWN", "EXCLUDE_FROM_ALL",
})
_NATIVE_CRYPTO_EXCLUDED_TARGETS = frozenset({
    "cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
    "cxet_tls_certificates", "cxet_native_tls",
})
_NATIVE_CRYPTO_CONTEXT = (
    first_if("src/src/CMakeLists.txt", 234, ("NOT", "TARGET", "cxet_crypto")),
)
_PARSER_PROCESS_CONTEXT = (
    first_if(
        "apps/hft-parser/cmake/HftpProcesses.cmake", 3,
        ("HFT_PARSER_BUILD_PROCESSES",)),
)
_LIBURING_IMPORT_CONTEXT = (
    first_if(
        "src/src/CMakeLists.txt", 101,
        ("NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
         "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure")),
)
_TARGET_FILE = re.compile(r"\$<TARGET_FILE:([^>$]+)>")


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _flat(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _opaque(value: str) -> bool:
    return (
        not value or "\\" in value or
        any(marker in value for marker in _CARRIERS)
    )


def _instance_scope(instance) -> str | None:
    scope = getattr(instance.evaluation, "scope", None)
    return scope if isinstance(scope, str) and scope else None


def covered_provider_scopes(
    *,
    use_scope: str,
    use_paths: PathSet,
    evidence_by_scope: dict[str, PathSet],
    live_eof_paths: dict[str, PathSet],
) -> tuple[str, ...]:
    """Return independently sufficient declaration scopes.

    Same-scope declarations prove the concrete use paths.  A declaration in
    another composed family root is visible only when declarations from that
    one provider scope cover that scope's own successful EOF universe.  Path
    fragments from different scopes are deliberately never combined.
    """
    covered: list[str] = []
    for provider_scope, evidence in sorted(evidence_by_scope.items()):
        universe = (
            use_paths if provider_scope == use_scope else
            live_eof_paths.get(provider_scope, NO_PATHS)
        )
        if paths_cover(universe=universe, evidence=evidence):
            covered.append(provider_scope)
    return tuple(covered)


@dataclass(frozen=True)
class TargetDeclaration:
    name: str
    kind: str
    role: str
    instance: object
    spec: TargetSpec | None
    alias_target: str | None = None

    @property
    def imported(self) -> bool:
        return self.role == ROLE_IMPORTED

    @property
    def alias(self) -> bool:
        return self.role == ROLE_ALIAS

    @property
    def custom(self) -> bool:
        return self.role == ROLE_CUSTOM


def _classify(instance, errors: list[str]) -> TargetDeclaration | None:
    command = instance.body.command.name
    tokens = _flat(instance)
    if not tokens:
        errors.append(f"{_origin(instance)}: empty target declaration")
        return None
    name = tokens[0]
    if _opaque(name):
        errors.append(f"{_origin(instance)}: unresolved target name {name}")
        return None
    from CMake.Policy.CmakeFamilyBenchmarkRecipe import benchmark_target_context
    benchmark = (benchmark_target_context(instance.body, name) and
                 benchmark_target_context(instance.evaluation, name))
    reviewed_excluded = benchmark or name in EXCLUDED_LOCAL_TARGETS.get(
        instance.body.relative, frozenset())
    if reviewed_excluded:
        prefix = (
            [name, "EXCLUDE_FROM_ALL"] if command == "add_executable" else
            [name, "OBJECT" if name in {"trader_startup_network", "trader_tbank_startup_network"}
             else "STATIC", "EXCLUDE_FROM_ALL"])
        if tokens[:len(prefix)] != prefix or tokens.count("EXCLUDE_FROM_ALL") != 1:
            errors.append(f"{_origin(instance)}: changed excluded local-test declaration {tokens}")
            return None
    if command in {"add_library", "add_executable"} and "ALIAS" in tokens:
        if len(tokens) != 3 or tokens[1] != "ALIAS" or _opaque(tokens[2]):
            errors.append(
                f"{_origin(instance)}: malformed ALIAS declaration {tokens}")
            return None
        return TargetDeclaration(
            name, "ALIAS", ROLE_ALIAS, instance, None, tokens[2])
    if command == "add_library":
        if name == "liburing::uring":
            expected = ["liburing::uring", "STATIC", "IMPORTED", "GLOBAL"]
            if tokens != expected:
                errors.append(
                    f"{_origin(instance)}: changed liburing import {tokens}")
                return None
            return TargetDeclaration(
                name, "STATIC", ROLE_IMPORTED, instance,
                IMPORTED_TARGETS[name])
        native_crypto = name in _NATIVE_CRYPTO_EXCLUDED_TARGETS
        resident_memory = name == "cxet_resident_memory"
        if resident_memory and (
                instance.body.relative != "src/src/CMakeLists.txt" or
                tokens[:3] != [name, "STATIC", "EXCLUDE_FROM_ALL"] or
                tokens.count("EXCLUDE_FROM_ALL") != 1 or
                not exact_context(instance.body.structural_context, ()) or
                not exact_context(instance.evaluation.structural_context, ())):
            errors.append(f"{_origin(instance)}: changed resident memory declaration {tokens}")
            return None
        if native_crypto and (
                instance.body.relative != "src/src/CMakeLists.txt" or
                tokens[:3] != [name, "STATIC", "EXCLUDE_FROM_ALL"] or
                tokens.count("EXCLUDE_FROM_ALL") != 1 or
                not exact_context(instance.body.structural_context, _NATIVE_CRYPTO_CONTEXT) or
                not exact_context(instance.evaluation.structural_context, _NATIVE_CRYPTO_CONTEXT)):
            errors.append(
                f"{_origin(instance)}: changed native crypto excluded declaration {tokens}")
            return None
        controls = _LIBRARY_CONTROLS - {"EXCLUDE_FROM_ALL"} if native_crypto or resident_memory or reviewed_excluded else _LIBRARY_CONTROLS
        if any(token in controls for token in tokens[1:]):
            errors.append(
                f"{_origin(instance)}: unsupported library signature {tokens}")
            return None
        if len(tokens) < 2 or tokens[1] not in LIBRARY_KINDS:
            errors.append(
                f"{_origin(instance)}: library kind must be explicit {tokens}")
            return None
        kind = tokens[1]
    elif command == "add_executable":
        controls = _EXECUTABLE_CONTROLS - {"EXCLUDE_FROM_ALL"} if reviewed_excluded else _EXECUTABLE_CONTROLS
        if any(token in controls for token in tokens[1:]):
            errors.append(
                f"{_origin(instance)}: unsupported executable signature {tokens}")
            return None
        kind = "EXECUTABLE"
    elif command == "add_custom_target":
        kind = "CUSTOM"
    else:
        return None
    owner = product_root(instance.evaluation)
    spec = target_spec(name, owner, instance.body.relative)
    role = (
        ROLE_CUSTOM if kind == "CUSTOM" else
        spec.role if spec is not None else ROLE_PRODUCTION)
    return TargetDeclaration(name, kind, role, instance, spec)


class TargetRegistry:
    """One occupied target namespace with path-aware declaration lookup."""

    def __init__(
        self,
        instances,
        errors: list[str],
        *,
        live_eof_paths: dict[str, PathSet],
        require_complete_live_eof: bool = True,
        active_origins: frozenset[str] | None = None,
        active_commands=None,
        snapshots=None,
    ) -> None:
        self.errors = errors
        self.live_eof_paths = dict(live_eof_paths)
        self.active_origins = active_origins
        self.active_commands = active_commands
        self.snapshots = snapshots
        if require_complete_live_eof:
            instance_scopes = {
                scope for instance in instances
                if (scope := _instance_scope(instance)) is not None}
            missing_live_scopes = sorted(
                scope for scope in instance_scopes
                if not self.live_eof_paths.get(scope))
            if missing_live_scopes:
                errors.append(
                    "target registry has no live EOF universe for scopes: " +
                    ", ".join(missing_live_scopes))
        self.order = {
            id(instance): index for index, instance in enumerate(instances)}
        self.by_name: dict[str, list[TargetDeclaration]] = {}
        self.declarations: list[TargetDeclaration] = []
        for instance in instances:
            if instance.body.command.name not in {
                    "add_library", "add_executable", "add_custom_target"}:
                continue
            declaration = _classify(instance, errors)
            if declaration is None:
                continue
            if not instance.path_alternatives:
                errors.append(
                    f"{_origin(instance)}: target declaration has no successful "
                    "execution path")
                continue
            for previous in self.by_name.get(declaration.name, ()):
                if paths_intersect(
                        previous.instance.path_alternatives,
                        instance.path_alternatives):
                    errors.append(
                        f"{_origin(instance)}: target namespace collision for "
                        f"{declaration.name} with {_origin(previous.instance)}")
            self.by_name.setdefault(declaration.name, []).append(declaration)
            self.declarations.append(declaration)
        self._validate_inventory()
        self._validate_disjoint_duplicates()
        self._validate_test_registrations(instances)


    def optional_target_disabled(self, name):
        from Family.Targets.CxetFamilyCompressionPolicy import (
            compressor_cli_disabled, recorder_full_runtime_disabled,
        )
        if name == 'hft-compressor':
            return compressor_cli_disabled(getattr(self, 'active_commands', None),
                                           getattr(self, 'snapshots', None))
        if name in {'hftrec_core', 'hftrec_recorder_api'}:
            return recorder_full_runtime_disabled(getattr(self, 'active_commands', None),
                                                 getattr(self, 'snapshots', None))
        return False

    def disabled_contract_targets(self):
        """Only exact optional owners proven OFF and absent may omit contracts."""
        present = self.concrete_names()
        return frozenset(name for name in ('hft-compressor',)
                         if name not in present and self.optional_target_disabled(name))

    def _validate_disjoint_duplicates(self) -> None:
        from CMake.Policy.CmakeFamilyPropertyPolicy import reviewed_wasm_alternatives
        for name, declarations in self.by_name.items():
            if len(declarations) <= 1:
                continue
            if (name == 'vetron-math-wasm' and
                    reviewed_wasm_alternatives([item.instance for item in declarations])):
                continue
            self.errors.append(
                f"target {name}: duplicate declarations have no approved owner")

    def _validate_inventory(self) -> None:
        required = {**PRODUCTION_TARGETS, **CUSTOM_TARGETS, **IMPORTED_TARGETS}
        for declaration in self.declarations:
            if declaration.alias:
                continue
            spec = declaration.spec
            owner = product_root(declaration.instance.evaluation)
            if spec is None:
                if owner is not None:
                    self.errors.append(
                        f"{_origin(declaration.instance)}: unreviewed target "
                        f"{declaration.name} in known product {owner}")
                continue
            if declaration.kind != spec.kind:
                self.errors.append(
                    f"{_origin(declaration.instance)}: target "
                    f"{declaration.name} kind {declaration.kind} != {spec.kind}")
            if declaration.instance.body.relative != spec.owner:
                self.errors.append(
                    f"{_origin(declaration.instance)}: target "
                    f"{declaration.name} escaped owner {spec.owner}")
            if declaration.role in {ROLE_TEST, ROLE_BENCH, ROLE_FUZZ}:
                self._validate_role_source(declaration, owner)
        for name, spec in required.items():
            if self.active_origins is not None and spec.owner not in self.active_origins:
                continue
            found = [
                declaration for declaration in self.by_name.get(name, ())
                if not declaration.alias]
            if not found:
                if self.optional_target_disabled(name):
                    continue
                self.errors.append(
                    f"required {spec.role.lower()} target {name} is absent")
        for name, expected_kind in CANONICAL_KINDS.items():
            if (self.active_origins is not None and
                    TARGET_OWNERS[name] not in self.active_origins):
                continue
            found = [
                declaration for declaration in self.by_name.get(name, ())
                if not declaration.alias]
            if len(found) != 1:
                self.errors.append(
                    f"canonical target {name} must have one declaration, "
                    f"found {len(found)}")
                continue
            declaration = found[0]
            instance = declaration.instance
            expected_owner = TARGET_OWNERS[name]
            expected_root = CANONICAL_EVALUATION_ROOTS[name]
            expected_context = (
                _PARSER_PROCESS_CONTEXT
                if name in {"hft-parserd", "hft-algosd"} else
                (first_if("src/src/CMakeLists.txt", 443, ("DEFINED", "CXET_BUILD_OWNER")),)
                if name == "cxet_lib" else ())
            if declaration.kind != expected_kind:
                self.errors.append(
                    f"{_origin(instance)}: canonical {name} has kind "
                    f"{declaration.kind}, expected {expected_kind}")
            if (instance.body.relative != expected_owner or
                    instance.evaluation.source_base.as_posix() != expected_root or
                    instance.evaluation.binary_base.as_posix() != expected_root):
                self.errors.append(
                    f"{_origin(instance)}: canonical {name} escaped exact "
                    "declaration/evaluation owner")
            context_valid = (recorder_contract_context(instance.body) and
                recorder_contract_context(instance.evaluation)) if name == "hftrec_corpus_contract" else (
                exact_context(instance.body.structural_context, expected_context) and
                exact_context(instance.evaluation.structural_context, expected_context))
            if not context_valid:
                self.errors.append(
                    f"{_origin(instance)}: canonical {name} escaped reviewed "
                    "structural context")

    def _validate_role_source(
        self, declaration: TargetDeclaration, owner: str | None
    ) -> None:
        roots = ROLE_SOURCE_ROOTS.get((owner, declaration.role), ())
        if not roots:
            self.errors.append(
                f"{_origin(declaration.instance)}: no source-root policy for "
                f"{declaration.role.lower()} target {declaration.name}")
            return
        tokens = _flat(declaration.instance)
        source_tokens = tokens[1:]
        if declaration.instance.body.command.name == "add_library":
            source_tokens = source_tokens[1:]
        normalized: list[str] = []
        for token in source_tokens:
            if _opaque(token):
                continue
            source, failure = normalize_project_source_path(
                declaration.instance.evaluation, token, ROOT)
            if failure is None and source is not None:
                normalized.append(source)
        exact = ROLE_SOURCE_EXCEPTIONS.get((
            declaration.name, declaration.instance.body.relative),
            frozenset())
        if not any(
                source == root or source.startswith(root + "/")
                for source in normalized for root in roots) and not (
                    exact and set(normalized) == set(exact)):
            self.errors.append(
                f"{_origin(declaration.instance)}: {declaration.role.lower()} "
                f"target {declaration.name} has no concrete source in {roots}")

    def _validate_test_registrations(self, instances) -> None:
        registrations: dict[str, list[object]] = {}
        for instance in instances:
            if instance.body.command.name != "add_test":
                continue
            tokens = _flat(instance)
            if len(tokens) < 4 or tokens[0] != "NAME":
                continue
            try:
                index = next(
                    item for item, token in enumerate(tokens)
                    if token == "COMMAND")
            except StopIteration:
                continue
            if index != 2 or len(tokens) <= index + 1:
                continue
            executable = tokens[index + 1]
            match = _TARGET_FILE.fullmatch(executable)
            target = match.group(1) if match is not None else executable
            declarations = self.resolve(
                target, instance, require_prior=True, report=False)
            if not declarations:
                continue
            if any(declaration.kind != "EXECUTABLE" for declaration in declarations):
                self.errors.append(
                    f"{_origin(instance)}: add_test target {target} is not "
                    "an executable")
                continue
            registration_owner = product_root(instance.evaluation)
            if any(product_root(declaration.instance.evaluation) !=
                   registration_owner for declaration in declarations):
                self.errors.append(
                    f"{_origin(instance)}: add_test for {target} crosses "
                    "product ownership")
                continue
            registrations.setdefault(target, []).append(instance)
        coverage_by_target = {
            target: bounded_merge(
                self.errors, f"direct test registration coverage for {target}",
                *(registration.path_alternatives for registration in selected))
            for target, selected in registrations.items()
        }
        infrastructure_edges: list[tuple[str, str, object]] = []
        aliases = {
            declaration.name: declaration.alias_target
            for declaration in self.declarations if declaration.alias
        }
        for instance in instances:
            tokens = _flat(instance)
            if not tokens:
                continue
            key = (instance.body.relative, instance.body.command.name, tokens[0])
            expected = TEST_REGISTRATION_DEPENDENCIES.get(key)
            if expected is None:
                continue
            source = tokens[0]
            if instance.body.command.name == "add_executable":
                actual = tuple(
                    value[len("$<TARGET_OBJECTS:"):-1] for value in tokens[1:]
                    if value.startswith("$<TARGET_OBJECTS:") and value.endswith(">"))
            else:
                actual = tuple(aliases.get(value, value) for value in tokens[1:]
                               if value not in {"PUBLIC", "PRIVATE", "INTERFACE"})
            expected_source = Path(instance.body.relative).parent
            expected_binary = (
                Path("apps/trader/tests/offline/startup")
                if instance.body.relative == "apps/trader/tests/startup/CMakeLists.txt" else
                expected_source)
            if actual != expected or (
                    instance.evaluation.source_base != expected_source or
                    instance.evaluation.binary_base != expected_binary):
                self.errors.append(
                    f"{_origin(instance)}: changed reviewed test-infrastructure dependencies for {source}")
                continue
            source_declarations = self.resolve(
                source, instance, require_prior=True,
                allow_same=instance.body.command.name == "add_executable", report=False)
            if not source_declarations or any(
                    declaration.role != ROLE_TEST for declaration in source_declarations):
                continue
            for provider in expected:
                declarations = self.resolve(provider, instance, require_prior=True, report=False)
                if declarations and all(
                        declaration.role == ROLE_TEST and
                        product_root(declaration.instance.evaluation) == product_root(instance.evaluation)
                        for declaration in declarations):
                    infrastructure_edges.append((source, provider, instance))
        # Only the small explicit infrastructure graph above participates;
        # arbitrary add_dependencies or target links confer no registration.
        for _ in range(len(infrastructure_edges)):
            changed = False
            for source, provider, instance in infrastructure_edges:
                inherited = bounded_intersection(
                    coverage_by_target.get(source, NO_PATHS), instance.path_alternatives,
                    self.errors, f"test-infrastructure registration {source}->{provider}")
                previous = coverage_by_target.get(provider, NO_PATHS)
                updated = bounded_merge(self.errors, f"registration coverage for {provider}", previous, inherited)
                if updated != previous:
                    coverage_by_target[provider] = updated
                    changed = True
            if not changed:
                break
        for declaration in self.declarations:
            if declaration.role != ROLE_TEST:
                continue
            coverage = coverage_by_target.get(declaration.name, NO_PATHS)
            if not paths_cover(
                    universe=declaration.instance.path_alternatives,
                    evidence=coverage):
                self.errors.append(
                    f"{_origin(declaration.instance)}: test executable "
                    f"{declaration.name} is not registered on every "
                    "declaration path")

    def resolve(
        self,
        name: str,
        use,
        *,
        require_prior: bool,
        allow_same: bool = False,
        roles: frozenset[str] | None = None,
        report: bool = True,
    ) -> list[TargetDeclaration]:
        use_scope = _instance_scope(use)
        if use_scope is None:
            if report:
                self.errors.append(
                    f"{_origin(use)}: target {name} use has no modeled scope")
            return []
        use_paths = use.path_alternatives
        if not require_prior:
            # Link references bind at CMake generation time. A provider may
            # appear later, but must cover every successful configure path on
            # which this reference reaches the generation phase.
            use_paths = bounded_intersection(
                use_paths, self.live_eof_paths.get(use_scope, NO_PATHS),
                self.errors, f"generation-time use paths for {name}")
            if not use_paths:
                if report:
                    self.errors.append(
                        f"{_origin(use)}: target {name} has no successful "
                        "generation-time use path")
                return []
        candidates: list[TargetDeclaration] = []
        for declaration in self.by_name.get(name, ()):
            declaration_scope = _instance_scope(declaration.instance)
            if declaration_scope is None:
                continue
            same_scope = declaration_scope == use_scope
            if (roles is not None and declaration.role not in roles) or (
                    same_scope and not paths_intersect(
                        declaration.instance.path_alternatives,
                        use_paths)):
                continue
            declaration_order = self.order[id(declaration.instance)]
            use_order = self.order[id(use)]
            if (require_prior and not (
                    declaration_order < use_order or
                    allow_same and declaration_order == use_order)):
                continue
            candidates.append(declaration)
        by_scope: dict[str, list[TargetDeclaration]] = {}
        for candidate in candidates:
            scope = _instance_scope(candidate.instance)
            if scope is not None:
                by_scope.setdefault(scope, []).append(candidate)
        evidence_by_scope = {
            scope: bounded_merge(
                self.errors,
                f"declaration coverage for {name} in {scope}",
                *(candidate.instance.path_alternatives
                  for candidate in scoped_candidates),
            )
            for scope, scoped_candidates in by_scope.items()
        }
        covered_scopes = set(covered_provider_scopes(
            use_scope=use_scope,
            use_paths=use_paths,
            evidence_by_scope=evidence_by_scope,
            live_eof_paths=self.live_eof_paths,
        ))
        if len(covered_scopes) != 1:
            if report:
                detail = (
                    "has ambiguous independently sufficient provider scopes"
                    if covered_scopes else
                    "is not declared on every required path before the mutation"
                    if require_prior else
                    "is not declared on every successful generation path"
                )
                self.errors.append(
                    f"{_origin(use)}: target {name} {detail}")
            return []
        selected_scope = next(iter(covered_scopes))
        return by_scope[selected_scope]

    def exact_prior_imported(self, name: str, use) -> list[TargetDeclaration]:
        """Return only the reviewed prior liburing import, without coverage.

        This is intentionally not part of generic resolution.  The sole
        caller is the exact vendor link edge whose producer and consumer
        guards are independently pinned by the vendor policy.
        """
        if name != "liburing::uring":
            return []
        candidates: list[TargetDeclaration] = []
        for declaration in self.by_name.get(name, ()):
            instance = declaration.instance
            tokens = _flat(instance)
            scope = _instance_scope(instance)
            if (
                declaration.imported and
                self.order[id(instance)] < self.order[id(use)] and
                scope is not None and self.live_eof_paths.get(scope) and
                instance.body.relative == "src/src/CMakeLists.txt" and
                instance.body.source_base == Path("src/src") and
                instance.evaluation.source_base == Path("src/src") and
                exact_liburing_import(
                    instance, [name], set(tokens[1:])) and
                exact_context(
                    instance.body.structural_context,
                    _LIBURING_IMPORT_CONTEXT) and
                exact_context(
                    instance.evaluation.structural_context,
                    _LIBURING_IMPORT_CONTEXT)
            ):
                candidates.append(declaration)
        return candidates if len(candidates) == 1 else []

    def context_for_use(
        self, name: str, use, *, allow_same: bool = False
    ) -> object | None:
        candidates = self.resolve(
            name, use, require_prior=True, allow_same=allow_same)
        if not candidates:
            return None
        roots = {
            product_root(candidate.instance.evaluation)
            for candidate in candidates}
        kinds = {candidate.kind for candidate in candidates}
        if len(roots) != 1 or len(kinds) != 1:
            self.errors.append(
                f"{_origin(use)}: target {name} has ambiguous declaration "
                "owner/kind on the use paths")
            return None
        use_scope = _instance_scope(use)
        candidate_scopes = {
            _instance_scope(candidate.instance) for candidate in candidates}
        if len(candidate_scopes) != 1 or None in candidate_scopes:
            self.errors.append(
                f"{_origin(use)}: target {name} has ambiguous declaration "
                "scope on the use paths")
            return None
        candidate_scope = next(iter(candidate_scopes))
        universe = (
            use.path_alternatives if candidate_scope == use_scope else
            self.live_eof_paths.get(candidate_scope or "", NO_PATHS)
        )
        individually_sufficient = [
            candidate for candidate in candidates
            if paths_cover(
                universe=universe,
                evidence=candidate.instance.path_alternatives)
        ]
        if len(individually_sufficient) == 1:
            return individually_sufficient[0].instance
        from CMake.Policy.CmakeFamilyPropertyPolicy import reviewed_wasm_alternatives
        if (name == 'vetron-math-wasm' and
                candidate_scope == use_scope and
                all(candidate.instance.emission_ordinal < use.emission_ordinal for candidate in candidates) and
                reviewed_wasm_alternatives([candidate.instance for candidate in candidates])):
            # resolve() already proved one same-scope, all-use-path provider.
            # Preserve that exact pair's coverage for declaration_precedes;
            # neither branch attests tool availability or grants source rights.
            coverage = bounded_merge(self.errors, 'reviewed WASM declaration context',
                *(candidate.instance.path_alternatives for candidate in candidates))
            if paths_cover(universe=use.path_alternatives, evidence=coverage):
                earliest = min(candidates, key=lambda candidate: candidate.instance.emission_ordinal)
                return replace(earliest.instance, path_alternatives=coverage)
        self.errors.append(
            f"{_origin(use)}: target {name} requires a union of declaration "
            "contexts; no unique context covers the use")
        return None

    def get(self, name: str, default=None):
        declarations = [
            declaration for declaration in self.by_name.get(name, ())
            if not declaration.alias]
        if len(declarations) == 1:
            return declarations[0].instance
        return default

    def concrete_names(self) -> set[str]:
        return {
            declaration.name for declaration in self.declarations
            if not declaration.alias}

    def declaration_paths(self, name: str):
        declarations = [
            declaration for declaration in self.by_name.get(name, ())
            if not declaration.alias]
        if not declarations:
            return NO_PATHS
        return bounded_merge(
            self.errors, f"declaration paths for {name}",
            *(declaration.instance.path_alternatives
              for declaration in declarations))

    def role(self, name: str, use=None) -> str | None:
        declarations = self.by_name.get(name, ())
        if use is not None:
            declarations = tuple(
                declaration for declaration in declarations
                if paths_intersect(
                    declaration.instance.path_alternatives,
                    use.path_alternatives))
        roles = {declaration.role for declaration in declarations}
        return next(iter(roles)) if len(roles) == 1 else None


def build_target_registry(
    instances,
    errors: list[str],
    *,
    live_eof_paths: dict[str, PathSet],
    require_complete_live_eof: bool = True,
    active_origins: frozenset[str] | None = None,
    active_commands=None,
    snapshots=None,
) -> TargetRegistry:
    return TargetRegistry(
        instances,
        errors,
        live_eof_paths=live_eof_paths,
        require_complete_live_eof=require_complete_live_eof,
        active_origins=active_origins,
        active_commands=active_commands,
        snapshots=snapshots,
    )
