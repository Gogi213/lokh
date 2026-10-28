"""SHA-256 identities for reviewed scripts and executable source trees."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]

# A reviewed file is hashed byte-for-byte. Tree identities hash a canonical
# manifest with ``D  <repo-path>`` directory rows and
# ``F <file-sha256>  <repo-path>`` file rows. Build outputs, dependency
# installs and VCS metadata are excluded explicitly; all remaining topology is
# covered.
_FILE_DIGESTS = {
    "apps/vetron/wasm/CMakeLists.txt":
        "ad021694e9420c013ab0b379ecbe63f9f697b419a3217db30718ebb4fffae9cb",
    "apps/vetron/wasm/BuildMathWasm.py":
        "7c5a83ffa24ff841282c306197b6b56c2c822f7e4a249f319481d9541036717d",
    "tools/Toolchain/BootstrapEmscripten.py":
        "dfa17a03b69323d267bdf51225439048e4ccfa45f79a60aca7387e3f676519e7",
    "tools/Testing/RunOffline.py":
        "9308d4e6a3c49433b1bdad1b5703da01268f538494d47f40a3a887b569030fe5",
    "tools/Build/ToolchainProfiles.py":
        "9b3c0633ba4bf64a2acff698fa12f23b14a73c66aabf5c3f2f44f086fc3cec91",
    "tools/Build/ParallelPolicy.py":
        "00a9a7046628451780428bf66f371e4b7515e23161dbd1730145a88b2813b038",
    "tools/Testing/CheckCaseCatalog.py":
        "9ffc3cb075a9679f7857e016c24e0faca32b0b816bdfd59e43da77f1e9a26768",
    "tools/Testing/ExtractCaseCatalog.py":
        "b36198e03732fbb48b005cd5c51deb933d18ebe8385fe7f315d183448bf44154",
    "tools/Codex/Family/Sources/CxetFamilyCppPolicy.py":
        "63ee0fdae64eb8f7939219c8d1f90acdfbb17424b16e84ef3a22250757953bb2",
    "cmake/CxetToolchain.cmake":
        "a60f00fd9d87176cdf3dfec3e4a0513ce93c6ecbd4de262761c386981389a132",
    "cmake/CxetExchangeSelection.cmake":
        "96abe2efdbe0a2d5dd5dd2d08d5aada2a130de3f48a7a36b53628c2dde15bd07",
    "apps/trading-core/cmake/GenerateStrategyRegistry.cmake":
        "48b4b2bee540ec07a2c729c90b52202584c4d1496348734f3ccab1a970316dfa",
    "cmake/SanitizeCRLF.cmake":
        "8f6b036c09f6fb56771c17ab107bac02e95612451b9ea8c82714671deba3c6db",
    "cmake/Vendor/mbedtls-cold/AdaptX509.cmake":
        "07dc772971d2948eec280eb8264a5814d1f5aa12a495fbf73f571480fa3f58c3",
    "extra/mbedtls-cold/library/x509.c":
        "cdd67a9f53f3029c712cfd843038ffaf25dc477f9de215f55e585a15bc164995",
    'apps/hft-parser/tests/Contracts/BoundaryTests.sh':
        "444db65695e086a8a93f7eb5195fd2005b8ac5b77eab849f2e07f594e144164f",
    "apps/hft-parser/scripts/check-source-ownership.sh":
        "e7021d205c439ba7fc1771d336c81e6179dd443870047f2a1946980c9dfa76f1",
    "apps/hft-parser/tests/offline/Launcher/launcher-storage-authority.py":
        "9f569e4f822b4f7d0f44af1053573b3a690cc3bc95e4f10e0d8376b6842b8ca7",
    "apps/hft-recorder/CMakeLists.txt":
        "9233df56db22f02a13d27e0f589bbb6b9a407d84f95d15025919a163a7c206a8",
    "src/benchmarks/MarketIngress/tests/TestManifestContract.py":
        "560f6a35a2f90d3a3cebf65c5ffc2137cd87c4962983c44adb96c85be5ea9f52",
    "src/benchmarks/MarketIngress/ManifestContract.py":
        "56cea8165d78201fafbddfb655e9db9867955569a9683984c63392d97d6ceb9e",
    "tools/Codex/CheckNativeBoundaries.sh":
        "0b69ed4b0a056ea45736b9205e9652db7630eb8663278a48bb3420f98106533e",
    "tools/Codex/CheckExchangeStructure.sh":
        "335116eaa8163d86a5fc6fd21668d34beeb0e78c1b6848e4b63733b32b1c0617",
    "tools/Codex/CheckVersionNaming.sh":
        "04487eb81c6dcad84f6c5545effbb09022d39a219cc453ee6ed9172dac064bca",
    "tools/Codex/VersionNamingAllowlist.txt":
        "1c7656fd3653d9a5a174e79e6f74cdb627f0140f12628411f0d82b2d5cf3415a",
    "apps/vetron/frontend/package.json":
        "e0adddc5eef0c06860e4bd46aa0e6132d1c386b7b56288b299d96f92c80a9d23",
    "apps/vetron/CMakeLists.txt":
        "21cf4250a5d1b3842df1ada7c2cb9cae84befc7396075595cb7021b5b37a80e5",
    "apps/vetron/frontend/BuildFrontend.py":
        "95d5750d660d60b35ed7d3b539c5ba6ae9cd447400f9a27584b9dede22196e81",
    "apps/vetron/frontend/ProfilePaths.py":
        "03523102f3ca65ec06a49d73ad70a12e463811f462918c3d3dd4e6da2cf9a393",
    "apps/vetron/frontend/package-lock.json":
        "db8613b81892a095ac3cdbaa48c3a517cd2cd83ff800007b54ebf9cecd05aa45",
    "apps/vetron/frontend/vite.config.ts":
        "411bd3becc6811d386900ece2072e4291cd121b2535ae287f53c6dd21f85038b",
    "apps/vetron/frontend/vite.generated.ts":
        "438b7a61ab45302928eb7c8342e330a4f9948ae0b81497bcfc710a5776cdc76b",
    "apps/vetron/frontend/tsconfig.base.json":
        "976736c0ba488a73123ebb8a114e7738502c1826ef52b971c6e7cb1ba39d26e4",
    "apps/vetron/frontend/tsconfig.json":
        "4c194db757ee604a8574e7452f8be46e0b4420d603041df23b7bc1efc0ef9a65",
    "apps/vetron/frontend/tsconfig.worker.json":
        "77f151f4ade9f72aead78a91ff40f9991f9e7d90683ed8d53564c4cb0d3f3c76",
    "apps/vetron/scripts/GenerateHistoryCatalog.mjs":
        "53fd33f85cebcebb29779825475139739ea83cf2fab1d49f794d98966be5491d",
    "apps/vetron/scripts/GenerateTradingCostProfile.mjs":
        "88e78c109789c3307fc90830bf26080c1b72858a43f7db3529938292cfe340ab",
    "apps/vetron/scripts/Lib/SplitCppMacroArguments.mjs":
        "1d568efad1b8bbcbdfb988d387797fb10dba704c8345bd4684b96dfbd931e434",
    "apps/vetron/scripts/Lib/CppStringConstant.mjs":
        "ef6164ad3e71b782deb9b9ff7ce2b1f9941e3da86f56c987d87f62425e880452",
}

_TREE_POLICIES = {
    "vetron_frontend": (
        "apps/vetron/frontend",
        frozenset({".git", "build", "dist", "node_modules"}),
        "d1ddec3ac53a0a13716377fe785177213929aad3d6dda734d3603a102e60dc40",
    ),
    "liburing_vendor": (
        "extra/liburing",
        # The library/configure authority excludes the documentation-only
        # manpage symlink forest. Executed scripts and compiled inputs remain
        # byte-for-byte covered.
        frozenset({".git", "man"}),
        "3f6d720cbf91b22fca1ba85700a58c88f9563682d19c4494ac82ab6eb6658e39",
    ),
}

# Vendored add_subdirectory executes more than its entry CMakeLists: included
# CMake fragments, templates, generated-source inputs and configure helpers can
# all alter declarations or compiled inputs.  Authority is therefore the full
# regular source tree, excluding only VCS metadata, with an exact file count.
_EXTERNAL_AUTHORITY_POLICIES = {
    "secp256k1": (
        "extra/secp256k1", 177,
        "3494b587b4184b805cf8bb16007ac11e377dae37870d8c54a8292459ab215eb0",
    ),
    # Root gitlink 54fac219c4ef0bc379dfffb0b8098725d77ac81b; manifest
    # recomputed from committed blobs and matched against the clean checkout.
    "abseil-cpp": (
        "extra/abseil-cpp", 1517,
        "944e27208b3a31e25636c9989f1c1ab472b12cf530f36d7c6b06a41b644a3367",
    ),
}


def _file_sha256(path: Path, *, boundary: Path | None = None) -> str | None:
    if not _unsymlinked_regular_path(path, ROOT if boundary is None else boundary):
        return None
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _unsymlinked_regular_path(path: Path, boundary: Path) -> bool:
    """Accept only a lexical regular path with no symlink component."""
    try:
        relative = path.relative_to(boundary)
        boundary_resolved = boundary.resolve(strict=True)
    except (OSError, ValueError):
        return False
    current = boundary
    try:
        if current.is_symlink() or not current.is_dir():
            return False
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        return (
            current.is_file() and
            current.resolve(strict=True).is_relative_to(boundary_resolved)
        )
    except OSError:
        return False


def unsymlinked_regular_path(path: Path, boundary: Path = ROOT) -> bool:
    """Public structural guard for repository-owned regular files."""
    return _unsymlinked_regular_path(path, boundary)


def unsymlinked_directory_path(path: Path, boundary: Path = ROOT) -> bool:
    """Accept a lexical directory only when no component is a symlink."""
    try:
        relative = path.relative_to(boundary)
        boundary_resolved = boundary.resolve(strict=True)
    except (OSError, ValueError):
        return False
    current = boundary
    try:
        if current.is_symlink() or not current.is_dir():
            return False
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                return False
        return (
            current.is_dir() and
            current.resolve(strict=True).is_relative_to(boundary_resolved)
        )
    except OSError:
        return False


def _regular_tree_entries(
    tree: Path,
    excluded_parts: frozenset[str],
) -> tuple[tuple[Path, ...], tuple[Path, ...]] | None:
    """Enumerate non-excluded directories/files without following aliases."""
    try:
        tree_relative = tree.relative_to(ROOT)
    except ValueError:
        return None
    current = ROOT
    try:
        for part in tree_relative.parts:
            current /= part
            if current.is_symlink():
                return None
        if not current.is_dir():
            return None
    except OSError:
        return None

    directories: list[Path] = []
    paths: list[Path] = []
    traversal_failed = False

    def walk_error(_: OSError) -> None:
        nonlocal traversal_failed
        traversal_failed = True

    for current_name, directory_names, file_names in os.walk(
            tree, followlinks=False, onerror=walk_error):
        current_path = Path(current_name)
        kept_directories: list[str] = []
        for name in sorted(directory_names):
            if name in excluded_parts:
                continue
            path = current_path / name
            try:
                if (path.is_symlink() or not path.is_dir() or
                        not unsymlinked_directory_path(path, tree)):
                    return None
                directories.append(path)
                kept_directories.append(name)
            except OSError:
                return None
        directory_names[:] = kept_directories
        for name in sorted(file_names):
            if name in excluded_parts:
                continue
            path = current_path / name
            if not _unsymlinked_regular_path(path, tree):
                return None
            paths.append(path)
    if traversal_failed:
        return None
    return tuple(directories), tuple(paths)


def _regular_tree_paths(
    tree: Path,
    excluded_parts: frozenset[str],
) -> tuple[Path, ...] | None:
    entries = _regular_tree_entries(tree, excluded_parts)
    return None if entries is None else entries[1]


def _tree_manifest(
    tree: Path,
    excluded_parts: frozenset[str],
) -> tuple[int, bytes] | None:
    entries = _regular_tree_entries(tree, excluded_parts)
    if entries is None:
        return None
    directories, paths = entries
    directory_set = frozenset(directories)
    manifest = bytearray()
    # Use lexical repository paths, independent of pathlib component ordering.
    # This matches the committed-tree manifest used to review the vendor pins.
    for path in sorted((*directories, *paths),
                       key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        try:
            raw_relative = os.fsencode(relative)
            if (re.search(rb"[\x00-\x1f\x7f]", raw_relative) is not None or
                    raw_relative.decode("utf-8") != relative):
                return None
        except (UnicodeError, ValueError):
            return None
        if path in directory_set:
            manifest.extend(f"D  {relative}\n".encode("utf-8"))
            continue
        digest = _file_sha256(path)
        if digest is None:
            return None
        manifest.extend(f"F {digest}  {relative}\n".encode("utf-8"))
    return len(paths), bytes(manifest)


def reviewed_file_identity(relative: str, *, root: Path | None = None) -> bool:
    expected = _FILE_DIGESTS.get(relative)
    selected_root = ROOT if root is None else root
    if expected is None or _file_sha256(selected_root / relative, boundary=selected_root) != expected:
        return False
    # The offline driver delegates resource admission to this reviewed helper.
    return (relative != 'tools/Testing/RunOffline.py' or
            reviewed_file_identity('tools/Build/ParallelPolicy.py', root=selected_root))


def reviewed_tree_identity(name: str) -> bool:
    policy = _TREE_POLICIES.get(name)
    if policy is None:
        return False
    relative, excluded_parts, expected = policy
    tree = ROOT / relative
    subject = _tree_manifest(tree, excluded_parts)
    if subject is None:
        return False
    _, manifest = subject
    return hashlib.sha256(manifest).hexdigest() == expected


def reviewed_external_authority(name: str) -> bool:
    """Verify one full vendored source authority by canonical manifest."""
    policy = _EXTERNAL_AUTHORITY_POLICIES.get(name)
    if policy is None:
        return False
    relative, expected_count, expected_digest = policy
    tree = ROOT / relative
    subject = _tree_manifest(tree, frozenset({".git"}))
    if subject is None:
        return False
    file_count, manifest = subject
    if file_count != expected_count:
        return False
    return hashlib.sha256(manifest).hexdigest() == expected_digest


def reviewed_external_authority_paths(name: str) -> tuple[str, ...]:
    """Expose the exact full-tree subject to formal-review scope builders."""
    policy = _EXTERNAL_AUTHORITY_POLICIES.get(name)
    if policy is None:
        return ()
    tree = ROOT / policy[0]
    paths = _regular_tree_paths(tree, frozenset({".git"}))
    if paths is None:
        return ()
    return tuple(sorted(
        path.relative_to(ROOT).as_posix()
        for path in paths
    ))
