"""Positive cache/option producers for the active direct-source graph."""

from __future__ import annotations

from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT


_OPTIONS = {
    "src/src/CMakeLists.txt": {
        "CXET_ORDER_WS_WRITE_DUP_CANDIDATE": "OFF",
    },
    "apps/hft-parser/CMakeLists.txt": {
        "HFT_PARSER_PORTABLE_BUILD": "OFF",
        "HFT_PARSER_BUILD_PROCESSES": "ON",
        "HFT_PARSER_CANDLE_HISTORY": "ON",
        "HFT_PARSER_BUILD_TESTS": "OFF",
        "HFT_PARSER_BUILD_BENCHMARKS": "OFF",
        "HFT_PARSER_EXPERIMENT_EARLY_EVENT_YIELD": "OFF",
        "HFT_PARSER_BUILD_FUZZERS": "OFF",
    },
    "apps/hft-backtest/CMakeLists.txt": {
        "CXET_PORTABLE_BUILD": "OFF",
    },
    "apps/hft-compressor/CMakeLists.txt": {
        "HFT_COMPRESSOR_PORTABLE_BUILD": "OFF",
    },
    "apps/vetron/CMakeLists.txt": {
        "VETRON_BUILD_FRONTEND_CONTRACT_TESTS": "OFF",
    },
}


def approved_direct_option(
    relative: str,
    variable: str,
    raw_words: list[str],
) -> bool:
    if relative == "apps/hft-compressor/CMakeLists.txt" and variable == "HFT_COMPRESSOR_BUILD_CLI":
        return raw_words == [variable, "Build hft-compressor CLI", "${_HFT_COMPRESSOR_BUILD_TOOLS_DEFAULT}"]
    expected = _OPTIONS.get(relative, {}).get(variable)
    return (
        expected is not None and len(raw_words) == 3 and
        raw_words[0] == variable and raw_words[-1].upper() == expected and
        all(marker not in raw_words[1]
            for marker in ("${", "$ENV{", "$CACHE{", "$<"))
    )


_CORE_CACHE = {
    "CXET_COMPILE_JOBS": ("STRING", ("1",), False),
    "CXET_ENABLE_HFT_MAGIC": ("BOOL", ("ON", "OFF"), None),
    "CXET_DISABLE_HFT_MAGIC": ("BOOL", ("OFF",), False),
    "CXET_SANITIZER_PROFILE": ("STRING", ("none",), False),
    "CXET_SAFETY_BUILD": ("BOOL", ("OFF",), False),
    "CXET_PORTABLE_BUILD": ("BOOL", ("OFF",), False),
    "CXET_LTO": ("BOOL", ("OFF",), False),
    "CXET_NO_EXCEPTIONS_RTTI": ("BOOL", ("OFF",), False),
    "CXET_SECP256K1_NATIVE_OPT": ("BOOL", ("ON",), False),
    "CMAKE_C_FLAGS_RELEASE": (
        "STRING", ("-O3 -DNDEBUG", "-O3 -DNDEBUG -march=native"), True),
    "CMAKE_CXX_FLAGS_RELEASE": (
        "STRING", ("-O3 -DNDEBUG", "-O3 -DNDEBUG -march=native"), True),
    "SECP256K1_INSTALL": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_RECOVERY": ("BOOL", ("ON",), True),
    "SECP256K1_ENABLE_MODULE_ECDH": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_EXTRAKEYS": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_SCHNORRSIG": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_MUSIG": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_ELLSWIFT": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_BENCHMARK": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_EXHAUSTIVE_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_CTIME_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_EXAMPLES": ("BOOL", ("OFF",), True),
}

_DIRECT_CACHE = {
    "src/src/CMakeLists.txt": _CORE_CACHE,
    "apps/hft-parser/CMakeLists.txt": {
        "CMAKE_BUILD_TYPE": ("STRING", ("Release",), True),
        "HFT_PARSER_SANITIZER": ("STRING", ("none",), False),
    },
    "apps/vetron/wasm/CMakeLists.txt": {
        "VETRON_EMXX_EXECUTABLE": ("FILEPATH", ("",), False),
    },
    "src/tests/CMakeLists.txt": {
        "gtest_force_shared_crt": ("BOOL", ("ON",), True),
        "CXET_STRESS_SANITIZERS": ("STRING", ("",), False),
    },
}


def approved_direct_cache_set(relative: str, signature) -> bool:
    expected = _DIRECT_CACHE.get(relative, {}).get(signature.variable)
    if expected is None:
        return False
    cache_type, allowed_values, force = expected
    return (
        signature.cache_type == cache_type and
        len(signature.values) == 1 and
        signature.values[0] in allowed_values and
        (force is None or signature.force == force)
    )


_ROOT_CACHE = {
    "CMAKE_INTERPROCEDURAL_OPTIMIZATION": ("BOOL", ("OFF",), True),
    "CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE": ("BOOL", ("OFF",), True),
    "CXET_FULL_BUILD": ("BOOL", ("ON",), False),
    "CXET_FAMILY_SOURCE_GRAPH": ("BOOL", ("OFF",), False),
    "CXET_FAMILY_PROFILE": ("STRING", ("essential",), False),
    "CXET_CLANG24_LIFETIME_PROFILE": (
        "STRING", ("off",), False),
    "CXET_BUILD_REPLAY": ("BOOL", ("OFF",), False),
    "CXET_EXCHANGE_FEED_RACE_BUILD": ("BOOL", ("OFF",), False),
    "CXET_ENABLE_HFT_MAGIC": ("BOOL", ("ON", "OFF"), None),
    "CXET_DISABLE_HFT_MAGIC": ("BOOL", ("OFF",), False),
    "CXET_SANITIZER_PROFILE": ("STRING", ("none",), False),
    "CXET_SAFETY_BUILD": ("BOOL", ("OFF",), False),
    "CXET_PORTABLE_BUILD": ("BOOL", ("OFF",), False),
    "CMAKE_C_FLAGS_RELEASE": ("STRING", ("${_CXET_RELEASE_FLAGS}",), True),
    "CMAKE_CXX_FLAGS_RELEASE": ("STRING", ("${_CXET_RELEASE_FLAGS}",), True),
    "CXET_STRESS_SANITIZERS": ("STRING", ("",), False),
    "CXET_LTO": ("BOOL", ("ON", "OFF"), False),
    "CXET_NO_EXCEPTIONS_RTTI": ("BOOL", ("OFF",), False),
    "CXET_SECP256K1_NATIVE_OPT": ("BOOL", ("ON", "OFF"), False),
    "SECP256K1_INSTALL": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_RECOVERY": ("BOOL", ("ON",), True),
    "SECP256K1_ENABLE_MODULE_ECDH": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_EXTRAKEYS": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_SCHNORRSIG": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_MUSIG": ("BOOL", ("OFF",), True),
    "SECP256K1_ENABLE_MODULE_ELLSWIFT": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_BENCHMARK": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_EXHAUSTIVE_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_CTIME_TESTS": ("BOOL", ("OFF",), True),
    "SECP256K1_BUILD_EXAMPLES": ("BOOL", ("OFF",), True),
    "HFT_PARSER_PORTABLE_BUILD": (
        "BOOL", ("${CXET_PORTABLE_BUILD}",), True),
    "HFT_COMPRESSOR_PORTABLE_BUILD": (
        "BOOL", ("${CXET_PORTABLE_BUILD}",), True),
}

_ROOT_OPTIONS = {
    "CXET_DIAGNOSTIC_DEPLOY": "OFF",
    "CXET_MACHINE_SAFETY_AUDIT": "OFF",
    "CXET_ENABLE_PREPARED_ORDER_CHECKS": "OFF",
    "CXET_ENABLE_ABSEIL_REGISTRY_BENCH": "OFF",
    "CXET_ENABLE_MARKET_INGRESS_RPS_BENCH": "OFF",
    "CXET_ENABLE_FAMILY_STRATEGY_BENCH": "OFF",
    "CXET_ENABLE_SORT_LAB": "OFF",
    "CXET_ENABLE_SRC_TESTS": "OFF",
    "CXET_ENABLE_PRIMITIVES_PARSE_BENCH": "OFF",
}


def approved_root_option(tokens: list[str]) -> bool:
    return (
        len(tokens) == 3 and tokens[0] in _ROOT_OPTIONS and
        tokens[-1].upper() == _ROOT_OPTIONS[tokens[0]]
    )


def approved_root_cache_set(tokens: list[str]) -> bool:
    if tokens == ["CXET_PORTABLE_BUILD", "ON", "CACHE", "BOOL",
                  "Portable CPU target", "FORCE"]:
        return True
    if not tokens or tokens.count("CACHE") != 1:
        return False
    cache_index = tokens.index("CACHE")
    suffix = tokens[cache_index + 1:]
    force = bool(suffix and suffix[-1].upper() == "FORCE")
    if force:
        suffix = suffix[:-1]
    if len(suffix) != 2:
        return False
    expected = _ROOT_CACHE.get(tokens[0])
    if expected is None:
        return False
    cache_type, values, expected_force = expected
    return (
        suffix[0].upper() == cache_type and
        tuple(tokens[1:cache_index]) in {(value,) for value in values} and
        (expected_force is None or force == expected_force)
    )
