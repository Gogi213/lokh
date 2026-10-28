"""Full inventory regressions."""
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

class FullFamilyInventoryTests(unittest.TestCase):
    def _instances(self, relative):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        self.assertEqual(errors, [])
        result = []
        for ordinal, (command, context) in enumerate(zip(commands, contexts), 1):
            active = ActiveCommand('inventory-fixture', relative, Path(relative).parent,
                Path(relative).parent, (), command, ordinal, structural_context=context)
            result.append(InstantiatedCommand(active, active,
                tuple((token,) for token in cmake_list_words(command.body)), ordinal, ALL_PATHS))
        return result

    def test_current_core_source_and_secp_recipe_keep_exact_guard_contexts(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyTargetPolicy import (
            canonical_source_structural_error, build_dependency_error)
        rows = self._instances('src/src/CMakeLists.txt')
        declaration = next(row for row in rows if row.body.command.name == 'add_library' and
            cmake_list_words(row.body.command.body) == ['cxet_lib', 'STATIC', '${CXET_LIB_SOURCES}'])
        self.assertIsNone(canonical_source_structural_error('cxet_lib', declaration))
        dependency = next(row for row in rows if row.body.command.name == 'add_dependencies' and
            cmake_list_words(row.body.command.body) == ['cxet_lib', 'secp256k1'])
        with patch('CMake.Flow.CmakeFamilyExecutionIdentity.reviewed_external_authority', return_value=True):
            self.assertIsNone(build_dependency_error(dependency, 'cxet_lib', 'secp256k1', {'cxet_lib': declaration}))
            for original in (declaration, dependency):
                changed = replace(original.body, structural_context=())
                mutated = replace(original, body=changed, evaluation=changed)
                if original is declaration:
                    self.assertIsNotNone(canonical_source_structural_error('cxet_lib', mutated))
                else:
                    self.assertIsNotNone(build_dependency_error(mutated, 'cxet_lib', 'secp256k1', {'cxet_lib': declaration}))

    def test_resident_memory_keeps_direct_declaration_alias_and_exact_owner(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyPropertyPolicy import validate_property_command
        from CMake.Syntax.CmakeFamilyContext import StructuralArm, StructuralFrame
        from Family.Targets.CxetFamilyAliasPolicy import EXACT_ALIASES, target_aliases
        from Family.Targets.CxetFamilyTargetRegistry import _classify
        relative = 'src/src/CMakeLists.txt'
        target = 'cxet_resident_memory'
        alias_name = 'cxet::resident_memory'
        rows = self._instances(relative)
        declaration = next(row for row in rows if row.body.command.name == 'add_library' and
            cmake_list_words(row.body.command.body)[:1] == [target])
        alias = next(row for row in rows if row.body.command.name == 'add_library' and
            cmake_list_words(row.body.command.body)[:1] == [alias_name])
        owner = next(row for row in rows if row.body.command.name == 'set_target_properties' and
            cmake_list_words(row.body.command.body)[:1] == [target])
        errors = []
        classified = _classify(declaration, errors)
        self.assertIsNotNone(classified)
        registry = SimpleNamespace(active_origins={relative}, concrete_names=lambda: {target},
            resolve=lambda name, use, **kwargs: [classified] if name == target and
                declaration.emission_ordinal < use.emission_ordinal else [])
        with patch.dict(EXACT_ALIASES, {alias_name: target}, clear=True):
            self.assertEqual(target_aliases([alias], errors, registry), {alias_name: target})
        validate_property_command(owner, errors)
        self.assertEqual(errors, [])
        # add_subdirectory preserves a nonempty directory execution chain.
        # Equivalent direct occurrences may be copied by the model adapter.
        directory = (relative,)
        occurrence = replace(owner.body, directory=directory,
            execution_chain=((directory, relative),))
        copied = replace(owner, body=occurrence, evaluation=replace(occurrence))
        self.assertIsNot(copied.body, copied.evaluation)
        errors = []
        validate_property_command(copied, errors)
        self.assertEqual(errors, [])
        foreign = replace(copied.evaluation, execution_chain=((directory, 'foreign/CMakeLists.txt'),))
        errors = []
        validate_property_command(replace(copied, evaluation=foreign), errors)
        self.assertTrue(errors)
        opener = ('NOT', 'TARGET', target)
        context = (StructuralFrame('if', relative, declaration.body.command.line,
            declaration.body.ordinal, opener, StructuralArm('if', opener)),)
        guarded = []
        for instance in (declaration, alias, owner):
            active = replace(instance.body, structural_context=context)
            guarded.append(replace(instance, body=active, evaluation=active))
        errors = []
        self.assertIsNone(_classify(guarded[0], errors))
        with patch.dict(EXACT_ALIASES, {alias_name: target}, clear=True):
            target_aliases([guarded[1]], errors, registry)
        validate_property_command(guarded[2], errors)
        self.assertTrue(any('resident memory declaration' in error for error in errors))
        self.assertTrue(any('direct top-level declaration' in error for error in errors))
        self.assertTrue(any('CXET_COMPILE_OWNER' in error for error in errors))
        for source in ('foreign', 'changed owner', 'disabled PIC'):
            text = owner.body.command.body
            if source == 'changed owner':text = text.replace('CXETCPP', 'foreign')
            if source == 'disabled PIC':text = text.replace(' ON', ' OFF')
            active = replace(owner.body, command=replace(owner.body.command, body=text),
                source_base=Path('apps/hft-parser') if source == 'foreign' else owner.body.source_base)
            errors = []
            validate_property_command(replace(owner, body=active, evaluation=active,
                token_groups=tuple((token,) for token in cmake_list_words(text))), errors)
            self.assertTrue(errors, source)

    def test_reviewed_wasm_context_preserves_all_use_paths_and_prior_emissions(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyFlow import bounded_merge
        from Family.Targets.CxetFamilyTargetRegistry import TargetDeclaration, TargetRegistry
        from Family.Targets.CxetFamilyTargetInventory import ROLE_CUSTOM
        from Family.Targets.CxetFamilyTargetPolicy import declaration_precedes
        target = 'vetron-math-wasm'
        rows = self._instances('apps/vetron/wasm/CMakeLists.txt')
        declarations = [row for row in rows if row.body.command.name == 'add_custom_target' and
                        row.token_groups[:1] == ((target,),)]
        self.assertEqual(len(declarations), 2)
        declarations = [replace(row, path_alternatives=((("wasm-owner", index),),),
                                emission_ordinal=index + 1)
                        for index, row in enumerate(declarations)]
        universe = bounded_merge([], 'WASM test use paths',
                                 *(row.path_alternatives for row in declarations))
        use = next(row for row in self._instances('apps/vetron/CMakeLists.txt')
                   if row.body.command.name == 'add_dependencies' and
                   row.token_groups[:1] == (('vetron-read-product',),))
        use = replace(use, path_alternatives=universe, emission_ordinal=1000)

        def registry(candidates, mutation=use):
            result = TargetRegistry.__new__(TargetRegistry)
            result.errors = []
            result.live_eof_paths = {use.evaluation.scope: universe}
            result.by_name = {target: [TargetDeclaration(target, 'CUSTOM', ROLE_CUSTOM,
                row, CUSTOM_TARGETS[target]) for row in candidates]}
            result.order = {id(row): index for index, row in enumerate((*candidates, mutation))}
            return result

        result = registry(declarations)
        context = result.context_for_use(target, use)
        self.assertIsNotNone(context, result.errors)
        self.assertTrue(declaration_precedes(context, use))
        self.assertEqual(context.path_alternatives, universe)
        self.assertNotEqual(declarations[0].path_alternatives, universe)
        late = replace(declarations[1], emission_ordinal=1001)
        changed = replace(declarations[1].body,
                          command=replace(declarations[1].body.command,
                                          body=declarations[1].body.command.body + ' unsafe'))
        for candidates in (declarations[:1], [declarations[0], late],
                           [declarations[0], replace(declarations[1], body=changed, evaluation=changed)]):
            with self.subTest(candidates=candidates):
                self.assertIsNone(registry(candidates).context_for_use(target, use))
        foreign = replace(use.body, scope='foreign-root')
        foreign_use = replace(use, body=foreign, evaluation=foreign)
        self.assertIsNone(registry(declarations, foreign_use).context_for_use(target, foreign_use))

    def test_optional_contract_omission_requires_actual_off_absence_and_retires_old_vetron_tests(self):
        from Family.Targets.CxetFamilyTargetRegistry import TargetRegistry
        from Family.Targets.CxetFamilyMayMustGraph import validate_direct_and_transitive_contracts
        from Family.Targets.CxetFamilyTargetInventory import (
            REQUIRED_DIRECT_LINKS, ROLE_SOURCE_EXCEPTIONS, target_spec,
        )
        for target in ('vetron-math-abi-contract-tests', 'vetron-math-parity-export'):
            self.assertNotIn(target, PRODUCTION_TARGETS)
            self.assertNotIn(target, REQUIRED_DIRECT_LINKS)
            self.assertFalse(any(key[0] == target for key in ROLE_SOURCE_EXCEPTIONS))
        self.assertIsNotNone(target_spec('vetron_offline_math', 'apps/vetron',
                                        'apps/vetron/tests/offline/CMakeLists.txt'))
        rows = [row.body for row in self._instances('apps/hft-compressor/CMakeLists.txt')]
        guard = next(row for row in rows if row.command.name == 'if' and
                     row.command.body.strip() == 'HFT_COMPRESSOR_BUILD_CLI')
        result = TargetRegistry.__new__(TargetRegistry)
        result.active_commands = rows
        result.snapshots = SimpleNamespace(values={guard.ordinal: {'HFT_COMPRESSOR_BUILD_CLI': ('OFF',)}})
        result.declarations = []
        graphs = SimpleNamespace(may={'hft_compressor_core': set()}, must={'hft_compressor_core': set()})
        origins = frozenset({'apps/hft-compressor/CMakeLists.txt', 'apps/vetron/wasm/CMakeLists.txt'})
        self.assertEqual(result.disabled_contract_targets(), frozenset({'hft-compressor'}))
        errors = []
        validate_direct_and_transitive_contracts(graphs, errors, active_origins=origins,
            disabled_contract_targets=result.disabled_contract_targets())
        self.assertEqual(errors, [])
        for selection in (('ON',), ('${unknown}',), None):
            result.snapshots.values[guard.ordinal]['HFT_COMPRESSOR_BUILD_CLI'] = selection
            self.assertEqual(result.disabled_contract_targets(), frozenset())
            errors = []
            validate_direct_and_transitive_contracts(graphs, errors, active_origins=origins,
                disabled_contract_targets=result.disabled_contract_targets())
            self.assertTrue(any('target hft-compressor:' in error for error in errors))
        result.snapshots.values[guard.ordinal]['HFT_COMPRESSOR_BUILD_CLI'] = ('OFF',)
        result.declarations = [SimpleNamespace(name='hft-compressor', alias=False)]
        self.assertEqual(result.disabled_contract_targets(), frozenset())
        graphs.may['hft-compressor'] = set()
        graphs.must['hft-compressor'] = set()
        errors = []
        validate_direct_and_transitive_contracts(graphs, errors, active_origins=origins,
            disabled_contract_targets={'hft-compressor'})
        self.assertTrue(any('disabled contract targets are still declared' in error for error in errors))
        self.assertTrue(any('target hft-compressor:' in error for error in errors))

    def test_codec_conditional_headers_require_fresh_complete_owner_recipes(self):
        from Family.Targets.CxetFamilyCompressionPolicy import compression_conditional_include
        cmake = (ROOT / 'apps/hft-compressor/CMakeLists.txt').read_bytes()
        instances = self._instances('apps/hft-compressor/CMakeLists.txt')
        for name, feature, header in (
                ('Zstd', 'ZSTD', 'zstd.h'), ('Lz4', 'LZ4', 'lz4.h'),
                ('Brotli', 'BROTLI', 'brotli/decode.h'), ('Xz', 'LZMA', 'lzma.h'),
                ('Gzip', 'ZLIB', 'zlib.h')):
            source = f'apps/hft-compressor/src/Runtime/src/Codecs/{name}JsonlBlocks/{name}JsonlBlocks.cpp'
            data = (ROOT / source).read_bytes()

            def accepts(body=data, recipe=cmake, rows=instances, target='hft_compressor_core',
                        site=source, tu=source, public=False):
                return compression_conditional_include(
                    target, site, header, tu, body, rows, recipe, public_seed=public)

            with self.subTest(codec=name):
                self.assertTrue(accepts())
                self.assertFalse(accepts(public=True))
                self.assertFalse(accepts(target='hftrec_core'))
                self.assertFalse(accepts(site=source.replace('.cpp', '.hpp')))
                self.assertFalse(accepts(tu='apps/hft-compressor/src/Api/src/Compressor.cpp'))
                self.assertFalse(accepts(rows=[]))
                guard = f'#if HFT_COMPRESSOR_WITH_{feature}\n'.encode()
                self.assertFalse(accepts(body=data.replace(guard, b'#if 1\n', 1)))
                self.assertFalse(accepts(body=f'#define HFT_COMPRESSOR_WITH_{feature} 1\n'.encode() + data))
                self.assertFalse(accepts(body=data + f'\n#include <{header}>\n'.encode()))
                for directive in (
                        b'%:include', b'%:\tinclude', b'#\vinclude\f',
                        b'%:inc\\\nlude', b'#include_next', b'%:include_next',
                        b'#import', b'%:import'):
                    with self.subTest(extra_directive=directive):
                        extra = b'\n' + directive + b' <' + header.encode() + b'>\n'
                        self.assertFalse(accepts(body=data + extra))
                self.assertFalse(accepts(recipe=cmake.replace(
                    f'set(HFT_COMPRESSOR_WITH_{feature} ON)'.encode(),
                    f'set(HFT_COMPRESSOR_WITH_{feature} OFF)'.encode())))
                self.assertFalse(accepts(recipe=cmake.replace(
                    f'HFT_COMPRESSOR_WITH_{feature}=$<BOOL:${{HFT_COMPRESSOR_WITH_{feature}}}>'.encode(),
                    f'HFT_COMPRESSOR_WITH_{feature}=1'.encode())))
                self.assertFalse(accepts(recipe=cmake.replace(
                    b'target_compile_definitions(hft_compressor_core\n    PUBLIC',
                    b'target_compile_definitions(hft_compressor_core\n    PRIVATE')))
                provider_variables = {
                    'ZSTD': ('ZSTD_LIBRARY', 'ZSTD_INCLUDE_DIR', 'ZSTD_FOUND', 'PkgConfig_FOUND'),
                    'LZ4': ('LZ4_LIBRARY', 'LZ4_INCLUDE_DIR', 'LZ4_FOUND', 'PkgConfig_FOUND'),
                    'BROTLI': ('BROTLIENC_LIBRARY', 'BROTLIDEC_LIBRARY', 'BROTLICOMMON_LIBRARY',
                               'BROTLI_INCLUDE_DIR', 'BROTLIENC_FOUND', 'BROTLIDEC_FOUND', 'PkgConfig_FOUND'),
                    'LZMA': ('LZMA_LIBRARY', 'LZMA_INCLUDE_DIR', 'LZMA_FOUND', 'PkgConfig_FOUND'),
                    'ZLIB': ('ZLIB_LIBRARY', 'ZLIB_LIBRARIES', 'ZLIB_INCLUDE_DIR', 'ZLIB_INCLUDE_DIRS', 'ZLIB_FOUND'),
                }[feature]
                for variable in (*provider_variables, 'HFT_COMPRESSOR_WITH_' + feature):
                    with self.subTest(late_output_write=variable):
                        lines = cmake.splitlines(keepends=True)
                        self.assertEqual(lines[101].strip(), b'')
                        lines[101] = f'set({variable} "")\n'.encode()
                        changed = b''.join(lines)
                        self.assertEqual(changed.count(b'\n'), cmake.count(b'\n'))
                        # Keep all original emitted bindings and line identities;
                        # fresh raw proof must reject the later output overwrite.
                        self.assertFalse(accepts(recipe=changed))
                lines = cmake.splitlines(keepends=True)
                self.assertEqual(lines[96].strip(), b'')
                self.assertEqual(lines[101].strip(), b'')
                lines[96] = b'set(_codec_prefix HFT_COMPRESSOR_WITH_)\n'
                lines[101] = ('set(${_codec_prefix}' + feature + ' ON)\n').encode()
                changed = b''.join(lines)
                self.assertEqual(changed.count(b'\n'), cmake.count(b'\n'))
                self.assertFalse(accepts(recipe=changed))
        source = 'apps/hft-compressor/src/Runtime/src/Codecs/ZstdJsonlBlocks/ZstdJsonlBlocks.cpp'
        data = (ROOT / source).read_bytes()
        for original, replacement in (
                (b'target_link_libraries(hft_compressor_core PUBLIC PkgConfig::ZSTD)',
                 b'target_link_libraries(hft_compressor_core PUBLIC Threads::Threads)'),
                (b'target_link_libraries(hft_compressor_core PUBLIC ${ZSTD_LIBRARY})',
                 b'target_link_libraries(hft_compressor_core PUBLIC)'),
                (b'target_include_directories(hft_compressor_core PUBLIC ${ZSTD_INCLUDE_DIR})',
                 b'target_include_directories(hft_compressor_core PRIVATE ${ZSTD_INCLUDE_DIR})'),
                (b'ZSTD_INCLUDE_DIR AND ZSTD_LIBRARY', b'ZSTD_INCLUDE_DIR OR ZSTD_LIBRARY')):
            with self.subTest(missing=original):
                self.assertFalse(compression_conditional_include(
                    'hft_compressor_core', source, 'zstd.h', source, data, instances,
                    cmake.replace(original, replacement), public_seed=False))

    def test_vetron_shared_roots_do_not_seed_or_grant_full_control_to_read(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import (
            canonical_api_headers, vetron_full_api_available,
        )
        gateway = 'apps/vetron/src/Gateway/include/vetron/Gateway/FullControlBridge.hpp'
        process = 'apps/vetron/src/Process/include/vetron/Process/FullVetrond.hpp'
        errors = []
        physical = compiler_visible_header_inventory(ROOT, {
            'vetron_read_gateway': ('apps/vetron/src/Gateway/include',),
            'vetron_read_process': ('apps/vetron/src/Process/include',),
        }, errors)
        concrete = {'vetron_read_gateway', 'vetron_read_process', 'vetron_full_control', 'vetron_full_process'}
        semantic = canonical_api_headers(physical, concrete, errors)
        self.assertEqual(errors, [])
        self.assertNotIn(gateway, semantic.get('vetron_read_gateway', ()))
        self.assertNotIn(process, semantic.get('vetron_read_process', ()))
        self.assertIn(gateway, semantic['vetron_full_control'])
        self.assertIn(process, semantic['vetron_full_process'])
        self.assertFalse(vetron_full_api_available(gateway, {'vetron_read_gateway'}))
        self.assertTrue(vetron_full_api_available(gateway, {'vetron_full_control'}))
        self.assertFalse(vetron_full_api_available(process, {'vetron_read_process', 'vetron_full_control'}))
        self.assertTrue(vetron_full_api_available(process, {'vetron_full_process'}))

    def test_optional_compressor_cli_requires_exact_option_guard_and_proven_off(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyCompressionPolicy import compressor_cli_disabled
        rows = [instance.body for instance in self._instances('apps/hft-compressor/CMakeLists.txt')]
        guard = next(row for row in rows if row.command.name == 'if' and
                     row.command.body.strip() == 'HFT_COMPRESSOR_BUILD_CLI')
        snapshots = SimpleNamespace(values={guard.ordinal: {'HFT_COMPRESSOR_BUILD_CLI': ('OFF',)}})
        self.assertTrue(compressor_cli_disabled(rows, snapshots))
        for selection in (('ON',), ('OFF', 'ON'), ('${unknown}',), None):
            snapshots.values[guard.ordinal]['HFT_COMPRESSOR_BUILD_CLI'] = selection
            self.assertFalse(compressor_cli_disabled(rows, snapshots))
        snapshots.values[guard.ordinal]['HFT_COMPRESSOR_BUILD_CLI'] = ('OFF',)
        self.assertFalse(compressor_cli_disabled([row for row in rows
            if row.command.name != 'option'], snapshots))
        self.assertFalse(compressor_cli_disabled([replace(row, source_base=Path('apps/trader'))
            for row in rows], snapshots))
        self.assertFalse(compressor_cli_disabled(None, snapshots))

    def test_recorder_full_runtime_omission_requires_exact_offline_return(self):
        from Family.Targets.CxetFamilyCompressionPolicy import recorder_full_runtime_disabled
        rows = [instance.body for instance in self._instances('apps/hft-recorder/src/Runtime/CMakeLists.txt')]
        guard = next(row for row in rows if row.command.name == 'if' and
                     row.command.body.strip() == 'CXET_LOCAL_TESTS')
        snapshots = SimpleNamespace(values={guard.ordinal: {'CXET_LOCAL_TESTS': ('ON',)}})
        self.assertTrue(recorder_full_runtime_disabled(rows, snapshots))
        snapshots.values[guard.ordinal]['CXET_LOCAL_TESTS'] = ('OFF',)
        self.assertFalse(recorder_full_runtime_disabled(rows, snapshots))
        snapshots.values[guard.ordinal]['CXET_LOCAL_TESTS'] = ('ON',)
        self.assertFalse(recorder_full_runtime_disabled([row for row in rows
            if row.command.name != 'return'], snapshots))

    def test_parent_attachments_are_exact_tus_and_cannot_borrow_another_target(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyOwnershipPolicy import reviewed_recorder_parent_source
        runtime = self._instances('apps/hft-recorder/src/Runtime/CMakeLists.txt')
        contracts = self._instances('apps/hft-recorder/src/Contracts/CMakeLists.txt')
        cases = (
            ('hftrec_json_capture', runtime,
             'apps/hft-recorder/src/Process/src/Finam/FinamEnvSync.cpp'),
            ('hftrec_core', runtime,
             'apps/hft-recorder/src/Lab/src/Arbitrage/BookTickerSpread.cpp'),
            ('hftrec_capture_launch', contracts,
             'apps/hft-recorder/src/Runtime/src/Capture/Coordinator/RecorderCaptureSelection.cpp'),
            ('hftrec_capture_client', contracts,
             'apps/hft-recorder/src/Runtime/src/Capture/Parser/ParserMarketCaptureClient.cpp'),
        )
        for target, rows, source in cases:
            with self.subTest(target=target):
                row = next(row for row in rows if row.body.command.name == 'add_library' and
                           row.token_groups[0] == (target,))
                self.assertTrue(reviewed_recorder_parent_source(target, row, source))
                self.assertFalse(reviewed_recorder_parent_source(target, row, source + '.unreviewed.cpp'))
                self.assertFalse(reviewed_recorder_parent_source(target, replace(row,
                    evaluation=replace(row.evaluation, source_base=Path('apps/trader'))), source))
        json = next(row for row in runtime if row.token_groups[:1] == (('hftrec_json_capture',),))
        self.assertFalse(reviewed_recorder_parent_source('hftrec_core', json,
            'apps/hft-recorder/src/Lab/src/Arbitrage/BookTickerSpread.cpp'))

    def test_probe_external_headers_require_their_exact_capability(self):
        from Family.Sources.CxetFamilyIncludeReachability import _scoped_external_include
        for header, capability in (("nghttp2/nghttp2.h", "PkgConfig::NGHTTP2"),
                                   ("boost/json/value.hpp", "Boost::json"),
                                   ("boost/asio/ip/tcp.hpp", "Boost::json")):
            with self.subTest(header=header):
                self.assertTrue(_scoped_external_include(header, frozenset({capability})))
                self.assertFalse(_scoped_external_include(header, frozenset()))
        self.assertFalse(_scoped_external_include("boost/unreviewed.hpp", frozenset({"Boost::json"})))
        self.assertFalse(_scoped_external_include("nghttp2/unreviewed.h", frozenset({"PkgConfig::NGHTTP2"})))

    def test_compression_fallbacks_keep_exact_context_and_typed_capabilities(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyCompressionPolicy import (
            compression_link_values, compression_include_provider, compression_external_link,
            family_external_link, compression_compile_definitions,
        )
        from Family.Sources.CxetFamilyIncludeReachability import _scoped_external_include
        rows = self._instances('apps/hft-compressor/CMakeLists.txt')
        definitions = next(row for row in rows if row.body.command.line == 158)
        from CMake.Flow.CmakeFamilyState import UNCERTAIN_BRANCH_ALTERNATIVE
        names = tuple('HFT_COMPRESSOR_WITH_' + feature for feature in ('ZSTD', 'LZ4', 'BROTLI', 'LZMA', 'ZLIB'))
        baseline = [name + '=$<BOOL:ON>' for name in names]
        alternatives = [name + '=$<BOOL:' + value + '>' for name in names
                        for value in ('ON', 'OFF', UNCERTAIN_BRANCH_ALTERNATIVE)]
        self.assertTrue(compression_compile_definitions(definitions, 'hft_compressor_core', baseline))
        self.assertTrue(compression_compile_definitions(definitions, 'hft_compressor_core', alternatives))
        self.assertFalse(compression_compile_definitions(definitions, 'hftrec_core', alternatives))
        for marker in ('$<foreign>', '$<CXET_INTERNAL_UNCERTAIN_EMPTY>', '${OTHER_FLAG}'):
            changed = [*baseline[1:], names[0] + '=$<BOOL:' + marker + '>']
            self.assertFalse(compression_compile_definitions(definitions, 'hft_compressor_core', changed))
        self.assertFalse(compression_compile_definitions(definitions, 'hft_compressor_core', alternatives + [alternatives[0]]))
        changed = [*baseline[1:], 'HFT_COMPRESSOR_WITH_FOREIGN=$<BOOL:' + UNCERTAIN_BRANCH_ALTERNATIVE + '>']
        self.assertFalse(compression_compile_definitions(definitions, 'hft_compressor_core', changed))
        original_read_bytes = Path.read_bytes
        recipe_path = ROOT / 'apps/hft-compressor/CMakeLists.txt'
        recipe_bytes = recipe_path.read_bytes()
        with patch.object(Path, 'read_bytes', new=lambda path:
                recipe_bytes + b'\nset(HFT_COMPRESSOR_WITH_ZSTD ON)\n' if path == recipe_path else original_read_bytes(path)):
            self.assertFalse(compression_compile_definitions(definitions, 'hft_compressor_core', alternatives))
        link = next(row for row in rows if row.body.command.line == 173)
        raw = ['PUBLIC', '${ZSTD_LIBRARY}']
        self.assertEqual(compression_link_values(link, raw), ['PUBLIC', 'zstd'])
        self.assertTrue(compression_external_link(link, 'hft_compressor_core', 'zstd'))
        self.assertFalse(compression_external_link(link, 'hftrec_core', 'zstd'))
        changed = replace(link.body, structural_context=())
        unguarded = replace(link, body=changed, evaluation=changed)
        self.assertEqual(compression_link_values(unguarded, raw), raw)
        self.assertEqual(compression_link_values(link, ['PUBLIC', '/tmp/foreign.a']),
                         ['PUBLIC', '/tmp/foreign.a'])
        include = next(row for row in rows if row.body.command.line == 172)
        self.assertEqual(compression_include_provider(include, 'hft_compressor_core',
            'PUBLIC', '${ZSTD_INCLUDE_DIR}'), 'zstd')
        self.assertIsNone(compression_include_provider(include, 'hft_compressor_core',
            'PRIVATE', '${ZSTD_INCLUDE_DIR}'))
        self.assertIsNone(compression_include_provider(include, 'hft_compressor_core',
            'PUBLIC', '/tmp/project-shadow'))
        self.assertTrue(_scoped_external_include('zstd.h', {'zstd'}))
        self.assertFalse(_scoped_external_include('zstd.h', set()))
        self.assertFalse(_scoped_external_include('zstd.h', {'PkgConfig::Unknown'}))
        corpus = next(row for row in self._instances('apps/hft-recorder/src/Contracts/CMakeLists.txt')
            if row.body.command.name == 'target_link_libraries' and
               row.token_groups[0] == ('hftrec_corpus_contract',))
        self.assertTrue(family_external_link(corpus, 'hftrec_corpus_contract', 'Threads::Threads'))
        self.assertFalse(family_external_link(corpus, 'hftrec_corpus_contract', 'ZLIB::ZLIB'))

    def test_recorder_implementation_roots_do_not_expand_foreign_corpus_access(self):
        source = 'apps/hft-recorder/src/Runtime/src/Capture/Coordinator/CaptureCoordinator.cpp'
        api = 'apps/hft-recorder/src/Runtime/include/hftrec/RecorderApi.hpp'
        foreign = 'apps/hft-backtest/src/Runtime/src/Run/Backtest.cpp'
        corpus = 'apps/hft-recorder/src/Contracts/include/hftrec/Status.hpp'
        self.assertTrue(verification_include_allowed(source, api))
        self.assertTrue(verification_include_allowed(foreign, corpus))
        self.assertFalse(verification_include_allowed(foreign, api))
        self.assertTrue(verification_include_allowed(
            'apps/hft-compressor/src/Api/src/Compressor.cpp',
            'apps/hft-compressor/src/Api/include/hft_compressor/Compressor.hpp'))

    def test_recorder_current_targets_aliases_and_twenty_json_sources_stay_exact(self):
        from Family.Targets.CxetFamilyAliasPolicy import EXACT_ALIASES
        from Family.Targets.CxetFamilyOwnershipPolicy import CANONICAL_EXACT_SOURCE_ATTACHMENTS
        rows = self._instances('apps/hft-recorder/src/Runtime/CMakeLists.txt')
        for name, kind in (('hftrec_core', 'STATIC'), ('hftrec_recorder_api', 'INTERFACE'),
                           ('hftrec_json_capture', 'OBJECT')):
            self.assertEqual(PRODUCTION_TARGETS[name].kind, kind)
            self.assertEqual(PRODUCTION_TARGETS[name].owner,
                             'apps/hft-recorder/src/Runtime/CMakeLists.txt')
        for alias, target in (('hftrec::core', 'hftrec_core'),
                              ('hftrec::recorder_api', 'hftrec_recorder_api'),
                              ('hftrec::capture_launch', 'hftrec_capture_launch'),
                              ('hftrec::capture_client', 'hftrec_capture_client'),
                              ('hft_compressor::core', 'hft_compressor_core')):
            self.assertEqual(EXACT_ALIASES[alias], target)
        declaration = next(row for row in rows if row.body.command.name == 'add_library' and
                           row.token_groups[0] == ('hftrec_json_capture',))
        actual = frozenset((ROOT / 'apps/hft-recorder/src/Runtime' / group[0]).resolve()
                           .relative_to(ROOT).as_posix() for group in declaration.token_groups[2:])
        self.assertEqual(len(actual), 20)
        self.assertEqual(actual, CANONICAL_EXACT_SOURCE_ATTACHMENTS['hftrec_json_capture'])


if __name__ == '__main__':
    unittest.main()
