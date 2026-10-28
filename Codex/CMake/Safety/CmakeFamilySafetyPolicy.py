"""Exact root-branch ownership policy for the optional CXET safety suite."""

from __future__ import annotations

from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import (
    alternate_if,
    exact_context,
    first_if,
)
from CMake.Policy.CmakeFamilyProperties import target_property_mutations
from CMake.Safety.CmakeFamilySafetyContract import (
    validate_optional_guard_structure,
    validate_safety_target_contract,
    validate_stress_fold_context,
)


ROOT = Path(__file__).resolve().parents[4]
SAFETY_CMAKE = "src/tests/CMakeLists.txt"
SAFETY_DIRECTORY = "src/tests"

SAFETY_FIXED_TARGETS = (
    "stress_buffer_pool_tests",
    "decimal_to_scaled_tests",
    "registered_json_runtime_decimal_tests",
    "hot_string_view_tests",
    "byte_scan_tests",
    "cstring_primitives_tests",
    "fast_rest_session_tests",
    "fix_client_immediate_tests",
    "grpc_codec_tests",
    "sbe_parse_foundation_tests",
    "protobuf_parse_foundation_tests",
    "ws_deflate_inflate_tests",
    "binance_spot_fix_sbe_tests",
    "prepared_json_template_tests",
    "transport_resilience_private_auth_tests",
    "ws_runtime_tests",
    "order_ws_pending_state_tests",
    "user_ws_first_unique_tests",
    "scoped_pow10_tests",
    "spsc_ring_tests",
)

SAFETY_FUZZ_SOURCES = {
    "cxet_fuzz_ws_frame_decode": 'Fuzz/WsFrameDecodeFuzzer.cpp',
    "cxet_fuzz_fix_tag_value": 'Fuzz/FixTagValueFuzzer.cpp',
    "cxet_fuzz_protobuf_cursor": 'Fuzz/ProtobufCursorFuzzer.cpp',
    "cxet_fuzz_sbe_cursor": 'Fuzz/SbeCursorFuzzer.cpp',
    "cxet_fuzz_prepared_payload": 'Fuzz/PreparedPayloadFuzzer.cpp',
}

_SAFETY_GUARD = ("CXET_SAFETY_BUILD",)
_FUZZ_GUARD = (
    "CXET_SANITIZER_PROFILE", "STREQUAL", "address-undefined",
)
_THREAD_GUARD = (
    "CXET_SANITIZER_PROFILE", "STREQUAL", "thread",
)


def approved_safety_parent_scope(
    owner,
    member_relative: str,
    raw_words: list[str],
    signatures,
) -> bool:
    """Approve only the reviewed fuzzer helper's exact caller-list return."""
    return (
        owner[1] == "cxet_add_bounded_fuzzer" and
        member_relative == SAFETY_CMAKE and
        raw_words == [
            "_CXET_SAFETY_TARGETS", "${_CXET_SAFETY_TARGETS}",
            "PARENT_SCOPE",
        ] and
        bool(signatures) and all(
            signature.variable == "_CXET_SAFETY_TARGETS" and
            signature.parent_scope and signature.cache_type is None and
            not signature.cache_removal
            for signature in signatures)
    )


def _safety_frame():
    return first_if(SAFETY_CMAKE, 662, _SAFETY_GUARD)


def _fuzz_frame():
    return first_if(SAFETY_CMAKE, 709, _FUZZ_GUARD)


def _address_frame():
    return first_if(SAFETY_CMAKE, 16, _FUZZ_GUARD)


def _thread_frame():
    return alternate_if(SAFETY_CMAKE, 16, _FUZZ_GUARD, _THREAD_GUARD)


def _validate_gtest_provider(
    commands, tokenize, viable_ordinals: frozenset[int], errors: list[str]
) -> None:
    """Require one pinned top-level provider before every GTest consumer."""
    expected = (
        ("include", ("FetchContent",)),
        ("fetchcontent_declare", (
            "googletest", "URL",
            "https://github.com/google/googletest/archive/refs/tags/"
            "v1.14.0.tar.gz",
            "URL_HASH",
            "SHA256=8ad598c73ad796e0d8280b082cebd82a630d73e73cd3c7005"
            "7938a6501bba5d7",
            "DOWNLOAD_EXTRACT_TIMESTAMP", "TRUE")),
        ("set", (
            "gtest_force_shared_crt", "ON", "CACHE", "BOOL", "", "FORCE")),
        ("fetchcontent_makeavailable", ("googletest",)),
        ("enable_testing", ()),
    )
    provider_names = {
        "fetchcontent_declare", "fetchcontent_makeavailable", "enable_testing",
    }
    selected = []
    for active in commands:
        if active.relative != SAFETY_CMAKE:
            continue
        tokens = tuple(tokenize(active.command.body))
        if (active.command.name in provider_names or
                (active.command.name == "include" and
                 tokens[:1] == ("FetchContent",)) or
                (active.command.name == "set" and
                 tokens[:1] == ("gtest_force_shared_crt",))):
            selected.append(active)
    actual = [
        (active.command.name, tuple(tokenize(active.command.body)))
        for active in selected]
    if actual != list(expected):
        errors.append(
            f"{SAFETY_CMAKE}: pinned GTest provider set/order changed")
    for active in selected:
        if (active.scope != SAFETY_CMAKE or
                active.source_base != Path(SAFETY_DIRECTORY) or
                active.binary_base != Path(SAFETY_DIRECTORY) or
                not exact_context(active.structural_context, ())):
            errors.append(
                f"{SAFETY_CMAKE}:{active.command.line}: GTest provider escaped "
                "top-level safety ownership")
        if active.ordinal not in viable_ordinals:
            errors.append(
                f"{SAFETY_CMAKE}:{active.command.line}: GTest provider is not "
                "on a viable execution path")

    consumers = [
        active for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.name == "target_link_libraries" and
        any(value.startswith("GTest::")
            for value in tokenize(active.command.body))
    ]
    if not consumers:
        errors.append(f"{SAFETY_CMAKE}: GTest provider has no owned consumer")
    elif (len(selected) != len(expected) or
          max(active.ordinal for active in selected) >=
          min(active.ordinal for active in consumers)):
        errors.append(
            f"{SAFETY_CMAKE}: GTest provider/enable_testing must precede the "
            "first GTest consumer")
    if consumers and not any(
            active.ordinal in viable_ordinals for active in consumers):
        errors.append(
            f"{SAFETY_CMAKE}: no GTest consumer is on a viable execution path")


def _validate_structural_contract(commands, tokenize, errors: list[str]) -> None:
    """Pin complete sanitizer and safety if-chain reachability."""
    expected = {
        (16, "if"): (_FUZZ_GUARD, ()),
        (31, "elseif"): (_THREAD_GUARD, (_address_frame(),)),
        (43, "endif"): ((), (_thread_frame(),)),
        (662, "if"): (_SAFETY_GUARD, ()),
        (709, "if"): (_FUZZ_GUARD, (_safety_frame(),)),
        (726, "endif"): ((), (_safety_frame(), _fuzz_frame())),
        (731, "endif"): ((), (_safety_frame(),)),
    }
    for identity, (tokens, context) in expected.items():
        found = [
            active for active in commands
            if active.relative == SAFETY_CMAKE and
            (active.command.line, active.command.name) == identity]
        if (len(found) != 1 or
                tuple(tokenize(found[0].command.body)) != tokens or
                not exact_context(found[0].structural_context, context)):
            errors.append(
                f"{SAFETY_CMAKE}:{identity[0]}: exact safety structural "
                "context changed")


def _helper_body(commands, tokenize):
    start = next((
        index for index, active in enumerate(commands)
        if active.relative == SAFETY_CMAKE and
        active.command.name == "function" and
        tokenize(active.command.body) == [
            "cxet_add_bounded_fuzzer", "target", "source"]
    ), None)
    if start is None:
        return ()
    end = next((
        index for index in range(start + 1, len(commands))
        if commands[index].relative == SAFETY_CMAKE and
        commands[index].command.name == "endfunction"
    ), None)
    if end is None:
        return ()
    return tuple(
        (active.command.name, tuple(tokenize(active.command.body)))
        for active in commands[start:end + 1]
    )


def _validate_helper(commands, tokenize, errors: list[str]) -> None:
    expected = (
        ("function", ("cxet_add_bounded_fuzzer", "target", "source")),
        ("add_executable", ("${target}", "${source}")),
        ("set_target_properties", (
            "${target}", "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            "${CMAKE_BINARY_DIR}")),
        ("target_include_directories", (
            "${target}", "PRIVATE", "${CXET_LIB_INCLUDE_DIR}")),
        ("target_link_libraries", ("${target}", "PRIVATE", "cxet_lib")),
        ("target_compile_options", (
            "${target}", "PRIVATE", "-fsanitize=fuzzer")),
        ("target_link_options", (
            "${target}", "PRIVATE", "-fsanitize=fuzzer")),
        ("list", (
            "APPEND", "_CXET_SAFETY_TARGETS", "${target}")),
        ("set", (
            "_CXET_SAFETY_TARGETS", "${_CXET_SAFETY_TARGETS}",
            "PARENT_SCOPE")),
        ("endfunction", ()),
    )
    if _helper_body(commands, tokenize) != expected:
        errors.append(
            f"{SAFETY_CMAKE}: bounded-fuzzer helper contract changed")
    definitions = [
        active for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.name == "function" and
        tokenize(active.command.body)[:1] == ["cxet_add_bounded_fuzzer"]
    ]
    if (len(definitions) != 1 or not exact_context(
            definitions[0].structural_context,
            (_safety_frame(), _fuzz_frame()))):
        errors.append(
            f"{SAFETY_CMAKE}: fuzzer helper escaped address-undefined guard")


def _validate_safety_branch_inventory(commands, tokenize, errors) -> None:
    """Exact-close every command/effect in the reviewed safety branch."""
    helper = (
        (710, "function", ("cxet_add_bounded_fuzzer", "target", "source")),
        (711, "add_executable", ("${target}", "${source}")),
        (712, "set_target_properties", (
            "${target}", "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            "${CMAKE_BINARY_DIR}")),
        (713, "target_include_directories", (
            "${target}", "PRIVATE", "${CXET_LIB_INCLUDE_DIR}")),
        (714, "target_link_libraries", ("${target}", "PRIVATE", "cxet_lib")),
        (715, "target_compile_options", (
            "${target}", "PRIVATE", "-fsanitize=fuzzer")),
        (716, "target_link_options", (
            "${target}", "PRIVATE", "-fsanitize=fuzzer")),
        (717, "list", ("APPEND", "_CXET_SAFETY_TARGETS", "${target}")),
        (718, "set", ("_CXET_SAFETY_TARGETS",
                       "${_CXET_SAFETY_TARGETS}", "PARENT_SCOPE")),
        (719, "endfunction", ()),
    )
    rows = [
        (662, "if", _SAFETY_GUARD),
        (663, "set", ("_CXET_SAFETY_TARGETS", *SAFETY_FIXED_TARGETS)),
        (685, "set", (
            "_CXET_SAFETY_TESTS",
            *(target.removesuffix("_tests") for target in
              SAFETY_FIXED_TARGETS))),
        (707, "set_tests_properties", (
            "${_CXET_SAFETY_TESTS}", "PROPERTIES", "LABELS", "safety")),
        (709, "if", _FUZZ_GUARD),
        *helper,
        *((721 + index, "cxet_add_bounded_fuzzer", (target, source))
          for index, (target, source) in enumerate(SAFETY_FUZZ_SOURCES.items())),
        (726, "endif", ()),
        (728, "add_custom_target", (
            "cxet_safety_suite", "DEPENDS", "${_CXET_SAFETY_TARGETS}")),
        (729, "unset", ("_CXET_SAFETY_TARGETS",)),
        (730, "unset", ("_CXET_SAFETY_TESTS",)),
        (731, "endif", ()),
    ]
    actual = [
        (active.command.line, active.command.name,
         tuple(tokenize(active.command.body)))
        for active in commands
        if active.relative == SAFETY_CMAKE and (
            (active.command.name == "if" and
             tuple(tokenize(active.command.body)) == _SAFETY_GUARD) or
            any(frame.relative == SAFETY_CMAKE and
                frame.opener == _SAFETY_GUARD
                for frame in active.structural_context))
    ]
    if actual != rows:
        errors.append(
            f"{SAFETY_CMAKE}: CXET_SAFETY_BUILD command/effect inventory "
            "changed")


def _source_path(instance, source: str) -> str | None:
    if any(marker in source for marker in ("${", "$ENV{", "$CACHE{", "$<")):
        return None
    candidate = Path(source)
    if not candidate.is_absolute():
        candidate = ROOT / instance.evaluation.source_base / candidate
    try:
        relative = candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    return relative if (ROOT / relative).is_file() else None


def _validate_directory_effects(commands, tokenize, errors) -> None:
    expected = {
        "add_compile_options": (
            ((_address_frame(),), (
                "-O2", "-g3", "-fsanitize=address,undefined",
                "-fsanitize-address-use-after-scope",
                "-fno-omit-frame-pointer", "-fno-optimize-sibling-calls",
                "-fno-sanitize-recover=all")),
            ((_thread_frame(),), (
                "-O2", "-g3", "-fsanitize=thread",
                "-fno-omit-frame-pointer", "-fno-optimize-sibling-calls")),
        ),
        "add_link_options": (
            ((_address_frame(),), (
                "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                "-fno-sanitize-recover=all")),
            ((_thread_frame(),), (
                "-fsanitize=thread", "-fno-omit-frame-pointer")),
        ),
    }
    for name, forms in expected.items():
        actual = [
            active
            for active in commands
            if active.relative == SAFETY_CMAKE and
            active.command.name == name
        ]
        matched = (
            len(actual) == len(forms) and
            all(
                tuple(tokenize(active.command.body)) == body and
                exact_context(active.structural_context, context)
                for active, (context, body) in zip(actual, forms)
            )
        )
        if not matched:
            errors.append(
                f"{SAFETY_CMAKE}: directory {name} profile contract changed")


def _validate_target_isolation(instances, errors: list[str]) -> None:
    """Keep the optional test directory from mutating composed-family owners."""
    local = {
        instance.token_groups[0][0]
        for instance in instances
        if instance.body.relative == SAFETY_CMAKE and
        instance.body.command.name in {
            "add_library", "add_executable", "add_custom_target"} and
        instance.token_groups and len(instance.token_groups[0]) == 1
    }
    custom_targets = [
        instance.token_groups[0][0]
        for instance in instances
        if instance.body.relative == SAFETY_CMAKE and
        instance.body.command.name == "add_custom_target" and
        instance.token_groups and len(instance.token_groups[0]) == 1
    ]
    if custom_targets != ["cxet_safety_suite"]:
        errors.append(
            f"{SAFETY_CMAKE}: unexpected safety custom targets "
            f"{custom_targets}")
    for instance in instances:
        if instance.body.relative != SAFETY_CMAKE or not instance.token_groups:
            continue
        name = instance.body.command.name
        owners: list[str] = []
        if name.startswith("target_") or name == "add_dependencies":
            owners = list(instance.token_groups[0])
        elif name in {"set_property", "set_target_properties"}:
            mutations, ambiguous = target_property_mutations(instance)
            if ambiguous:
                errors.append(
                    f"{SAFETY_CMAKE}:{instance.body.command.line}: ambiguous "
                    "safety target property mutation")
            owners = [mutation.target for mutation in mutations]
        elif name in {
                "set_directory_properties", "link_libraries",
                "set_source_files_properties", "add_custom_command"}:
            errors.append(
                f"{SAFETY_CMAKE}:{instance.body.command.line}: unsupported "
                f"safety-directory effect {name}()")
            continue
        escaped = sorted(set(owners) - local)
        if escaped:
            errors.append(
                f"{SAFETY_CMAKE}:{instance.body.command.line}: test-directory "
                f"mutation escapes local target ownership: {escaped}")


def _validate_test_registrations(instances, errors: list[str]) -> None:
    executables = {
        instance.token_groups[0][0]
        for instance in instances
        if instance.body.relative == SAFETY_CMAKE and
        instance.body.command.name == "add_executable" and
        instance.token_groups and len(instance.token_groups[0]) == 1
    }
    names: set[str] = set()
    properties = []
    for instance in instances:
        if instance.body.relative != SAFETY_CMAKE:
            continue
        name = instance.body.command.name
        flat = [value for group in instance.token_groups for value in group]
        if name == "install":
            errors.append(
                f"{SAFETY_CMAKE}:{instance.body.command.line}: safety "
                "scenario may not install artifacts")
        elif name == "add_test":
            if (len(flat) != 4 or flat[0] != "NAME" or
                    flat[2] != "COMMAND" or flat[3] not in executables or
                    any(marker in value for value in flat for marker in (
                        "${", "$ENV{", "$CACHE{", "$<")) or
                    flat[1] in names):
                errors.append(
                    f"{SAFETY_CMAKE}:{instance.body.command.line}: "
                    f"unapproved safety add_test form {flat}")
            elif len(flat) == 4:
                names.add(flat[1])
        elif name == "set_tests_properties":
            properties.append(instance)
    expected = [
        target.removesuffix("_tests")
        for target in SAFETY_FIXED_TARGETS
    ] + ["PROPERTIES", "LABELS", "safety"]
    if (len(properties) != 1 or
            [value for group in properties[0].token_groups for value in group]
            != expected or
            properties[0].body.command.line != 707 or
            not exact_context(
                properties[0].evaluation.structural_context,
                (_safety_frame(),))):
        errors.append(f"{SAFETY_CMAKE}: safety TEST label closure changed")


def _state_destination(name: str, raw: list[str]) -> str | None:
    if name in {"set", "unset"}:
        return raw[0] if raw else None
    if name == "list":
        return raw[1] if len(raw) > 1 else None
    if name != "string" or not raw:
        return None
    operation = raw[0].upper()
    index = {
        "APPEND": 1, "PREPEND": 1, "CONCAT": 1, "JOIN": 2,
        "TOUPPER": 2, "TOLOWER": 2, "STRIP": 2, "REPLACE": 3,
    }.get(operation)
    return raw[index] if index is not None and len(raw) > index else None


def _validate_safety_target_state(commands, tokenize, errors: list[str]):
    """Interpret the one reviewed caller-list return without inventing deps."""
    carriers = ("${", "$ENV{", "$CACHE{", "$<")
    mutations = []
    for active in commands:
        if active.relative != SAFETY_CMAKE:
            continue
        raw = tokenize(active.command.body)
        destination = _state_destination(active.command.name, raw)
        if destination is not None and any(
                marker in destination for marker in carriers):
            errors.append(
                f"{SAFETY_CMAKE}:{active.command.line}: dynamic safety-state "
                f"destination {destination}")
        if destination == "_CXET_SAFETY_TARGETS":
            mutations.append((active.command.line, active.command.name, raw))

    expected_mutations = [
        (663, "set", ["_CXET_SAFETY_TARGETS", *SAFETY_FIXED_TARGETS]),
        (717, "list", [
            "APPEND", "_CXET_SAFETY_TARGETS", "${target}"]),
        (718, "set", [
            "_CXET_SAFETY_TARGETS", "${_CXET_SAFETY_TARGETS}",
            "PARENT_SCOPE"]),
        (729, "unset", ["_CXET_SAFETY_TARGETS"]),
    ]
    if mutations != expected_mutations:
        errors.append(
            f"{SAFETY_CMAKE}: safety target-state mutation chain changed")

    call_rows = [
        (active.command.line, tuple(tokenize(active.command.body)))
        for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.name == "cxet_add_bounded_fuzzer"
    ]
    expected_rows = [
        (721 + index, (target, source))
        for index, (target, source) in enumerate(SAFETY_FUZZ_SOURCES.items())
    ]
    if call_rows != expected_rows:
        errors.append(
            f"{SAFETY_CMAKE}: ordered bounded-fuzzer fold changed")

    suites = [
        active for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.name == "add_custom_target" and
        tokenize(active.command.body)[:1] == ["cxet_safety_suite"]
    ]
    if (len(suites) != 1 or suites[0].command.line != 728 or
            tokenize(suites[0].command.body) != [
                "cxet_safety_suite", "DEPENDS",
                "${_CXET_SAFETY_TARGETS}"] or
            not exact_context(
                suites[0].structural_context, (_safety_frame(),))):
        errors.append(
            f"{SAFETY_CMAKE}: modeled safety-suite consumer changed")

    thread = tuple(SAFETY_FIXED_TARGETS)
    address = thread + tuple(row[1][0] for row in expected_rows)
    if (len(thread) != 20 or len(address) != 25 or
            len(set(address)) != len(address)):
        errors.append(f"{SAFETY_CMAKE}: safety scenario fold is ambiguous")
    return thread, address


def validate_safety_suite(
    commands,
    instances,
    tokenize,
    viable_ordinals: frozenset[int],
    errors: list[str],
) -> None:
    """Validate OFF/thread/address closures from parsed and instantiated CMake."""
    _validate_gtest_provider(
        commands, tokenize, viable_ordinals, errors)
    _validate_structural_contract(commands, tokenize, errors)
    validate_stress_fold_context(commands, errors)
    validate_optional_guard_structure(commands, errors)
    _validate_helper(commands, tokenize, errors)
    _validate_safety_branch_inventory(commands, tokenize, errors)
    _validate_directory_effects(commands, tokenize, errors)
    _validate_target_isolation(instances, errors)
    _validate_test_registrations(instances, errors)
    validate_safety_target_contract(instances, errors)
    thread_dependencies, address_dependencies = (
        _validate_safety_target_state(commands, tokenize, errors))

    base_sets = [
        active for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.line == 663 and
        active.command.name == "set" and
        tokenize(active.command.body)[:1] == ["_CXET_SAFETY_TARGETS"]
    ]
    expected_base = ["_CXET_SAFETY_TARGETS", *SAFETY_FIXED_TARGETS]
    if (len(base_sets) != 1 or
            tokenize(base_sets[0].command.body) != expected_base or
            not exact_context(
                base_sets[0].structural_context, (_safety_frame(),))):
        errors.append(f"{SAFETY_CMAKE}: fixed safety target set changed")

    calls = [
        active for active in commands
        if active.relative == SAFETY_CMAKE and
        active.command.name == "cxet_add_bounded_fuzzer"
    ]
    actual_calls = [
        tuple(tokenize(active.command.body))
        for active in calls
        if exact_context(
            active.structural_context, (_safety_frame(), _fuzz_frame()))
    ]
    expected_calls = list(SAFETY_FUZZ_SOURCES.items())
    if len(calls) != len(expected_calls) or actual_calls != expected_calls:
        errors.append(
            f"{SAFETY_CMAKE}: address-undefined fuzzer calls changed")

    required = set(SAFETY_FIXED_TARGETS) | set(SAFETY_FUZZ_SOURCES)
    declarations = {}
    for instance in instances:
        if (instance.body.command.name != "add_executable" or
                not instance.token_groups or
                len(instance.token_groups[0]) != 1):
            continue
        target = instance.token_groups[0][0]
        if target in required:
            declarations.setdefault(target, []).append(instance)
    if set(declarations) != required or any(
            len(values) != 1 for values in declarations.values()):
        errors.append(
            f"{SAFETY_CMAKE}: safety dependency declarations are incomplete "
            "or duplicated")
    guarded_declarations = [
        instance.token_groups[0][0]
        for instance in instances
        if instance.body.command.name == "add_executable" and
        instance.token_groups and len(instance.token_groups[0]) == 1 and
        exact_context(
            instance.evaluation.structural_context,
            (_safety_frame(), _fuzz_frame()))
    ]
    if (len(guarded_declarations) != len(SAFETY_FUZZ_SOURCES) or
            set(guarded_declarations) != set(SAFETY_FUZZ_SOURCES)):
        errors.append(
            f"{SAFETY_CMAKE}: address branch has unowned declarations")
    for target, values in declarations.items():
        if len(values) != 1:
            continue
        instance = values[0]
        sources = [
            value for group in instance.token_groups[1:] for value in group]
        normalized = [_source_path(instance, value) for value in sources]
        expected_source = SAFETY_FUZZ_SOURCES.get(target)
        expected_count = 2 if target == "binance_spot_fix_sbe_tests" else 1
        if (len(sources) != expected_count or
                any(value is None or not value.startswith("src/tests/")
                    for value in normalized) or
                expected_source is not None and
                normalized[0] != "src/tests/" + expected_source):
            errors.append(
                f"{SAFETY_CMAKE}: target {target} escaped its test source owner")

    suites = [
        instance for instance in instances
        if instance.body.command.name == "add_custom_target" and
        instance.token_groups and
        instance.token_groups[0] == ("cxet_safety_suite",)
    ]
    if len(suites) != 1:
        errors.append(
            f"{SAFETY_CMAKE}: expected one effective cxet_safety_suite")
        return
    suite = suites[0]
    if not exact_context(
            suite.evaluation.structural_context, (_safety_frame(),)):
        errors.append(
            f"{SAFETY_CMAKE}: cxet_safety_suite must be absent when safety is OFF")
    if thread_dependencies != SAFETY_FIXED_TARGETS:
        errors.append(f"{SAFETY_CMAKE}: thread safety closure changed")
    if address_dependencies != (
            SAFETY_FIXED_TARGETS + tuple(SAFETY_FUZZ_SOURCES)):
        errors.append(
            f"{SAFETY_CMAKE}: address-undefined safety closure changed")
