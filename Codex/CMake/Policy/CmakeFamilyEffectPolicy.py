"""Central fail-closed policy for variables that can redirect build effects."""

from __future__ import annotations

import re


_PACKAGE_PREFIXES = (
    "ABSL_", "FETCHCONTENT_", "GTEST_", "OPENSSL_", "PYTHON3_",
    "SECP256K1_", "THREADS_", "WOLFSSL_",
)
_PACKAGE_NAMES = ("ABSL", "OPENSSL", "PYTHON3", "THREADS")
_EXACT_EFFECT_VARIABLES = frozenset({
    "CMAKE_AR",
    "CMAKE_CROSSCOMPILING_EMULATOR",
    "CMAKE_FIND_PACKAGE_REDIRECTS_DIR",
    "CMAKE_LINKER",
    "CMAKE_MAKE_PROGRAM",
    "CMAKE_MODULE_PATH",
    "CMAKE_NM",
    "CMAKE_OBJCOPY",
    "CMAKE_OBJDUMP",
    "CMAKE_PREFIX_PATH",
    "CMAKE_PROJECT_INCLUDE",
    "CMAKE_PROJECT_INCLUDE_BEFORE",
    "CMAKE_PROJECT_TOP_LEVEL_INCLUDES",
    "CMAKE_RANLIB",
    "CMAKE_READELF",
    "CMAKE_STRIP",
    "CMAKE_SYSTEM_PREFIX_PATH",
    "CMAKE_TOOLCHAIN_FILE",
    "CXET_ROOT_SOURCE_GRAPH",
})
_FAMILY_SELECTOR_VARIABLES = frozenset({
    "CXET_FAMILY_PROFILE",
    "CXET_FAMILY_VERIFICATION",
    "HFT_PARSER_BUILD_TESTS",
    "VETRON_BUILD_FRONTEND_CONTRACT_TESTS",
})


def selector_variable(variable: str) -> bool:
    """Return whether a cache selector controls the REF7 CTest surface."""
    return variable.upper() in _FAMILY_SELECTOR_VARIABLES


def effect_variable(variable: str) -> bool:
    """Return whether a variable can redirect package, compiler, or linker IO."""
    upper = variable.upper()
    if selector_variable(upper):
        return True
    # CMake grows new compiler, launcher, package, and rule variables over
    # time.  Treating the namespace as protected by default avoids a stale
    # blacklist silently turning a new variable into an ownership carrier.
    if upper.startswith("CMAKE_"):
        return True
    if upper in {"BUILD_SHARED_LIBS", "BUILD_TESTING"}:
        return True
    if upper in _EXACT_EFFECT_VARIABLES or upper.startswith("CMAKE_FIND_"):
        return True
    if upper.startswith(_PACKAGE_PREFIXES):
        return True
    if any(
            upper == prefix + package
            for prefix in (
                "CMAKE_DISABLE_FIND_PACKAGE_",
                "CMAKE_REQUIRE_FIND_PACKAGE_",
            )
            for package in _PACKAGE_NAMES):
        return True
    if re.fullmatch(
            r"CMAKE_PROJECT_[A-Z0-9_]+_INCLUDE(?:_BEFORE)?", upper):
        return True
    if re.fullmatch(r"CMAKE_[A-Z0-9]+_FLAGS(?:_[A-Z0-9_]+)?", upper):
        return True
    if re.fullmatch(
            r"CMAKE_(?:EXE|SHARED|MODULE|STATIC)_LINKER_FLAGS"
            r"(?:_[A-Z0-9_]+)?", upper):
        return True
    if re.fullmatch(
            r"CMAKE_[A-Z0-9]+_(?:COMPILER|COMPILER_LAUNCHER|"
            r"LINKER_LAUNCHER|STANDARD_INCLUDE_DIRECTORIES|"
            r"STANDARD_LIBRARIES)", upper):
        return True
    if re.fullmatch(
            r"CMAKE_[A-Z0-9]+_(?:COMPILE_OBJECT|LINK_EXECUTABLE|"
            r"CREATE_SHARED_LIBRARY|CREATE_SHARED_MODULE|"
            r"CREATE_STATIC_LIBRARY)", upper):
        return True
    return upper.startswith((
        "CMAKE_RULE_LAUNCH_",
        "CMAKE_USER_MAKE_RULES_OVERRIDE",
    ))


def approved_effect_set(
    relative: str,
    variable: str,
    raw_words: list[str],
    expanded_value: list[str],
) -> bool:
    """Accept exact current CMake-namespace producers, never a name class."""
    recorder_outputs = {"CMAKE_RUNTIME_OUTPUT_DIRECTORY": "bin",
                        "CMAKE_ARCHIVE_OUTPUT_DIRECTORY": "lib",
                        "CMAKE_LIBRARY_OUTPUT_DIRECTORY": "lib"}
    if relative == "apps/hft-recorder/CMakeLists.txt" and variable in recorder_outputs:
        suffix = recorder_outputs[variable]
        return raw_words == [variable, "${CMAKE_BINARY_DIR}/" + suffix] and expanded_value == [
            "__CXET_CMAKE_BINARY__/" + suffix]
    if (relative == "CMakeLists.txt" and
            variable == "CXET_ROOT_SOURCE_GRAPH" and
            raw_words == [variable, "ON"] and
            expanded_value == ["ON"]):
        return True
    if (relative == "CMakeLists.txt" and
            (variable, raw_words, expanded_value) in (
                ("CMAKE_CXX_VISIBILITY_PRESET",
                 ["CMAKE_CXX_VISIBILITY_PRESET", "hidden"], ["hidden"]),
                ("CMAKE_VISIBILITY_INLINES_HIDDEN",
                 ["CMAKE_VISIBILITY_INLINES_HIDDEN", "ON"], ["ON"]))):
        return True

    if relative == "CMakeLists.txt" and variable in {"CMAKE_INTERPROCEDURAL_OPTIMIZATION", "CMAKE_INTERPROCEDURAL_OPTIMIZATION_RELEASE"}:
        return len(raw_words) == 6 and raw_words[:4] == [variable, "OFF", "CACHE", "BOOL"] and raw_words[-1] == "FORCE" and expanded_value == ["OFF"]

    release_flags = (
        relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
        variable in {"CMAKE_C_FLAGS_RELEASE", "CMAKE_CXX_FLAGS_RELEASE"} and
        len(raw_words) == 6 and
        raw_words[1] == "${_CXET_RELEASE_FLAGS}" and
        raw_words[2:4] == ["CACHE", "STRING"] and
        raw_words[-1] == "FORCE" and
        bool(expanded_value) and
        set(expanded_value).issubset({
            "-O3 -DNDEBUG",
            "-O3 -DNDEBUG -march=native",
            "-O3 -DNDEBUG -ffunction-sections -fdata-sections",
            "-O3 -DNDEBUG -ffunction-sections -fdata-sections -march=native -mtune=native",
            "-O1 -DNDEBUG -ffunction-sections -fdata-sections",
            "-O1 -DNDEBUG -ffunction-sections -fdata-sections -march=native -mtune=native",
            "-O2 -DNDEBUG -ffunction-sections -fdata-sections",
            "-O2 -DNDEBUG -ffunction-sections -fdata-sections -march=native -mtune=native",
        })
    )
    if release_flags:
        return True

    if (relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
            variable == "BUILD_SHARED_LIBS" and raw_words in (
                ["BUILD_SHARED_LIBS", "OFF"],
                ["BUILD_SHARED_LIBS", "${_CXET_BUILD_SHARED_LIBS_SAVED}"],
            ) and expanded_value):
        return True
    if (relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
            variable == "BUILD_TESTING" and
            raw_words == ["BUILD_TESTING", "OFF"] and
            expanded_value == ["OFF"]):
        return True

    secp_values = {
        "SECP256K1_INSTALL": "OFF",
        "SECP256K1_ENABLE_MODULE_RECOVERY": "ON",
        "SECP256K1_ENABLE_MODULE_ECDH": "OFF",
        "SECP256K1_ENABLE_MODULE_EXTRAKEYS": "OFF",
        "SECP256K1_ENABLE_MODULE_SCHNORRSIG": "OFF",
        "SECP256K1_ENABLE_MODULE_MUSIG": "OFF",
        "SECP256K1_ENABLE_MODULE_ELLSWIFT": "OFF",
        "SECP256K1_BUILD_BENCHMARK": "OFF",
        "SECP256K1_BUILD_TESTS": "OFF",
        "SECP256K1_BUILD_EXHAUSTIVE_TESTS": "OFF",
        "SECP256K1_BUILD_CTIME_TESTS": "OFF",
        "SECP256K1_BUILD_EXAMPLES": "OFF",
    }
    if (relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
            variable in secp_values and len(raw_words) == 6 and
            raw_words[1] == secp_values[variable] and
            raw_words[2:4] == ["CACHE", "BOOL"] and
            raw_words[-1] == "FORCE" and
            expanded_value == [secp_values[variable]]):
        return True
    if (relative == "src/tests/CMakeLists.txt" and
            variable == "gtest_force_shared_crt" and
            raw_words == [variable, "ON", "CACHE", "BOOL", "", "FORCE"] and
            expanded_value == ["ON"]):
        return True

    standard_origins = {
        "CMakeLists.txt",
        "src/src/CMakeLists.txt",
        "apps/hft-parser/CMakeLists.txt",
    }
    standard_values = {
        "CMAKE_CXX_STANDARD": "23",
        "CMAKE_CXX_STANDARD_REQUIRED": "ON",
        "CMAKE_CXX_EXTENSIONS": "OFF",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
    }
    if (relative in standard_origins and variable in standard_values and
            raw_words == [variable, standard_values[variable]] and
            expanded_value == [standard_values[variable]]):
        return True

    if (relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
            variable == "CMAKE_BUILD_TYPE" and
            raw_words == [variable, "Release"] and
            expanded_value == ["Release"]):
        return True
    if (relative == "apps/hft-parser/CMakeLists.txt" and
            variable == "CMAKE_BUILD_TYPE" and
            raw_words == [
                variable, "Release", "CACHE", "STRING", "", "FORCE"] and
            expanded_value == ["Release"]):
        return True
    return (
        relative in {"CMakeLists.txt", "src/src/CMakeLists.txt"} and
        variable == "CMAKE_POSITION_INDEPENDENT_CODE" and
        len(raw_words) == 2 and raw_words[1] in {"ON", "OFF"} and
        expanded_value == [raw_words[1]]
    )


def validate_effect_policy_microcases(errors: list[str]) -> None:
    """Keep the root-composition marker owned by one exact root write."""
    marker = "CXET_ROOT_SOURCE_GRAPH"
    if not effect_variable(marker):
        errors.append(
            "effect-policy self-check left the root graph marker mutable")
    if not approved_effect_set(
            "CMakeLists.txt", marker, [marker, "ON"], ["ON"]):
        errors.append(
            "effect-policy self-check rejected the canonical root marker")
    for relative, value in (
        ("apps/hft-parser/CMakeLists.txt", "ON"),
        ("apps/trading-core/CMakeLists.txt", "OFF"),
    ):
        if approved_effect_set(
                relative, marker, [marker, value], [value]):
            errors.append(
                "effect-policy self-check accepted an app-owned root marker")
