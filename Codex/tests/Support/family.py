"""Focused static regressions for current owner/offline activation."""
import sys
from pathlib import Path as _CodexPath
_CODEX_TOOLS = _CodexPath(__file__).resolve().parents[2]
if str(_CODEX_TOOLS) not in sys.path:
    sys.path.insert(0, str(_CODEX_TOOLS))


from pathlib import Path

import ast

import tempfile

import unittest

from unittest.mock import patch

from types import SimpleNamespace

from Family.Profile.CxetFamilyActivation import (
    owner_activation, lower_offline_registrations, validate_offline_helper,
    source_profile_roots, source_cases, offline_registration_inventory,
)

from CMake.Flow.CmakeFamilyGraph import (
    cmake_list_words, compose_active_commands, parse_commands, function_model, variable_snapshots,
    instantiated_commands,
)

from Family.Verification import CxetFamilyReadOnlySurface as surface

from Family.Sources.CxetFamilyHeaderContract import (
    HEADER_OWNER_ROOTS, compiler_visible_header_inventory, exported_header_targets,
)

from Family.Targets.CxetFamilyTargetInventory import PRODUCTION_TARGETS, CUSTOM_TARGETS

from Family.Sources.CxetFamilyIncludeReachability import _include_value

from Family.Sources.CxetFamilyIncludeInputs import IncludeInputs, native_include_context

from Family.Sources.CxetFamilyCppPolicy import approved_external_angle_include

from CMake.Policy.CmakeFamilyStrategyPolicy import validate_registration_predicate, registry_outputs

from Family.Sources.CxetFamilySourcePolicy import typed_generated_source

from Family.Targets.CxetFamilyTargetPolicy import verification_include_allowed

ROOT = Path(__file__).resolve().parents[4]

def _ownership_checker_for_harness():
    """Import CLI functions for mocked unit tests without weakening its gate."""
    import sys
    flags = sys.flags

    class HarnessFlags:
        def __getattr__(self, name):
            return True if name in {"isolated", "no_site"} else getattr(flags, name)

    # No checker main runs in this context. The tests below replace physical
    # inventory/activation and exercise only prerequisite error propagation.
    with patch.object(sys, "flags", HarnessFlags()):
        import CheckCxetFamilyOwnership as checker
    return checker

def _insert_before_configure_argv(text: str, statement: str) -> str:
    function = next(node for node in ast.parse(text).body
                    if isinstance(node, ast.FunctionDef) and node.name == "configure")
    assignment = next(node for node in function.body if isinstance(node, ast.Assign) and
                      any(isinstance(target, ast.Name) and target.id == "argv" for target in node.targets))
    lines = text.splitlines(keepends=True)
    lines.insert(assignment.lineno - 1, "    " + statement + "\n")
    return "".join(lines)

class StrategyFixture:
    def _strategy_active(self, text):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        relative = "apps/trading-core/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative, text, errors)
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        self.assertEqual(errors, [])
        return [ActiveCommand(relative, relative, Path("apps/trading-core"),
                Path("apps/trading-core"), (relative,), command, index, context)
                for index, (command, context) in enumerate(zip(commands, contexts))]


class CurrentRecipeFixture(StrategyFixture):
    _strategy_active = StrategyFixture._strategy_active

    def _current_metadata_instance(self, relative, line, state):
        from types import SimpleNamespace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import InstantiatedCommand
        from CMake.Flow.CmakeFamilyState import expand_active_tokens
        from CMake.Syntax.CmakeFamilyContext import StructuralTracker
        from CMake.Syntax.CmakeFamilyLexer import words
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        tracker = StructuralTracker(relative, (), errors)
        selected = None
        for ordinal, command in enumerate(commands):
            active = ActiveCommand(relative, relative, Path(relative).parent, Path(relative).parent,
                (relative,), command, ordinal, tracker.context())
            if command.line == line:
                selected = active
            tracker.advance(command.name, tuple(cmake_list_words(command.body)), command.line, ordinal)
        tracker.finish()
        self.assertEqual(errors, [])
        self.assertIsNotNone(selected)
        snapshots = SimpleNamespace(values={selected.ordinal: state})
        groups = tuple(tuple(expand_active_tokens(selected, [token], snapshots, ROOT))
                       for token in words(selected.command.body))
        return InstantiatedCommand(selected, selected, groups, selected.ordinal)

    def _registry_instances(self):
        from CMake.Policy.CmakeFamilyStrategyPolicy import validate_registration_predicate
        active = self._strategy_active((ROOT / "apps/trading-core/CMakeLists.txt").read_text())
        errors = []
        fold = validate_registration_predicate([item.command for item in active], cmake_list_words, errors)
        fold_ids = {id(command) for command in fold}
        selected = [item for item in active if id(item.command) in fold_ids or
            item.command.name == "set" and cmake_list_words(item.command.body)[:1] and
            cmake_list_words(item.command.body)[0].startswith("TRADING_CORE_") or
            item.command.name == "file" and cmake_list_words(item.command.body)[:1] in (["GLOB"], ["GLOB_RECURSE"]) or
            item.command.name == "string" and cmake_list_words(item.command.body)[:3] ==
                ["JOIN", "|", "TRADING_CORE_STRATEGY_HEADERS_ARG"] or
            item.command.name in {"set_property", "add_custom_target", "add_custom_command"}]
        model = function_model(selected, errors)
        snapshots = variable_snapshots(selected, model, errors)
        instances = instantiated_commands(selected, model, snapshots,
            {"set_property", "add_custom_command", "add_custom_target"}, errors)
        self.assertEqual(errors, [])
        return instances


class ActivationFixture:
    @staticmethod
    def _declaration(name, tail, scope, ordinal, paths=((),)):
        return SimpleNamespace(
            body=SimpleNamespace(command=SimpleNamespace(name="add_library")),
            token_groups=((name,), *[(value,) for value in tail]),
            evaluation=SimpleNamespace(scope=scope, directory=(scope,), ordinal=ordinal),
            path_alternatives=paths)


