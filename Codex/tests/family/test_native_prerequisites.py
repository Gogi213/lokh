"""Native prerequisites regressions."""
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

class NativePrerequisiteTests(unittest.TestCase):
    def test_function_body_index_preserves_members_without_caching_termination(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, NO_PATHS
        relative = "provider/CMakeLists.txt"
        text = ('function(helper)\nif(FLAG)\nmessage(FATAL_ERROR "refused")\nendif()\nendfunction()\n'
                'helper()\nadd_library(provider STATIC Main.cpp)')
        errors = []
        commands = compose_active_commands(ROOT,
            {relative: (text, parse_commands(relative, text, errors))}, (relative,), set(), errors)
        model = function_model(commands, errors)
        owner = model.global_definitions["helper"]
        self.assertEqual(model.bodies[owner], tuple(command for command in commands
                         if model.members.get(command.ordinal) == owner))
        for flag, expected in (("ON", NO_PATHS), ("OFF", ALL_PATHS), ("ON", NO_PATHS)):
            run_errors = []
            snapshots = variable_snapshots(commands, model, run_errors, {"FLAG": (flag,)})
            self.assertEqual(snapshots.live_eof_paths[relative], expected)
            self.assertEqual(run_errors, [
                f"{relative}: no feasible LIVE path reaches composed root EOF"
            ] if flag == "ON" else [])
        independent = function_model(commands, errors)
        self.assertIsNot(independent.bodies, model.bodies)
        self.assertEqual(errors, [])

    def test_keccak_generic_paste_include_stays_inside_pinned_upstream_caller(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_include_edge
        selected = "extra/xkcp/lib/high/Keccak/KeccakSponge.inc"
        caller = "extra/xkcp/lib/high/Keccak/KeccakSponge.c"
        self.assertTrue(native_crypto_include_edge("cxet_crypto", caller, selected))
        for source in ("src/src/Core/src/Crypto/Crypto.cpp", "extra/xkcp/lib/common/unreviewed.h"):
            self.assertFalse(native_crypto_include_edge("cxet_crypto", source, selected))
            self.assertFalse(verification_include_allowed(source, selected))
        self.assertFalse(native_crypto_include_edge("cxet_crypto_rsa", caller, selected))

    def test_literal_sanitizer_list_find_proves_guard_before_native_declarations(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        relative = "provider/CMakeLists.txt"
        text = ('set(valid none address-undefined thread)\n'
                'list(FIND valid "${CXET_SANITIZER_PROFILE}" index)\n'
                'if(index EQUAL -1)\nmessage(FATAL_ERROR "invalid")\nendif()\n'
                'add_library(provider STATIC Main.cpp)')
        errors = []
        files = {relative: (text, parse_commands(relative, text, errors))}
        commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
        model = function_model(commands, errors)
        for profile, index in (("none", "0"), ("address-undefined", "1"), ("thread", "2")):
            snapshots = variable_snapshots(commands, model, errors,
                {"CXET_SANITIZER_PROFILE": (profile,)})
            self.assertEqual(snapshots.live_eof_paths[relative], ALL_PATHS)
            self.assertEqual(snapshots.path_alternatives[5], ALL_PATHS)
            self.assertEqual(snapshots.values[2]["index"], (index,))
        self.assertEqual(errors, [])

    def test_list_find_keeps_unknown_and_serialized_lists_tainted(self):
        from CMake.Flow.CmakeFamilyMutations import apply_list_command
        from CMake.Flow.CmakeFamilyState import expand_variable_tokens
        for values, searched, expected in (
                (("a", "b", "a"), "a", ("${index}",)),
                (("a", "b"), "missing", ("${index}",)),
                ((), "a", ("${index}",)),
                (("${unknown}",), "a", ("${index}",)),
                (("a;b",), "a", ("${index}",))):
            state = {"items": values}
            errors = []
            apply_list_command(["FIND", "items", searched, "index"], state,
                lambda tokens: expand_variable_tokens(tokens, state), errors, "fixture")
            self.assertEqual(errors, [])
            self.assertEqual(state["index"], expected)

    def test_find_after_ordered_mutations_requires_direct_literal_producer(self):
        from CMake.Flow.CmakeFamilyMutations import apply_list_command
        from CMake.Flow.CmakeFamilyState import expand_variable_tokens
        for operation in (["SORT", "items"], ["REVERSE", "items"],
                          ["REMOVE_DUPLICATES", "items"],
                          ["INSERT", "items", "0", "x"]):
            state = {"items": ("b", "a")}
            errors = []
            expand = lambda tokens: expand_variable_tokens(tokens, state)
            apply_list_command(operation, state, expand, errors, "fixture")
            apply_list_command(["FIND", "items", "a", "index"], state, expand, errors, "fixture")
            self.assertEqual(state["index"], ("${index}",))
            self.assertEqual(errors, [])

    def test_copied_find_inputs_do_not_borrow_literal_producer_proof(self):
        from CMake.Flow.CmakeFamilyMutations import apply_list_command
        from CMake.Flow.CmakeFamilyState import expand_variable_tokens
        for operation in (["SORT", "items", "CASE", "INSENSITIVE"],
                          ["INSERT", "items", "${unknown}", "x"]):
            state = {"items": ("b", "a")}
            errors = []
            expand = lambda tokens: expand_variable_tokens(tokens, state)
            apply_list_command(operation, state, expand, errors, "fixture")
            state["alias"] = tuple(expand(["${items}"]))
            apply_list_command(["FIND", "alias", "a", "index"], state, expand, errors, "fixture")
            self.assertEqual(state["index"], ("${index}",))
            self.assertEqual(errors, [])

    def test_find_producer_proof_requires_immediate_same_context_set(self):
        from dataclasses import replace
        relative = "provider/CMakeLists.txt"
        for before, expected in (
                ("set(items b a)\n", ("1",)),
                ("set(items b b a)\n", ("2",)),
                ("set(items b a)\nlist(SORT items)\n", ("${index}",)),
                ("set(items b a)\nset(alias ${items})\n", ("${index}",)),
                ("if(unknown)\nset(items b a)\nendif()\n", ("${index}",))):
            text = before + "list(FIND items a index)\nadd_library(provider STATIC Main.cpp)"
            errors = []
            files = {relative: (text, parse_commands(relative, text, errors))}
            commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
            model = function_model(commands, errors)
            snapshots = variable_snapshots(commands, model, errors)
            self.assertEqual(snapshots.values[commands[-1].ordinal]["index"], expected)
            self.assertEqual(errors, [])
        # An adjacent command from another physical include is no producer
        # proof, even when the directory state currently has the same values.
        text = "set(items b a)\nlist(FIND items a index)\nadd_library(provider STATIC Main.cpp)"
        errors = []
        commands = compose_active_commands(ROOT,
            {relative: (text, parse_commands(relative, text, errors))}, (relative,), set(), errors)
        commands[0] = replace(commands[0], relative="provider/child.cmake")
        snapshots = variable_snapshots(commands, function_model(commands, errors), errors)
        self.assertEqual(snapshots.values[commands[-1].ordinal]["index"], ("${index}",))
        self.assertEqual(errors, [])

    def test_parser_history_definition_is_backend_owned_and_resolved(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        from Family.Targets.CxetFamilyTargetPolicy import unsafe_compile_definition_carriers
        relative = "apps/hft-parser/cmake/HftpLibraries.cmake"
        base = Path("apps/hft-parser")
        command = Command("target_compile_definitions",
            "hftp_backend_headers INTERFACE HFTP_CANDLE_HISTORY=$<BOOL:${HFT_PARSER_CANDLE_HISTORY}>", 38)
        active = ActiveCommand("fixture", relative, base, base, (), command, 0)
        instance = InstantiatedCommand(active, active, (), 0, ALL_PATHS)
        for selection in ("ON", "OFF", "1", "0"):
            values = (f"HFTP_CANDLE_HISTORY=$<BOOL:{selection}>",)
            self.assertEqual(unsafe_compile_definition_carriers(instance, "hftp_backend_headers", values), ())
            self.assertEqual(unsafe_compile_definition_carriers(instance, "hftp_client_headers", values), values)
            shifted = replace(active, source_base=Path("apps/trader"))
            self.assertEqual(unsafe_compile_definition_carriers(
                replace(instance, body=shifted, evaluation=shifted), "hftp_backend_headers", values), values)
        for selection in ("${unknown}", "", "ON;OFF"):
            values = (f"HFTP_CANDLE_HISTORY=$<BOOL:{selection}>",)
            self.assertEqual(unsafe_compile_definition_carriers(instance, "hftp_backend_headers", values), values)
        changed = replace(active, command=replace(command,
            body=command.body.replace("INTERFACE", "PUBLIC")))
        values = ("HFTP_CANDLE_HISTORY=$<BOOL:ON>",)
        self.assertEqual(unsafe_compile_definition_carriers(
            replace(instance, body=changed, evaluation=changed), "hftp_backend_headers", values), values)

    def test_native_definition_domain_rejects_architect_platform_counterexample(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_definition_error
        from Family.Targets.CxetFamilyTargetPolicy import unsafe_compile_definition_carriers
        from Family.Sources.CxetFamilyNativeInputs import native_syntax_data
        definitions = ("__APPLE__=1", "__MACH__=1")
        self.assertEqual(unsafe_compile_definition_carriers(SimpleNamespace(), "cxet_crypto", definitions), definitions)
        for value in (*definitions, "__ARM_NEON=1", "UNKNOWN_NATIVE_MACRO=1"):
            self.assertTrue(native_crypto_definition_error("cxet_crypto", value))
        for value in ("CXET_NO_HFT_MAGIC=1", "HACL_CAN_COMPILE_UINT128=1", "HACL_CAN_COMPILE_VEC128=1"):
            self.assertFalse(native_crypto_definition_error("cxet_crypto", value))
        self.assertTrue(native_crypto_definition_error("cxet_crypto_rsa", "HACL_CAN_COMPILE_VEC128=1"))
        raw = b'#include <AvailabilityMacros.h>\n'
        source = "extra/hacl-star/dist/karamel/include/krml/internal/target.h"
        # Only the pinned native/compiler domain can use its dormant adapter.
        self.assertEqual(native_syntax_data(source, raw, verified=False), raw)

    def test_native_project_configuration_bytes_cannot_override_platform(self):
        from Family.Sources.CxetFamilyNativeInputs import NativeInputs
        relative = "src/src/Core/src/Crypto/RsaMbedConfig.h"
        raw = (ROOT / relative).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            self.assertEqual(NativeInputs(IncludeInputs(root)).configuration(relative), raw)
            path.write_bytes(raw + b"\n#define __APPLE__ 1\n#define __MACH__ 1\n")
            with self.assertRaises(OSError):
                NativeInputs(IncludeInputs(root)).configuration(relative)

    def test_xkcp_configuration_cannot_enable_dormant_reference_includes(self):
        from Family.Sources.CxetFamilyNativeInputs import NativeInputs
        relative = "cmake/Vendor/xkcp/config.h"
        raw = (ROOT / relative).read_bytes()
        source = "extra/xkcp/lib/high/Keccak/KeccakSponge.c"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(raw)
            self.assertEqual(NativeInputs(IncludeInputs(root)).configuration(relative), raw)
            path.write_bytes(raw + b"\n#define KeccakReference 1\n")
            native = NativeInputs(IncludeInputs(root))
            with self.assertRaises(OSError):
                native.configuration(relative)
            with self.assertRaises(OSError):
                native.verify(source, (ROOT / source).read_bytes())

    def test_native_config_adapters_keep_enabled_or_unknown_hooks_fail_closed(self):
        from Family.Sources.CxetFamilyNativeInputs import native_syntax_data
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_definition_error
        source = "extra/mbedtls-cold/include/mbedtls/aes.h"
        data = b'#include "aes_alt.h"\n#include "unknown_hook.h"\n'
        absent = native_syntax_data(source, data, verified=True, config_data=b"#define MBEDTLS_AES_C\n")
        self.assertNotIn(b"aes_alt.h", absent)
        self.assertIn(b"unknown_hook.h", absent)
        enabled = native_syntax_data(source, data, verified=True, config_data=b"#define MBEDTLS_AES_ALT\n")
        self.assertEqual(enabled, data)
        self.assertTrue(native_crypto_definition_error("cxet_crypto_rsa", "MBEDTLS_AES_ALT=1"))
        with self.assertRaises(OSError):
            native_syntax_data(source, data, verified=True, config_data=b'#include "indirect.h"\n')

    def test_native_file_probe_records_actual_missing_candidates(self):
        from Family.Sources.CxetFamilyNativeInputs import native_syntax_data
        source = "extra/hacl-star/dist/gcc-compatible/libintvector.h"
        raw = b'#if defined(__has_include)\n#if __has_include("libintvector_debug.h")\n#include "libintvector_debug.h"\n#endif\n#endif\n#if __has_include("unknown.h")\n#endif\n'
        probes = []
        adapted = native_syntax_data(source, raw, verified=True,
            probe_include=lambda spelling: probes.append(spelling) or False)
        self.assertEqual(probes, ["libintvector_debug.h"])
        self.assertNotIn(b'#include "libintvector_debug.h"', adapted)
        self.assertIn(b'__has_include("unknown.h")', adapted)

    def test_native_private_config_and_textual_source_edges_stay_exact(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_include_edge, native_crypto_textual_source
        config = "src/src/Core/src/Crypto/RsaMbedConfig.h"
        header = "extra/mbedtls-cold/include/mbedtls/build_info.h"
        self.assertTrue(native_crypto_include_edge("cxet_crypto_rsa", header, config, config=config))
        self.assertFalse(native_crypto_include_edge("cxet_crypto_rsa", header, config))
        self.assertTrue(native_crypto_textual_source("cxet_crypto_rsa", "src/src/Core/src/Crypto/RsaMbedConstantTime.c", "extra/mbedtls-cold/library/constant_time.c"))
        self.assertFalse(native_crypto_textual_source("cxet_lib", "src/src/Core/src/Crypto/RsaMbedConstantTime.c", "extra/mbedtls-cold/library/constant_time.c"))

    def test_contextual_import_function_does_not_enable_module_carriers(self):
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        self.assertEqual(cpp_include_syntax(b"bool import(int x) { return x; } void f(){ import(1); }")[2], [])
        for sample in (b"import foreign.module;", b"export module foreign;",
                       b"IDENTITY(import) foreign.module;", b"#define BODY import(1)\n"):
            self.assertTrue(cpp_include_syntax(sample)[2], sample)

    def test_contextual_module_fields_and_range_variables_keep_source_visible(self):
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        source = b'''#include "Research.hpp"
          struct Spec {std::string module; int import=0;};
          void render() {
            spec.module=value; use(spec->module); use(model::module);
            for (const auto& module : catalog) use(module.name);
          }'''
        _, includes, errors = cpp_include_syntax(source)
        self.assertEqual(errors, [])
        self.assertEqual(includes, [(b"Research.hpp", False)])

    def test_contextual_identifiers_do_not_hide_real_module_carriers(self):
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        prefix = b"struct Spec {std::string module;}; void f(){spec.module.clear();}\n"
        for carrier in (b"module;", b"module :private;", b"export module hidden;",
                        b"import hidden.module;", b"IDENTITY(module) hidden;",
                        b"IDENTITY(import) hidden;", b"PREFIX module;",
                        b"PREFIX module:private;", b"#define int\nint module;",
                        b"#define auto\nauto module:private;"):
            with self.subTest(carrier=carrier):
                self.assertTrue(cpp_include_syntax(prefix + carrier)[2])

    def test_native_adaptation_requires_pinned_bytes_and_preserves_unknown_carriers(self):
        from Family.Sources.CxetFamilyNativeInputs import NativeInputs, native_syntax_data
        inputs = IncludeInputs(ROOT)
        native = NativeInputs(inputs)
        source = "extra/mbedtls-cold/library/common.h"
        raw = inputs.read(source)
        self.assertTrue(native.verify(source, raw))
        with self.assertRaises(OSError):
            native.verify(source, raw + b'\n#include "foreign.h"\n')
        sample = b'#define asm __asm\n#define BODY import foreign.module;\n'
        self.assertEqual(native_syntax_data(source, sample, verified=False), sample)
        adapted = native_syntax_data(source, sample, verified=True)
        self.assertNotIn(b"#define asm", adapted)
        self.assertIn(b"import foreign.module", adapted)
        for relative in ("extra/mbedtls-cold/library/aes.c", "extra/mbedtls-cold/library/aesni.c",
                         "extra/mbedtls-cold/library/sha1.c"):
            self.assertTrue(native.verify(relative, inputs.read(relative)))

    def test_frontend_recipe_requires_all_independent_producer_identities(self):
        from CMake.Policy import CmakeFamilyFrontendRecipe as frontend
        with patch.object(frontend, "reviewed_file_identity", return_value=False):
            self.assertIsNone(frontend.reviewed_frontend_recipe())

    @staticmethod
    def active(name, body, ordinal, *, relative="src/src/CMakeLists.txt", context=()):
        line = 234 if body == "NOT TARGET cxet_crypto" else 101
        return SimpleNamespace(relative=relative, source_base=Path("src/src"), scope="test",
            binary_base=Path("src/src"), structural_context=context, ordinal=ordinal,
            command=SimpleNamespace(name=name, body=body, line=line))

    def test_native_secp_namespace_requires_independent_edge_not_ghost(self):
        from CMake.Flow import CmakeFamilyInstances as instances
        from CMake.Flow.CmakeFamilyState import SHARED_TARGET_NAMESPACE, NATIVE_PREREQUISITE_NAMESPACE
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        from CMake.Syntax.CmakeFamilyContext import StructuralFrame, StructuralArm
        guard = self.active("if", "CXET_HAS_SECP256K1 AND NOT TARGET secp256k1", 10)
        guard.command.line = 192
        opener = ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1")
        edge = self.active("add_subdirectory", '"${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1" "${CMAKE_CURRENT_BINARY_DIR}/_deps/secp256k1" EXCLUDE_FROM_ALL', 20,
            context=(StructuralFrame("if", "src/src/CMakeLists.txt", 192, 0,
                opener, StructuralArm("if", opener)),))
        snapshots = SimpleNamespace(live_eof_paths={"test": ALL_PATHS}, path_alternatives={20: ALL_PATHS})
        def prove(commands, *, authority=True, eof=ALL_PATHS):
            result = {SHARED_TARGET_NAMESPACE: {}, NATIVE_PREREQUISITE_NAMESPACE: {10: {"secp256k1": "PROVED_ABSENT"}}}
            snapshots.live_eof_paths["test"] = eof
            with patch.object(instances, "reviewed_external_authority", return_value=authority):
                instances._native_external_targets(result, commands, snapshots)
            return result[SHARED_TARGET_NAMESPACE]
        self.assertEqual(set(prove([guard, edge])), {"secp256k1", "secp256k1_precomputed"})
        self.assertEqual(prove([guard, edge], authority=False), {})
        self.assertEqual(prove([guard, edge], eof=()), {})
        later_symbolic = ((("later-platform-probe", 0),),)
        self.assertEqual(set(prove([guard, edge], eof=later_symbolic)), {"secp256k1", "secp256k1_precomputed"})
        snapshots.path_alternatives[20] = later_symbolic
        self.assertEqual(prove([guard, edge], eof=later_symbolic), {})
        snapshots.path_alternatives[20] = ALL_PATHS
        earlier = self.active("add_library", "${dynamic} STATIC source.c", 5)
        self.assertEqual(prove([earlier, guard, edge]), {})

    def test_native_absence_rejects_prior_possible_or_dynamic_declaration(self):
        from CMake.Flow.CmakeFamilyInstances import _native_prerequisites
        guard = self.active("if", "NOT TARGET cxet_crypto", 10)
        self.assertEqual(_native_prerequisites([guard], [])[10]["cxet_crypto"], "PROVED_ABSENT")
        for spelling in ("cxet_crypto", "${dynamic}"):
            earlier = self.active("add_library", spelling + " STATIC source.c", 5,
                                  context=("conditional",))
            self.assertNotIn("cxet_crypto", _native_prerequisites([earlier, guard], []).get(10, {}))
        foreign = self.active("if", "NOT TARGET cxet_crypto", 10, relative="foreign/CMakeLists.txt")
        self.assertEqual(_native_prerequisites([foreign], []), {})

    def test_native_vendor_file_requires_unsymlinked_presence(self):
        from CMake.Flow import CmakeFamilyInstances as instances
        raw = "${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"
        guard = self.active("if", 'NOT TARGET liburing::uring AND EXISTS "' + raw + '"', 10)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "extra/liburing/configure"
            path.parent.mkdir(parents=True)
            with patch.object(instances, "ROOT", root):
                self.assertNotIn("EXISTS:" + raw, instances._native_prerequisites([guard], [])[10])
                path.write_bytes(b"configure")
                self.assertEqual(instances._native_prerequisites([guard], [])[10]["EXISTS:" + raw], "PROVED_PRESENT")
                path.rename(path.with_name("real"))
                path.symlink_to(path.with_name("real"))
                self.assertNotIn("EXISTS:" + raw, instances._native_prerequisites([guard], [])[10])

    def test_absence_marker_does_not_ground_arbitrary_target(self):
        from CMake.Flow.CmakeFamilyFlow import evaluate_condition, Truth
        identity = lambda tokens, preserve: list(tokens)
        self.assertIs(evaluate_condition(("TARGET", "ghost"), {}, identity,
            ("TARGET", "ghost"), known_targets={"ghost": "PROVED_ABSENT"}), Truth.UNKNOWN)
        self.assertIs(evaluate_condition(("NOT", "TARGET", "cxet_crypto"), {}, identity,
            ("NOT", "TARGET", "cxet_crypto"), known_targets={"cxet_crypto": "PROVED_ABSENT"}), Truth.TRUE)


if __name__ == '__main__':
    unittest.main()
