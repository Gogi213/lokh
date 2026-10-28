"""Lower the byte-reviewed diagnostic producer without executing CMake."""

import hashlib
import json
from pathlib import Path
import re

from CMake.Flow.CmakeFamilyExecutionIdentity import unsymlinked_regular_path
from CMake.Flow.CmakeFamilyGraph import Command, cmake_list_words, parse_commands
from CMake.Policy.CmakeFamilyBenchmarkRecipe import BENCHMARK_ROOTS, BENCHMARK_TARGETS


BENCHMARK_HELPER = "cmake/CxetBenchmarks.cmake"
_HELPER_SHA256 = "9bfcc600b3f86339f0e4d1104982d6fba72461aba7fe17b7ecdd8724a8f81248"
_KEYWORDS = {"OWNER", "SOURCES", "LIBRARIES", "INCLUDE_DIRECTORIES", "LABELS", "REQUIRES"}
_REQUIREMENTS = {"CXET_SELECTION_ALL", "CXET_EXCHANGE_BINANCE", "CXET_HAS_FIX", "CXET_HAS_GRPC", "CXET_HAS_WS",
                 "_trader_vstack_exchange_enabled"}
_TRADER_AUXILIARY = '''
foreach(binary IN ITEMS trader-bench-json-ws trader-bench-json-ws_traced)
  if(TARGET ${binary})
    set_property(TARGET ${binary} PROPERTY CXET_COMPILE_INPUTS
      "${CMAKE_SOURCE_DIR}/src/benchmarks/WsBenchmarkPeer.hpp"
      "${CMAKE_SOURCE_DIR}/src/benchmarks/WsBenchmarkFixture.hpp"
      "${CMAKE_SOURCE_DIR}/src/benchmarks/MarketFixture.hpp"
      "${CMAKE_SOURCE_DIR}/src/benchmarks/Cases.hpp")
  endif()
endforeach()
set(_trader_vstack_exchange_enabled OFF)
if(CXET_EXCHANGE_FINAM OR CXET_EXCHANGE_TBANK)
  set(_trader_vstack_exchange_enabled ON)
endif()
foreach(binary IN ITEMS trader-bench-vstack trader-bench-vstack_traced)
  if(TARGET ${binary})
    target_compile_options(${binary} PRIVATE -fno-access-control)
  endif()
endforeach()
unset(_trader_vstack_exchange_enabled)
'''


def _body(values):
    return " ".join(json.dumps(value) if not value or any(char.isspace() for char in value)
                    else value for value in values)


def validate_benchmark_helper(root, errors, *, text=None):
    path = root / BENCHMARK_HELPER
    try:
        data = path.read_bytes() if unsymlinked_regular_path(path, root) else b""
    except OSError as exc:
        errors.append(f"cannot read benchmark producer: {exc}")
        return False
    if (hashlib.sha256(data).hexdigest() != _HELPER_SHA256 or
            text is not None and text.encode("utf-8") != data):
        errors.append("unsupported ownership model: benchmark helper identity changed; "
                      "review declaration/source/include/link/tracing/catalog semantics before lowering")
        return False
    return True


def lower_benchmark_registrations(root, relative, commands, errors):
    """Preserve physical call context, guards, both binaries and traced inputs."""
    if relative not in BENCHMARK_ROOTS:
        raise ValueError("benchmark lowering requires a canonical registration root")
    lowered, seen = [], []
    auxiliary = [command for command in commands if command.name != "cxet_add_benchmark"]
    expected = (parse_commands(relative, _TRADER_AUXILIARY, errors)
                if BENCHMARK_ROOTS[relative] == "trader" else [])
    if [(command.name, cmake_list_words(command.body)) for command in auxiliary] != [
            (command.name, cmake_list_words(command.body)) for command in expected]:
        errors.append(f"{relative}: unsupported benchmark auxiliary commands")
        return []
    for command in commands:
        if command.name != "cxet_add_benchmark":
            lowered.append(command)
            continue
        try:
            words = cmake_list_words(command.body)
            if not words or words[0] not in BENCHMARK_TARGETS[relative]:
                raise ValueError("unknown benchmark target")
            target, options, index = words[0], {}, 1
            while index < len(words):
                key = words[index]
                if key not in _KEYWORDS or key in options:
                    raise ValueError("unknown/duplicate benchmark keyword")
                start = index = index + 1
                while index < len(words) and words[index] not in _KEYWORDS:
                    index += 1
                options[key] = words[start:index]
                if not options[key]:
                    raise ValueError("empty benchmark keyword")
            owner = BENCHMARK_ROOTS[relative]
            if options.get("OWNER") != [owner] or not options.get("SOURCES"):
                raise ValueError("benchmark must bind its exact owner and concrete sources")
            for source in options["SOURCES"]:
                path = Path(source)
                if (path.is_absolute() or any(part in {".", ".."} for part in path.parts) or
                        re.fullmatch(r"[A-Za-z0-9_./+-]+", source) is None or
                        path.suffix not in {".c", ".cc", ".cpp", ".cxx"} or
                        not unsymlinked_regular_path(root / Path(relative).parent / path, root)):
                    raise ValueError(f"unsupported/nonregular benchmark source {source}")
            for dependency in options.get("LIBRARIES", ()):
                if re.fullmatch(r"[A-Za-z0-9_.:+-]+", dependency) is None:
                    raise ValueError("nonliteral benchmark dependency")
            for requirement in options.get("REQUIRES", ()):
                if (requirement not in _REQUIREMENTS or
                        requirement == "_trader_vstack_exchange_enabled" and owner != "trader"):
                    raise ValueError("unreviewed benchmark requirement")
            seen.append(target)
            def add(name, values):
                lowered.append(Command(name, _body(values), command.line))
            add("if", ["NOT", "CXET_LOCAL_BENCHMARKS", "OR", "NOT", "CXET_LOCAL_TESTS",
                       "OR", "NOT", "CXET_BUILD_OWNER", "STREQUAL", owner])
            add("message", ["FATAL_ERROR", "benchmark requires its exact owner's all stage"])
            add("endif", [])
            for requirement in options.get("REQUIRES", ()):
                add("if", [requirement])
            add("find_package", ["OpenSSL", "REQUIRED", "COMPONENTS", "SSL"])
            for suffix in ("", "_traced"):
                binary = target + suffix
                add("add_executable", [binary, "EXCLUDE_FROM_ALL", *options["SOURCES"]])
                add("target_compile_features", [binary, "PRIVATE", "cxx_std_23"])
                add("target_include_directories", [binary, "PRIVATE",
                    "${CMAKE_SOURCE_DIR}/tools/Benchmarks/native", *options.get("INCLUDE_DIRECTORIES", ())])
                add("target_link_libraries", [binary, "PRIVATE", *options.get("LIBRARIES", ()), "OpenSSL::SSL"])
                add("set_target_properties", [binary, "PROPERTIES", "CXET_COMPILE_OWNER", owner,
                                               "CXET_BENCHMARK", "TRUE"])
                if suffix:
                    add("target_sources", [binary, "PRIVATE", "${CMAKE_SOURCE_DIR}/tools/Benchmarks/native/SendTrace.cpp"])
                    add("target_link_options", [binary, "PRIVATE", "-Wl,--wrap=send"])
                    add("target_compile_definitions", [binary, "PRIVATE", "CXET_BENCH_TRACED=1"])
                # The pinned helper also attaches this binary to the root
                # benchmark aggregate and emits its catalog entry. Those cold
                # scheduling/output facts introduce no source/link authority.
            for _ in options.get("REQUIRES", ()):
                add("endif", [])
        except (OSError, ValueError) as exc:
            errors.append(f"{relative}:{command.line}: unsupported benchmark registration: {exc}")
    if tuple(seen) != BENCHMARK_TARGETS[relative]:
        errors.append(f"{relative}: benchmark target registration order/multiplicity/inventory changed")
    return lowered
