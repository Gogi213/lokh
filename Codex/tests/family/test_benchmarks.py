"""Benchmarks regressions."""
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

class BenchmarkActivationTests(unittest.TestCase):
    def test_benchmark_diagnostic_edges_keep_target_and_tu_boundaries(self):
        from Family.Sources.CxetFamilySourcePolicy import (
            benchmark_include_edge, benchmark_external_include, benchmark_translation_unit_context,
        )
        from CMake.Policy.CmakeFamilyLinkOptions import safe_link_option
        target = "trader-bench-vstack_traced"
        own = "apps/trader/benchmarks/VstackPeer.cpp"
        trace = "tools/Benchmarks/native/SendTrace.cpp"
        self.assertEqual(benchmark_translation_unit_context(target, own), "owner")
        self.assertEqual(benchmark_translation_unit_context(target, trace), "trace")
        self.assertIsNone(benchmark_translation_unit_context("trader-bench-vstack", trace))
        self.assertTrue(benchmark_external_include(target, own, "source_location", own))
        self.assertFalse(benchmark_external_include(target, own, "source_location", trace))
        header = "tools/Benchmarks/native/LoopbackTls.hpp"
        selected = "src/src/Core/src/Network/Tls/SocketState.hpp"
        self.assertTrue(benchmark_include_edge(target, header, selected, own))
        self.assertFalse(benchmark_include_edge("cxet_lib", header, selected, own))
        self.assertFalse(benchmark_include_edge(target, header, selected, "apps/trader/src/Main.cpp"))
        self.assertFalse(safe_link_option("-Wl,--wrap=send"))

    def test_order_private_benchmark_edges_keep_target_source_and_tu_boundaries(self):
        from Family.Sources.CxetFamilySourcePolicy import benchmark_include_edge
        header = "src/src/Core/src/Api/Order/OrderSessionPoolInternal.hpp"
        for target, source, translation_unit in (
                ("parser-bench-native-fix", "tools/Benchmarks/native/NativeFixPeer.hpp",
                 "apps/hft-parser/benchmarks/NativeFix.cpp"),
                ("trader-bench-native-lane", "tools/Benchmarks/native/NativeFixPeer.hpp",
                 "apps/trader/benchmarks/NativeLane.cpp"),
                ("trader-bench-capacity", "tools/Benchmarks/native/NativeFixPeer.hpp",
                 "apps/trader/benchmarks/Capacity.cpp"),
                ("trader-bench-vstack", "apps/trader/benchmarks/VstackPeerOrder.cpp",
                 "apps/trader/benchmarks/VstackPeerOrder.cpp"),
                ("trader-bench-json-ws", "apps/trader/benchmarks/JsonWsNativePeer.hpp",
                 "apps/trader/benchmarks/JsonWs.cpp")):
            for selected_target in (target, target + "_traced"):
                with self.subTest(target=selected_target):
                    self.assertTrue(benchmark_include_edge(selected_target, source, header, translation_unit))
                    self.assertFalse(benchmark_include_edge(selected_target, source, header,
                        "apps/trader/benchmarks/Foreign.cpp"))
                    self.assertFalse(benchmark_include_edge(selected_target, source + ".future", header, translation_unit))
                    self.assertFalse(benchmark_include_edge(selected_target, source,
                        "src/src/Core/src/Api/Order/Common/OrderSessionOwnerState.hpp", translation_unit))
                    self.assertFalse(benchmark_include_edge(selected_target, source, header,
                        "tools/Benchmarks/native/SendTrace.cpp"))
            self.assertFalse(benchmark_include_edge("cxet_lib", source, header, translation_unit))
            self.assertFalse(benchmark_include_edge("trader-bench-hot-trader", source, header, translation_unit))

    def test_benchmark_role_requires_exact_target_and_physical_context(self):
        from CMake.Policy.CmakeFamilyBenchmarkRecipe import benchmark_target_context, benchmark_target_owner
        origin = "src/benchmarks/CMakeLists.txt"
        active = SimpleNamespace(relative=origin, source_base=Path("src/benchmarks"),
                                 binary_base=Path("src/benchmarks"))
        self.assertEqual(benchmark_target_owner("cxet_bench_core_traced", origin), "CXETCPP")
        self.assertTrue(benchmark_target_context(active, "cxet_bench_core"))
        self.assertFalse(benchmark_target_context(active, "unreviewed_bench"))
        active.source_base = Path("src/src")
        self.assertFalse(benchmark_target_context(active, "cxet_bench_core"))
        self.assertIsNone(benchmark_target_owner("cxet_bench_core", "src/src/CMakeLists.txt"))

    def test_current_benchmark_producer_lowers_both_exact_binaries(self):
        from CMake.Policy.CmakeFamilyBenchmarkRecipe import BENCHMARK_ROOTS, BENCHMARK_TARGETS
        from Family.Profile.CxetFamilyBenchmarkActivation import lower_benchmark_registrations, validate_benchmark_helper
        from CMake.Syntax.CmakeFamilyDialect import validate_exact_active_inventory
        errors = []
        self.assertTrue(validate_benchmark_helper(ROOT, errors))
        for relative in BENCHMARK_ROOTS:
            text = (ROOT / relative).read_text()
            lowered = lower_benchmark_registrations(ROOT, relative,
                parse_commands(relative, text, errors), errors)
            declarations = [cmake_list_words(command.body)[0] for command in lowered
                            if command.name == "add_executable"]
            self.assertEqual(declarations,
                [binary for target in BENCHMARK_TARGETS[relative] for binary in (target, target + "_traced")])
            traces = [command for command in lowered if command.name == "target_sources"]
            self.assertEqual(len(traces), len(BENCHMARK_TARGETS[relative]))
            self.assertTrue(all(cmake_list_words(command.body)[0].endswith("_traced") for command in traces))
            active = compose_active_commands(ROOT, {relative: (text, lowered)}, (relative,), set(), errors)
            validate_exact_active_inventory(active, cmake_list_words, errors,
                                            active_origins=frozenset({relative}))
        self.assertEqual(errors, [])

    def test_benchmark_helper_and_registration_mutations_fail_closed(self):
        from Family.Profile.CxetFamilyBenchmarkActivation import (
            BENCHMARK_HELPER, lower_benchmark_registrations, validate_benchmark_helper,
        )
        raw = (ROOT / BENCHMARK_HELPER).read_text()
        errors = []
        self.assertFalse(validate_benchmark_helper(ROOT, errors, text=raw + "\n"))
        self.assertTrue(errors)
        relative = "src/benchmarks/CMakeLists.txt"
        original = (ROOT / relative).read_text()
        for changed in (original.replace("OWNER CXETCPP", "OWNER trader", 1),
                        original.replace("SOURCES CoreBench.cpp", "SOURCES ../src/Core/src/Crypto/Crypto.cpp", 1),
                        original.replace("REQUIRES CXET_SELECTION_ALL", "REQUIRES UNKNOWN_REQUIREMENT", 1),
                        original + "\nadd_library(rogue STATIC Rogue.cpp)\n"):
            errors = []
            lower_benchmark_registrations(ROOT, relative,
                parse_commands(relative, changed, errors), errors)
            self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
