"""Exact source-tree headers exported by canonical CXET family boundaries."""

from __future__ import annotations

import os
from pathlib import Path

from Family.Sources.CxetFamilyCppPolicy import (
    CPP_ASSEMBLY_SUFFIXES,
    CPP_COMPILED_SUFFIXES,
    CPP_SCAN_SUFFIXES,
    CPP_TEXTUAL_INCLUDE_SUFFIXES,
)
from Family.Sources.CxetFamilySourcePaths import source_artifact_path as _source_artifact_path


# These exact project metadata files sit below source owner roots but are not
# source entrypoints. Every regular file below a direct public
# include root must have a reviewed C/C++ textual spelling; in particular an
# extensionless file cannot become an invisible include carrier.
_COMPILER_VISIBLE_NON_SOURCE_ASSETS = frozenset({
    "src/src/Core/include/cxet/Exchanges/Bybit/MmwsV5/Shared/Ws/Helpers/Sbe/Xml/Market.xml",
    "src/src/Core/include/cxet/Exchanges/Bybit/MmwsV5/Shared/Ws/Order/Sbe/Request/Xml/OrderEntry.xml",
    "src/src/Core/include/cxet/Exchanges/Bybit/MmwsV5/Shared/Ws/Order/Sbe/Response/Xml/FastOrderAck.xml",
    "src/src/Core/include/cxet/Exchanges/Gate/ApiV4/Futures/Ws/Helpers/Sbe/Schema/gate_fex_ws_latest.xml",
    "src/src/Core/include/cxet/Exchanges/Gate/ApiV4/Spot/Ws/Helpers/Sbe/Schema/gate_spot_ws_v2.0.0.xml",
    "src/src/Core/include/cxet/Exchanges/Tbank/InvestApiV1/Shared/Grpc/Reference/Protobuf/Instrument/WireSchema.md",
    "apps/trading-core/AGENTS.md",
    "apps/trading-core/CMakeLists.txt",
    "apps/trading-core/README.md",
    "apps/trading-core/cmake/GenerateStrategyRegistry.cmake",
    "src/src/.clangd",
    "src/src/CMakeLists.txt",
    "src/src/README.md",
    "src/src/cmake/Sources/CxetCoreSources.cmake",
    "src/src/cmake/Sources/CxetExchangeSources.cmake",
    "src/src/cmake/Sources/CxetNetworkSources.cmake",
})

HEADER_OWNER_ROOTS = (
    ("apps/diagnostic", "diagnostic"),
    ("tools/exchange_api_probe", "exchange-api-probe"),
    ("apps/hft-compressor", "hft-compressor"),
    ("apps/hft-recorder", "hft-recorder"),
    ("apps/hft-backtest", "hft-backtest"),
    ("apps/trading-core", "trading-core"),
    ("apps/hft-parser", "hft-parser"),
    ("apps/trader", "trader"),
    ("apps/vetron", "vetron"),
    ("src/src", "cxet-core"),
)


def source_artifact_path(relative: str) -> bool:
    """Recognize checkout artifacts without reserving source words globally."""
    return _source_artifact_path(
        relative, tuple(owner_root for owner_root, _ in HEADER_OWNER_ROOTS))


def unsymlinked_source_path(
    path: Path,
    root: Path,
    *,
    directory: bool,
) -> bool:
    try:
        relative = path.relative_to(root)
        resolved_root = root.resolve(strict=True)
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        kind_ok = current.is_dir() if directory else current.is_file()
        return kind_ok and current.resolve(strict=True).is_relative_to(
            resolved_root)
    except (OSError, ValueError):
        return False


def source_tree_files(
    root: Path,
    directory: Path,
    errors: list[str],
    context: str,
) -> tuple[Path, ...]:
    """Walk one source root without following or silently skipping paths."""
    if not unsymlinked_source_path(directory, root, directory=True):
        errors.append(f"{context} is missing/nonregular")
        return ()
    result: list[Path] = []

    def walk_error(exc: OSError) -> None:
        location = str(exc.filename) if exc.filename is not None else str(directory)
        errors.append(f"cannot enumerate {context} at {location}: {exc}")

    for current, directory_names, file_names in os.walk(
            directory, followlinks=False, onerror=walk_error):
        current_path = Path(current)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            candidate = current_path / name
            relative = candidate.relative_to(root).as_posix()
            if source_artifact_path(relative):
                continue
            if not unsymlinked_source_path(candidate, root, directory=True):
                errors.append(
                    f"{context} contains nonregular/symlinked directory: "
                    f"{relative}")
                continue
            kept_directories.append(name)
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if source_artifact_path(relative):
                continue
            if not unsymlinked_source_path(path, root, directory=False):
                errors.append(
                    f"{context} contains nonregular/symlinked header: "
                    f"{relative}")
                continue
            result.append(path)
    return tuple(sorted(result))


def source_header_files(
    root: Path,
    directory: Path,
    errors: list[str],
    context: str,
) -> tuple[Path, ...]:
    """Return reviewed textual header fragments for identity comparison."""
    return tuple(
        path for path in source_tree_files(root, directory, errors, context)
        if path.suffix.lower() in CPP_TEXTUAL_INCLUDE_SUFFIXES)


def compiler_visible_header_inventory(
    root: Path,
    interface_roots: dict[str, tuple[str, ...]],
    errors: list[str],
) -> dict[str, tuple[str, ...]]:
    """Assign every physical header below each target's direct interface."""
    result: dict[str, set[str]] = {
        target: set() for target in interface_roots
    }
    visible_roots = sorted({
        include_root
        for roots in interface_roots.values()
        for include_root in roots
    })
    seen_assets: set[str] = set()
    headers_by_root: dict[str, tuple[str, ...]] = {}
    for include_root in visible_roots:
        directory = root / include_root
        paths = source_tree_files(
            root, directory, errors,
            f"compiler-visible header tree {include_root}")
        headers: list[str] = []
        for path in paths:
            relative = path.relative_to(root).as_posix()
            if relative in _COMPILER_VISIBLE_NON_SOURCE_ASSETS:
                seen_assets.add(relative)
                continue
            suffix = path.suffix.lower()
            if suffix in CPP_COMPILED_SUFFIXES:
                continue
            if suffix in CPP_ASSEMBLY_SUFFIXES:
                errors.append(
                    "compiler-visible tree contains assembly entrypoint: "
                    f"{relative}")
                continue
            if suffix not in CPP_SCAN_SUFFIXES:
                errors.append(
                    "compiler-visible tree contains an unreviewed non-C++ "
                    f"file: {relative}")
                continue
            headers.append(relative)
        headers_by_root[include_root] = tuple(sorted(headers))
    for target, include_roots in interface_roots.items():
        for include_root in include_roots:
            result[target].update(headers_by_root.get(include_root, ()))
    missing_assets = sorted(asset for asset in _COMPILER_VISIBLE_NON_SOURCE_ASSETS - seen_assets
        if any(asset == include_root or asset.startswith(include_root + "/")
               for include_root in visible_roots))
    if missing_assets:
        errors.append(
            "compiler-visible non-source asset policy is stale: " +
            str(missing_assets))
    return {
        target: tuple(sorted(headers))
        for target, headers in sorted(result.items())
    }


def exported_header_targets(
    inventory: dict[str, tuple[str, ...]],
) -> dict[str, frozenset[str]]:
    """Invert the reviewed target inventory for consumer boundary checks."""
    owners: dict[str, set[str]] = {}
    for target, headers in inventory.items():
        for relative in headers:
            owners.setdefault(relative, set()).add(target)
    return {
        relative: frozenset(targets)
        for relative, targets in owners.items()
    }


def logical_header_owner(relative: str) -> str | None:
    for owner_root, owner in HEADER_OWNER_ROOTS:
        if relative == owner_root or relative.startswith(owner_root + "/"):
            return owner
    return None
