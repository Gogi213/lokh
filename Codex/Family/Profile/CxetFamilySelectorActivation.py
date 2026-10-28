"""Exact configure-only projections of the venue and compiler-ISA selectors.

No compiler or CMake module is executed. The all-exchange profile proves source
selection is identity; ISA support remains unknown until an authorized configure.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from CMake.Flow.CmakeFamilyExecutionIdentity import unsymlinked_regular_path
from CMake.Flow.CmakeFamilyGraph import Command, cmake_list_words, parse_commands
from CMake.Flow.CmakeFamilyState import UNCERTAIN_BRANCH_ALTERNATIVE

_SELECTION = "cmake/CxetExchangeSelection.cmake"
_HOT = "cmake/CxetHotOptions.cmake"
_DIGESTS = {
    _SELECTION: "330aecdf3dbdedf536093f1b1906edd1332cce54a9b5436ab886f6c2ca1b92bf",
    _HOT: "37ded9a90a5c657c7642bfe13633d71bd77367e97d1a821264b005c0308932ca",
}


def _body(values) -> str:
    return " ".join(json.dumps(value) for value in values)


def _literal(commands, variable: str) -> tuple[str, ...]:
    matches = [tuple(cmake_list_words(command.body)[1:]) for command in commands
               if command.name == "set" and cmake_list_words(command.body)[:1] == [variable]]
    if len(matches) != 1 or not 0 < len(matches[0]) <= 64:
        raise ValueError(f"selector lost its bounded literal inventory {variable}")
    return matches[0]


def _verified(root: Path, relative: str, source: str, commands, errors):
    path = root / relative
    if not unsymlinked_regular_path(path, root):
        raise ValueError(f"selector source is missing/nonregular/symlinked: {relative}")
    data = path.read_bytes()
    if (hashlib.sha256(data).hexdigest() != _DIGESTS[relative] or
            source.encode("utf-8") != data or
            list(commands) != parse_commands(relative, source, errors)):
        raise ValueError(f"reviewed selector source/parsed identity changed: {relative}")


def _selection_projection(commands, exchanges, flags):
    definitions = ("CXET_CONFIGURED_EXCHANGE_SELECTION=1",
                   *(f"CXET_EXCHANGE_{exchange.upper()}=1" for exchange in exchanges),
                   *(f"CXET_HAS_{flag}=1" for flag in flags), "CXET_SELECTION_ALL=1")
    result = [next(command for command in commands if command.name == "include_guard")]
    for variable, values, line in (
        ("_cxet_exchange_names", exchanges, 7),
        ("_cxet_selected", exchanges, 27),
        ("CXET_ENABLED_EXCHANGES", exchanges, 42),
        ("CXET_SELECTION_ALL", ("1",), 45),
        ("CXET_EXCHANGE_PROFILE", ("all",), 48),
        *((f"CXET_EXCHANGE_{exchange.upper()}", ("1",), 58) for exchange in exchanges),
        *((f"CXET_HAS_{flag}", ("1",), 96) for flag in flags),
        ("CXET_EXCHANGE_DEFINITIONS", definitions, 52),
        ("CXET_EXCHANGES", exchanges, 147),
        ("CXET_EXCHANGE_RECORD", (json.dumps({"exchanges": exchanges,
                                            "profile": "all", "all": True}, separators=(",", ":")),), 106),
    ):
        result.append(Command("set", _body((variable, *values)), line))
    result.extend((Command("function", "cxet_select_sources result", 108),
                   Command("set", '${result} "${ARGN}" PARENT_SCOPE', 138),
                   Command("endfunction", "", 139)))
    result.extend(command for command in commands
                  if command.name in {"add_compile_definitions", "file"})
    return result


def _hot_projection(commands, probes, switches):
    # Loop expansion retains the original target, visibility and definitions.
    # Probe includes/push/check/pop and saved compiler variables are omitted:
    # their only exported result is the explicitly unknown support state.
    result = [command for command in commands
              if command.name == "include_guard" or
              command.name == "set" and cmake_list_words(command.body)[:1] in (
                  ["_CXET_PARSER_HOT_FEATURES"], ["_CXET_OPTIONAL_HOT_SWITCHES"])]
    result.extend(command for command in commands if 77 <= command.line <= 79)
    result.append(Command("if", "CXET_ENABLE_HFT_MAGIC", 83))
    for feature, isa in probes:
        result.extend((
            Command("if", f"{feature} AND NOT _CXET_HOT_SUPPORTED_{feature}", 88),
            Command("message", _body(("FATAL_ERROR", f"{feature} requires {isa} in the selected CPU profile; select a compatible native profile or disable this feature")), 91),
            Command("endif", "", 93)))
    result.append(Command("endif", "", 95))
    result.extend((Command("function", "cxet_apply_hot_options target", 97),
                   Command("if", "CXET_ENABLE_HFT_MAGIC", 98)))
    for feature in switches:
        result.extend((Command("if", feature, 100),
                       Command("target_compile_definitions", f'${{target}} PUBLIC "{feature}=1"', 101),
                       Command("endif", "", 102)))
    result.append(Command("endif", "", 104))
    result.append(Command("if", 'CXET_ENABLE_NAPI_BUSY_POLL AND "${target}" STREQUAL "cxet_lib"', 105))
    result.extend(command for command in commands if 106 <= command.line <= 108)
    return result


def lower_selector_modules(root: Path, files, scope_values, errors):
    """Lower only exact inputs and proven all-exchange configure profiles."""
    projected = dict(files)
    values = {scope: dict(state) for scope, state in scope_values.items()}
    try:
        for relative in _DIGESTS:
            if relative not in files:
                raise ValueError(f"missing reviewed selector module: {relative}")
            source, commands = files[relative]
            _verified(root, relative, source, commands, errors)
        selection = files[_SELECTION][1]
        hot = files[_HOT][1]
        exchanges = _literal(selection, "_cxet_exchange_names")
        flags = _literal(selection, "_cxet_protocol_flags")
        parser_features = _literal(hot, "_CXET_PARSER_HOT_FEATURES")
        switches = _literal(hot, "_CXET_OPTIONAL_HOT_SWITCHES")
        probes = tuple(tuple(pair.split("|")) for pair in _literal(hot, "_CXET_HOT_PROBES"))
        if any(len(pair) != 2 for pair in probes):
            raise ValueError("hot selector lost exact feature/ISA pairs")
        required = {"CXET_SELECTION_ALL": ("1",), "CXET_EXCHANGE_PROFILE": ("all",),
                    **{f"CXET_EXCHANGE_{exchange.upper()}": ("1",) for exchange in exchanges},
                    **{f"CXET_HAS_{flag}": ("1",) for flag in flags}}
        if not values:
            raise ValueError("selector projection requires exact configure inputs")
        for scope, state in values.items():
            if (any(state.get(key) != value for key, value in required.items()) or
                    state.get("CXET_EXCHANGES") != ("all",) or
                    state.get("CXET_EXCHANGE_PRESET") != ("",) or
                    state.get("CMAKE_SCRIPT_MODE_FILE", ("OFF",)) != ("OFF",)):
                raise ValueError(f"selector projection has no proven all-exchange configure: {scope}")
            profile = state.get("CXET_HOT_FEATURE_PROFILE")
            if profile not in {("default",), ("none",)}:
                raise ValueError(f"hot selector profile has no reviewed projection: {scope}")
            for feature in (*switches, "CXET_ENABLE_NAPI_BUSY_POLL"):
                if feature in state and state[feature] not in {("ON",), ("OFF",)}:
                    raise ValueError(f"hot selector override is not an exact driver boolean: {feature}")
                state.setdefault(feature, (UNCERTAIN_BRANCH_ALTERNATIVE,)
                                 if feature in parser_features and profile == ("default",) else ("OFF",))
            for feature, _ in probes:
                state[f"_CXET_HOT_SUPPORTED_{feature}"] = (UNCERTAIN_BRANCH_ALTERNATIVE,)
            state.setdefault("CMAKE_SCRIPT_MODE_FILE", ("OFF",))
        projected[_SELECTION] = (files[_SELECTION][0], _selection_projection(selection, exchanges, flags))
        projected[_HOT] = (files[_HOT][0], _hot_projection(hot, probes, switches))
    except (OSError, UnicodeError, ValueError, KeyError) as exc:
        errors.append(f"selector activation: {exc}")
    return projected, values
