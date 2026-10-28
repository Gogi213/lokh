"""Exact root-composed Compressor options and external provider recipes."""

from pathlib import Path
import hashlib
import re

from CMake.Syntax.CmakeFamilyContext import exact_context, first_if, alternate_if
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words


COMPRESSOR_CMAKE = 'apps/hft-compressor/CMakeLists.txt'
# This complete configure recipe is the closed feature => provider authority.
# Partial command matching cannot prove absence of later direct or computed
# writes to discovery outputs. Read through IncludeInputs and revalidate at
# end of proof; a changed recipe requires review rather than a new allowance.
_COMPRESSOR_RECIPE_SHA256 = 'd325f35497f83036d9d92ae9f8fc66c0feec500c27ba7c76e12ac61b4ca43dc2'


def compressor_context(instance):
    return (instance.body.relative == COMPRESSOR_CMAKE and
            instance.evaluation.source_base == Path('apps/hft-compressor') and
            instance.evaluation.binary_base == Path('apps/hft-compressor'))


def compressor_cli_disabled(active_commands, snapshots):
    """Absence is valid only for the current canonical option's proven OFF arm."""
    if snapshots is None or active_commands is None:
        return False
    local = [active for active in active_commands
             if active.relative == COMPRESSOR_CMAKE and
             active.source_base == Path('apps/hft-compressor') and
             active.binary_base == Path('apps/hft-compressor')]
    options = [active for active in local if active.command.name == 'option' and
        tuple(cmake_list_words(active.command.body)) == (
            'HFT_COMPRESSOR_BUILD_CLI', 'Build hft-compressor CLI',
            '${_HFT_COMPRESSOR_BUILD_TOOLS_DEFAULT}') and
        active.command.line == 31 and exact_context(active.structural_context, ())]
    guards = [active for active in local if active.command.name == 'if' and
        tuple(cmake_list_words(active.command.body)) == ('HFT_COMPRESSOR_BUILD_CLI',) and
        active.command.line == 211 and exact_context(active.structural_context, ())]
    declarations = [active for active in local if active.command.name == 'add_executable' and
        tuple(cmake_list_words(active.command.body)) == ('hft-compressor', 'src/Process/Main.cpp') and
        exact_context(active.structural_context, (
            first_if(COMPRESSOR_CMAKE, 211, ('HFT_COMPRESSOR_BUILD_CLI',)),))]
    if len(options) != 1 or len(guards) != 1 or len(declarations) != 1:
        return False
    return snapshots.values.get(guards[0].ordinal, {}).get(
        'HFT_COMPRESSOR_BUILD_CLI') == ('OFF',)


def recorder_full_runtime_disabled(active_commands, snapshots):
    """The exact offline-only return omits Full Recorder owners, not JSON capture."""
    if active_commands is None or snapshots is None:
        return False
    relative = 'apps/hft-recorder/src/Runtime/CMakeLists.txt'
    base = Path(relative).parent
    local = [active for active in active_commands if active.relative == relative and
             active.source_base == base and active.binary_base == base]
    guards = [active for active in local if active.command.name == 'if' and
        active.command.line == 40 and cmake_list_words(active.command.body) == ['CXET_LOCAL_TESTS']]
    returns = [active for active in local if active.command.name == 'return' and
        active.command.line == 42 and not cmake_list_words(active.command.body) and
        exact_context(active.structural_context, (first_if(relative, 40, ('CXET_LOCAL_TESTS',)),))]
    declarations = {tuple(cmake_list_words(active.command.body)) for active in local
                    if active.command.name == 'add_library' and
                    exact_context(active.structural_context, ())}
    return (len(guards) == 1 and len(returns) == 1 and
        ('hftrec_core', 'STATIC', '${HFTREC_CORE_SOURCES}') in declarations and
        ('hftrec_recorder_api', 'INTERFACE') in declarations and
        snapshots.values.get(guards[0].ordinal, {}).get('CXET_LOCAL_TESTS') == ('ON',))


def _codec_context(line, feature, package_tokens):
    return (alternate_if(COMPRESSOR_CMAKE, line, package_tokens,
                         ('HFT_COMPRESSOR_WITH_' + feature,)),)


_ZSTD = ('TARGET', 'PkgConfig::ZSTD')
_LZ4 = ('TARGET', 'PkgConfig::LZ4')
_BROTLI = ('TARGET', 'PkgConfig::BROTLIENC', 'AND', 'TARGET', 'PkgConfig::BROTLIDEC')
_LZMA = ('TARGET', 'PkgConfig::LZMA')
_LINK_RECIPES = {
    170: (('PkgConfig::ZSTD',), ('PkgConfig::ZSTD',), (first_if(COMPRESSOR_CMAKE, 169, _ZSTD),)),
    173: (('${ZSTD_LIBRARY}',), ('zstd',), _codec_context(169, 'ZSTD', _ZSTD)),
    184: (('PkgConfig::LZ4',), ('PkgConfig::LZ4',), (first_if(COMPRESSOR_CMAKE, 183, _LZ4),)),
    187: (('${LZ4_LIBRARY}',), ('lz4',), _codec_context(183, 'LZ4', _LZ4)),
    191: (('PkgConfig::BROTLIENC', 'PkgConfig::BROTLIDEC'),
          ('PkgConfig::BROTLIENC', 'PkgConfig::BROTLIDEC'),
          (first_if(COMPRESSOR_CMAKE, 190, _BROTLI),)),
    194: (('${BROTLIENC_LIBRARY}', '${BROTLIDEC_LIBRARY}'),
          ('brotlienc', 'brotlidec'), _codec_context(190, 'BROTLI', _BROTLI)),
    196: (('${BROTLICOMMON_LIBRARY}',), ('brotlicommon',),
          (*_codec_context(190, 'BROTLI', _BROTLI),
           first_if(COMPRESSOR_CMAKE, 195, ('BROTLICOMMON_LIBRARY',)))),
    201: (('PkgConfig::LZMA',), ('PkgConfig::LZMA',), (first_if(COMPRESSOR_CMAKE, 200, _LZMA),)),
    204: (('${LZMA_LIBRARY}',), ('lzma',), _codec_context(200, 'LZMA', _LZMA)),
    208: (('ZLIB::ZLIB',), ('ZLIB::ZLIB',),
          (first_if(COMPRESSOR_CMAKE, 207, ('HFT_COMPRESSOR_WITH_ZLIB',)),)),
}
_INCLUDE_RECIPES = {
    172: ('${ZSTD_INCLUDE_DIR}', 'zstd', _codec_context(169, 'ZSTD', _ZSTD)),
    186: ('${LZ4_INCLUDE_DIR}', 'lz4', _codec_context(183, 'LZ4', _LZ4)),
    193: ('${BROTLI_INCLUDE_DIR}', 'brotlienc', _codec_context(190, 'BROTLI', _BROTLI)),
    203: ('${LZMA_INCLUDE_DIR}', 'lzma', _codec_context(200, 'LZMA', _LZMA)),
}
COMPRESSION_EXTERNAL_LEAVES = frozenset({
    'PkgConfig::ZSTD', 'PkgConfig::LZ4', 'PkgConfig::BROTLIENC',
    'PkgConfig::BROTLIDEC', 'PkgConfig::LZMA', 'ZLIB::ZLIB',
    'zstd', 'lz4', 'brotlienc', 'brotlidec', 'brotlicommon', 'lzma',
})
COMPRESSION_HEADER_PROVIDERS = {
    'zstd.h': frozenset({'PkgConfig::ZSTD', 'zstd'}),
    'lz4.h': frozenset({'PkgConfig::LZ4', 'lz4'}),
    'brotli/encode.h': frozenset({'PkgConfig::BROTLIENC', 'brotlienc'}),
    'brotli/decode.h': frozenset({'PkgConfig::BROTLIDEC', 'brotlidec'}),
    'lzma.h': frozenset({'PkgConfig::LZMA', 'lzma'}),
    'zlib.h': frozenset({'ZLIB::ZLIB'}),
}


def _recipe_context(instance, command, raw, context):
    return (compressor_context(instance) and instance.body.command.name == command and
            tuple(cmake_list_words(instance.body.command.body)) == raw and
            exact_context(instance.body.structural_context, context) and
            exact_context(instance.evaluation.structural_context, context))


def compression_link_values(instance, values):
    """Retain discovery placeholders as typed leaves, never as invented paths."""
    recipe = _LINK_RECIPES.get(instance.body.command.line)
    if recipe is None:
        return values
    raw, leaves, context = recipe
    if (tuple(values) == ('PUBLIC', *raw) and _recipe_context(instance,
            'target_link_libraries', ('hft_compressor_core', 'PUBLIC', *raw), context)):
        return ['PUBLIC', *leaves]
    return values


def compression_include_provider(instance, target, scope, value):
    recipe = _INCLUDE_RECIPES.get(instance.body.command.line)
    if recipe is None:
        return None
    raw, provider, context = recipe
    return provider if (target == 'hft_compressor_core' and scope == 'PUBLIC' and
        value == raw and _recipe_context(instance, 'target_include_directories',
            (target, 'PUBLIC', raw), context)) else None


def compression_external_link(instance, target, dependency):
    recipe = _LINK_RECIPES.get(instance.body.command.line)
    if target != 'hft_compressor_core' or recipe is None:
        return False
    raw, leaves, context = recipe
    return dependency in leaves and _recipe_context(instance, 'target_link_libraries',
        (target, 'PUBLIC', *raw), context)


_CODEC_FEATURES = {
    'Zstd': ('ZSTD', ('zstd.h',)),
    'Lz4': ('LZ4', ('lz4.h',)),
    'Brotli': ('BROTLI', ('brotli/decode.h', 'brotli/encode.h')),
    'Xz': ('LZMA', ('lzma.h',)),
    'Gzip': ('ZLIB', ('zlib.h',)),
}
_CODEC_SOURCES = {
    f'apps/hft-compressor/src/Runtime/src/Codecs/{name}JsonlBlocks/{name}JsonlBlocks.cpp': value
    for name, value in _CODEC_FEATURES.items()
}
_CODEC_DEFINITIONS = (
    'hft_compressor_core', 'PUBLIC',
    *(f'HFT_COMPRESSOR_WITH_{feature}=$<BOOL:${{HFT_COMPRESSOR_WITH_{feature}}}>'
      for feature in ('ZSTD', 'LZ4', 'BROTLI', 'LZMA', 'ZLIB')),
    'PRIVATE', 'HFT_COMPRESSOR_BUILDING_LIBRARY',
)


def compression_translation_unit_context(target, translation_unit):
    return translation_unit if target == 'hft_compressor_core' and translation_unit in _CODEC_SOURCES else None


def compression_compile_definitions(instance, target, values):
    """Only the owner's five public BOOL facts are opaque definition carriers."""
    expected_names = {'HFT_COMPRESSOR_WITH_' + feature for feature in ('ZSTD', 'LZ4', 'BROTLI', 'LZMA', 'ZLIB')}
    if (target != 'hft_compressor_core' or instance.body != instance.evaluation or
            instance.body.source_base != Path('apps/hft-compressor') or
            not _recipe_context(instance, 'target_compile_definitions', _CODEC_DEFINITIONS, ())):
        return False
    # The complete recipe, including absence of later output writers, remains
    # the authority. An unresolved BOOL carrier is never a true feature fact.
    from CMake.Flow.CmakeFamilyExecutionIdentity import ROOT, unsymlinked_regular_path
    recipe = ROOT / COMPRESSOR_CMAKE
    try:
        if (not unsymlinked_regular_path(recipe, ROOT) or
                hashlib.sha256(recipe.read_bytes()).hexdigest() != _COMPRESSOR_RECIPE_SHA256):
            return False
    except OSError:
        return False
    names = [value.split('=', 1)[0] for value in values]
    if (not 5 <= len(values) <= 15 or len(values) != len(set(values)) or set(names) != expected_names or
            any(not 1 <= names.count(name) <= 3 for name in expected_names)):
        return False
    from CMake.Flow.CmakeFamilyState import UNCERTAIN_BRANCH_ALTERNATIVE
    for value in values:
        name = value.split('=', 1)[0]
        allowed = {'ON', 'OFF', '0', '1', '$<CXET_UNKNOWN_SOURCE_PROFILE>',
                   UNCERTAIN_BRANCH_ALTERNATIVE, '${' + name + '}'}
        if value not in {name + '=$<BOOL:' + payload + '>' for payload in allowed}:
            return False
    return True


def compression_feature_mutation(target, translation_unit, data, *, public_seed):
    """A codec's imported feature facts cannot be rewritten in its include closure."""
    if public_seed or target != 'hft_compressor_core' or translation_unit not in _CODEC_SOURCES:
        return False
    from Family.Sources.CxetFamilyCppPolicy import cpp_phase_two, _directive_view
    directives = _directive_view(cpp_phase_two(data))
    return re.search(rb'(?m)^\s*(?:#|%:)\s*(?:define|undef)\s+HFT_COMPRESSOR_WITH_\w+\b',
                     directives) is not None


def compression_conditional_include(target, source, include, translation_unit, data,
                                    instances, cmake_data, *, public_seed):
    """Prove feature => provider for five original codec TUs, never export a capability.

    The configure may discover no codec at all. Its only accepted positive
    include arm is nevertheless safe when the fresh, complete canonical
    discovery/definition/provider recipes guarantee that same feature.
    """
    codec = _CODEC_SOURCES.get(source)
    if (public_seed or target != 'hft_compressor_core' or source != translation_unit or
            codec is None or include not in codec[1]):
        return False
    if hashlib.sha256(cmake_data).hexdigest() != _COMPRESSOR_RECIPE_SHA256:
        return False
    feature, headers = codec
    from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax, _directive_view
    normalized, records, syntax_failures = cpp_include_syntax(data)
    if syntax_failures:
        return False
    directives = _directive_view(normalized)
    if compression_feature_mutation(target, translation_unit, data, public_seed=False):
        return False
    # Pin the whole top-level positive block, including every external header.
    block = (rb'(?m)^\s*#\s*if\s+HFT_COMPRESSOR_WITH_' + feature.encode() + rb'\s*\n' +
             b''.join(rb'[ \t]*#\s*include\s*<' + re.escape(header.encode()) + rb'>[ \t]*\n'
                      for header in headers) + rb'[ \t]*#\s*endif\b[^\n]*')
    matches = list(re.finditer(block, directives))
    if len(matches) != 1:
        return False
    # The canonical lexer counts every admitted spelling, including %: and
    # phase-two splices. A second unguarded include cannot borrow this block.
    for header in headers:
        uses = [quoted for spelling, quoted in records if spelling == header.encode()]
        if uses != [False]:
            return False
    definitions = [instance for instance in instances
                   if instance.body.command.name == 'target_compile_definitions' and
                   instance.token_groups and tuple(instance.token_groups[0]) == ('hft_compressor_core',) and
                   'HFT_COMPRESSOR_WITH_' in instance.body.command.body]
    if (len(definitions) != 1 or not _recipe_context(definitions[0], 'target_compile_definitions',
            _CODEC_DEFINITIONS, ()) or definitions[0].body != definitions[0].evaluation or
            definitions[0].body.command.line != 158):
        return False
    return True


_FAMILY_EXTERNAL_RECIPES = {
    ('hft_compressor_core', COMPRESSOR_CMAKE): (
        'hft_compressor_core', 'PUBLIC', 'Threads::Threads'),
    ('hftrec_corpus_contract', 'apps/hft-recorder/src/Contracts/CMakeLists.txt'): (
        'hftrec_corpus_contract', 'PRIVATE', 'hft_compressor::core', 'Threads::Threads'),
    ('hftrec_json_capture', 'apps/hft-recorder/src/Runtime/CMakeLists.txt'): (
        'hftrec_json_capture', 'PUBLIC', 'hftrec::corpus_contract', 'cxet::cxet_lib',
        'Threads::Threads', 'absl::flat_hash_map'),
    ('hftrec_core', 'apps/hft-recorder/src/Runtime/CMakeLists.txt'): (
        'hftrec_core', 'PUBLIC', 'hftrec_json_capture', 'hftrec::corpus_contract',
        'hftrec::capture_launch', 'hftrec::capture_client', 'hftp_client_headers',
        'cxet::cxet_lib', 'Threads::Threads', 'absl::flat_hash_map', 'ZLIB::ZLIB'),
}


def family_external_link(instance, target, dependency):
    raw = _FAMILY_EXTERNAL_RECIPES.get((target, instance.body.relative))
    return bool(raw and dependency in {'Threads::Threads', 'absl::flat_hash_map', 'ZLIB::ZLIB'} and
        dependency in raw and instance.body.command.name == 'target_link_libraries' and
        tuple(cmake_list_words(instance.body.command.body)) == raw and
        instance.evaluation.source_base == Path(instance.body.relative).parent and
        instance.evaluation.binary_base == Path(instance.body.relative).parent and
        exact_context(instance.body.structural_context, ()) and
        exact_context(instance.evaluation.structural_context, ()))
