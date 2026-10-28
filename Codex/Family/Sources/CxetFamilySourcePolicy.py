"""Typed source exceptions for the CXET canonical ownership checker."""

from __future__ import annotations

from pathlib import Path
import re

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from CMake.Flow.CmakeFamilyGraph import ActiveCommand, InstantiatedCommand
from CMake.Policy.CmakeFamilyStrategyPolicy import proven_strategy_names
from Family.Targets.CxetFamilyOwnershipPolicy import CANONICAL_EVALUATION_ROOTS
from Family.Targets.CxetFamilyBuildPolicy import BENCHMARK_INCLUDE_CONTRACTS


_BENCH_PRIVATE_INCLUDE_EDGES = frozenset({
    ("src/benchmarks/GrpcTransportCases.cpp", "src/src/Core/src/Network/Grpc/Private/GrpcClientInternal.hpp"),
    ("tools/Benchmarks/native/LoopbackTls.hpp", "src/src/Core/src/Network/Tls/SocketState.hpp"),
    ("tools/Benchmarks/native/LoopbackTls.hpp", "src/src/Core/src/Network/Grpc/Private/NativeGrpcTlsState.hpp"),
    ("tools/Benchmarks/native/NativeFixPeer.hpp", "src/src/Core/src/Api/User/Common/NativeAccountWriterLeaseInternal.hpp"),
    ("apps/trader/benchmarks/VstackPeer.cpp", "src/src/Core/src/Network/Grpc/Private/GrpcClientInternal.hpp"),
    ("apps/trader/benchmarks/VstackFleetFixture.cpp", "apps/hft-parser/src/Runtime/src/Market/Ingestion/Detail/Publication/PublicMarketPublicationDirectory.hpp"),
})
_BENCH_ORDER_PRIVATE_INCLUDE_EDGES = frozenset({
    ("parser-bench-native-fix", "tools/Benchmarks/native/NativeFixPeer.hpp",
     "apps/hft-parser/benchmarks/NativeFix.cpp"),
    ("trader-bench-native-lane", "tools/Benchmarks/native/NativeFixPeer.hpp",
     "apps/trader/benchmarks/NativeLane.cpp"),
    ("trader-bench-capacity", "tools/Benchmarks/native/NativeFixPeer.hpp",
     "apps/trader/benchmarks/Capacity.cpp"),
    ("trader-bench-vstack", "apps/trader/benchmarks/VstackPeerOrder.cpp",
     "apps/trader/benchmarks/VstackPeerOrder.cpp"),
    ("trader-bench-json-ws", "apps/trader/benchmarks/JsonWsNativePeer.hpp",
     "apps/trader/benchmarks/JsonWs.cpp"),
})
_BENCH_SHARED = "tools/Benchmarks/native/"
_BENCH_PARSER_FIXTURE = "apps/hft-parser/benchmarks/NativeFixFixture.hpp"
_BENCH_TRADER_FIXTURE = "apps/trader/tests/offline/Support/NativeLaneFixture.hpp"
_BENCH_JSON_FIXTURES = frozenset({
    "src/benchmarks/WsBenchmarkPeer.hpp", "src/benchmarks/WsBenchmarkFixture.hpp",
    "src/benchmarks/MarketFixture.hpp", "src/benchmarks/Cases.hpp",
})


def benchmark_translation_unit_context(target: str, translation_unit: str | None) -> str | None:
    """The complete finite TU distinction used by diagnostic include seams."""
    contract = BENCHMARK_INCLUDE_CONTRACTS.get(target)
    if contract is None or translation_unit is None:
        return None
    if translation_unit.startswith(Path(contract[0]).parent.as_posix() + "/"):
        return "owner"
    if target.endswith("_traced") and translation_unit == _BENCH_SHARED + "SendTrace.cpp":
        return "trace"
    return None


def benchmark_external_include(target: str, source: str, include: str,
                               translation_unit: str | None) -> bool:
    return (target in {"trader-bench-vstack", "trader-bench-vstack_traced"} and
            benchmark_translation_unit_context(target, translation_unit) == "owner" and
            (source, include) in {
                ("apps/trader/benchmarks/VstackPeer.cpp", "source_location"),
                ("apps/trader/benchmarks/VstackLoad.cpp", "execinfo.h"),
            })


def benchmark_backend_include_edge(target: str, selected: str) -> bool:
    contract = BENCHMARK_INCLUDE_CONTRACTS.get(target)
    return bool(contract and any(
        root in {"apps/hft-parser/src/Runtime/include", "apps/hft-parser/src/Process/include"} and
        selected.startswith(root + "/") for root in contract[1]))


def benchmark_include_edge(target: str, source: str, selected: str,
                           translation_unit: str | None) -> bool:
    """Private diagnostic seams, scoped to a finite benchmark and its TU.

    Compiler reachability still requires the concrete declared include roots;
    ordinary exported headers still require their canonical linked provider.
    """
    contract = BENCHMARK_INCLUDE_CONTRACTS.get(target)
    if contract is None or benchmark_translation_unit_context(target, translation_unit) is None:
        return False
    origin, roots = contract
    source_root = Path(origin).parent.as_posix() + "/"
    json_fixture_context = (target.removesuffix("_traced") == "trader-bench-json-ws" and
                            translation_unit == "apps/trader/benchmarks/JsonWs.cpp")
    diagnostic_source = (source.startswith(source_root) or source.startswith(_BENCH_SHARED) or
                         source in {_BENCH_PARSER_FIXTURE, _BENCH_TRADER_FIXTURE} or
                         json_fixture_context and source in _BENCH_JSON_FIXTURES or
                         benchmark_backend_include_edge(target, source))
    if not diagnostic_source:
        return False
    if (selected == "src/src/Core/src/Api/Order/OrderSessionPoolInternal.hpp" and
            (target.removesuffix("_traced"), source, translation_unit) in _BENCH_ORDER_PRIVATE_INCLUDE_EDGES):
        return True
    if (source, selected) in _BENCH_PRIVATE_INCLUDE_EDGES:
        return True
    if json_fixture_context:
        if selected in _BENCH_JSON_FIXTURES:
            return True
        if (source == "apps/trader/benchmarks/JsonWsNativePeer.hpp" and
                selected == "src/src/Core/src/Api/User/Common/NativeAccountWriterLeaseInternal.hpp"):
            return True
        if source in _BENCH_JSON_FIXTURES and selected.startswith((
                "src/src/Core/include/", "src/src/Contracts/include/")):
            return True
    if selected.startswith(_BENCH_SHARED):
        return True
    if selected == "tools/Testing/OfflineCase.hpp" and "tools/Testing" in roots:
        return True
    if (origin == "apps/trader/benchmarks/CMakeLists.txt" and
            selected in {_BENCH_PARSER_FIXTURE, _BENCH_TRADER_FIXTURE}):
        return True
    if benchmark_backend_include_edge(target, selected):
        return True
    if source.startswith(_BENCH_SHARED):
        return selected.startswith((
            "src/src/Core/include/", "src/src/Contracts/include/",
            "apps/trading-core/src/Core/include/", "apps/trading-core/src/Contracts/include/",
            "apps/trading-core/src/Strategy/include/"))
    return False


def canonical_evaluation_context(target: str, active: ActiveCommand) -> bool:
    expected = CANONICAL_EVALUATION_ROOTS.get(target)
    if expected is None:
        return False
    expected_path = Path(expected)
    return (
        active.source_base == expected_path and
        active.binary_base == expected_path
    )


def typed_generated_source(
    target: str,
    active: ActiveCommand,
    token: str,
) -> bool:
    from CMake.Flow.CmakeFamilyGraph import active_binary_dir

    if target == "cxet_tls_certificates":
        return (active.relative == "src/src/CMakeLists.txt" and
                active.source_base == Path("src/src") and
                active.binary_base == Path("src/src") and
                token == active_binary_dir(active) +
                "/generated/mbedtls-cold/x509.c")
    if (not canonical_evaluation_context(target, active) or
            any(marker in token for marker in (
                "${", "$ENV{", "$CACHE{", "$<"))):
        return False
    if target != "trading_core_strategy":
        return False
    prefix = (
        active_binary_dir(active) +
        "/generated/trading_core/Strategy/"
    )
    if not token.startswith(prefix):
        return False
    relative = token[len(prefix):]
    if relative in {
            "GeneratedStrategyRegistry.hpp",
            "GeneratedStrategyRegistry.cpp"}:
        return True
    return any(
        relative == f"GeneratedStrategyRegistry_{name}.cpp"
        for name in proven_strategy_names()
    )


def approved_external_source_mutation(
    instance: InstantiatedCommand,
    target: str,
    value: str,
) -> bool:
    # External targets may not receive first-party source mutations. Native
    # vendor compilation belongs to explicit project-owned crypto libraries.
    return False


# Exact native source authorities. Vendor roots never become general product
# roots; only these project-owned targets compile the named upstream units.
_HACL = "extra/hacl-star/dist/gcc-compatible"
_MBED = "extra/mbedtls-cold"
NATIVE_CRYPTO_IMPORT_MODULES = (
        "asn1parse", "asn1write", "base64", "bignum", "bignum_core", "bignum_mod",
        "bignum_mod_raw", "constant_time", "ecp", "ecp_curves", "ecdsa", "md", "oid",
        "pem", "pk", "pk_ecc", "pk_wrap", "pkparse", "platform_util", "rsa",
        "rsa_alt_helpers", "sha1", "sha256", "sha512")
NATIVE_CRYPTO_VENDOR_SOURCES = {
    "cxet_crypto": frozenset({
        *(_HACL + "/" + name for name in (
            "Hacl_AEAD_Chacha20Poly1305_Simd128.c", "Hacl_Chacha20_Vec128.c",
            "Hacl_Chacha20.c", "Hacl_MAC_Poly1305_Simd128.c", "Hacl_Hash_SHA1.c",
            "Hacl_Hash_SHA2.c", "Hacl_HMAC_DRBG.c", "Hacl_HMAC.c", "Hacl_Hash_SHA3.c",
            "Hacl_Hash_MD5.c", "Hacl_Hash_Blake2s.c", "Hacl_Hash_Blake2b.c",
            "Hacl_Curve25519_51.c", "Hacl_Ed25519.c", "Hacl_P256.c", "aesgcm-x86_64-linux.S")),
        "extra/xkcp/lib/high/Keccak/KeccakSponge.c",
        "extra/xkcp/lib/low/KeccakP-1600/ref-64bits/KeccakP-1600-reference.c",
    }),
    "cxet_crypto_import": frozenset(_MBED + "/library/" + name + ".c"
                                    for name in NATIVE_CRYPTO_IMPORT_MODULES),
    "cxet_tls_certificates": frozenset({_MBED + "/library/x509_crt.c"}),
}
NATIVE_CRYPTO_VENDOR_INCLUDES = {
    "cxet_offline_crypto_primitives": frozenset({_MBED + "/library"}),
    "cxet_crypto": frozenset({
        _HACL, "extra/hacl-star/dist/karamel/include",
        "extra/hacl-star/dist/karamel/krmllib/dist/minimal", "cmake/Vendor/xkcp",
        "extra/xkcp", "extra/xkcp/lib/common", "extra/xkcp/lib/high/Keccak",
        "extra/xkcp/lib/low/KeccakP-1600/ref-64bits", _MBED + "/include", _MBED + "/library",
    }),
    "cxet_crypto_rsa": frozenset({_MBED + "/include", _MBED + "/library"}),
    "cxet_crypto_import": frozenset({_MBED + "/include", "cmake/Vendor/mbedtls-cold", _MBED}),
    "cxet_tls_certificates": frozenset({_MBED + "/library"}),
}


def native_crypto_owner(instance) -> bool:
    return (instance.body.relative == "src/src/CMakeLists.txt" and
            instance.evaluation.source_base == Path("src/src") and
            instance.evaluation.binary_base == Path("src/src"))


_NATIVE_VENDOR_ROOTS = {
    "cxet_offline_crypto_primitives": ("extra/mbedtls-cold", "cmake/Vendor/mbedtls-cold"),
    "cxet_crypto": ("extra/hacl-star/dist/gcc-compatible", "extra/hacl-star/dist/karamel",
                    "extra/xkcp", "extra/mbedtls-cold", "cmake/Vendor/xkcp"),
    "cxet_crypto_rsa": ("extra/mbedtls-cold",),
    "cxet_crypto_import": ("extra/mbedtls-cold", "cmake/Vendor/mbedtls-cold"),
    "cxet_tls_certificates": ("extra/mbedtls-cold", "cmake/Vendor/mbedtls-cold"),
    "cxet_native_tls": ("extra/mbedtls-cold", "cmake/Vendor/mbedtls-cold"),
}
_NATIVE_TEXTUAL_SOURCES = frozenset({
    ("src/src/Core/src/Crypto/RsaMbedConstantTime.c", "extra/mbedtls-cold/library/constant_time.c"),
    ("src/src/Core/src/Crypto/RsaMbedAes.c", "extra/mbedtls-cold/library/aes.c"),
    ("src/src/Core/src/Crypto/RsaMbedAesni.c", "extra/mbedtls-cold/library/aesni.c"),
})


def native_crypto_include_edge(target: str, source: str, selected: str, *, config=None) -> bool:
    if target == "cxet_offline_crypto_primitives" and config not in native_configs(target):
        return False
    if selected == "extra/xkcp/lib/high/Keccak/KeccakSponge.inc":
        # JOIN0's generic token-paste macro is safe only inside its pinned
        # upstream caller, never as a carrier exposed to a new product TU.
        return target == "cxet_crypto" and source == "extra/xkcp/lib/high/Keccak/KeccakSponge.c"
    if (source == "extra/mbedtls-cold/include/mbedtls/build_info.h" and
            selected in native_configs(target)):
        return selected == config
    roots = _NATIVE_VENDOR_ROOTS.get(target, ())
    source_allowed = (source.startswith("src/src/Core/src/Crypto/") or
        target == "cxet_offline_crypto_primitives" and config in native_configs(target) and source in {
            "src/tests/offline/Primitives/Crypto/RsaSigner.cpp", "src/tests/offline/Primitives/Crypto/RsaTestAes.c"} or
        target == "cxet_native_tls" and source.startswith("src/src/Core/src/Network/Tls/") or any(
        source.startswith(root + "/") for root in roots)
    )
    return source_allowed and any(selected.startswith(root + "/") for root in roots)


def native_crypto_textual_source(target: str, source: str, selected: str) -> bool:
    return target == "cxet_crypto_rsa" and (source, selected) in _NATIVE_TEXTUAL_SOURCES


_NATIVE_CONFIGS = {
    "cxet_offline_crypto_primitives": "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h",
    "cxet_crypto": "src/src/Core/src/Crypto/RsaMbedConfig.h",
    "cxet_crypto_rsa": "src/src/Core/src/Crypto/RsaMbedConfig.h",
    "cxet_crypto_import": "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h",
    "cxet_tls_certificates": "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h",
    "cxet_native_tls": "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h",
}


def native_configs(target):
    default = _NATIVE_CONFIGS.get(target)
    return ({default, _NATIVE_CONFIGS["cxet_crypto_rsa"]}
            if target == "cxet_offline_crypto_primitives" else {default} - {None})
_NATIVE_OPTIONAL_INCLUDE_MACROS = frozenset({
    "MBEDTLS_USER_CONFIG_FILE", "MBEDTLS_PSA_CRYPTO_CONFIG_FILE",
    "MBEDTLS_PSA_CRYPTO_USER_CONFIG_FILE", "MBEDTLS_PSA_CRYPTO_PLATFORM_FILE",
    "MBEDTLS_PSA_CRYPTO_STRUCT_FILE", "MBEDTLS_PLATFORM_STD_MEM_HDR",
})


def native_crypto_include_data(root: Path, target: str, source: str, data: bytes,
                               config_bindings: dict[str, str] | None = None,
                               *, read_input=None) -> bytes:
    """Resolve only canonical native config macros; unknown forms still fail."""
    config = (config_bindings or {}).get(target)
    if config not in native_configs(target) or config is None or source not in {
            "extra/mbedtls-cold/include/mbedtls/build_info.h",
            "extra/mbedtls-cold/include/mbedtls/platform.h",
            "extra/mbedtls-cold/include/psa/crypto.h",
            "extra/mbedtls-cold/include/psa/crypto_types.h"}:
        return data
    try:
        configuration = (read_input(config) if read_input is not None else
                         (root / config).read_bytes())
    except OSError:
        return data
    # These optional hooks are absent from the selected project config. If a
    # config starts selecting one, leave it opaque for an explicit new review.
    for macro in (*_NATIVE_OPTIONAL_INCLUDE_MACROS, "MBEDTLS_PSA_CRYPTO_CONFIG"):
        if re.search(rb"(?m)^\s*#\s*define\s+" + macro.encode() + rb"\b", configuration):
            return data
    pattern = rb'(?m)^([ \t]*#[ \t]*include[ \t]+)([A-Z_]+)[ \t]*$'
    def selected(match):
        macro = match[2].decode("ascii")
        if macro == "MBEDTLS_CONFIG_FILE":
            return match[1] + b'"' + Path(config).name.encode() + b'"'
        if macro in _NATIVE_OPTIONAL_INCLUDE_MACROS:
            return b""
        return match[0]
    data = re.sub(pattern, selected, data)
    if source == "extra/mbedtls-cold/include/mbedtls/build_info.h":
        # Both lines belong to the inactive default/PSA branches of the exact
        # selected config above. No general conditional preprocessing occurs.
        data = data.replace(b'#include "mbedtls/mbedtls_config.h"', b"")
        data = data.replace(b'#include "psa/crypto_config.h"', b"")
    return data



def native_crypto_definition_error(target: str, value: str) -> bool:
    if target not in _NATIVE_CONFIGS:
        return False
    # These targets have a finite definition contract. A platform/macro
    # blacklist cannot justify inactive upstream branches: e.g. __APPLE__ and
    # __MACH__ would activate the otherwise dormant AvailabilityMacros include.
    allowed = {"CXET_NO_HFT_MAGIC=1"}
    if target == "cxet_crypto":
        allowed.update({"HACL_CAN_COMPILE_UINT128=1", "HACL_CAN_COMPILE_VEC128=1"})
    if target in {"cxet_crypto_rsa", "cxet_crypto_import"}:
        allowed.add('MBEDTLS_CONFIG_FILE="' + Path(_NATIVE_CONFIGS[target]).name + '"')
    # The caller additionally proves the exact raw CMake recipe for the
    # normalized (quote-stripped) MBEDTLS_CONFIG_FILE alternative.
    return value not in allowed



def native_crypto_config_bindings(instances, declaration_paths, errors: list[str]) -> dict[str, str]:
    """Prove effective native config definitions before interpreting macros.

    Source-specific Rsa.cpp and PRIVATE RSA target definitions are distinct.
    The cold config reaches certificates and TLS through the exact PUBLIC
    import edge and TLS's PRIVATE certificate edge; no target-name inference.
    """
    from CMake.Flow.CmakeFamilyFlow import paths_cover
    from CMake.Syntax.CmakeFamilyContext import exact_context, first_if
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words, words
    from CMake.Flow.CmakeFamilyState import expand_variable_tokens

    bindings: dict[str, str] = {}
    guard = (first_if("src/src/CMakeLists.txt", 234, ("NOT", "TARGET", "cxet_crypto")),)
    def flat(instance):
        return tuple(value for group in instance.token_groups for value in group)
    def exact(candidates, expected, target, *, raw=None):
        universe = declaration_paths(target)
        if not universe:
            return False
        if raw is not None:
            # The bounded value lexer removes embedded quotes. Pin the raw
            # compiler-definition spelling as well as its modeled value so an
            # unquoted CMake source cannot borrow the canonical config proof.
            expected = tuple(expand_variable_tokens(cmake_list_words(" ".join(raw)), {}))
        valid = (len(candidates) == 1 and flat(candidates[0]) == expected and
                 (raw is None or tuple(words(candidates[0].body.command.body)) == raw) and
                 native_crypto_owner(candidates[0]) and
                 exact_context(candidates[0].body.structural_context, guard) and
                 exact_context(candidates[0].evaluation.structural_context, guard) and
                 paths_cover(universe=universe, evidence=candidates[0].path_alternatives))
        if not valid:
            errors.append(f"{target}: missing/conflicting effective native MBEDTLS_CONFIG_FILE binding")
        return valid
    definitions = [item for item in instances if item.body.command.name == "target_compile_definitions"]
    def config_definitions(target):
        return [item for item in definitions if flat(item)[:1] == (target,) and
                any(value.startswith("MBEDTLS_CONFIG_FILE=") for value in flat(item)[1:])]
    for target, visibility in (("cxet_crypto_rsa", "PRIVATE"), ("cxet_crypto_import", "PUBLIC")):
        config = _NATIVE_CONFIGS[target]
        expected = (target, visibility, 'MBEDTLS_CONFIG_FILE="' + Path(config).name + '"')
        if exact(config_definitions(target), expected, target, raw=expected):
            bindings[target] = config
    overrides = [item for item in instances if item.body.command.name == "set_source_files_properties" and
                 "Core/src/Crypto/Rsa.cpp" in flat(item) and "COMPILE_DEFINITIONS" in flat(item)]
    source_raw = ("Core/src/Crypto/Rsa.cpp", "PROPERTIES", "COMPILE_DEFINITIONS",
                  '"MBEDTLS_CONFIG_FILE=\\"RsaMbedConfig.h\\""')
    if exact(overrides, (), "cxet_crypto", raw=source_raw):
        if config_definitions("cxet_crypto"):
            errors.append("cxet_crypto: target config conflicts with source-only Rsa.cpp override")
        else:
            bindings["cxet_crypto"] = _NATIVE_CONFIGS["cxet_crypto"]
    links = [item for item in instances if item.body.command.name == "target_link_libraries"]
    for target, expected, provider in (
            ("cxet_tls_certificates", ("cxet_tls_certificates", "PUBLIC", "cxet_crypto_import"), "cxet_crypto_import"),
            ("cxet_native_tls", ("cxet_native_tls", "PUBLIC", "cxet_crypto", "cxet::resident_memory",
                                 "PRIVATE", "cxet_tls_certificates"), "cxet_tls_certificates")):
        if not declaration_paths(target):
            continue
        candidates = [item for item in links if flat(item)[:1] == (target,)]
        if config_definitions(target):
            errors.append(f"{target}: direct config conflicts with canonical inherited native config")
            continue
        if exact(candidates, expected, target) and provider in bindings:
            bindings[target] = bindings[provider]
        elif provider not in bindings:
            errors.append(f"{target}: inherited native config provider {provider} has no effective binding")
    # The core crypto oracle inherits the cold import profile through its
    # validated helper-produced PRIVATE edge. RsaTestAes.c overrides that profile
    # locally; its exact bytes are verified independently before traversal.
    from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration, offline_instance_context
    target = "cxet_offline_crypto_primitives"
    if declaration_paths(target):
        candidates = [item for item in links if flat(item)[:1] == (target,)]
        expected = (target, "PRIVATE", "cxet_crypto", "cxet_crypto_import")
        if (len(candidates) == 1 and flat(candidates[0]) == expected and
                tuple(cmake_list_words(candidates[0].body.command.body)) == expected and
                offline_instance_context(candidates[0], target) and
                offline_registration(candidates[0], target).libraries == expected[2:] and
                paths_cover(universe=declaration_paths(target), evidence=candidates[0].path_alternatives) and
                not config_definitions(target) and "cxet_crypto_import" in bindings):
            bindings[target] = bindings["cxet_crypto_import"]
        else:
            errors.append(f"{target}: missing/conflicting registered cold native config provider")
    return bindings
