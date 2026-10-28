"""Exact target/effect inventory for the optional ``src/tests`` scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import (
    alternate_if,
    exact_context,
    first_body,
    first_if,
)
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT


ROOT = Path(__file__).resolve().parents[4]
RELATIVE = "src/tests/CMakeLists.txt"


@dataclass(frozen=True)
class TargetSpec:
    target: str
    source: str
    test: str
    declaration: int
    properties: int
    includes: int
    links: int
    registration: int
    context: tuple = ()


_FIXED_ROWS = (
    ("stress_buffer_pool_tests", "StressBufferPool.cpp", 48, 49, 51, 52, 87),
    ("decimal_to_scaled_tests", "DecimalToScaledTests.cpp", 121, 122, 123, 124, 125),
    ("registered_json_runtime_decimal_tests", "RegisteredJsonRuntimeDecimalTests.cpp", 127, 128, 129, 130, 131),
    ("hot_string_view_tests", "HotStringViewTests.cpp", 133, 134, 135, 136, 137),
    ("byte_scan_tests", "ByteScanTests.cpp", 139, 140, 141, 142, 143),
    ("cstring_primitives_tests", "CstringPrimitivesTests.cpp", 145, 146, 147, 148, 149),
    ("fast_rest_session_tests", "FastRestSessionTests.cpp", 176, 177, 178, 179, 180),
    ("fix_client_immediate_tests", "FixClientImmediateTests.cpp", 188, 189, 190, 191, 192),
    ("grpc_codec_tests", "GrpcCodecTests.cpp", 194, 195, 196, 197, 198),
    ("sbe_parse_foundation_tests", "SbeParseFoundationTests.cpp", 250, 251, 252, 253, 254),
    ("protobuf_parse_foundation_tests", "ProtobufParseFoundationTests.cpp", 256, 257, 258, 259, 260),
    ("ws_deflate_inflate_tests", "WsDeflateInflateTests.cpp", 311, 312, 313, 314, 315),
    ("binance_spot_fix_sbe_tests", "BinanceSpotFixSbeTests.cpp", 371, 374, 375, 376, 377),
    ("prepared_json_template_tests", "PreparedJsonTemplateTests.cpp", 604, 605, 606, 607, 608),
    ("transport_resilience_private_auth_tests", "TransportResiliencePrivateAuthTests.cpp", 618, 619, 620, 621, 622),
    ("ws_runtime_tests", "WsRuntimeTests.cpp", 624, 625, 626, 627, 628),
    ("order_ws_pending_state_tests", "OrderPendingStateTests.cpp", 630, 631, 632, 633, 634),
    ("user_ws_first_unique_tests", "UserWsFirstUniqueTests.cpp", 636, 637, 638, 639, 640),
    ("scoped_pow10_tests", "ScopedBufferPow10Tests.cpp", 643, 644, 645, 646, 647),
    ("spsc_ring_tests", "SpscRingTests.cpp", 650, 651, 652, 653, 654),
)


FIXED_SPECS = tuple(TargetSpec(
    target, source, target.removesuffix("_tests"), declaration, properties,
    includes, links, registration)
    for target, source, declaration, properties, includes, links, registration
    in _FIXED_ROWS)

_REPLAY = first_if(RELATIVE, 733, ("TARGET", "cxet_replay_core"))
_COMPRESSOR = first_if(RELATIVE, 745, ("TARGET", "hft_compressor_core"))

OPTIONAL_SPECS = (
    TargetSpec(
        "replay_config_tests", "ReplayConfigTests.cpp", "replay_config",
        734, 735, 736, 737, 738, (_REPLAY,)),
    TargetSpec(
        "replay_session_tests", "ReplaySessionTests.cpp", "replay_session",
        740, 741, 742, 744, 749, (_REPLAY,)),
)


def _flat(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _repo_path(instance, value: str) -> str | None:
    if any(marker in value for marker in ("${", "$ENV{", "$CACHE{", "$<")):
        return None
    path = Path(value)
    source = instance.evaluation.source_base
    source_text = source.as_posix().rstrip("/")
    normalized = path.as_posix().rstrip("/")
    if path.is_absolute():
        candidate = path
    elif normalized == source_text or normalized.startswith(source_text + "/"):
        candidate = ROOT / path
    else:
        candidate = ROOT / source / path
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _instances_for(instances, command: str, target: str):
    return [
        instance for instance in instances
        if instance.body.relative == RELATIVE and
        instance.body.command.name == command and
        instance.token_groups and
        instance.token_groups[0] == (target,)
    ]


def _one(
    instances, command: str, spec: TargetSpec, line: int, errors: list[str]
):
    found = _instances_for(instances, command, spec.target)
    allowed_lines = {line}
    if (command == "target_link_libraries" and
            spec.target == "replay_session_tests"):
        # The secondary compressor edge is separately pinned with its nested
        # TARGET guard below; it must not make the primary replay edge look
        # duplicated.
        allowed_lines.add(746)
    selected = [value for value in found if value.body.command.line == line]
    if ({value.body.command.line for value in found} != allowed_lines or
            len(selected) != 1 or not exact_context(
                selected[0].evaluation.structural_context, spec.context)):
        errors.append(
            f"{RELATIVE}:{line}: exact {command} identity/context changed "
            f"for {spec.target}")
        return None
    return selected[0]


def _validate_spec(spec: TargetSpec, instances, errors: list[str]) -> None:
    declaration = _one(
        instances, "add_executable", spec, spec.declaration, errors)
    properties = _one(
        instances, "set_target_properties", spec, spec.properties, errors)
    includes = _one(
        instances, "target_include_directories", spec, spec.includes, errors)
    links = _one(
        instances, "target_link_libraries", spec, spec.links, errors)
    registrations = [
        instance for instance in instances
        if instance.body.relative == RELATIVE and
        instance.body.command.name == "add_test" and
        _flat(instance) == [
            "NAME", spec.test, "COMMAND", spec.target]
    ]
    if (len(registrations) != 1 or
            registrations[0].body.command.line != spec.registration or
            not exact_context(
                registrations[0].evaluation.structural_context,
                spec.context)):
        errors.append(
            f"{RELATIVE}:{spec.registration}: exact test registration "
            f"changed for {spec.target}")

    if declaration is not None:
        flat = _flat(declaration)
        expected_sources = [spec.source]
        if spec.target == "binance_spot_fix_sbe_tests":
            expected_sources.append("BinanceSpotFixSbeMarketParserTests.cpp")
        if (flat[:1] != [spec.target] or
                [_repo_path(declaration, value) for value in flat[1:]] != [
                    f"src/tests/{value}" for value in expected_sources]):
            errors.append(
                f"{RELATIVE}:{spec.declaration}: source owner changed for "
                f"{spec.target}")
    if properties is not None and _flat(properties) != [
            spec.target, "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            SYNTHETIC_BINARY_ROOT]:
        errors.append(
            f"{RELATIVE}:{spec.properties}: output property changed for "
            f"{spec.target}")
    if includes is not None:
        flat = _flat(includes)
        paths = [_repo_path(includes, value) for value in flat[2:]]
        expected_paths = (
            ["src/tests"]
            if spec.target in {"replay_config_tests", "replay_session_tests"}
            else [
                "src/src/Core/include",
                "src/src/Contracts/include",
                "src/tests",
            ]
        )
        if flat[:2] != [spec.target, "PRIVATE"] or paths != expected_paths:
            errors.append(
                f"{RELATIVE}:{spec.includes}: include ownership changed for "
                f"{spec.target}")
    if links is not None:
        dependency = (
            "cxet_replay_core"
            if spec.target in {"replay_config_tests", "replay_session_tests"}
            else "cxet_lib"
        )
        expected = [spec.target, "PRIVATE", dependency, "GTest::gtest",
                    "GTest::gtest_main"]
        if spec.target == "hot_string_view_tests":
            expected.append("absl::flat_hash_map")
        if _flat(links) != expected:
            errors.append(
                f"{RELATIVE}:{spec.links}: link closure changed for "
                f"{spec.target}")

    effects = [value for value in (
        declaration, properties, includes, links,
        registrations[0] if len(registrations) == 1 else None) if value]
    if effects and [value.evaluation.ordinal for value in effects] != sorted(
            value.evaluation.ordinal for value in effects):
        errors.append(
            f"{RELATIVE}:{spec.declaration}: effects precede declaration "
            f"for {spec.target}")


def validate_safety_target_contract(instances, errors: list[str]) -> None:
    """Pin fixed and replay targets to their real guarded effects."""
    for spec in (*FIXED_SPECS, *OPTIONAL_SPECS):
        _validate_spec(spec, instances, errors)

    replay_definitions = {
        743: (
            ["replay_session_tests", "PRIVATE",
             f"CXET_REPO_ROOT={ROOT.as_posix()}"], (_REPLAY,)),
        747: (
            ["replay_session_tests", "PRIVATE",
             "CXET_REPLAY_TEST_WITH_HFT_COMPRESSOR=1"],
            (_REPLAY, _COMPRESSOR)),
    }
    for line, (expected, context) in replay_definitions.items():
        found = [
            instance for instance in instances
            if instance.body.relative == RELATIVE and
            instance.body.command.name == "target_compile_definitions" and
            instance.body.command.line == line]
        if (len(found) != 1 or _flat(found[0]) != expected or
                not exact_context(
                    found[0].evaluation.structural_context, context)):
            errors.append(
                f"{RELATIVE}:{line}: replay definition/context changed")

    compressor_links = [
        instance for instance in instances
        if instance.body.relative == RELATIVE and
        instance.body.command.name == "target_link_libraries" and
        instance.body.command.line == 746]
    if (len(compressor_links) != 1 or
            _flat(compressor_links[0]) != [
                "replay_session_tests", "PRIVATE", "hft_compressor_core"] or
            not exact_context(
                compressor_links[0].evaluation.structural_context,
                (_REPLAY, _COMPRESSOR))):
        errors.append(f"{RELATIVE}:746: replay compressor guard changed")


def _else_frame(
    line: int,
    opener: tuple[str, ...],
    prior_elseif: tuple[str, ...] | None = None,
):
    prior = [("if", opener)]
    if prior_elseif is not None:
        prior.append(("elseif", prior_elseif))
    return (
        "if", RELATIVE, line, opener, "else", (), tuple(prior))


def validate_stress_fold_context(commands, errors: list[str]) -> None:
    """Pin the only reviewed state-mutating direct foreach fold."""
    outer = first_if(RELATIVE, 57, ("CXET_STRESS_SANITIZERS",))
    enabled = first_if(
        RELATIVE, 58,
        ("CXET_STRESS_SANITIZERS", "STREQUAL", "ON"))
    enabled_else = _else_frame(
        58, ("CXET_STRESS_SANITIZERS", "STREQUAL", "ON"))
    loop = first_body(
        "foreach", RELATIVE, 65, ("_s", "IN", "LISTS", "_san_list"))
    thread = first_if(RELATIVE, 67, ("_s", "STREQUAL", "thread"))
    undefined = alternate_if(
        RELATIVE, 67, ("_s", "STREQUAL", "thread"),
        ("_s", "STREQUAL", "undefined"))
    address = (
        "if", RELATIVE, 67, ("_s", "STREQUAL", "thread"),
        "elseif", ("_s", "STREQUAL", "address"),
        (("if", ("_s", "STREQUAL", "thread")),
         ("elseif", ("_s", "STREQUAL", "undefined"))),
    )
    flags = first_if(RELATIVE, 75, ("_stress_san_flags",))
    expected = {
        (59, "set"): (
            ("_stress_san", "thread,undefined"), (outer, enabled)),
        (61, "set"): (
            ("_stress_san", "${CXET_STRESS_SANITIZERS}"),
            (outer, enabled_else)),
        (63, "string"): (
            ("REPLACE", ",", ";", "_san_list", "${_stress_san}"),
            (outer,)),
        (64, "set"): (("_stress_san_flags", ""), (outer,)),
        (65, "foreach"): (
            ("_s", "IN", "LISTS", "_san_list"), (outer,)),
        (66, "string"): (("STRIP", "${_s}", "_s"), (outer, loop)),
        (68, "list"): (
            ("APPEND", "_stress_san_flags", "-fsanitize=thread"),
            (outer, loop, thread)),
        (70, "list"): (
            ("APPEND", "_stress_san_flags", "-fsanitize=undefined"),
            (outer, loop, undefined)),
        (72, "list"): (
            ("APPEND", "_stress_san_flags", "-fsanitize=address"),
            (outer, loop, address)),
        (76, "target_compile_options"): (
            ("stress_buffer_pool_tests", "PRIVATE", "${_stress_san_flags}"),
            (outer, flags)),
        (77, "target_link_options"): (
            ("stress_buffer_pool_tests", "PRIVATE", "${_stress_san_flags}"),
            (outer, flags)),
    }
    for identity, (tokens, context) in expected.items():
        found = [
            active for active in commands
            if active.relative == RELATIVE and
            (active.command.line, active.command.name) == identity]
        if (len(found) != 1 or
                tuple(cmake_list_words(found[0].command.body)) != tokens or
                not exact_context(found[0].structural_context, context)):
            errors.append(
                f"{RELATIVE}:{identity[0]}: stress foreach fold/context "
                "changed")


def validate_optional_guard_structure(commands, errors: list[str]) -> None:
    """Pin replay branch openers and exact closes."""
    expected = {
        (733, "if"): (("TARGET", "cxet_replay_core"), ()),
        (745, "if"): (("TARGET", "hft_compressor_core"), (_REPLAY,)),
        (748, "endif"): ((), (_REPLAY, _COMPRESSOR)),
        (750, "endif"): ((), (_REPLAY,)),
    }
    for identity, (tokens, context) in expected.items():
        found = [
            active for active in commands
            if active.relative == RELATIVE and
            (active.command.line, active.command.name) == identity]
        if (len(found) != 1 or
                tuple(cmake_list_words(found[0].command.body)) != tokens or
                not exact_context(found[0].structural_context, context)):
            errors.append(
                f"{RELATIVE}:{identity[0]}: optional target guard changed")
