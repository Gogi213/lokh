"""Protected verification-friend and source-identity inventory policy."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from CMake.Policy.CmakeFamilyCommandPolicy import safe_compile_option
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from Family.Sources.CxetFamilyOfflineSourcePolicy import startup_resident_external_include
from Family.Sources.CxetFamilyIncludeInputs import IncludeInputs
from Family.Sources.CxetFamilyCppPolicy import (
    CPP_ASSEMBLY_SUFFIXES as _CPP_ASSEMBLY_SUFFIXES,
    CPP_NON_TEXTUAL_INCLUDE_SUFFIXES as _CPP_NON_TEXTUAL_INCLUDE_SUFFIXES,
    CPP_SCAN_SUFFIXES as _CPP_SCAN_SUFFIXES,
    CPP_TEXTUAL_INCLUDE_SUFFIXES as _CPP_TEXTUAL_INCLUDE_SUFFIXES,
    approved_external_angle_include as _approved_external_angle_include,
    cpp_include_syntax as _cpp_include_syntax,
    cpp_phase_two as _cpp_phase_two,
)
from Family.Targets.CxetFamilyTargetPolicy import (
    ROOT,
    _VERIFICATION_OPTIONAL_SOURCE_ROOTS,
    _VERIFICATION_SOURCE_CANDIDATE_ROOTS,
    _VERIFICATION_SOURCE_ROOTS,
    _VERIFICATION_TARGET_PRIVATE_INCLUDE_ROOTS,
    _VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS,
    _exported_include_allowed,
    _generated_verification_path,
    _include_path_syntax_error,
    _reviewed_recorder_source,
    _unsymlinked_repo_path,
    _validate_cpp_include_microcases,
    _verification_source_root,
    unsafe_compile_definition_carriers,
    verification_unresolved_quoted_inventory,
)
from Family.Verification.CxetFamilyVerificationInventory import (
    VERIFICATION_FRIEND_DEFINE as _VERIFICATION_FRIEND_DEFINE,
    VERIFICATION_FRIEND_IDENTIFIERS as _VERIFICATION_FRIEND_IDENTIFIERS,
    VERIFICATION_FRIEND_SOURCE_LINES as _VERIFICATION_FRIEND_SOURCE_LINES,
    VERIFICATION_PROTECTED_FRIEND_LINES as _VERIFICATION_PROTECTED_FRIEND_LINES,
    VERIFICATION_PROTECTED_SHA256 as _VERIFICATION_PROTECTED_SHA256,
    VERIFICATION_RETIRED_SEAM_PATHS as _VERIFICATION_RETIRED_SEAM_PATHS,
    VERIFICATION_UNRESOLVED_DORMANT_ONLY as
        _VERIFICATION_UNRESOLVED_DORMANT_ONLY,
    VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS as
        _VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS,
    VERIFICATION_UNRESOLVED_GENERATED_ROOTS as
        _VERIFICATION_UNRESOLVED_GENERATED_ROOTS,
    VERIFICATION_UNRESOLVED_QUOTED_INCLUDES as
        _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES,
)


_MAX_VERIFICATION_MACRO_SOURCE_BYTES = 16 * 1024 * 1024
_MAX_VERIFICATION_SNAPSHOT_PROBES = 131072


class _VerificationSnapshotLimit(OSError):
    """A terminal source-audit bound, never a recoverable file diagnostic."""


class _VerificationSourceInputs(IncludeInputs):
    """One bounded immutable input snapshot for the physical source audit."""

    def __init__(self):
        super().__init__(ROOT)
        self.payload_bytes = 0

    def probe(self, path):
        if path not in self.probes and len(self.probes) >= _MAX_VERIFICATION_SNAPSHOT_PROBES:
            raise _VerificationSnapshotLimit(
                f"verification source snapshot exceeds {_MAX_VERIFICATION_SNAPSHOT_PROBES} path probes")
        return super().probe(path)

    def read(self, relative, *, max_bytes=None):
        if relative in self.files:
            return super().read(relative, max_bytes=max_bytes)
        if len(self.files) >= 32768:
            raise OSError("verification source snapshot exceeds 32768 files")
        remaining = 256 * 1024 * 1024 - self.payload_bytes
        bound = min(_MAX_VERIFICATION_MACRO_SOURCE_BYTES, remaining)
        if max_bytes is not None:
            bound = min(bound, max_bytes)
        data = super().read(relative, max_bytes=bound)
        self.payload_bytes += len(data)
        return data


@dataclass(frozen=True)
class VerificationSourceAudit:
    inputs: _VerificationSourceInputs
    include_boundaries: bool
    failures: tuple[str, ...]

    def validate(self, errors):
        errors.extend(self.inputs.validate())


def capture_verification_source_audit(errors, *, check_include_boundaries=False, syntax_memo=None):
    inputs = _VerificationSourceInputs()
    failures = []
    try:
        validate_verification_source_macro_inventory(failures,
            check_include_boundaries=check_include_boundaries, syntax_memo=syntax_memo,
            source_inputs=inputs)
    except _VerificationSnapshotLimit as exc:
        failures.append(str(exc))
    failures.extend(inputs.validate())
    errors.extend(failures)
    return VerificationSourceAudit(inputs, check_include_boundaries, tuple(failures))


def _bounded_verification_source_bytes(
    path: Path,
    relative: str,
    errors: list[str],
) -> bytes | None:
    """Read one macro source with a hard allocation bound and stable size."""
    try:
        path_size = path.stat().st_size
    except OSError as exc:
        errors.append(
            f"cannot inspect verification macro source {relative}: {exc}")
        return None
    if path_size > _MAX_VERIFICATION_MACRO_SOURCE_BYTES:
        errors.append(
            f"{relative}: verification macro source is {path_size} bytes; "
            "bounded scan limit is "
            f"{_MAX_VERIFICATION_MACRO_SOURCE_BYTES} bytes")
        return None

    try:
        with path.open("rb") as source:
            opened_size = os.fstat(source.fileno()).st_size
            if opened_size > _MAX_VERIFICATION_MACRO_SOURCE_BYTES:
                errors.append(
                    f"{relative}: verification macro source is "
                    f"{opened_size} bytes; bounded scan limit is "
                    f"{_MAX_VERIFICATION_MACRO_SOURCE_BYTES} bytes")
                return None
            data = source.read(opened_size + 1)
            final_size = os.fstat(source.fileno()).st_size
    except OSError as exc:
        errors.append(
            f"cannot inspect verification macro source {relative}: {exc}")
        return None

    if (opened_size != final_size or len(data) != opened_size):
        errors.append(
            f"{relative}: verification macro source changed size during "
            f"bounded scan: opened={opened_size}, final={final_size}, "
            f"read={len(data)}")
        return None
    return data


def validate_verification_source_read_microcases(
    errors: list[str],
) -> None:
    """Prove an oversized unknown-suffix file is rejected before opening."""
    class OversizedUnknownSource:
        opened = False

        @staticmethod
        def stat():
            class Stat:
                st_size = _MAX_VERIFICATION_MACRO_SOURCE_BYTES + 1
            return Stat()

        def open(self, _mode: str):
            self.opened = True
            raise OSError("oversized source must not be opened")

    relative = "verification-source-read-microcase"
    expected = (
        f"{relative}: verification macro source is "
        f"{_MAX_VERIFICATION_MACRO_SOURCE_BYTES + 1} bytes; bounded scan "
        f"limit is {_MAX_VERIFICATION_MACRO_SOURCE_BYTES} bytes")
    probe = OversizedUnknownSource()
    failures: list[str] = []
    data = _bounded_verification_source_bytes(
        probe, relative, failures)  # type: ignore[arg-type]
    if data is not None or probe.opened or failures != [expected]:
        errors.append(
            "verification source read self-check did not reject an "
            "oversized unknown-suffix file before opening it")


def validate_compile_definition_carrier_microcases(
    errors: list[str],
) -> None:
    """Keep every unresolved macro-producing channel fail-closed."""
    unsafe = (
        "${CXET_UNRESOLVED_DEFINES}",
        "$CACHE{CXET_UNRESOLVED_DEFINES}",
        "$ENV{CXET_UNRESOLVED_DEFINES}",
        "$<TARGET_PROPERTY:attacker,INTERFACE_COMPILE_DEFINITIONS>",
        "$<GENEX_EVAL:$ENV{CXET_UNRESOLVED_DEFINES}>",
        "$<TARGET_GENEX_EVAL:attacker,$<TARGET_PROPERTY:attacker,"
        "INTERFACE_COMPILE_DEFINITIONS>>",
    )
    for value in unsafe:
        if not unsafe_compile_definition_carriers(
                object(), "nonfriend", (value,)):
            errors.append(
                "verification compile-definition carrier self-check "
                f"accepted {value}")
    for value in ("CXET_LITERAL_DEFINE=1", "ASM=1", "IMPORT=1", "MODULE=1"):
        if unsafe_compile_definition_carriers(
                object(), "nonfriend", (value,)):
            errors.append(
                "verification compile-definition carrier self-check "
                f"rejected literal definition {value}")
    for value in (
        "private=public", "protected=public", "friend=public",
        "ACCESS=public", "K=private", "F=friend",
    ):
        if not unsafe_compile_definition_carriers(
                object(), "nonfriend", (value,)):
            errors.append(
                "verification compile-definition carrier self-check "
                f"accepted access rewrite {value}")
    for value in (
        'ASM_PAYLOAD=__asm__(".incbin foreign.bin")',
        "ASM_KEYWORD=__asm__",
        "ASM_PASTE=__as##m__",
        "ASM_DIGRAPH_PASTE=__as%:%:m__",
        r"ASM_ESCAPED_PASTE=__as\#\#m__",
        "ASM_CONTINUED=__a\\\nsm__",
        r"ASM_ESCAPED_GENEX=$\<JOIN:__as;m__,>",
        "MODULE_KEYWORD=import",
        "MODULE_PASTE=im##port",
        "MODULE_PRAGMA=_Pragma",
        "FILE_PROBE=__has_include",
        "FILE_PROBE_NEXT=__has_include_next",
        "EMBED_PROBE=__has_embed",
        "SYSTEM_CONCAT=__CONCAT(as,m)",
    ):
        if not unsafe_compile_definition_carriers(
                object(), "nonfriend", (value,)):
            errors.append(
                "verification compile-definition carrier self-check "
                f"accepted inline assembler carrier {value}")


def _reserved_verification_compile_option(value: str) -> bool:
    """Detect define/undef spellings after CMake has expanded the value."""
    return (
        any(identifier in value for identifier in (
            _VERIFICATION_FRIEND_DEFINE,
            *_VERIFICATION_FRIEND_IDENTIFIERS,
        )) and
        any(prefix in value for prefix in (
            "-D", "-U", "/D", "/U", "/d", "/u"))
    )


def validate_verification_compile_option_microcases(
    errors: list[str],
) -> None:
    """Prove split CMake values cannot mutate the reserved friend macro."""
    head = "CXET_FAMILY_DIFFERENTIAL_"
    tail = "TESTING=1"
    expanded = head + tail
    cases = (
        ("target_compile_options split define", f"-D{expanded}"),
        ("target_compile_options split undef", f"-U{expanded}"),
        ("target COMPILE_OPTIONS split define", f"/D{expanded}"),
        ("target COMPILE_OPTIONS split undef", f"/U{expanded}"),
    )
    for label, option in cases:
        if safe_compile_option(option):
            errors.append(
                f"verification compile-option self-check accepted {label}")
        if not _reserved_verification_compile_option(option):
            errors.append(
                f"verification compile-option self-check missed {label}")
    for identifier in _VERIFICATION_FRIEND_IDENTIFIERS:
        for spelling in (f"-D{identifier}=1", f"-U{identifier}"):
            if not _reserved_verification_compile_option(spelling):
                errors.append(
                    "verification compile-option self-check missed protected "
                    f"friend identifier {spelling}")


def validate_verification_source_macro_inventory(
    errors: list[str],
    *,
    check_include_boundaries: bool = True,
    syntax_memo=None,
    source_inputs=None,
) -> None:
    """Pin the unconditional friend seam and forbid its retired build macro."""
    legacy_actual: dict[str, list[str]] = {}
    friend_actual: dict[str, list[str]] = {}
    protected_friend_actual: dict[str, list[str]] = {}
    protected_hash_seen: set[str] = set()
    unresolved_quoted_seen: set[tuple[str, str]] = set()
    source_seen: set[str] = set()
    def snapshot_probe(path):
        if source_inputs is not None:
            try:
                source_inputs.probe(path)
                # A missing leaf can be created and removed again. Retain
                # its nearest existing directory to detect that restoration
                # through the directory's ctime, including unscanned roots.
                ancestor = path.parent
                while ancestor.is_relative_to(ROOT):
                    if source_inputs.probe(ancestor):
                        break
                    ancestor = ancestor.parent
            except _VerificationSnapshotLimit:
                raise
            except OSError as exc:
                errors.append(f"verification source snapshot: {exc}")
    token = _VERIFICATION_FRIEND_DEFINE.encode("ascii")
    friend_tokens = tuple(
        value.encode("ascii") for value in _VERIFICATION_FRIEND_IDENTIFIERS)

    validate_verification_source_read_microcases(errors)
    _validate_cpp_include_microcases(errors)
    for relative in _VERIFICATION_RETIRED_SEAM_PATHS:
        snapshot_probe(ROOT / relative)
        if (ROOT / relative).exists() or (ROOT / relative).is_symlink():
            errors.append(f"retired verification seam path reappeared: {relative}")

    for newline in (b"\n", b"\r\n"):
        spliced = b"CXET_FAMILY_DIFFERENTIAL_\\" + newline + b"TESTING"
        if token not in _cpp_phase_two(spliced):
            errors.append(
                "verification source macro phase-two self-check missed "
                f"{newline!r} splicing")

    def include_boundary_error(
        path: Path,
        include: str,
        quoted: bool,
    ) -> str | None:
        syntax_failure = _include_path_syntax_error(include, quoted=quoted)
        if syntax_failure is not None:
            return syntax_failure
        owner = _verification_source_root(path)
        if owner is None:
            return "quoted include has no reviewed source owner"
        source_relative = path.resolve().relative_to(
            ROOT.resolve()).as_posix()
        local_candidate = path.parent / include
        local_exists = (
            quoted and
            (local_candidate.exists() or local_candidate.is_symlink()))
        candidates = [local_candidate] if local_exists else []
        if not local_exists and not Path(include).is_absolute():
            candidates.append(ROOT / include)
            for candidate_owner in sorted(
                    _VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS):
                candidates.extend(
                    ROOT / root / include
                    for root in sorted(
                        _VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS[
                            candidate_owner]))
            candidates.extend(
                ROOT / root / include
                for prefix, roots in
                _VERIFICATION_SOURCE_CANDIDATE_ROOTS.items()
                if (source_relative == prefix or
                    source_relative.startswith(prefix + "/"))
                for root in roots)
        resolved: list[str] = []
        for candidate in dict.fromkeys(candidates):
            snapshot_probe(candidate)
            if not candidate.exists() and not candidate.is_symlink():
                continue
            if not _unsymlinked_repo_path(candidate):
                return f"include uses a symlinked repository path: {include}"
            try:
                relative = candidate.resolve().relative_to(
                    ROOT.resolve()).as_posix()
            except (OSError, ValueError):
                return f"include escapes repository: {include}"
            if _generated_verification_path(relative):
                return f"include enters generated tree: {relative}"
            if not candidate.resolve().is_file():
                return f"include does not name a regular file: {relative}"
            suffix = Path(relative).suffix.lower()
            if suffix in _CPP_NON_TEXTUAL_INCLUDE_SUFFIXES:
                return f"include names compiled source: {relative}"
            if suffix not in _CPP_TEXTUAL_INCLUDE_SUFFIXES:
                return (
                    "include has an unreviewed textual suffix: "
                    f"{relative}")
            resolved.append(relative)
        resolved = list(dict.fromkeys(resolved))
        if not resolved:
            if not quoted:
                if (_approved_external_angle_include(include) or
                        startup_resident_external_include(source_relative, include)):
                    return None
                return f"unresolved angle include is not reviewed: {include}"
            if include in _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES.get(
                    source_relative, frozenset()):
                unresolved_quoted_seen.add((source_relative, include))
                return None
            return f"unresolved quoted include is not reviewed: {include}"
        if len(resolved) != 1:
            return f"include resolves ambiguously: {include}: {resolved}"
        foreign = [
            relative for relative in resolved
            if not _exported_include_allowed(
                owner, source_relative, relative)
        ]
        if foreign:
            return (
                f"quoted include crosses source ownership from {owner}: "
                f"{foreign}")
        return None

    def unresolved_inventory_repo_hits(
        source_path: Path,
        include: str,
    ) -> tuple[str, ...]:
        """Prove an allowlisted provider/generated spelling has no repo shim."""
        root_values = {
            value
            for values in _VERIFICATION_TARGET_PUBLIC_INCLUDE_ROOTS.values()
            for value in values
        } | {
            value
            for values in _VERIFICATION_TARGET_PRIVATE_INCLUDE_ROOTS.values()
            for value in values
        } | {
            value
            for values in _VERIFICATION_SOURCE_CANDIDATE_ROOTS.values()
            for value in values
        }
        candidates = [source_path.parent / include, ROOT / include]
        candidates.extend(ROOT / value / include for value in root_values)
        hits: list[str] = []
        for candidate in dict.fromkeys(candidates):
            snapshot_probe(candidate)
            if not candidate.exists() and not candidate.is_symlink():
                continue
            try:
                relative = candidate.relative_to(ROOT).as_posix()
            except ValueError:
                relative = candidate.as_posix()
            hits.append(relative)
        return tuple(hits)

    for root_relative in _VERIFICATION_SOURCE_ROOTS:
        source_root = ROOT / root_relative
        snapshot_probe(source_root)
        if source_root.is_symlink():
            errors.append(
                f"verification source macro root is symlinked: {root_relative}")
            continue
        if not source_root.is_dir():
            if root_relative in _VERIFICATION_OPTIONAL_SOURCE_ROOTS:
                continue
            errors.append(
                f"verification source macro root is missing: {root_relative}")
            continue
        if not _unsymlinked_repo_path(source_root):
            errors.append(
                "verification source macro root has a symlinked component: "
                f"{root_relative}")
            continue

        def walk_error(exc: OSError) -> None:
            location = (
                str(exc.filename) if exc.filename is not None else
                source_root.as_posix())
            errors.append(
                "cannot enumerate verification source macro root "
                f"{root_relative} at {location}: {exc}")

        for directory, directories, filenames in os.walk(
                source_root, followlinks=False, onerror=walk_error):
            snapshot_probe(Path(directory))
            retained_directories: list[str] = []
            for name in sorted(directories):
                candidate_directory = Path(directory) / name
                candidate_relative = candidate_directory.relative_to(
                    ROOT).as_posix()
                if (name.casefold() in {".git", "node_modules"} or
                        _generated_verification_path(candidate_relative)):
                    continue
                if (candidate_directory.is_symlink() or
                        not candidate_directory.is_dir() or
                        not _unsymlinked_repo_path(candidate_directory)):
                    errors.append(
                        "verification source directory is not an "
                        "unsymlinked repository directory: "
                        f"{candidate_relative}")
                    continue
                retained_directories.append(name)
                snapshot_probe(candidate_directory)
            directories[:] = retained_directories
            for filename in sorted(filenames):
                path = Path(directory) / filename
                relative = path.relative_to(ROOT).as_posix()
                if (path.is_symlink() or not path.is_file() or
                        not _unsymlinked_repo_path(path)):
                    errors.append(
                        "verification source path is not an unsymlinked "
                        f"regular repository file: {relative}")
                    continue
                if (relative.startswith("apps/hft-recorder/") and
                        not _reviewed_recorder_source(relative)):
                    continue
                if relative in source_seen:
                    continue
                if source_inputs is not None and len(source_seen) >= 32768:
                    errors.append("verification source snapshot exceeds 32768 files")
                    return
                source_seen.add(relative)
                if source_inputs is None:
                    data = _bounded_verification_source_bytes(path, relative, errors)
                else:
                    try:
                        source_inputs.regular_relative(path)
                        data = source_inputs.read(relative)
                    except _VerificationSnapshotLimit:
                        raise
                    except (OSError, ValueError) as exc:
                        errors.append(f"verification source snapshot: {exc}")
                        continue
                if data is None:
                    continue
                expected_hash = _VERIFICATION_PROTECTED_SHA256.get(relative)
                if expected_hash is not None:
                    protected_hash_seen.add(relative)
                    if hashlib.sha256(data).hexdigest() != expected_hash:
                        errors.append(
                            f"{relative}: exact protected test/friend seam "
                            "identity changed")
                normalized = _cpp_phase_two(data)
                if relative in _VERIFICATION_PROTECTED_FRIEND_LINES:
                    try:
                        protected_friend_actual[relative] = [
                            line.strip() for line in normalized.decode("utf-8").splitlines()
                            if re.search(r"\bfriend\b", line)]
                    except UnicodeError:
                        errors.append(f"{relative}: non-UTF8 protected runtime friend surface")
                suffix = path.suffix.lower()
                if suffix in _CPP_ASSEMBLY_SUFFIXES:
                    errors.append(
                        f"{relative}: assembly verification source is "
                        "unsupported because textual include/incbin ownership "
                        "is not modeled")
                    continue
                if suffix in _CPP_SCAN_SUFFIXES:
                    normalized, includes, include_failures = (
                        _cpp_include_syntax(data) if syntax_memo is None else
                        syntax_memo.full_syntax(relative, data))
                    errors.extend(
                        f"{relative}: {failure}"
                        for failure in include_failures)
                    for include_bytes, quoted in includes:
                        if not check_include_boundaries:
                            try:
                                include = include_bytes.decode("utf-8")
                            except UnicodeError:
                                continue
                            if (quoted and include in
                                    _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES.get(
                                        relative, frozenset())):
                                hits = unresolved_inventory_repo_hits(
                                    path, include)
                                if hits:
                                    errors.append(
                                        f"{relative}: reviewed unresolved "
                                        "include gained repository shadow "
                                        f"{include}: {list(hits)}")
                                else:
                                    unresolved_quoted_seen.add(
                                        (relative, include))
                            continue
                        try:
                            include = include_bytes.decode("utf-8")
                        except UnicodeError:
                            errors.append(
                                f"{relative}: non-UTF8 include path")
                            continue
                        failure = include_boundary_error(
                            path, include, quoted)
                        if failure is not None:
                            errors.append(f"{relative}: {failure}")
                if (token not in normalized and
                        not any(value in normalized for value in friend_tokens)):
                    continue
                try:
                    lines = normalized.decode("utf-8").splitlines()
                except UnicodeError:
                    if token in normalized:
                        legacy_actual[relative] = [
                            "<non-UTF8 retired-token occurrence>"]
                    if any(value in normalized for value in friend_tokens):
                        friend_actual[relative] = [
                            "<non-UTF8 verification-friend occurrence>"]
                    continue
                legacy_occurrences = [
                    line.strip()
                    for line in lines
                    for _ in range(line.count(_VERIFICATION_FRIEND_DEFINE))
                    if _VERIFICATION_FRIEND_DEFINE in line
                ]
                friend_occurrences = [
                    line.strip()
                    for line in lines
                    for identifier in _VERIFICATION_FRIEND_IDENTIFIERS
                    for _ in range(line.count(identifier))
                    if identifier in line
                ]
                if legacy_occurrences:
                    legacy_actual[relative] = legacy_occurrences
                if friend_occurrences:
                    friend_actual[relative] = friend_occurrences
    if legacy_actual:
        errors.append(
            "retired CXET family differential build macro reappeared: "
            f"{legacy_actual}")
    unresolved_quoted_expected = {
        (relative, include)
        for relative, includes in
        _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES.items()
        for include in includes
    }
    if unresolved_quoted_seen != unresolved_quoted_expected:
        errors.append(
            "reviewed unresolved quoted include inventory changed: "
            f"expected={sorted(unresolved_quoted_expected)}, "
            f"actual={sorted(unresolved_quoted_seen)}")
    friend_expected = {
        relative: list(lines)
        for relative, lines in _VERIFICATION_FRIEND_SOURCE_LINES.items()
    }
    if friend_actual != friend_expected:
        errors.append(
            "unconditional CXET family verification friend inventory "
            f"changed: expected={friend_expected}, actual={friend_actual}")
    protected_friend_expected = {
        relative: list(lines)
        for relative, lines in _VERIFICATION_PROTECTED_FRIEND_LINES.items()
    }
    if protected_friend_actual != protected_friend_expected:
        errors.append(
            "protected runtime class friend declarations changed: "
            f"expected={protected_friend_expected}, "
            f"actual={protected_friend_actual}")
    missing_protected = sorted(
        set(_VERIFICATION_PROTECTED_SHA256) - protected_hash_seen)
    if missing_protected:
        errors.append(
            "protected test/friend seam files are missing from source "
            f"inventory: {missing_protected}")


def _validate_verification_macro_command_inventory(
    active_commands,
    errors: list[str],
) -> bool:
    """Require the retired differential macro to stay out of CMake."""
    found = [
        command for command in active_commands
        if any(
            _VERIFICATION_FRIEND_DEFINE in token
            for token in cmake_list_words(command.command.body))
    ]
    identities = [
        (command.command.line,
         tuple(cmake_list_words(command.command.body)))
        for command in found
    ]
    valid = not found
    if not valid:
        errors.append(
            "retired CXET family differential macro command inventory "
            f"changed: {identities}")
    return valid


def validate_verification_friend_inventory(
    instances,
    errors: list[str],
) -> frozenset[int]:
    """Reject every attempted reintroduction of the retired macro channel."""
    for instance in instances:
        raw = tuple(cmake_list_words(instance.body.command.body))
        flat = tuple(
            value for group in instance.token_groups for value in group)
        reserved_option_reference = any(
            _reserved_verification_compile_option(token)
            for token in (*raw, *flat))
        macro_reference = any(
            _VERIFICATION_FRIEND_DEFINE in token
            for token in (*raw, *flat))
        if reserved_option_reference or macro_reference:
            errors.append(
                f"{instance.body.relative}:{instance.body.command.line}: "
                "retired differential build macro uses "
                f"{instance.body.command.name}")
    return frozenset()


def validate_verification_friend_contract(
    active_commands,
    instances,
    errors: list[str],
    *,
    check_include_boundaries: bool = True,
    syntax_memo=None,
    source_audit=None,
) -> frozenset[int]:
    """Validate the macro-free friend seam; return no mutation exceptions."""
    failures: list[str] = []
    expected_unresolved = verification_unresolved_quoted_inventory()
    typed_unresolved = (
        _VERIFICATION_UNRESOLVED_DORMANT_ONLY |
        frozenset(_VERIFICATION_UNRESOLVED_EXTERNAL_TARGETS) |
        frozenset(_VERIFICATION_UNRESOLVED_GENERATED_ROOTS))
    if typed_unresolved != expected_unresolved:
        failures.append(
            "typed unresolved quoted include inventory changed: "
            f"missing={sorted(expected_unresolved - typed_unresolved)}, "
            f"extra={sorted(typed_unresolved - expected_unresolved)}")
    validate_compile_definition_carrier_microcases(failures)
    validate_verification_compile_option_microcases(failures)
    if source_audit is None:
        validate_verification_source_macro_inventory(
            failures, check_include_boundaries=check_include_boundaries,
            syntax_memo=syntax_memo)
    elif (not isinstance(source_audit, VerificationSourceAudit) or
            source_audit.include_boundaries != check_include_boundaries):
        failures.append("verification source audit mode/identity mismatch")
    else:
        failures.extend(source_audit.failures)
    macro_inventory_valid = _validate_verification_macro_command_inventory(
        active_commands, failures)
    validate_verification_friend_inventory(instances, failures)
    if not macro_inventory_valid or failures:
        errors.extend(failures)
    return frozenset()
