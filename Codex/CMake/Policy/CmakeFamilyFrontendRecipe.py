"""Independent inputs and outputs of the pinned all-exchange frontend producer."""

from __future__ import annotations

from pathlib import Path

from CMake.Flow.CmakeFamilyExecutionIdentity import (
    ROOT, reviewed_file_identity, unsymlinked_regular_path,
)
from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT


# These are executed producers/configuration, rather than generated artifacts
# or arbitrary browser application content. The CMake pin also proves the
# source GLOB patterns, all-profile directory writers and dependency edges.
_AUTHORITIES = (
    "apps/vetron/CMakeLists.txt", "apps/vetron/wasm/CMakeLists.txt",
    "apps/vetron/frontend/BuildFrontend.py", "apps/vetron/frontend/ProfilePaths.py",
    "apps/vetron/frontend/package.json", "apps/vetron/frontend/package-lock.json",
    "apps/vetron/frontend/vite.config.ts", "apps/vetron/frontend/vite.generated.ts",
    "apps/vetron/frontend/tsconfig.base.json", "apps/vetron/frontend/tsconfig.json",
    "apps/vetron/frontend/tsconfig.worker.json",
    "apps/vetron/scripts/GenerateHistoryCatalog.mjs",
    "apps/vetron/scripts/GenerateTradingCostProfile.mjs",
    "apps/vetron/scripts/Lib/SplitCppMacroArguments.mjs",
    "apps/vetron/scripts/Lib/CppStringConstant.mjs",
    "cmake/CxetToolchain.cmake", "tools/Toolchain/BootstrapEmscripten.py",
)


def reviewed_frontend_recipe(*, local_tests: bool = False):
    """Return exact declared recipe paths; never execute a producer or read outputs.

    The caller separately proves actual all-profile command arguments and the
    real WASM dependency. This is source/configure evidence only: installed
    npm/toolchain validation and the bounded asset manifest remain producer
    responsibilities, not claims made by the static checker.
    """
    if type(local_tests) is not bool or not all(
            reviewed_file_identity(relative) for relative in _AUTHORITIES):
        return None
    # Reuse the interpreter's CMake glob semantics instead of a second glob
    # implementation that could silently omit a real configure dependency.
    from CMake.Flow.CmakeFamilyWriters import apply_output_writer

    frontend = ROOT / "apps/vetron/frontend"
    source = ROOT / "apps/vetron"
    source_patterns = (
        frontend / "src/*.ts", frontend / "src/*.tsx", frontend / "src/*.css",
        frontend / "public/*", source / "scripts/*.mjs",
    )
    config_patterns = (frontend / "tsconfig*.json", frontend / "vite*.ts")
    catalog_patterns = (
        ROOT / "src/src/Core/src/Exchanges/*/HistoricalTradesSources.ipp",
        ROOT / "src/src/Core/include/cxet/Exchanges/*.hpp",
    )
    state = {}
    errors = []
    for variable, recursive, patterns in (
            ("source_globs", True, source_patterns),
            ("config_globs", False, config_patterns),
            ("catalog_globs", True, catalog_patterns)):
        apply_output_writer(
            "file", ["GLOB_RECURSE" if recursive else "GLOB", variable,
                     "CONFIGURE_DEPENDS", *(path.as_posix() for path in patterns)],
            ROOT, source, state, lambda values: list(values), errors,
            "apps/vetron/CMakeLists.txt:261")
    if errors or any(not unsymlinked_regular_path(Path(value), ROOT)
                     for values in state.values() for value in values):
        return None
    fixed = (
        frontend / "BuildFrontend.py", frontend / "ProfilePaths.py",
        source / "CMakeLists.txt", frontend / "package.json",
        frontend / "package-lock.json", frontend / "index.html",
        ROOT / "cmake/CxetToolchain.cmake",
        ROOT / "tools/Toolchain/BootstrapEmscripten.py",
        ROOT / "src/src/Core/include/cxet/Exchanges/Finam/TradeApiV1/Shared/Grpc/Reference/Protobuf/TradingCost/FinamTradingCostPolicy.hpp",
    )
    if not all(unsymlinked_regular_path(path, ROOT) for path in fixed):
        return None
    binary = SYNTHETIC_BINARY_ROOT
    stamp = binary + "/apps/vetron/frontend-build.stamp.json"
    output = (source / "build/frontend-static").as_posix()
    generated = (frontend / ".generated").as_posix()
    wasm = (binary + "/apps/vetron/wasm/trading-core-math.wasm" if local_tests else
            generated + "/trading-core-math.wasm")
    fixed_values = tuple(path.as_posix() for path in fixed)
    inputs = (*fixed_values[:3], binary + "/.cxet-exchanges.json",
              *fixed_values[3:], *state["source_globs"],
              *state["config_globs"], *state["catalog_globs"])
    outputs = (stamp, output + "/index.html", *(generated + "/" + name for name in (
        "HistoryCatalog.generated.ts", "TradingCostProfile.generated.ts",
        "BrowserConnectOrigins.generated.hpp", "ExchangeSelection.generated.ts")))
    command = ("${Python3_EXECUTABLE}", fixed_values[0],
               "--output-dir", output, "--stamp", stamp,
               "--cache-dir", binary + "/frontend/npm-cache",
               "--exchanges", "all", "--generated-dir", generated,
               *(("--math-wasm", wasm) if local_tests else ()))
    return dict(state, inputs=inputs, outputs=outputs, manifest=(stamp,),
                wasm=(wasm,), command=command, dependencies=(*inputs, wasm))
