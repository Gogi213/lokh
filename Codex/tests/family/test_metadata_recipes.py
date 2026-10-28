"""Metadata recipes regressions."""
from tools.Codex.tests.Support.family import (
    ActivationFixture,
    CUSTOM_TARGETS,
    CurrentRecipeFixture,
    HEADER_OWNER_ROOTS,
    IncludeInputs,
    PRODUCTION_TARGETS,
    Path,
    ROOT,
    SimpleNamespace,
    StrategyFixture,
    _include_value,
    _insert_before_configure_argv,
    _ownership_checker_for_harness,
    approved_external_angle_include,
    ast,
    cmake_list_words,
    compiler_visible_header_inventory,
    compose_active_commands,
    exported_header_targets,
    function_model,
    instantiated_commands,
    lower_offline_registrations,
    native_include_context,
    offline_registration_inventory,
    owner_activation,
    parse_commands,
    patch,
    registry_outputs,
    source_cases,
    source_profile_roots,
    surface,
    tempfile,
    typed_generated_source,
    unittest,
    validate_offline_helper,
    validate_registration_predicate,
    variable_snapshots,
    verification_include_allowed,
)

class MetadataRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_wasm_output_parent_scope_preserves_exact_child_value_and_context(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT
        parent, child = "apps/vetron/CMakeLists.txt", "apps/vetron/wasm/CMakeLists.txt"
        variable = "VETRON_MATH_WASM_OUTPUT"
        publish = ActiveCommand(parent, child, Path("apps/vetron/wasm"), Path("apps/vetron/wasm"),
            (parent, child), Command("set", f'{variable} "${{{variable}}}" PARENT_SCOPE', 29), 2)
        outputs = ((ROOT / "apps/vetron/frontend/.generated/trading-core-math.wasm").as_posix(),
            f"{SYNTHETIC_BINARY_ROOT}/apps/vetron/frontend-generated/trading-core-math.wasm",
            f"{SYNTHETIC_BINARY_ROOT}/apps/vetron/wasm/trading-core-math.wasm")

        def snapshots_for(output, publication):
            active = [
                ActiveCommand(parent, parent, Path("apps/vetron"), Path("apps/vetron"), (parent,),
                    Command("set", f"{variable} parent-value", 1), 0),
                replace(publish, command=Command("set", f'{variable} "{output}"', 28), ordinal=1),
                publication,
                ActiveCommand(parent, parent, Path("apps/vetron"), Path("apps/vetron"), (parent,),
                    Command("set", f'observed "${{{variable}}}"', 241), 3),
            ]
            errors = []
            snapshots = variable_snapshots(active, function_model(active, errors), errors)
            return snapshots.values[3][variable], errors

        for output in outputs:
            value, errors = snapshots_for(output, publish)
            self.assertEqual(errors, [])
            self.assertEqual(value, (output,))
        for output, mutation in (
                ("${unknown_output}", publish),
                ("/foreign/trading-core-math.wasm", publish),
                (outputs[0], replace(publish, command=replace(publish.command, body=f"{variable} foreign PARENT_SCOPE"))),
                (outputs[0], replace(publish, command=replace(publish.command, line=30))),
                (outputs[0], replace(publish, source_base=Path("apps/trader"))),
                (outputs[0], replace(publish, binary_base=Path("foreign"))),
                (outputs[0], replace(publish, directory=(parent, "foreign/CMakeLists.txt", child)))):
            value, errors = snapshots_for(output, mutation)
            self.assertTrue(any("PARENT_SCOPE" in error for error in errors), errors)
            self.assertEqual(value, ("parent-value",))

    def test_completed_nested_provider_keeps_reviewed_probe_prerequisites_independent(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyInstances import GRAPH_INSTANCE_NAMES, directory_target_types
        from CMake.Syntax.CmakeFamilyContext import StructuralTracker
        from CMake.Flow.CmakeFamilyFlow import Truth, evaluate_condition
        from CMake.Flow.CmakeFamilyState import UNCERTAIN_BRANCH_ALTERNATIVE
        from Family.Profile.CxetFamilySelectorActivation import _literal, _hot_projection
        core, parser, child, consumer = ("src/src/CMakeLists.txt", "apps/hft-parser/CMakeLists.txt",
            "apps/hft-parser/src/Contracts/CMakeLists.txt", "consumer/CMakeLists.txt")
        hot = "cmake/CxetHotOptions.cmake"
        source = parse_commands(hot, (ROOT / hot).read_text(), [])
        probes = tuple(tuple(pair.split("|")) for pair in _literal(source, "_CXET_HOT_PROBES"))
        projection = _hot_projection(source, probes, _literal(source, "_CXET_OPTIONAL_HOT_SWITCHES"))
        root_guard = ("NOT", "DEFINED", "CXET_ROOT_SOURCE_GRAPH", "OR", "NOT", "CXET_ROOT_SOURCE_GRAPH")
        for state, expected in (({"CXET_ROOT_SOURCE_GRAPH": ("ON",)}, Truth.FALSE),
                ({"CXET_ROOT_SOURCE_GRAPH": ("OFF",)}, Truth.TRUE), ({}, Truth.UNKNOWN),
                ({"CXET_ROOT_SOURCE_GRAPH": ("ON", UNCERTAIN_BRANCH_ALTERNATIVE)}, Truth.UNKNOWN)):
            self.assertIs(evaluate_condition(root_guard, state, lambda raw, preserve: raw), expected)
        declarations = ('add_library(core INTERFACE)\nadd_library(cxet::cxet_lib ALIAS core)\n'
            'add_library(read INTERFACE)\nadd_library(cxet::read_only_contracts ALIAS read)\n'
            'add_library(liburing::uring STATIC IMPORTED GLOBAL)\n'
            'add_library(absl::flat_hash_set INTERFACE IMPORTED GLOBAL)')
        prerequisites = ('if(NOT DEFINED CXET_ROOT_SOURCE_GRAPH OR NOT CXET_ROOT_SOURCE_GRAPH)\n'
            'message(FATAL_ERROR "root graph")\nendif()\n'
            'foreach(required IN ITEMS cxet::cxet_lib cxet::read_only_contracts liburing::uring absl::flat_hash_set)\n'
            'if(NOT TARGET ${required})\nmessage(FATAL_ERROR "missing provider")\nendif()\nendforeach()')
        fold = ('set(providers base)\nif(TARGET hftp_contract_headers)\nadd_library(client INTERFACE)\nendif()\n'
            'if(TARGET client)\nlist(APPEND providers client)\nendif()\n'
            'foreach(target IN LISTS providers)\ntarget_compile_features(${target} INTERFACE cxx_std_23)\nendforeach()')
        for mode in ("valid", "unknown-fatal", "loop-return", "changed-probe", "nonglobal"):
            errors, active = [], []

            def append(scope, relative, commands, directory, chain):
                tracker = StructuralTracker(relative, (), errors)
                for command in commands:
                    member = ActiveCommand(scope, relative, Path(directory[-1]).parent,
                        Path(directory[-1]).parent, directory, command, len(active), tracker.context(), chain)
                    active.append(member)
                    tracker.advance(command.name, tuple(cmake_list_words(command.body)), command.line, member.ordinal)
                tracker.finish()

            projected = list(projection)
            if mode == "changed-probe":
                index = next(index for index, command in enumerate(projected) if command.name == "if" and command.line == 88)
                projected[index] = replace(projected[index], body="TARGET ghost")
            append(core, hot, projected, (core,), (((core,), core), ((core,), hot)))
            loop_body = 'if(unknown)\nreturn()\nendif()' if mode == "loop-return" else 'set(seen ${value})'
            prefix = f'foreach(value IN ITEMS first second)\n{loop_body}\nendforeach()\n'
            if mode == "unknown-fatal":
                prefix += 'if(unknown)\nmessage(FATAL_ERROR "unreviewed")\nendif()\n'
            emitted = declarations.replace("STATIC IMPORTED GLOBAL", "STATIC IMPORTED") if mode == "nonglobal" else declarations
            append(core, core, parse_commands(core, prefix + emitted, errors), (core,), (((core,), core),))
            append(parser, parser, parse_commands(parser, prerequisites, errors), (parser,), (((parser,), parser),))
            append(parser, child, parse_commands(child,
                'if(NOT TARGET hftp_contract_headers)\nadd_library(hftp_contract_headers INTERFACE)\nendif()', errors),
                (parser, child), (((parser,), parser), ((parser, child), child)))
            append(consumer, consumer, parse_commands(consumer, fold, errors), (consumer,), (((consumer,), consumer),))
            initial = {"CXET_ENABLE_HFT_MAGIC": ("ON",), "CXET_ROOT_SOURCE_GRAPH": ("ON",)}
            initial.update({feature: ("OFF",) for feature in _literal(source, "_CXET_OPTIONAL_HOT_SWITCHES")})
            initial.update({feature: ("ON",) for feature, _ in probes})
            model = function_model(active, errors)
            bootstrap = variable_snapshots(active, model, [], initial)
            instances = instantiated_commands(active, model, bootstrap, GRAPH_INSTANCE_NAMES, [])
            types = directory_target_types(instances, shared_namespace=True, snapshots=bootstrap,
                active_commands=active, live_eof_paths=bootstrap.live_eof_paths)
            snapshots = variable_snapshots(active, model, errors, initial, types)
            if mode == "valid":
                self.assertEqual(errors, [])
                loop = next(item for item in active if item.relative == consumer and item.command.name == "foreach")
                self.assertEqual(snapshots.values[loop.ordinal]["providers"], ("base", "client"))
                declaration = next(item for item in active if item.relative == core and
                    cmake_list_words(item.command.body)[:1] == ["read"])
                self.assertNotEqual(snapshots.path_alternatives[declaration.ordinal], ((),))
                self.assertIn(declaration.ordinal, snapshots.source_independent_ordinals)
            else:
                self.assertTrue(any("non-exact foreach" in error for error in errors), (mode, errors))

    def test_root_abseil_prerequisite_requires_actual_selected_vendor_recipe(self):
        import tempfile
        from unittest.mock import patch
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyState import reviewed_root_absl_target
        core = "src/src/CMakeLists.txt"
        member = ActiveCommand(core, core, Path("src/src"), Path("src/src"), (core,),
            Command("set", "unused ON", 1), 0)
        errors = []
        _roots, values = owner_activation(ROOT, errors)["compile:hft-parser:full:0:0:0"]
        self.assertEqual(errors, [])
        self.assertEqual(reviewed_root_absl_target([member], values, ROOT), {"absl::flat_hash_set": "LIBRARY"})
        self.assertEqual(reviewed_root_absl_target([member], {}, ROOT), {})
        source = (ROOT / "CMakeLists.txt").read_text()
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            (fixture / "CMakeLists.txt").write_text(source)
            self.assertEqual(reviewed_root_absl_target([member], values, fixture), {})
        original_read_text = Path.read_text
        for changed in (source.replace("  add_subdirectory(extra/abseil-cpp)", "  add_subdirectory(extra/other)"),
                source.replace("cxet_add_abseil_subdirectory()", ""),
                source.replace("  add_subdirectory(extra/abseil-cpp)", "  return()\n  add_subdirectory(extra/abseil-cpp)")):
            def read_text(path, *args, **kwargs):
                return changed if path == ROOT / "CMakeLists.txt" else original_read_text(path, *args, **kwargs)
            with patch.object(Path, "read_text", new=read_text):
                self.assertEqual(reviewed_root_absl_target([member], values, ROOT), {})
        with patch("CMake.Flow.CmakeFamilyExecutionIdentity.reviewed_external_authority", return_value=False):
            self.assertEqual(reviewed_root_absl_target([member], values, ROOT), {})

    def test_compressor_keeps_exact_owners_and_retired_backtest_recipe_is_rejected(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyFlow import InstantiatedCommand
        from CMake.Flow.CmakeFamilyState import expand_active_tokens
        from CMake.Policy.CmakeFamilyPropertyPolicy import validate_property_command
        from CMake.Policy.CmakeFamilyCommandPolicy import _validate_custom_target
        from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT
        compressor = "apps/hft-compressor/CMakeLists.txt"
        property_instance = self._current_metadata_instance(compressor, 140, {})
        errors = []
        validate_property_command(property_instance, errors)
        self.assertEqual(errors, [])
        for line in (176, 177):
            instance = self._current_metadata_instance(compressor, line, {})
            errors = []
            _validate_custom_target(instance, cmake_list_words, errors)
            self.assertEqual(errors, [])
            changed = replace(instance.body, command=replace(instance.body.command,
                body=instance.body.command.body + " COMMAND foreign"))
            errors = []
            _validate_custom_target(replace(instance, body=changed, evaluation=changed), cmake_list_words, errors)
            self.assertTrue(errors)
        changed = replace(property_instance.body, source_base=Path("apps/trader"))
        errors = []
        validate_property_command(replace(property_instance, body=changed, evaluation=changed), errors)
        self.assertTrue(errors)
        relative = "apps/hft-backtest/CMakeLists.txt"
        target = "hft_backtest_generate_strategy_metadata"
        state = {"HFT_BACKTEST_GENERATED_STRATEGY_METADATA":
            (SYNTHETIC_BINARY_ROOT + "/apps/hft-backtest/generated/hft_backtest/generated/StrategyMetadata.hpp",),
            "HFT_BACKTEST_STRATEGY_PROFILES": ()}

        def retired_instance(command, body):
            active = ActiveCommand(relative, relative, Path(relative).parent,
                Path(relative).parent, (relative,), Command(command, body, 1), 0)
            snapshots = SimpleNamespace(values={0: state})
            groups = tuple(tuple(expand_active_tokens(active, [token], snapshots, ROOT))
                for token in cmake_list_words(body))
            return InstantiatedCommand(active, active, groups, 0)

        for name, value in (
                ("CXET_COMPILE_INPUTS", '"${CMAKE_CURRENT_SOURCE_DIR}/tools/GenerateStrategyMetadata.py" ${HFT_BACKTEST_STRATEGY_PROFILES}'),
                ("CXET_COMPILE_OUTPUTS", '"${HFT_BACKTEST_GENERATED_STRATEGY_METADATA}"')):
            instance = retired_instance("set_property", f"TARGET {target} PROPERTY {name} {value}")
            errors = []
            validate_property_command(instance, errors)
            self.assertTrue(errors)
        instance = retired_instance("add_custom_target",
            f'{target} DEPENDS "${{HFT_BACKTEST_GENERATED_STRATEGY_METADATA}}"')
        errors = []
        _validate_custom_target(instance, cmake_list_words, errors)
        self.assertTrue(errors)

    def test_current_wasm_and_frontend_metadata_keep_readonly_recipe_and_exact_inputs(self):
        from dataclasses import replace
        from unittest.mock import patch
        from CMake.Policy.CmakeFamilyPropertyPolicy import (
            validate_property_command, reviewed_wasm_inputs, reviewed_wasm_alternatives,
        )
        from CMake.Policy.CmakeFamilyCommandPolicy import _validate_custom_target
        from CMake.Policy.CmakeFamilyFrontendRecipe import reviewed_frontend_recipe
        from CMake.Policy import CmakeFamilyFrontendRecipe as frontend_policy
        from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT
        generated = SYNTHETIC_BINARY_ROOT + "/apps/vetron/wasm/"
        compiler = "$<CXET_UNKNOWN_SOURCE_PROFILE>"
        prepared = reviewed_wasm_inputs(prepared=True, actual_inputs=(compiler,))
        self.assertIsNotNone(prepared)
        self.assertIsNotNone(reviewed_frontend_recipe(), "frontend producer authority must be current before proving WASM output paths")
        state = {
            "VETRON_MATH_WASM_OUTPUT": ((ROOT / "apps/vetron/frontend/.generated/trading-core-math.wasm").as_posix(),),
            "VETRON_MATH_WASM_SCRIPT": ((ROOT / "apps/vetron/wasm/BuildMathWasm.py").as_posix(),),
            "VETRON_MATH_WASM_STAMP": (generated + "math-wasm.stamp.json",),
            "VETRON_MATH_WASM_DEPFILE": (generated + "math-wasm.d",),
            "VETRON_EMSCRIPTEN_BOOTSTRAP": ((ROOT / "tools/Toolchain/BootstrapEmscripten.py").as_posix(),),
            "VETRON_EMXX_EXECUTABLE": (compiler,),
            "vetron_math_wasm_headers": tuple(sorted(value for value in prepared if value.startswith((
                (ROOT / "apps/trading-core/src/Core/include").as_posix() + "/",
                (ROOT / "apps/trading-core/src/Contracts/include").as_posix() + "/",
                (ROOT / "src/src/Contracts/include").as_posix() + "/")))),
        }
        wasm = "apps/vetron/wasm/CMakeLists.txt"
        identity = frontend_policy.reviewed_file_identity
        with patch.object(frontend_policy, "reviewed_file_identity", side_effect=lambda relative:
                relative != "apps/vetron/frontend/package.json" and identity(relative)):
            self.assertIsNone(reviewed_frontend_recipe())
            errors = []
            validate_property_command(self._current_metadata_instance(wasm, 48, state), errors)
            self.assertTrue(errors)
        for line in (40, 48, 93, 103):
            instance = self._current_metadata_instance(wasm, line, state)
            errors = []
            validate_property_command(instance, errors)
            self.assertEqual(errors, [], (line, errors))
            groups = (*instance.token_groups[:-1], (*instance.token_groups[-1], "/foreign/input"))
            errors = []
            validate_property_command(replace(instance, token_groups=groups), errors)
            self.assertTrue(errors)
        alternatives = []
        for line in (35, 66):
            instance = self._current_metadata_instance(wasm, line, state)
            errors = []
            _validate_custom_target(instance, cmake_list_words, errors)
            self.assertEqual(errors, [], (line, errors))
            alternatives.append(replace(instance, path_alternatives=((("reviewed-wasm", len(alternatives)),),)))
            replacement = (instance.body.command.body.replace("cxet::read_only_contracts", "trader::control_client")
                if line == 66 else instance.body.command.body.replace("-E false", "-E true"))
            changed = replace(instance.body, command=replace(instance.body.command, body=replacement))
            errors = []
            _validate_custom_target(replace(instance, body=changed, evaluation=changed), cmake_list_words, errors)
            self.assertTrue(errors)
        self.assertTrue(reviewed_wasm_alternatives(alternatives))
        self.assertFalse(reviewed_wasm_alternatives((*alternatives, alternatives[0])))
        self.assertFalse(reviewed_wasm_alternatives((alternatives[0],
            replace(alternatives[1], path_alternatives=alternatives[0].path_alternatives))))
        foreign = replace(alternatives[1].body, scope="foreign/CMakeLists.txt")
        self.assertFalse(reviewed_wasm_alternatives((alternatives[0],
            replace(alternatives[1], body=foreign, evaluation=foreign))))
        self.assertIsNone(reviewed_wasm_inputs(prepared=True, actual_inputs=("$<foreign>",)))
        recipe = reviewed_frontend_recipe()
        self.assertIsNotNone(recipe)
        frontend_state = {
            "VETRON_FRONTEND_SCRIPT": (recipe["command"][1],),
            "VETRON_FRONTEND_OUTPUT_DIR": ((ROOT / "apps/vetron/build/frontend-static").as_posix(),),
            "VETRON_FRONTEND_STAMP": recipe["manifest"],
            "VETRON_FRONTEND_GENERATED_DIR": ((ROOT / "apps/vetron/frontend/.generated").as_posix(),),
            "VETRON_FRONTEND_EXCHANGES": ("all",), "VETRON_FRONTEND_MATH_ARGUMENTS": (),
            "VETRON_FRONTEND_INPUTS": recipe["inputs"],
            "VETRON_FRONTEND_GENERATED_OUTPUTS": recipe["outputs"][2:],
            "VETRON_MATH_WASM_OUTPUT": recipe["wasm"],
        }
        for line in (279, 294, 296, 299):
            instance = self._current_metadata_instance("apps/vetron/CMakeLists.txt", line, frontend_state)
            errors = []
            if line == 279:
                _validate_custom_target(instance, cmake_list_words, errors)
            else:
                validate_property_command(instance, errors)
            self.assertEqual(errors, [], (line, errors))
            if line != 279:
                groups = (*instance.token_groups[:-1], (*instance.token_groups[-1], "/foreign/input"))
                errors = []
                validate_property_command(replace(instance, token_groups=groups), errors)
                self.assertTrue(errors)
        from CMake.Policy.CmakeFamilyCommandPolicy import _custom_target_dependencies
        from collections import Counter
        duplicated_policy = (ROOT / "src/src/Core/include/cxet/Exchanges/Finam/TradeApiV1/"
            "Shared/Grpc/Reference/Protobuf/TradingCost/FinamTradingCostPolicy.hpp").as_posix()
        self.assertEqual({path: count for path, count in Counter(recipe["dependencies"]).items()
            if count > 1}, {duplicated_policy: 2})
        frontend = self._current_metadata_instance("apps/vetron/CMakeLists.txt", 279, frontend_state)
        edge = self._current_metadata_instance("apps/vetron/CMakeLists.txt", 293, frontend_state)
        wasm_declaration = self._current_metadata_instance(wasm, 35, state)
        input_index = cmake_list_words(frontend.body.command.body).index("${VETRON_FRONTEND_INPUTS}")
        groups = list(frontend.token_groups)
        groups[input_index] = tuple(reversed(groups[input_index]))
        reordered = replace(frontend, token_groups=tuple(groups))
        errors = []
        _custom_target_dependencies([wasm_declaration, reordered, edge], {}, errors, False)
        self.assertEqual(errors, [])
        # The aggregate order is immaterial; producer input order remains exact.
        errors = []
        _validate_custom_target(reordered, cmake_list_words, errors)
        self.assertTrue(errors)
        missing_policy_copy = list(groups[input_index])
        missing_policy_copy.remove(duplicated_policy)
        for values in ((), (*groups[input_index], "/foreign/input"),
                (*groups[input_index], groups[input_index][0]),
                (*groups[input_index], duplicated_policy), tuple(missing_policy_copy)):
            changed = list(groups)
            changed[input_index] = values
            errors = []
            _custom_target_dependencies([wasm_declaration, replace(frontend, token_groups=tuple(changed)), edge],
                {}, errors, False)
            self.assertTrue(any("dependency closure changed" in error for error in errors), errors)
            self.assertTrue(all(len(error) < 6000 for error in errors), errors)


if __name__ == '__main__':
    unittest.main()
