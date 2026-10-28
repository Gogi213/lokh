"""Path-aware may/must dependency graph for the active CXET family."""

from __future__ import annotations

from dataclasses import dataclass

from CMake.Flow.CmakeFamilyFlow import bounded_merge, paths_cover
from CMake.Policy.CmakeFamilyLinkOptions import (
    safe_link_option, exact_benchmark_link_options, exact_offline_link_options,
)
from CMake.Policy.CmakeFamilyIncludeDirectories import target_include_items
from CMake.Flow.CmakeFamilyMutations import has_unresolved_cmake_carrier
from CMake.Policy.CmakeFamilyProperties import (
    ambiguous_target_property_names,
    target_property_mutations,
)
from Family.Targets.CxetFamilyAliasPolicy import canonical_target
from Family.Targets.CxetFamilyBuildPolicy import exact_liburing_property
from Family.Targets.CxetFamilyCompressionPolicy import compression_link_values
from Family.Targets.CxetFamilyProductPolicy import external_link_error, product_edge_error
from Family.Sources.CxetFamilySourceAttachment import compiled_attachment
from Family.Sources.CxetFamilySourcePolicy import approved_external_source_mutation
from Family.Targets.CxetFamilyTargetInventory import (
    APPROVED_EXTERNAL_LINK_ITEMS,
    EXACT_TRANSITIVE_CLOSURES,
    FORBIDDEN_TRANSITIVE_TARGETS,
    OBJECT_ATTACHMENTS,
    REQUIRED_DIRECT_LINKS,
    ROLE_ALIAS,
    ROLE_CUSTOM,
    ROLE_IMPORTED,
    ROLE_PRODUCTION,
    ROLE_TEST,
    target_spec,
)
from Family.Targets.CxetFamilyTargetPolicy import (
    approved_external_compile_options,
    build_dependency_error,
    target_include_error,
    target_mutation_context_error,
    target_property_effect_error,
    target_source_context_error,
)


MUST = "MUST"
MAY = "MAY"
_VISIBILITY = frozenset({
    "PUBLIC", "PRIVATE", "INTERFACE", "LINK_PUBLIC", "LINK_PRIVATE",
})
_CONFIG_KEYWORDS = frozenset({"debug", "optimized", "general"})
_CONDITION_OPERATORS = frozenset({
    "BOOL", "CONFIG", "PLATFORM_ID", "NOT", "AND", "OR", "STREQUAL",
    "EQUAL", "VERSION_LESS", "VERSION_GREATER", "VERSION_EQUAL",
    "VERSION_LESS_EQUAL", "VERSION_GREATER_EQUAL", "COMPILE_LANGUAGE",
    "COMPILE_LANG_AND_ID", "LINK_LANGUAGE", "LINK_LANG_AND_ID",
})
_SOURCE_VISIBILITY_WORDS = frozenset({"PUBLIC", "PRIVATE", "INTERFACE"})


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _flat(instance, start: int = 0) -> list[str]:
    return [
        value for group in instance.token_groups[start:] for value in group]


def single_expanded_target_argument(
    values: tuple[str, ...],
) -> tuple[str | None, str | None]:
    """Require one CMake list-expanded value for a target owner argument."""
    if len(values) != 1:
        return None, (
            "first argument must expand to exactly one target value; "
            f"got {list(values)}")
    return values[0], None


def validate_single_target_argument_microcases(errors: list[str]) -> None:
    target, failure = single_expanded_target_argument(("owner",))
    if target != "owner" or failure is not None:
        errors.append(
            "target-argument self-check rejected one expanded target")
    for values in ((), ("owner", "alternate")):
        target, failure = single_expanded_target_argument(values)
        if target is not None or failure is None:
            errors.append(
                "target-argument self-check accepted a non-singleton first "
                f"argument: {list(values)}")



def split_generator(value: str) -> tuple[str, str] | None:
    if not value.startswith("$<") or not value.endswith(">"):
        return None
    content = value[2:-1]
    depth = 0
    index = 0
    while index < len(content):
        if content.startswith("$<", index):
            depth += 1
            index += 2
            continue
        if content[index] == ">" and depth:
            depth -= 1
        elif content[index] == ":" and depth == 0:
            return content[:index], content[index + 1:]
        index += 1
    return content, ""


def _split_top_level(value: str, separator: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value):
        if value.startswith("$<", index):
            depth += 1
            index += 2
            continue
        if value[index] == ">" and depth:
            depth -= 1
        elif value[index] == separator and depth == 0:
            result.append(value[start:index])
            start = index + 1
        index += 1
    result.append(value[start:])
    return result


def _condition_truth(value: str) -> bool | None:
    upper = value.upper()
    if upper in {"0", "FALSE", "OFF", "NO", "N", "IGNORE", ""}:
        return False
    if upper in {"1", "TRUE", "ON", "YES", "Y"}:
        return True
    parsed = split_generator(value)
    if parsed is None:
        return None
    operator, payload = parsed
    upper = operator.upper()
    if upper == "BOOL":
        return _condition_truth(payload)
    if upper == "NOT":
        nested = _condition_truth(payload)
        return None if nested is None else not nested
    if upper in {"AND", "OR"}:
        values = [_condition_truth(item) for item in _split_top_level(payload, ",")]
        if upper == "AND":
            return False if False in values else True if all(
                item is True for item in values) else None
        return True if True in values else False if all(
            item is False for item in values) else None
    return None


def _parse_link_item(
    value: str,
    certainty: str,
) -> tuple[list[tuple[str, str]], str | None]:
    if not value:
        return [], "empty link item"
    if "\\" in value:
        return [], f"unsupported CMake escape in link item {value}"
    if has_unresolved_cmake_carrier(value):
        return [], f"unresolved link carrier {value}"
    parsed = split_generator(value)
    if parsed is None:
        if "$<" in value:
            return [], f"malformed embedded link generator {value}"
        return [(value, certainty)], None
    operator, payload = parsed
    upper = operator.upper()
    if upper == "INSTALL_INTERFACE":
        return [], f"unreviewed install-interface link payload {value}"
    if upper in {"BUILD_INTERFACE", "LINK_ONLY"}:
        result: list[tuple[str, str]] = []
        for item in _split_top_level(payload, ";"):
            found, failure = _parse_link_item(item, certainty)
            if failure is not None:
                return [], failure
            result.extend(found)
        return result, None
    if upper == "TARGET_NAME_IF_EXISTS":
        found, failure = _parse_link_item(payload, MAY)
        return found, failure
    if upper == "IF":
        parts = _split_top_level(payload, ",")
        if len(parts) != 3:
            return [], f"malformed IF link generator {value}"
        truth = _condition_truth(parts[0])
        selected = parts[1:] if truth is None else [
            parts[1] if truth else parts[2]]
        branch_certainty = certainty if truth is not None else MAY
        result: list[tuple[str, str]] = []
        for branch in selected:
            found, failure = _parse_link_item(branch, branch_certainty)
            if failure is not None:
                return [], failure
            result.extend(found)
        return result, None
    if operator.startswith("$<"):
        truth = _condition_truth(operator)
        if truth is False:
            return [], None
        if truth is True:
            return _parse_link_item(payload, certainty)
        parsed_condition = split_generator(operator)
        if (parsed_condition is None or
                parsed_condition[0].upper() not in _CONDITION_OPERATORS):
            return [], f"unknown conditional link generator {value}"
        return _parse_link_item(payload, MAY)
    if upper in _CONDITION_OPERATORS and not payload:
        return [], None
    return [], f"unknown link generator operator {operator}"


def parse_link_values(values: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    result: list[tuple[str, str]] = []
    errors: list[str] = []
    pending: str | None = None
    for value in values:
        if value in _VISIBILITY:
            if pending is not None:
                errors.append(f"dangling link configuration keyword before {value}")
                pending = None
            continue
        if value in _CONFIG_KEYWORDS:
            if pending is not None:
                errors.append(f"adjacent link configuration keywords {pending} {value}")
            pending = value
            continue
        certainty = MAY if pending in {"debug", "optimized"} else MUST
        found, failure = _parse_link_item(value, certainty)
        if failure is not None:
            errors.append(failure)
        else:
            result.extend(found)
        pending = None
    if pending is not None:
        errors.append(f"dangling link configuration keyword {pending}")
    return result, errors


def validate_link_item_microcases(errors: list[str]) -> None:
    parsed, failures = parse_link_values([
        "$<BUILD_INTERFACE:cxet::cxet_lib>"])
    if parsed != [("cxet::cxet_lib", MUST)] or failures:
        errors.append("link-item self-check rejected build-interface baseline")
    for value in (
        "$<INSTALL_INTERFACE:trader::runtime>",
        "$<INSTALL_INTERFACE:archive.a;cxet::cxet_lib>",
    ):
        parsed, failures = parse_link_values([value])
        if parsed or not failures:
            errors.append(
                "link-item self-check accepted install-interface payload")
    if safe_link_option(r"\-flto"):
        errors.append("link-item self-check accepted escaped link option")


def _target_source_items(
    values: list[str],
) -> tuple[list[tuple[str, str]], list[str]]:
    """Retain the scope of every target_sources attachment."""
    result: list[tuple[str, str]] = []
    errors: list[str] = []
    visibility: str | None = None
    section_has_value = False
    for value in values:
        if value in _SOURCE_VISIBILITY_WORDS:
            if visibility is not None and not section_has_value:
                errors.append(f"empty target_sources {visibility} section")
            visibility = value
            section_has_value = False
            continue
        if visibility is None:
            errors.append(
                f"target_sources attachment has no visibility: {value}")
            continue
        result.append((visibility, value))
        section_has_value = True
    if visibility is not None and not section_has_value:
        errors.append(f"empty target_sources {visibility} section")
    if visibility is None and not values:
        errors.append("target_sources has no visibility or attachments")
    return result, errors


def _compiled_target_source(value: str) -> bool:
    provider, failure = source_object_dependency(value)
    return (
        compiled_attachment(value) or
        provider is not None and failure is None
    )


def _target_source_visibility_error(
    target_kind: str,
    visibility: str,
    value: str,
) -> str | None:
    if (_compiled_target_source(value) and (
            target_kind == "INTERFACE" or visibility != "PRIVATE")):
        return (
            f"compiler-effective source attachment {value} on a "
            f"{target_kind} target uses {visibility}; compiler-effective "
            "attachments must use PRIVATE on a concrete compiling target")
    return None


def validate_target_source_visibility_microcases(errors: list[str]) -> None:
    """Pin PRIVATE-to-INTERFACE scope transitions for compiled sources."""
    items, failures = _target_source_items([
        "PRIVATE", "owner.cpp", "INTERFACE", "consumer.cpp",
    ])
    if failures or items != [
            ("PRIVATE", "owner.cpp"),
            ("INTERFACE", "consumer.cpp")]:
        errors.append(
            "target-sources self-check lost PRIVATE-to-INTERFACE scope")
        return
    visibility_failures = [
        failure for visibility, value in items
        if (failure := _target_source_visibility_error(
            "STATIC", visibility, value)) is not None
    ]
    if len(visibility_failures) != 1 or "consumer.cpp" not in (
            visibility_failures[0] if visibility_failures else ""):
        errors.append(
            "target-sources self-check accepted an INTERFACE compiled "
            "attachment on a non-INTERFACE target")
    if _target_source_visibility_error(
            "STATIC", "PUBLIC", "consumer.cppm") is None:
        errors.append(
            "target-sources self-check accepted a PUBLIC module attachment")
    if _target_source_visibility_error(
            "STATIC", "PUBLIC", "consumer.S") is None:
        errors.append(
            "target-sources self-check accepted a PUBLIC assembly attachment")
    if _target_source_visibility_error(
            "STATIC", "PUBLIC", "consumer.hpp") is not None:
        errors.append(
            "target-sources self-check rejected a PUBLIC textual header")
    if _target_source_visibility_error(
            "INTERFACE", "INTERFACE", "consumer.cpp") is None:
        errors.append(
            "target-sources self-check accepted a compiled INTERFACE source "
            "on an INTERFACE target")
    if _target_source_visibility_error(
            "INTERFACE", "PRIVATE", "consumer.cpp") is None:
        errors.append(
            "source self-check accepted add_library(INTERFACE) compiled "
            "source as a concrete compiling target")


def source_object_dependency(value: str) -> tuple[str | None, str | None]:
    parsed = split_generator(value)
    if parsed is None:
        if "$<" in value:
            return None, f"malformed source generator {value}"
        return None, None
    operator, payload = parsed
    if operator.upper() != "TARGET_OBJECTS":
        return None, f"unsupported source generator expression {value}"
    if (not payload or ";" in payload or "$<" in payload or
            has_unresolved_cmake_carrier(payload)):
        return None, f"ambiguous TARGET_OBJECTS carrier {value}"
    return payload, None


@dataclass(frozen=True)
class Edge:
    consumer: str
    provider: str
    certainty: str
    instance: object


@dataclass(frozen=True)
class FamilyGraphs:
    may: dict[str, set[str]]
    must: dict[str, set[str]]
    edges: tuple[Edge, ...]


class _Builder:
    def __init__(
        self,
        instances,
        registry,
        aliases,
        errors: list[str],
        verification_friend_proof: frozenset[int],
    ) -> None:
        self.instances = instances
        self.registry = registry
        self.aliases = aliases
        self.errors = errors
        del verification_friend_proof
        self.edges: list[Edge] = []
        self.object_edges: list[Edge] = []

    def _owner(self, instance, raw: str, *, source: bool = False):
        if raw in self.aliases:
            self.errors.append(
                f"{_origin(instance)}: ALIAS {raw} cannot own a target mutation")
            return None
        if raw in APPROVED_EXTERNAL_LINK_ITEMS:
            return raw
        canonical = canonical_target(raw, self.aliases)
        context = self.registry.context_for_use(
            canonical, instance, allow_same=source)
        if context is None:
            return None
        role = self.registry.role(canonical, instance)
        if role in {ROLE_ALIAS, ROLE_CUSTOM, ROLE_IMPORTED}:
            self.errors.append(
                f"{_origin(instance)}: {role.lower()} target {canonical} "
                "cannot own this mutation")
            return None
        failure = (
            target_source_context_error(
                instance, canonical, self.registry)
            if source else
            target_mutation_context_error(
                instance, canonical, self.registry))
        if failure is not None:
            self.errors.append(f"{_origin(instance)}: {failure}")
            return None
        return canonical

    def _edge(
        self, instance, raw_consumer: str, raw_provider: str, certainty: str
    ) -> None:
        consumer = self._owner(instance, raw_consumer)
        if consumer is None or consumer in APPROVED_EXTERNAL_LINK_ITEMS:
            if consumer in APPROVED_EXTERNAL_LINK_ITEMS:
                self.errors.append(
                    f"{_origin(instance)}: external target {consumer} receives "
                    "active link mutation")
            return
        provider = canonical_target(raw_provider, self.aliases)
        if raw_provider in self.aliases and provider == raw_provider:
            self.errors.append(
                f"{_origin(instance)}: unresolved alias dependency {raw_provider}")
            return
        if provider in APPROVED_EXTERNAL_LINK_ITEMS:
            if (provider == "liburing::uring" and not (
                    self.registry.resolve(
                        provider, instance, require_prior=True,
                        roles=frozenset({ROLE_IMPORTED}), report=False) or
                    self.registry.exact_prior_imported(provider, instance))):
                self.errors.append(
                    f"{_origin(instance)}: liburing::uring is not imported "
                    "on every consumer path before use")
                return
            failure = external_link_error(
                instance, consumer, provider, self.registry)
            if failure is not None:
                self.errors.append(f"{_origin(instance)}: {failure}")
            return
        providers = self.registry.resolve(
            provider, instance, require_prior=False, report=False)
        if not providers:
            self.errors.append(
                f"{_origin(instance)}: unknown/unresolved link item "
                f"{raw_provider}")
            return
        failure = product_edge_error(
            instance, consumer, provider, self.registry)
        if failure is not None:
            self.errors.append(f"{_origin(instance)}: {failure}")
        self.edges.append(Edge(consumer, provider, certainty, instance))

    def _link_values(self, instance, sources: list[str], values: list[str]) -> None:
        values = compression_link_values(instance, values)
        parsed, failures = parse_link_values(values)
        for failure in failures:
            self.errors.append(f"{_origin(instance)}: {failure}")
        for source in sources:
            for provider, certainty in parsed:
                if provider.startswith("-"):
                    self.errors.append(
                        f"{_origin(instance)}: raw linker item {provider} in "
                        "target_link_libraries")
                    continue
                self._edge(instance, source, provider, certainty)

    def _source_values(
        self,
        instance,
        sources: list[str],
        values: list[str],
        *,
        visibility: str = "PRIVATE",
    ) -> None:
        for raw_source in sources:
            source = self._owner(instance, raw_source, source=True)
            if source is None:
                continue
            if source in APPROVED_EXTERNAL_LINK_ITEMS:
                for value in values:
                    if not approved_external_source_mutation(
                            instance, source, value):
                        self.errors.append(
                            f"{_origin(instance)}: unapproved external source "
                            f"mutation {source} <- {value}")
                continue
            declarations = self.registry.resolve(
                source, instance, require_prior=True, allow_same=True,
                report=False)
            target_kinds = {declaration.kind for declaration in declarations}
            for value in values:
                if len(target_kinds) == 1:
                    visibility_failure = _target_source_visibility_error(
                        next(iter(target_kinds)), visibility, value)
                    if visibility_failure is not None:
                        self.errors.append(
                            f"{_origin(instance)}: {visibility_failure}")
                provider, failure = source_object_dependency(value)
                if failure is not None:
                    self.errors.append(f"{_origin(instance)}: {failure}")
                    continue
                if provider is None:
                    continue
                canonical = canonical_target(provider, self.aliases)
                if provider in self.aliases:
                    self.errors.append(
                        f"{_origin(instance)}: TARGET_OBJECTS cannot name alias "
                        f"{provider}")
                    continue
                expected = OBJECT_ATTACHMENTS.get(source, frozenset())
                if canonical not in expected:
                    self.errors.append(
                        f"{_origin(instance)}: unreviewed TARGET_OBJECTS "
                        f"attachment {source} <- {canonical}")
                    continue
                declarations = self.registry.resolve(
                    canonical, instance, require_prior=True, report=False)
                startup_test_object = (
                    (canonical, source) in {
                        ("trader_startup_network", "trader_startup_fixture"),
                        ("trader_startup_network", "trader_startup_alert_fixture"),
                        ("trader_startup_network", "trader_startup_isolation_probe"),
                        ("trader_tbank_startup_network", "trader_tbank_startup_fixture"),
                    } and
                    instance.body.relative == "apps/trader/tests/startup/CMakeLists.txt" and
                    declarations and all(
                        declaration.instance.body.relative == instance.body.relative and
                        declaration.role == ROLE_TEST for declaration in declarations))
                if (not declarations or any(
                        declaration.kind != "OBJECT" or
                        declaration.role != ROLE_PRODUCTION and not startup_test_object
                        for declaration in declarations)):
                    self.errors.append(
                        f"{_origin(instance)}: TARGET_OBJECTS provider "
                        f"{canonical} is not an earlier concrete OBJECT target")
                    continue
                ownership = product_edge_error(
                    instance, source, canonical, self.registry)
                if ownership is not None:
                    self.errors.append(
                        f"{_origin(instance)}: TARGET_OBJECTS {ownership}")
                edge = Edge(source, canonical, MUST, instance)
                self.edges.append(edge)
                self.object_edges.append(edge)

    def _build_dependency(
        self, instance, raw_source: str, raw_provider: str
    ) -> None:
        if raw_source in self.aliases:
            self.errors.append(
                f"{_origin(instance)}: ALIAS {raw_source} cannot own "
                "add_dependencies")
            return
        source = canonical_target(raw_source, self.aliases)
        provider = canonical_target(raw_provider, self.aliases)
        if source in APPROVED_EXTERNAL_LINK_ITEMS:
            failure = build_dependency_error(
                instance, source, provider, self.registry)
            if failure is not None:
                self.errors.append(f"{_origin(instance)}: {failure}")
            return
        failure = build_dependency_error(
            instance, source, provider, self.registry)
        if failure is not None:
            self.errors.append(f"{_origin(instance)}: {failure}")
            return
        if provider in APPROVED_EXTERNAL_LINK_ITEMS:
            failure = external_link_error(
                instance, source, provider, self.registry)
            if failure is not None:
                self.errors.append(f"{_origin(instance)}: {failure}")
            return
        product_failure = product_edge_error(
            instance, source, provider, self.registry)
        if product_failure is not None:
            self.errors.append(f"{_origin(instance)}: {product_failure}")

    def _target_properties(self, instance) -> None:
        ambiguous = ambiguous_target_property_names(instance)
        if ambiguous:
            self.errors.append(
                f"{_origin(instance)}: ambiguous TARGET properties "
                + ", ".join(ambiguous))
            return
        mutations, _ = target_property_mutations(instance)
        for mutation in mutations:
            raw_source = mutation.target
            if raw_source in self.aliases:
                self.errors.append(
                    f"{_origin(instance)}: ALIAS {raw_source} cannot own "
                    f"property {mutation.name}")
                continue
            source = canonical_target(raw_source, self.aliases)
            if source in APPROVED_EXTERNAL_LINK_ITEMS:
                if not exact_liburing_property(instance, mutation):
                    self.errors.append(
                        f"{_origin(instance)}: unapproved external property "
                        f"{mutation.name} on {source}")
                continue
            declaration = self.registry.context_for_use(source, instance)
            if declaration is None:
                continue
            ownership_failure = target_mutation_context_error(
                instance, source, self.registry)
            if ownership_failure is not None:
                self.errors.append(
                    f"{_origin(instance)}: {ownership_failure}")
                continue
            handled, failure = target_property_effect_error(
                instance, source, mutation, declaration, self.registry,
                APPROVED_EXTERNAL_LINK_ITEMS)
            if handled:
                if failure is not None:
                    self.errors.append(f"{_origin(instance)}: {failure}")
                continue
            if mutation.name in {"SOURCES", "INTERFACE_SOURCES"}:
                self.errors.append(
                    f"{_origin(instance)}: replacing/appending target sources "
                    "through properties is unsupported")
                continue
            if mutation.name in {
                    "LINK_LIBRARIES", "INTERFACE_LINK_LIBRARIES",
                    "INTERFACE_LINK_LIBRARIES_DIRECT"}:
                if not mutation.append:
                    self.errors.append(
                        f"{_origin(instance)}: replacing link property "
                        f"{mutation.name} is unsupported")
                    continue
                self.errors.append(
                    f"{_origin(instance)}: first-party link property "
                    f"{mutation.name} append is unsupported; use reviewed "
                    "target_link_libraries")
            elif mutation.name == "INTERFACE_LINK_LIBRARIES_DIRECT_EXCLUDE":
                self.errors.append(
                    f"{_origin(instance)}: unsupported {mutation.name}")
            elif mutation.name in {
                    "LINK_OPTIONS", "INTERFACE_LINK_OPTIONS", "LINK_FLAGS"}:
                if any(not safe_link_option(value) for value in mutation.values):
                    self.errors.append(
                        f"{_origin(instance)}: unsafe {mutation.name} values "
                        f"{list(mutation.values)}")

    def _mutation_context(self, instance, sources: list[str]) -> None:
        for raw_source in sources:
            if raw_source in APPROVED_EXTERNAL_LINK_ITEMS:
                self.errors.append(
                    f"{_origin(instance)}: external target {raw_source} "
                    "receives unapproved target mutation")
                continue
            self._owner(instance, raw_source)

    def scan(self) -> FamilyGraphs:
        for instance in sorted(
                self.instances,
                key=lambda item: self.registry.order[id(item)]):
            command = instance.body.command.name
            single_target_required = (
                command.startswith("target_") or
                command in {
                    "add_dependencies", "add_executable", "add_library",
                })
            if not instance.token_groups:
                if single_target_required:
                    _, failure = single_expanded_target_argument(())
                    self.errors.append(
                        f"{_origin(instance)}: {command}: {failure}")
                continue
            if single_target_required:
                source, failure = single_expanded_target_argument(
                    tuple(instance.token_groups[0]))
                if failure is not None or source is None:
                    self.errors.append(
                        f"{_origin(instance)}: {command}: {failure}")
                    continue
                sources = [source]
            else:
                sources = list(instance.token_groups[0])
            if any(has_unresolved_cmake_carrier(source) or "$<" in source
                   for source in sources):
                if command.startswith("target_") or command in {
                        "add_dependencies", "set_property",
                        "set_target_properties"}:
                    self.errors.append(
                        f"{_origin(instance)}: dynamic target mutation owner "
                        f"{sources}")
                continue
            if command == "target_link_libraries":
                self._link_values(instance, sources, _flat(instance, 1))
            elif command in {"add_library", "add_executable"}:
                declaration = self.registry.by_name.get(sources[0], ())
                if any(item.alias or item.imported for item in declaration):
                    continue
                values = _flat(instance, 1)
                if command == "add_library" and values:
                    values = values[1:]
                self._source_values(instance, sources, values)
            elif command == "target_sources":
                items, failures = _target_source_items(_flat(instance, 1))
                for failure in failures:
                    self.errors.append(f"{_origin(instance)}: {failure}")
                for visibility, value in items:
                    self._source_values(
                        instance, sources, [value],
                        visibility=visibility)
            elif command == "add_dependencies":
                for source in sources:
                    for provider in _flat(instance, 1):
                        self._build_dependency(instance, source, provider)
            elif command in {"set_property", "set_target_properties"}:
                self._target_properties(instance)
            elif command == "target_include_directories":
                raw_values = _flat(instance, 1)
                for raw_source in sources:
                    source = self._owner(instance, raw_source)
                    if source is None:
                        continue
                    if source in APPROVED_EXTERNAL_LINK_ITEMS:
                        self.errors.append(
                            f"{_origin(instance)}: external target {source} "
                            "receives unapproved include mutation")
                        continue
                    declaration = self.registry.context_for_use(source, instance)
                    if declaration is None:
                        continue
                    values, grammar_failure = target_include_items(
                        [raw_source, *raw_values])
                    if grammar_failure is not None:
                        self.errors.append(
                            f"{_origin(instance)}: {source}: "
                            f"{grammar_failure}")
                        continue
                    for value in values:
                        failure = target_include_error(
                            source, declaration, value, instance,
                            contexts=self.registry, instances=self.instances)
                        if failure is not None:
                            self.errors.append(
                                f"{_origin(instance)}: {source}: {failure}")
            elif command in {"target_compile_options", "target_link_options"}:
                values = [
                    value for value in _flat(instance, 1)
                    if value not in _VISIBILITY]
                for raw_source in sources:
                    if (raw_source in APPROVED_EXTERNAL_LINK_ITEMS and
                            command == "target_compile_options" and
                            approved_external_compile_options(
                                instance, raw_source, values)):
                        continue
                    if raw_source in APPROVED_EXTERNAL_LINK_ITEMS:
                        self.errors.append(
                            f"{_origin(instance)}: external target "
                            f"{raw_source} receives unapproved {command}")
                        continue
                    self._owner(instance, raw_source)
                if (command == "target_link_options" and any(
                        not safe_link_option(value) for value in values) and
                        not exact_benchmark_link_options(instance, sources, values) and
                        not exact_offline_link_options(instance, sources, values)):
                    self.errors.append(
                        f"{_origin(instance)}: unsafe target_link_options "
                        f"{values}")
            elif command == "target_compile_definitions":
                values = [
                    value for value in _flat(instance, 1)
                    if value not in _VISIBILITY]
                for raw_source in sources:
                    if raw_source in APPROVED_EXTERNAL_LINK_ITEMS:
                        self.errors.append(
                            f"{_origin(instance)}: external target "
                            f"{raw_source} receives unapproved compile "
                            "definitions")
                        continue
                    self._owner(instance, raw_source)
            elif command == "target_compile_features":
                self._mutation_context(instance, sources)
            elif command in {
                    "link_libraries", "add_link_options",
                    "set_directory_properties"}:
                self.errors.append(
                    f"{_origin(instance)}: directory-scoped build/link "
                    f"mutation {command} is unsupported")
            elif command == "target_precompile_headers":
                self.errors.append(
                    f"{_origin(instance)}: target_precompile_headers is "
                    "unsupported")
        self._validate_object_inventory()
        return self._finish()

    def _validate_object_inventory(self) -> None:
        actual: dict[str, list[str]] = {}
        for edge in self.object_edges:
            actual.setdefault(edge.consumer, []).append(edge.provider)
        for consumer, expected in OBJECT_ATTACHMENTS.items():
            if consumer not in self.registry.concrete_names():
                continue
            found = actual.get(consumer, [])
            if (set(found) != set(expected) or
                    len(found) != len(expected)):
                self.errors.append(
                    f"TARGET_OBJECTS inventory for {consumer} changed: "
                    f"expected={sorted(expected)}, "
                    f"actual={sorted(found)}")

    def _finish(self) -> FamilyGraphs:
        names = self.registry.concrete_names()
        may = {name: set() for name in names}
        must = {name: set() for name in names}
        grouped: dict[tuple[str, str], list[Edge]] = {}
        for edge in self.edges:
            may.setdefault(edge.consumer, set()).add(edge.provider)
            grouped.setdefault((edge.consumer, edge.provider), []).append(edge)
        for (consumer, provider), edges in grouped.items():
            coverage = bounded_merge(
                self.errors, f"must-edge coverage {consumer}->{provider}",
                *(edge.instance.path_alternatives for edge in edges
                  if edge.certainty == MUST))
            if paths_cover(
                    universe=self.registry.declaration_paths(consumer),
                    evidence=coverage):
                must.setdefault(consumer, set()).add(provider)
        return FamilyGraphs(may, must, tuple(self.edges))


def build_family_graph(
    instances,
    registry,
    aliases,
    errors,
    *,
    verification_friend_proof: frozenset[int] = frozenset(),
) -> FamilyGraphs:
    return _Builder(
        instances,
        registry,
        aliases,
        errors,
        verification_friend_proof,
    ).scan()


def reachable_targets(root: str, graph: dict[str, set[str]]) -> set[str]:
    reachable: set[str] = set()
    pending = [root]
    while pending:
        target = pending.pop()
        if target in reachable:
            continue
        reachable.add(target)
        pending.extend(sorted(graph.get(target, ()), reverse=True))
    return reachable


def validate_direct_and_transitive_contracts(
    graphs: FamilyGraphs, errors: list[str], *, active_origins=None,
    disabled_contract_targets=frozenset(),
) -> None:
    # The caller supplies a proven exact OFF absence, not a missing-target
    # shortcut. No other contract owner is eligible for this exception.
    disabled = frozenset(disabled_contract_targets)
    unsupported = disabled - {'hft-compressor'}
    if unsupported:
        errors.append('unreviewed disabled contract targets: ' + ', '.join(sorted(unsupported)))
    present = disabled & (graphs.may.keys() | graphs.must.keys())
    if present:
        errors.append('disabled contract targets are still declared: ' + ', '.join(sorted(present)))
    disabled = (disabled - unsupported) - present

    def applicable(target):
        if target in disabled:
            return False
        if active_origins is None:
            return True
        spec = target_spec(target, None, "")
        if spec is None:
            errors.append(f"target {target}: required contract has no reviewed profile owner")
            return True
        return spec.owner in active_origins

    for target, expected in REQUIRED_DIRECT_LINKS.items():
        if not applicable(target):
            continue
        actual_may = graphs.may.get(target, set())
        actual_must = graphs.must.get(target, set())
        if actual_may != set(expected) or actual_must != set(expected):
            errors.append(
                f"target {target}: exact direct link contract changed: "
                f"expected={sorted(expected)}, may={sorted(actual_may)}, "
                f"must={sorted(actual_must)}")
    for root, exact in EXACT_TRANSITIVE_CLOSURES.items():
        if not applicable(root):
            continue
        may_reachable = reachable_targets(root, graphs.may)
        must_reachable = reachable_targets(root, graphs.must)
        unexpected = sorted(may_reachable - exact)
        missing = sorted(exact - must_reachable)
        if unexpected:
            errors.append(
                f"target {root}: unexpected may-reachable dependencies: "
                + ", ".join(unexpected))
        if missing:
            errors.append(
                f"target {root}: required must-reachable dependencies "
                "disappeared: " + ", ".join(missing))
    for root, forbidden in FORBIDDEN_TRANSITIVE_TARGETS.items():
        leaked = sorted(reachable_targets(root, graphs.may) & forbidden)
        if leaked:
            errors.append(
                f"target {root}: terminal capability entered read-only "
                "transitive closure: " + ", ".join(leaked))
