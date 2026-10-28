"""Pinned upstream source identities for scoped native include adaptations."""

import hashlib
import re


_MANIFESTS = {
    "extra/mbedtls-cold/": ("cmake/Vendor/mbedtls-cold/UPSTREAM.sha256", "b83a6ff12ffaaddb9b3fb4f564b90dbea856275eea6ea01333ea4170b708577e"),
    "extra/hacl-star/": ("cmake/Vendor/hacl-star/UPSTREAM.sha256", "d0d3436e00cc1bbae3083f29dc0d76d6ef90baf87e50276eb211deb4153ace44"),
    "extra/xkcp/": ("cmake/Vendor/xkcp/UPSTREAM.sha256", "98ef5cd0b4a54155ff85709433c2661b472ba770c381558c829a37658943477d"),
}
_SUPPLEMENTAL = {
    # The legacy cold manifest predates these inputs. AES/AESNI are also pinned
    # in RsaMbedAdapt.py; all three are unchanged in the documented upstream
    # bd39c1b7c6a7022df1ca6bec1be4ec317ae9c22f checkout.
    "extra/mbedtls-cold/library/aes.c": "f30e6b7139527b41c32f68cc5430ceafa213e7fdf7a39bf4981f6a20cd0e77a1",
    "extra/mbedtls-cold/library/aesni.c": "a49c2513f08b692dcdfc612cbbb520a009d7b3bd22f9e1a00c5c4f2d54057770",
    "extra/mbedtls-cold/library/sha1.c": "5e95c9cf66265d1d90cb3f8d276074e7a8811adc5907118f68bef9b5ff68ec90",
}
_CONFIGURATIONS = {
    "src/src/Core/src/Crypto/RsaMbedConfig.h": "a2dbcf6aa57a50b514a130570e74eb8e3dfd0408167cf45f0d6f2a8ff925d66e",
    "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h": "834be8b6bf1c44dbf2f8b9ac0a141ad5287f4d1d43da16254e6c34f939fde3e5",
    "cmake/Vendor/xkcp/config.h": "437a8c0a6a7ae8050a6d5eb4be872907bb1ef35d6961783144dc14b58d4df903",
}
_LOCAL_CONFIG_OVERRIDES = {
    # This test TU undefines the inherited cold profile before including AES.
    # No other source-local platform/config mutation is interpreted here.
    "src/tests/offline/Primitives/Crypto/RsaTestAes.c": "57824467ff776bff4668e82d1b45468e6410dea44a8cfdb6d35a9c094a41911f",
}


def native_test_configuration_error(source, data):
    """No unproved first-party macro may invalidate the oracle's native model."""
    if source.startswith("extra/") or source in _CONFIGURATIONS or source in _LOCAL_CONFIG_OVERRIDES:
        # These bytes have independent manifest/config/override identity proof.
        return False
    from Family.Sources.CxetFamilyCppPolicy import cpp_phase_two, _directive_view
    directives = _directive_view(cpp_phase_two(data))
    for match in re.finditer(
            rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*(?:define|undef)[ \t\v\f]+([A-Za-z_][A-Za-z_0-9]*)', directives):
        name = match[1]
        if name.startswith((b"_", b"MBEDTLS_", b"PSA_", b"HACL_", b"Keccak")) or name == b"WIN32":
            return True
    return False


class NativeInputs:
    def __init__(self, inputs):
        self.inputs = inputs
        self.catalogs = {}

    def configuration(self, relative):
        data = self.inputs.read(relative)
        if hashlib.sha256(data).hexdigest() != _CONFIGURATIONS.get(relative):
            raise OSError(f"unreviewed native configuration: {relative}")
        return data

    def verify(self, source, data):
        if source in _LOCAL_CONFIG_OVERRIDES:
            if hashlib.sha256(data).hexdigest() != _LOCAL_CONFIG_OVERRIDES[source]:
                raise OSError(f"unreviewed source-local native config override: {source}")
            return False
        if source in _CONFIGURATIONS:
            if self.configuration(source) != data:
                raise OSError(f"unreviewed native configuration bytes: {source}")
            return False
        if source.startswith("extra/xkcp/"):
            # KeccakReference must remain absent before suppressing its debug
            # includes, including when this config is reached transitively.
            self.configuration("cmake/Vendor/xkcp/config.h")
        for prefix, (manifest, digest) in _MANIFESTS.items():
            if not source.startswith(prefix):
                continue
            if manifest not in self.catalogs:
                raw = self.inputs.read(manifest)
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise OSError(f"reviewed native manifest changed: {manifest}")
                entries = {}
                for line in raw.decode("ascii").splitlines():
                    match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_./+-]+)", line)
                    if (match is None or match[2] in entries or
                            any(part in {"", ".", ".."} for part in match[2].split("/"))):
                        raise OSError(f"invalid native manifest entry: {manifest}")
                    entries[match[2]] = match[1]
                self.catalogs[manifest] = entries
            expected = self.catalogs[manifest].get(source[len(prefix):], _SUPPLEMENTAL.get(source))
            if expected is None or hashlib.sha256(data).hexdigest() != expected:
                raise OSError(f"unreviewed/changed native source: {source}")
            return True
        return False


_INACTIVE_PLATFORM_INCLUDES = {
    "extra/xkcp/lib/high/Keccak/KeccakSponge.c": {"displayIntermediateValues.h"},
    "extra/xkcp/lib/low/KeccakP-1600/ref-64bits/KeccakP-1600-reference.c": {"displayIntermediateValues.h"},
    "extra/xkcp/lib/common/brg_endian.h": {"machine/endian.h"},
    "extra/mbedtls-cold/library/platform_util.c": {"windows.h", "sanitizer/msan_interface.h"},
    "extra/mbedtls-cold/library/sha256.c": {"Windows.h", "processthreadsapi.h"},
    "extra/mbedtls-cold/library/x509_crt.c": {"windows.h", "platform/mbed_retarget.h", "winsock2.h", "ws2tcpip.h"},
    "extra/mbedtls-cold/include/mbedtls/platform_util.h": {"sal.h"},
    "extra/hacl-star/dist/gcc-compatible/libintvector.h": {"arm_neon.h", "vecintrin.h", "altivec.h"},
    "extra/hacl-star/dist/karamel/include/krml/internal/target.h": {"AvailabilityMacros.h", "_mingw.h"},
    "extra/hacl-star/dist/karamel/include/krml/lowstar_endianness.h": {"libkern/OSByteOrder.h"},
}
_ALT_HEADERS = frozenset({"aes", "dhm", "ecp", "threading", "md5", "ripemd160", "sha1", "sha256", "sha512", "rsa", "des", "cmac", "gcm", "ccm", "chachapoly", "ecjpake", "poly1305", "chacha20", "aria", "camellia"})


def _without_include(data, spelling):
    return re.sub(rb'(?m)^[ \t]*#[ \t]*include[ \t]+[<"]' +
                  re.escape(spelling.encode()) + rb'[>"][ \t]*(?://[^\n]*)?$', b"", data)


def native_syntax_data(source, data, *, verified, config_data=None, probe_include=None):
    if not verified:
        return data
    if config_data is not None and re.search(
            rb'(?m)^\s*#\s*(?:include|undef)\b|^\s*#\s*define\s+(?:_WIN32|WIN32|_WIN64|_MSC_VER|__MBED__|__GNUC__|__clang__|__arm__|__aarch64__|__x86_64__|KeccakReference)\b', config_data):
        raise OSError("native configuration has an unreviewed indirect/platform override")
    # These branches are inactive in the checker's exact Linux/x86_64/Clang
    # profiles (memory sanitizer is not an admitted native sanitizer). The
    # native definition policy rejects caller platform/Keccak overrides.
    for include in _INACTIVE_PLATFORM_INCLUDES.get(source, ()):
        data = _without_include(data, include)
    if config_data is not None and not re.search(rb'(?m)^\s*#\s*(?:include|undef)\b', config_data):
        absent = lambda macro: not re.search(rb'(?m)^\s*#\s*define\s+' + macro.encode() + rb'\b', config_data)
        basename = source.removeprefix("extra/mbedtls-cold/include/mbedtls/").removesuffix(".h")
        if basename in _ALT_HEADERS and absent("MBEDTLS_" + basename.upper() + "_ALT"):
            data = _without_include(data, basename + "_alt.h")
        for owner, include, macro in (
            ("extra/mbedtls-cold/include/mbedtls/platform.h", "platform_alt.h", "MBEDTLS_PLATFORM_SETUP_TEARDOWN_ALT"),
            ("extra/mbedtls-cold/include/psa/crypto_platform.h", "crypto_spe.h", "MBEDTLS_PSA_CRYPTO_SPM"),
            ("extra/mbedtls-cold/include/psa/crypto_driver_contexts_primitives.h", "libtestdriver1/include/psa/crypto.h", "MBEDTLS_TEST_LIBTESTDRIVER1"),
            ("extra/mbedtls-cold/include/psa/crypto_driver_contexts_composites.h", "libtestdriver1/include/psa/crypto.h", "MBEDTLS_TEST_LIBTESTDRIVER1")):
            if source == owner and absent(macro):
                data = _without_include(data, include)
    if source in {"extra/hacl-star/dist/gcc-compatible/libintvector.h", "extra/hacl-star/dist/gcc-compatible/lib_intrinsics.h"}:
        if probe_include is None:
            return data
        for include in ("config.h", "libintvector_debug.h"):
            expression = b'__has_include("' + include.encode() + b'")'
            if expression not in data:
                continue
            present = probe_include(include)
            data = data.replace(expression, b"1" if present else b"0")
            if not present:
                data = _without_include(data, include)
        data = data.replace(b"defined(__has_include)", b"1")
    if source == "extra/mbedtls-cold/library/x509_crt.c":
        # These exact POSIX headers are admitted system interfaces of the
        # Linux compiler profile; includes remain in the recursive scan.
        data = data.replace(b"defined(__has_include)", b"1")
        for include in (b"sys/socket.h", b"arpa/inet.h"):
            data = data.replace(b"__has_include(<" + include + b">)", b"1")
    if source == "extra/xkcp/lib/high/Keccak/KeccakSponge.inc":
        data = data.replace(b"#define JOIN0(a, b)                     a ## b", b"#define JOIN0(a, b) a b")
    if source in {"extra/mbedtls-cold/library/bn_mul.h",
                  "extra/mbedtls-cold/library/constant_time_impl.h",
                  "extra/mbedtls-cold/library/aesni.c",
                  "extra/mbedtls-cold/library/padlock.h"}:
        # The pinned upstream multiplication macros contain assembler tokens,
        # never assembler-side file ingestion. Keep all instruction text for
        # the independent .include/.incbin scan.
        data = re.sub(rb"\b(?:asm|__asm|__asm__)\b", b"cxet_native_asm_token", data)
    if source == "extra/hacl-star/dist/karamel/include/krml/internal/target.h":
        data = data.replace(b'_Pragma("GCC diagnostic ignored \\"-Wtype-limits\\"")', b"")
    if verified and source == "extra/mbedtls-cold/library/common.h":
        # Exact upstream compatibility macros cannot introduce files. Retain
        # every include and the remainder of the pinned source for the lexer.
        for spelling in (
                b"#ifndef asm",
                b"#define asm __asm", b"#define asm __asm__",
                b'#        define MBEDTLS_MAYBE_UNUSED _Pragma("diag_suppress=Pe177")',
                b'#    define MBEDTLS_MAYBE_UNUSED __pragma(warning(suppress:4189))'):
            data = re.sub(rb"(?m)^" + re.escape(spelling) + rb"$", b"", data)
    return data


def native_external_include(source, include, *, verified):
    return verified and include in {
        "extra/mbedtls-cold/library/common.h": {"arm_neon.h", "arm64_neon.h"},
        "extra/mbedtls-cold/library/alignment.h": {"arm_acle.h"},
        "extra/mbedtls-cold/library/sha256.c": {"setjmp.h"},
        "extra/mbedtls-cold/library/sha512.c": {"setjmp.h"},
        "extra/mbedtls-cold/include/mbedtls/platform.h": {"stdarg.h"},
        "extra/hacl-star/dist/gcc-compatible/libintvector.h": {"smmintrin.h"},
        "extra/hacl-star/dist/karamel/include/krml/internal/target.h": {"mm_malloc.h"},
        "extra/hacl-star/dist/karamel/include/krml/lowstar_endianness.h": {"endian.h"},
        "extra/xkcp/lib/common/brg_endian.h": {"endian.h", "byteswap.h"},
    }.get(source, ())
