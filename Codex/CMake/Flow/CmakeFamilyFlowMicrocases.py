"""Pure negative microcases for bounded CMake flow semantics."""

from __future__ import annotations

from CMake.Syntax.CmakeFamilyBindings import validate_foreach_binding_microcases
from CMake.Flow.CmakeFamilyFlow import (
    ALL_PATHS,
    IteratingFlowController,
    Truth,
    evaluate_condition,
    evaluate_message_fatality,
)


def validate_message_terminal_microcases(errors: list[str]) -> None:
    validate_foreach_binding_microcases(errors)
    identity = lambda values, _preserve: tuple(values)
    flow_identity = lambda values, _bound, _preserve: tuple(values)
    expected = {
        "FATAL_ERROR": Truth.TRUE,
        "SEND_ERROR": Truth.TRUE,
        "fatal_error": Truth.FALSE,
        "send_error": Truth.FALSE,
        "STATUS": Truth.FALSE,
    }
    for mode, truth in expected.items():
        actual = evaluate_message_fatality((mode,), {}, identity)
        if actual is not truth:
            errors.append(
                f"message-terminal self-check {mode}: expected "
                f"{truth.name}, got {actual.name}")

    late_send_errors: list[str] = []
    late_send = IteratingFlowController(
        ALL_PATHS, late_send_errors, "late SEND_ERROR self-check")
    late_send.terminate_message(
        late_send.message_fatalities(("SEND_ERROR",), {}, flow_identity),
        "late SEND_ERROR self-check")
    if late_send.successful_paths() or late_send_errors:
        errors.append(
            "message-terminal self-check late SEND_ERROR retained a "
            "successful callable EOF path")

    if evaluate_condition(
            ('"CMAKE_EXPORT_COMPILE_COMMANDS"',),
            {"CMAKE_EXPORT_COMPILE_COMMANDS": ("ON",)}, identity,
    ) is not Truth.FALSE:
        errors.append(
            "condition self-check lost quote provenance for a variable-name "
            "literal")

    compiler_state = {
        "CMAKE_C_COMPILER_ID": ("Clang",),
        "CMAKE_CXX_COMPILER_ID": ("Clang",),
    }
    compiler_guard = (
        "NOT", "CMAKE_C_COMPILER_ID", "MATCHES", '"Clang"', "OR",
        "NOT", "CMAKE_CXX_COMPILER_ID", "MATCHES", '"Clang"',
    )
    if evaluate_condition(
            compiler_guard, compiler_state, identity) is not Truth.FALSE:
        errors.append(
            "condition self-check did not prove the exact Clang root guard "
            "nonfatal")
    if evaluate_condition(
            ("CMAKE_CXX_COMPILER_ID", "MATCHES", '"GNU|Clang"'),
            compiler_state, identity) is not Truth.UNKNOWN:
        errors.append(
            "condition self-check evaluated an unreviewed compiler regex")

    target_errors: list[str] = []
    late_target = IteratingFlowController(
        ALL_PATHS, target_errors, "late callable TARGET self-check")
    target_truths = late_target.condition_truths(
        ("TARGET", "trading_core_execution"), {}, flow_identity)
    late_target.open_if("late-target", target_truths)
    late_target.terminate_message(
        late_target.message_fatalities(
            ("FATAL_ERROR",), {}, flow_identity),
        "late callable TARGET self-check")
    late_target.close_if()
    surviving_target_paths = late_target.successful_paths()
    if (target_errors or target_truths != (Truth.UNKNOWN,) or
            not surviving_target_paths or surviving_target_paths == ALL_PATHS):
        errors.append(
            "condition self-check lost the unresolved literal TARGET "
            "nonfatal branch or retained its fatal branch")

    known_target_errors: list[str] = []
    known_target = IteratingFlowController(
        ALL_PATHS, known_target_errors, "proved callable TARGET self-check")
    known_truths = known_target.condition_truths(
        ("TARGET", "trading_core_execution"), {}, flow_identity,
        known_targets={"trading_core_execution": "apps/trading-core"})
    known_target.open_if("known-target", known_truths)
    known_target.terminate_message(
        known_target.message_fatalities(
            ("FATAL_ERROR",), {}, flow_identity),
        "proved callable TARGET self-check")
    known_target.close_if()
    if (known_target_errors or known_truths != (Truth.TRUE,) or
            known_target.successful_paths()):
        errors.append(
            "condition self-check retained successful EOF after a proved "
            "literal TARGET fatal")

    for label, tokens, state, expand in (
        ("COMMAND", ("COMMAND", "message"), {}, identity),
        ("MATCHES", ("x", "MATCHES", "^x$"), {}, identity),
        ("variable-generated TARGET", ("${_CXET_LATE_PREDICATE}",
         "cxet_lib"), {"_CXET_LATE_PREDICATE": ("TARGET",)},
         lambda values, _preserve: tuple(
             "TARGET" if value == "${_CXET_LATE_PREDICATE}" else value
             for value in values)),
    ):
        predicate_errors: list[str] = []
        predicate = IteratingFlowController(
            ALL_PATHS, predicate_errors, f"{label} self-check")
        truths = predicate.condition_truths(
            tokens, state,
            lambda raw, _bound, preserve: expand(raw, preserve))
        predicate.open_if(label, truths)
        predicate.terminate_message(
            predicate.message_fatalities(
                ("FATAL_ERROR",), {}, flow_identity),
            f"{label} self-check")
        predicate.close_if()
        if not predicate_errors or predicate.successful_paths():
            errors.append(
                f"condition self-check accepted late {label} fatal with "
                "successful EOF")
