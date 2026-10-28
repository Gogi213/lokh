"""Bounded root-only ownership and build-effect mutation guards."""

from __future__ import annotations

from CMake.Policy.CmakeFamilyEffectPolicy import approved_effect_set, effect_variable
from CMake.Policy.CmakeFamilyCachePolicy import (
    approved_root_cache_set,
    approved_root_option,
)
from CMake.Policy.CmakeFamilyPropertyPolicy import validate_root_property_command
from CMake.Policy.CmakeFamilyVendorPolicy import (
    approved_root_vendor_target_mutation,
    validate_root_vendor_contract,
)
from Family.Targets.CxetFamilyOwnershipPolicy import TARGET_OWNERS


_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_DECLARATIONS = frozenset({
    "add_executable", "add_library", "add_custom_target"})
_TARGET_MUTATIONS = frozenset({
    "add_dependencies",
    "set_property",
    "set_target_properties",
    "target_compile_definitions",
    "target_compile_features",
    "target_compile_options",
    "target_include_directories",
    "target_link_libraries",
    "target_link_options",
    "target_precompile_headers",
    "target_sources",
})
_EFFECT_WRITERS = frozenset({
    "aux_source_directory",
    "cmake_parse_arguments",
    "cmake_path",
    "file",
    "get_filename_component",
    "get_property",
    "get_target_property",
    "list",
    "math",
    "option",
    "separate_arguments",
    "set",
    "string",
    "unset",
})
_CANONICAL_ALIASES = frozenset({
    "diagnostic::runtime",
    "cxet::cxet_lib",
    "cxet::read_only_contracts",
    "hft_backtest::core",
    "hft_parser::execution_client",
    "hft_parser::history_client",
    "hft_parser::projection_client",
    "hft_parser::current_reference_client",
    "hft_parser::session_client",
    "hftrec::corpus_contract",
    "trader::market_client",
    "trader::public_analytics",
    "trader::projection_client",
    "trader::live_runtime",
    "trading_core::algorithm",
    "trading_core::execution",
    "trading_core::strategy",
    "vetron::gateway",
    "vetron::process",
    "vetron::runtime",
})
_VENDOR_TARGETS = {
    "extra/secp256k1": frozenset({
        "secp256k1", "secp256k1_precomputed"}),
    "extra/abseil-cpp": frozenset({"absl_raw_hash_set", "absl_type_traits"}),
}
_RELEASE_EFFECT_VARIABLES = frozenset({
    "CMAKE_C_FLAGS_RELEASE", "CMAKE_CXX_FLAGS_RELEASE",
})


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _dynamic(value: str) -> bool:
    return any(marker in value for marker in _CARRIERS)


def _declaration_target(command, tokenize) -> str | None:
    tokens = [_unquote(value) for value in tokenize(command.body)]
    return tokens[0] if tokens else None


def _mutation_owners(command, tokenize) -> list[str] | None:
    tokens = [_unquote(value) for value in tokenize(command.body)]
    if not tokens:
        return None
    if command.name == "set_property":
        if tokens[0].upper() != "TARGET":
            return []
        try:
            end = next(
                index for index, token in enumerate(tokens[1:], 1)
                if token.upper() in {"APPEND", "APPEND_STRING", "PROPERTY"})
        except StopIteration:
            return None
        return tokens[1:end]
    if command.name == "set_target_properties":
        try:
            end = next(
                index for index, token in enumerate(tokens)
                if token.upper() == "PROPERTIES")
        except StopIteration:
            return None
        return tokens[:end]
    return [tokens[0]]


def _exact_include_root_set(tokens: list[str]) -> bool:
    return tokens == [
        "CXET_LIB_INCLUDE_DIR",
        "${CMAKE_SOURCE_DIR}/src/src/Core/include",
        "${CMAKE_SOURCE_DIR}/src/src/Contracts/include",
    ]


def _effect_candidates(command, tokens: list[str]) -> list[str]:
    if not tokens:
        return []
    if command.name in {"set", "unset", "option"}:
        return tokens[:1]
    if command.name == "list":
        operation = tokens[0].upper()
        if operation in {"POP_BACK", "POP_FRONT"}:
            return tokens[1:]
        index = {
            "APPEND": 1, "PREPEND": 1, "INSERT": 1, "SORT": 1,
            "REVERSE": 1, "REMOVE_DUPLICATES": 1, "REMOVE_ITEM": 1,
            "REMOVE_AT": 1, "FILTER": 1, "TRANSFORM": 1,
            "LENGTH": 2, "GET": -1, "JOIN": 3, "SUBLIST": 4,
            "FIND": 3,
        }.get(operation)
        return [tokens[index]] if index is not None and len(tokens) > abs(index) else []
    if command.name == "string":
        operation = tokens[0].upper()
        index = {
            "APPEND": 1, "PREPEND": 1, "CONCAT": 1, "JOIN": 2,
            "TOUPPER": 2, "TOLOWER": 2, "REPLACE": 3,
            "MD5": 1, "SHA1": 1, "SHA224": 1, "SHA256": 1,
            "SHA384": 1, "SHA512": 1, "SUBSTRING": 4, "FIND": 3,
        }.get(operation)
        return [tokens[index]] if index is not None and len(tokens) > index else []
    if command.name == "file":
        operation = tokens[0].upper()
        if operation in {"GLOB", "GLOB_RECURSE"}:
            return tokens[1:2]
        if operation in {
                "READ", "STRINGS", "SIZE", "TIMESTAMP", "REAL_PATH",
                "MD5", "SHA1", "SHA224", "SHA256", "SHA384", "SHA512"}:
            return tokens[2:3]
        return []
    if command.name in {
            "get_filename_component", "get_property", "get_target_property",
            "separate_arguments"}:
        return tokens[:1]
    if command.name in {"aux_source_directory", "math"}:
        return tokens[1:2]
    if command.name == "cmake_parse_arguments":
        return tokens[:1]
    return []


def _approved_root_effect_set(
    command_name: str,
    variable: str,
    tokens: list[str],
    expanded_values: list[str],
) -> bool:
    if command_name != "set":
        return False
    exact_effect = approved_effect_set(
        "CMakeLists.txt", variable, tokens, expanded_values)
    if variable in _RELEASE_EFFECT_VARIABLES:
        # The raw cache spelling contains an indirection.  It is safe only when
        # that producer was proven and every expansion is an exact release
        # value; a syntactically approved CACHE form is not independent proof.
        return exact_effect
    return exact_effect or (
        "CACHE" in {token.upper() for token in tokens} and
        approved_root_cache_set(tokens))


def validate_root_ownership_effect_microcases(errors: list[str]) -> None:
    """Pin release-flag provenance across the CACHE indirection."""
    raw = [
        "CMAKE_CXX_FLAGS_RELEASE", "${_CXET_RELEASE_FLAGS}",
        "CACHE", "STRING", "CXET Release C++ flags", "FORCE",
    ]
    for value in ("-O3 -DNDEBUG", "-O1 -DNDEBUG -ffunction-sections -fdata-sections",
                  "-O2 -DNDEBUG -ffunction-sections -fdata-sections"):
        if not _approved_root_effect_set("set", raw[0], raw, [value]):
            errors.append(
                "root-effect self-check rejected exact release flag provenance")
    if _approved_root_effect_set(
            "set", raw[0], raw, ["-O3 -include/tmp/foreign.hpp"]):
        errors.append(
            "root-effect self-check accepted poisoned release flag provenance")
    if _approved_root_effect_set(
            "set", raw[0], raw,
            ["-O2 -DNDEBUG -ffunction-sections -fdata-sections -include/tmp/foreign.hpp"]):
        errors.append(
            "root-effect self-check accepted poisoned deployment release flags")


def validate_root_ownership_effects(
    commands,
    tokenize,
    errors: list[str],
    viable_offsets: frozenset[int],
) -> None:
    """Reject root redirection and mutation of composed family targets."""
    validate_root_vendor_contract(commands, errors, viable_offsets)
    root_targets: set[str] = set()
    vendor_targets: set[str] = set()
    composed = False
    release_values: set[str] | None = set()
    include_root_sets = 0

    for command in commands:
        if command.offset not in viable_offsets:
            continue
        tokens = [_unquote(value) for value in tokenize(command.body)]
        origin = f"CMakeLists.txt:{command.line}"

        if command.name == "set" and tokens[:1] == ["_CXET_RELEASE_FLAGS"]:
            release_values = (
                {f"{opt} -DNDEBUG -ffunction-sections -fdata-sections" for opt in ("-O3", "-O1", "-O2")}
                if tokens == ["_CXET_RELEASE_FLAGS", "${_CXET_RELEASE_OPTIMIZATION} -DNDEBUG -ffunction-sections -fdata-sections"]
                else None)
        elif (command.name == "string" and len(tokens) >= 3 and
              tokens[:2] == ["APPEND", "_CXET_RELEASE_FLAGS"]):
            if release_values is not None and tokens[2:] == [" -march=native -mtune=native"]:
                release_values |= {
                    value + " -march=native -mtune=native" for value in release_values}
            else:
                release_values = None
        elif (tokens and "_CXET_RELEASE_FLAGS" in tokens and
              command.name in _EFFECT_WRITERS and
              not (command.name == "set" and tokens[0] in {
                  "CMAKE_C_FLAGS_RELEASE", "CMAKE_CXX_FLAGS_RELEASE"})):
            release_values = None

        if command.name == "option" and not approved_root_option(tokens):
            errors.append(f"{origin}: unapproved root option CACHE producer")
        if (command.name == "set" and
                "CACHE" in {token.upper() for token in tokens} and
                not approved_root_cache_set(tokens)):
            errors.append(f"{origin}: unapproved root CACHE producer")

        if (command.name in {"set", "unset", "list", "string"} and
                tokens and "CXET_LIB_INCLUDE_DIR" in tokens):
            if command.name == "set" and _exact_include_root_set(tokens):
                include_root_sets += 1
            else:
                errors.append(
                    f"{origin}: unapproved CXET_LIB_INCLUDE_DIR mutation")

        if command.name in _EFFECT_WRITERS:
            for variable in _effect_candidates(command, tokens):
                if _dynamic(variable):
                    errors.append(
                        f"{origin}: unresolved root variable destination "
                        f"{variable}")
                    continue
                if not effect_variable(variable):
                    continue
                expanded_values = (
                    sorted(release_values)
                    if variable in _RELEASE_EFFECT_VARIABLES and
                    release_values is not None
                    else tokens[1:2]
                )
                approved_release = _approved_root_effect_set(
                    command.name, variable, tokens, expanded_values)
                approved_absl = (
                    command.name == "set" and
                    tokens in (["ABSL_PROPAGATE_CXX_STD", "ON"],
                               ["ABSL_USE_SYSTEM_INCLUDES", "ON"],
                               ["ABSL_ENABLE_INSTALL", "OFF"]))
                approved_fetch_clear = (
                    command.name == "unset" and
                    tokens in (["FETCHCONTENT_SOURCE_DIR_GOOGLETEST"],
                               ["FETCHCONTENT_SOURCE_DIR_GOOGLETEST",
                                "CACHE"]))
                if (not approved_release and not approved_absl and
                        not approved_fetch_clear):
                    errors.append(
                        f"{origin}: unapproved root build-effect variable "
                        f"mutation {variable}")

        if command.name == "add_subdirectory" and tokens:
            vendor_targets.update(
                _VENDOR_TARGETS.get(tokens[0].rstrip("/"), ()))
            composed = composed or tokens[0].rstrip("/") == "src/src"
        if command.name in _DECLARATIONS:
            target = _declaration_target(command, tokenize)
            if target is None or _dynamic(target):
                if composed:
                    errors.append(
                        f"{origin}: dynamic root target declaration after "
                        "family composition")
                continue
            tail = {token.upper() for token in tokens[1:]}
            if "ALIAS" in tail:
                errors.append(
                    f"{origin}: root target aliases are not part of the "
                    "reviewed root inventory")
                continue
            if target in TARGET_OWNERS or target in _CANONICAL_ALIASES:
                errors.append(
                    f"{origin}: root redeclares composed family target {target}")
                continue
            root_targets.add(target)
            continue
        if command.name in {"set_property", "set_target_properties"}:
            validate_root_property_command(
                command.name, tokens, root_targets, origin, errors)
        if command.name not in _TARGET_MUTATIONS:
            continue
        owners = _mutation_owners(command, tokenize)
        if owners is None or any(_dynamic(owner) for owner in owners):
            errors.append(
                f"{origin}: unresolved root target mutation owner {owners}")
            continue
        for owner in owners:
            if not composed and owner in vendor_targets:
                if not approved_root_vendor_target_mutation(
                        command.name, tokens):
                    errors.append(
                        f"{origin}: unapproved direct vendor target mutation "
                        f"{command.name}({tokens})")
                continue
            if owner not in root_targets or not composed:
                errors.append(
                    f"{origin}: root mutates undeclared/non-owned target "
                    f"{owner}")

    if include_root_sets != 1:
        errors.append(
            "CMakeLists.txt: expected one exact CXET_LIB_INCLUDE_DIR producer, "
            f"found {include_root_sets}")
