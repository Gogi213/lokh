"""Conservative scalar/list mutation model for the bounded CMake graph."""

from __future__ import annotations

import re

from CMake.Policy.CmakeFamilyEffectPolicy import effect_variable
from CMake.Policy.CmakeFamilyStrategyPolicy import (
    proven_replay_strategy_names, canonical_strategy_names, strategy_folder, reviewed_strategy_fold_member,
)


def has_unresolved_cmake_carrier(value: str) -> bool:
    return any(marker in value for marker in ("${", "$ENV{", "$CACHE{"))


def _mutation_variable(raw: str, expand, errors: list[str], origin: str) -> str | None:
    values = expand([raw])
    if (len(values) != 1 or has_unresolved_cmake_carrier(values[0]) or
            "$<" in values[0] or not re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", values[0])):
        errors.append(f"{origin}: ambiguous CMake mutation owner {values}")
        return None
    if effect_variable(values[0]):
        errors.append(
            f"{origin}: build-effect variable mutation is forbidden: "
            f"{values[0]}"
        )
        return None
    return values[0]


def _taint_variable(
    raw: str,
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
) -> None:
    variable = _mutation_variable(raw, expand, errors, origin)
    if variable is not None:
        state[variable] = (f"${{{variable}}}",)


def _literal_list(values) -> tuple[str, ...] | None:
    """The finite, already split list subset with exact CMake element values."""
    if (not isinstance(values, tuple) or len(values) > 256 or
            any(not isinstance(value, str) or not value or len(value) > 4096 or
                any(marker in value for marker in (
                    "${", "$ENV{", "$CACHE{", "$<", "\\", ";", "[", "]", "\x00"))
                for value in values)):
        return None
    return values


def apply_list_command(
    raw_words: list[str],
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
    *,
    direct_literal_find: tuple[str, ...] | None = None,
) -> None:
    """Apply value-preserving list operations and taint opaque rewrites."""
    if not raw_words:
        errors.append(f"{origin}: empty list() command")
        return
    operation = raw_words[0].upper()
    if operation == "TRANSFORM":
        for index, raw in enumerate(raw_words[2:], 2):
            controls = expand([raw])
            if not any(value.upper() == "OUTPUT_VARIABLE" for value in controls):
                continue
            errors.append(
                f"{origin}: list(TRANSFORM OUTPUT_VARIABLE) is unsupported")
            if (len(controls) != 1 or
                    controls[0].upper() != "OUTPUT_VARIABLE"):
                errors.append(
                    f"{origin}: dynamic list secondary-writer grammar")
            if index + 1 >= len(raw_words):
                errors.append(
                    f"{origin}: list(TRANSFORM) misses secondary output")
            else:
                _taint_variable(
                    raw_words[index + 1], state, expand, errors, origin)
            if len(raw_words) >= 2:
                _taint_variable(raw_words[1], state, expand, errors, origin)
            return
    if operation in {
            "APPEND", "PREPEND", "INSERT", "SORT", "REVERSE",
            "REMOVE_DUPLICATES", "REMOVE_ITEM", "REMOVE_AT", "FILTER",
            "TRANSFORM", "POP_BACK", "POP_FRONT"}:
        if len(raw_words) < 2:
            errors.append(f"{origin}: list({operation}) misses its owner")
            return
        variable = _mutation_variable(raw_words[1], expand, errors, origin)
        if variable is None:
            return
        if operation == "APPEND":
            if (origin == "apps/hft-backtest/CMakeLists.txt:71" and
                    raw_words == [
                        "APPEND", "HFT_BACKTEST_REQUIRED_STRATEGY_ARGS",
                        "--required-strategy", "${required_strategy}"]):
                names = tuple(expand([raw_words[3]]))
                if names != proven_replay_strategy_names():
                    errors.append(
                        f"{origin}: required-strategy loop order, multiplicity, "
                        "or binding changed")
                    state[variable] = (f"${{{variable}}}",)
                else:
                    pairs = tuple(
                        item for name in names
                        for item in ("--required-strategy", name))
                    state[variable] = state.get(variable, ()) + pairs
            else:
                state[variable] = state.get(variable, ()) + tuple(
                    expand(raw_words[2:]))
        elif operation == "PREPEND":
            state[variable] = tuple(expand(raw_words[2:])) + state.get(
                variable, ())
        elif operation == "INSERT":
            if len(raw_words) < 4:
                errors.append(
                    f"{origin}: list(INSERT) misses index or inserted values")
            # Ownership is order-insensitive, so retaining all old and new
            # values is conservative even for a dynamic insertion index.
            state[variable] = state.get(variable, ()) + tuple(
                expand(raw_words[3:]))
        elif operation in {"SORT", "REVERSE", "REMOVE_DUPLICATES"}:
            state.setdefault(variable, ())
        elif operation in {"POP_BACK", "POP_FRONT"}:
            state[variable] = (f"${{{variable}}}",)
            for output in raw_words[2:]:
                _taint_variable(output, state, expand, errors, origin)
        else:
            state[variable] = (f"${{{variable}}}",)
        return

    if operation == "FIND" and len(raw_words) == 4:
        variable = _mutation_variable(raw_words[1], expand, errors, origin)
        output = _mutation_variable(raw_words[3], expand, errors, origin)
        if variable is None or output is None:
            return
        values = _literal_list(direct_literal_find)
        searched = tuple(expand(raw_words[2:3]))
        # CMake's first matching list index is deterministic for this bounded
        # literal subset. Escaped/serialized lists and symbolic alternatives
        # stay tainted, rather than borrowing a guessed index or membership.
        if (values is not None and state.get(variable) == values and
                len(searched) == 1 and _literal_list(searched) is not None):
            state[output] = (str(values.index(searched[0]) if searched[0] in values else -1),)
        else:
            _taint_variable(raw_words[3], state, expand, errors, origin)
        return

    output_index = {
        "LENGTH": 2,
        "GET": -1,
        "JOIN": 3,
        "SUBLIST": 4,
        "FIND": 3,
    }.get(operation)
    if output_index is not None:
        if len(raw_words) <= (output_index if output_index >= 0 else 1):
            errors.append(f"{origin}: malformed list({operation}) command")
            return
        _taint_variable(
            raw_words[output_index], state, expand, errors, origin)
        return
    errors.append(f"{origin}: unsupported active list({operation}) command")


def _scalar_expansion(raw: list[str], expand) -> str | None:
    values: list[str] = []
    for token in raw:
        expanded = expand([token])
        if len(expanded) != 1:
            return None
        values.extend(expanded)
    return "".join(values)


def apply_string_command(
    raw_words: list[str],
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
    *,
    strategy_context=None,
) -> None:
    """Model current scalar writes and taint opaque derived values."""
    if not raw_words:
        errors.append(f"{origin}: empty string() command")
        return
    operation = raw_words[0].upper()
    if operation in {"APPEND", "PREPEND"}:
        if len(raw_words) < 2:
            errors.append(f"{origin}: string({operation}) misses its owner")
            return
        variable = _mutation_variable(raw_words[1], expand, errors, origin)
        if variable is None:
            return
        addition = _scalar_expansion(raw_words[2:], expand)
        previous = state.get(variable, ("",)) or ("",)
        if addition is None:
            state[variable] = (f"${{{variable}}}",)
            return
        state[variable] = tuple(
            (old + addition if operation == "APPEND" else addition + old)
            for old in previous
        )
        return
    if operation == "CONCAT":
        if len(raw_words) < 2:
            errors.append(f"{origin}: string(CONCAT) misses its owner")
            return
        variable = _mutation_variable(raw_words[1], expand, errors, origin)
        if variable is not None:
            value = _scalar_expansion(raw_words[2:], expand)
            state[variable] = (
                value,) if value is not None else (f"${{{variable}}}",)
        return
    if operation == "JOIN":
        if len(raw_words) < 3:
            errors.append(f"{origin}: malformed string(JOIN) command")
            return
        variable = _mutation_variable(raw_words[2], expand, errors, origin)
        separators = expand([raw_words[1]])
        if variable is not None:
            if len(separators) != 1:
                state[variable] = (f"${{{variable}}}",)
            else:
                state[variable] = (
                    separators[0].join(expand(raw_words[3:])),)
        return
    if operation in {"TOUPPER", "TOLOWER"}:
        if len(raw_words) != 3:
            errors.append(f"{origin}: malformed string({operation}) command")
            return
        variable = _mutation_variable(raw_words[2], expand, errors, origin)
        if variable is not None:
            if (operation == "TOLOWER" and strategy_context is not None and
                    reviewed_strategy_fold_member(strategy_context) and
                    raw_words == ["TOLOWER", "${strategy_name}", "strategy_name"]):
                # This exact foreach recipe executes once per header. Its
                # aggregate tuple contains separate scalar iterations, never
                # arguments to concatenate into one strategy/generated name.
                values = tuple(expand([raw_words[1]]))
                spellings = {re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", strategy_folder(name))
                             for name in canonical_strategy_names()}
                if not values or any(value not in spellings for value in values):
                    errors.append(f"{origin}: unreviewed strategy scalar case-fold inputs")
                    state[variable] = (f"${{{variable}}}",)
                else:
                    state[variable] = tuple(value.lower() for value in values)
                return
            value = _scalar_expansion([raw_words[1]], expand)
            state[variable] = (
                (value.upper() if operation == "TOUPPER" else value.lower()),
            ) if value is not None else (f"${{{variable}}}",)
        return
    if operation == "STRIP":
        if len(raw_words) != 3:
            errors.append(f"{origin}: malformed string(STRIP) command")
            return
        if (origin != "src/tests/CMakeLists.txt:66" or
                raw_words != ["STRIP", "${_s}", "_s"]):
            errors.append(
                f"{origin}: unreviewed string(STRIP) scalar producer")
            _taint_variable(raw_words[2], state, expand, errors, origin)
            return
        variable = _mutation_variable(raw_words[2], expand, errors, origin)
        if variable is None:
            return
        values = tuple(expand([raw_words[1]]))
        if not values or any(
                has_unresolved_cmake_carrier(value) or "$<" in value
                for value in values):
            state[variable] = (f"${{{variable}}}",)
            return
        # Each foreach binding is a scalar CMake string.  Preserve order,
        # duplicates and explicit empty elements while applying the exact
        # scalar transform to every modeled iteration.
        state[variable] = tuple(value.strip() for value in values)
        return
    if operation == "REGEX":
        expected = ["REGEX", "REPLACE", "([a-z0-9])([A-Z])", r"\\1_\\2",
                    "strategy_name", "${strategy_folder}"]
        values = expand([raw_words[-1]]) if raw_words else []
        folders = {strategy_folder(name) for name in canonical_strategy_names()}
        if (strategy_context is None or not reviewed_strategy_fold_member(strategy_context) or
                raw_words != expected or not values or any(value not in folders for value in values)):
            errors.append(f"{origin}: unreviewed string(REGEX) strategy producer")
        else:
            state["strategy_name"] = tuple(
                re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value) for value in values)
        return
    if operation == "REPLACE":
        if len(raw_words) < 5:
            errors.append(f"{origin}: malformed string(REPLACE) command")
            return
        variable = _mutation_variable(raw_words[3], expand, errors, origin)
        match = expand([raw_words[1]])
        replacement = expand([raw_words[2]])
        if variable is not None:
            if len(match) != 1 or len(replacement) != 1:
                state[variable] = (f"${{{variable}}}",)
            else:
                value = _scalar_expansion(raw_words[4:], expand)
                state[variable] = (
                    value.replace(match[0], replacement[0]),
                ) if value is not None else (f"${{{variable}}}",)
        return
    if operation in {
            "MD5", "SHA1", "SHA224", "SHA256", "SHA384", "SHA512",
            "SHA3_224", "SHA3_256", "SHA3_384", "SHA3_512"}:
        if len(raw_words) < 2:
            errors.append(f"{origin}: malformed string({operation}) command")
            return
        _taint_variable(raw_words[1], state, expand, errors, origin)
        return
    errors.append(f"{origin}: unsupported active string({operation}) command")
