"""Invocation-local include inputs, with end-of-proof freshness validation."""

from pathlib import Path
import stat


def _identity(path: Path):
    try:
        value = path.lstat()
    except FileNotFoundError:
        return None
    return (value.st_dev, value.st_ino, value.st_mode, value.st_size,
            value.st_mtime_ns, value.st_ctime_ns)


class IncludeInputs:
    """Reuse only unchanged bytes; retain missing search candidates as inputs.

    Each owner retains this object for one proof and validates it before
    success. Profile include proofs keep independent instances; the physical
    source audit owns one invocation snapshot. Target/path and native-config
    semantics remain in the caller's independent traversal key.
    """

    def __init__(self, root: Path, *, max_regular_paths: int = 16384):
        if max_regular_paths <= 0:
            raise ValueError("regular-path cache bound must be positive")
        self.root = root
        self.files = {}
        self.probes = {}
        self._regular_paths = {}
        self._max_regular_paths = max_regular_paths
        self._resolved_root = None

    def probe(self, path: Path) -> bool:
        identity = _identity(path)
        if path in self.probes and self.probes[path] != identity:
            raise OSError(f"include candidate changed during proof: {path}")
        self.probes[path] = identity
        return identity is not None

    def _component(self, path: Path, *, directory: bool):
        self.probe(path)
        identity = self.probes[path]
        if (identity is None or stat.S_ISLNK(identity[2]) or
                not (stat.S_ISDIR(identity[2]) if directory else stat.S_ISREG(identity[2]))):
            raise OSError(f"nonregular/symlinked include path component: {path}")

    def _anchor_root(self):
        if self._resolved_root is not None:
            return
        if not self.root.is_absolute():
            raise OSError(f"nonabsolute include root: {self.root}")
        # Keep ancestors above the workspace too: a root rename/symlink swap
        # followed by restoration must invalidate its parent's ctime snapshot.
        for ancestor in (*reversed(self.root.parents), self.root):
            self._component(ancestor, directory=True)
        self._resolved_root = self.root.resolve(strict=True)

    def regular_relative(self, path: Path) -> str:
        """Reuse positive canonical spellings inside this one FS snapshot.

        Leaf probes stay fresh on every use. First resolution records all
        lexical directory facts before normalizing '..'; validate() rechecks
        them, including transient replacement/restoration via parent ctime.
        No include search, target, provider or negative fact is cached here.
        """
        # Do not let an outside path borrow a cached canonical spelling.
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise OSError(f"include path is outside its root: {path}") from exc
        self._anchor_root()
        self._component(path, directory=False)
        cached = self._regular_paths.get(path)
        if cached is not None:
            return cached
        current, depth = self.root, 0
        for index, part in enumerate(relative.parts):
            if part == "..":
                if depth == 0:
                    raise OSError(f"include path leaves its root: {path}")
                depth -= 1
            else:
                depth += 1
            current /= part
            self._component(current, directory=index + 1 < len(relative.parts))
        resolved = path.resolve(strict=True)
        try:
            canonical = resolved.relative_to(self._resolved_root).as_posix()
        except ValueError as exc:
            raise OSError(f"resolved include path is outside its root: {path}") from exc
        # Resolve must not silently race a leaf replacement.
        self._component(path, directory=False)
        if len(self._regular_paths) < self._max_regular_paths:
            self._regular_paths[path] = canonical
        return canonical

    def read(self, relative: str, *, max_bytes: int | None = None) -> bytes:
        if max_bytes is not None and max_bytes < 0:
            raise ValueError("include input byte bound must not be negative")
        if (Path(relative).is_absolute() or not relative or
                any(part in {"", ".", ".."} for part in relative.split("/"))):
            raise OSError(f"noncanonical include input: {relative}")
        path = self.root / relative
        if relative in self.files:
            data = self.files[relative][1]
            if max_bytes is not None and len(data) > max_bytes:
                raise OSError(f"include input exceeds {max_bytes} byte bound: {relative}")
            return data
        # Validate every component, not merely the final file. A directory
        # symlink must never turn a repository spelling into another authority.
        current = self.root
        for part in Path(relative).parts:
            if part == "..":
                raise OSError(f"parent traversal in include input: {relative}")
            current /= part
            identity = _identity(current)
            if identity is None or stat.S_ISLNK(identity[2]):
                raise OSError(f"missing/symlinked include input: {relative}")
            self.probes.setdefault(current, identity)
        before = _identity(path)
        if before is None or not stat.S_ISREG(before[2]):
            raise OSError(f"nonregular include input: {relative}")
        if max_bytes is None:
            data = path.read_bytes()
        else:
            if before[3] > max_bytes:
                raise OSError(f"include input exceeds {max_bytes} byte bound: {relative}")
            with path.open("rb") as source:
                data = source.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise OSError(f"include input exceeds {max_bytes} byte bound: {relative}")
        if _identity(path) != before:
            raise OSError(f"include input changed while reading: {relative}")
        self.files[relative] = (before, data)
        return data

    def validate(self) -> tuple[str, ...]:
        failures = []
        for path, identity in self.probes.items():
            try:
                if _identity(path) != identity:
                    failures.append(f"include candidate changed during proof: {path}")
            except OSError as exc:
                failures.append(f"cannot revalidate include candidate {path}: {exc}")
        for relative, (identity, data) in self.files.items():
            path = self.root / relative
            try:
                if _identity(path) != identity:
                    failures.append(f"include input changed during proof: {relative}")
                    continue
                with path.open("rb") as source:
                    current_data = source.read(len(data) + 1)
                if (current_data != data or _identity(path) != identity):
                    failures.append(f"include input changed during proof: {relative}")
            except OSError as exc:
                failures.append(f"cannot revalidate include input {relative}: {exc}")
        return tuple(failures)


def native_include_context(target, translation_unit, public_seed, bindings):
    """TU identity affects include semantics only through this exact config."""
    if ((target == "cxet_crypto" and
         translation_unit != "src/src/Core/src/Crypto/Rsa.cpp") or
            public_seed and target not in {"cxet_crypto_import", "cxet_tls_certificates"}):
        return None
    if (target == "cxet_offline_crypto_primitives" and
            translation_unit == "src/tests/offline/Primitives/Crypto/RsaTestAes.c" and target in bindings):
        return "src/src/Core/src/Crypto/RsaMbedConfig.h"
    return bindings.get(target)
