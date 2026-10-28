#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 - "$repo_root" <<'PY'
"""Bounded static policy scan; no product imports, tools or build evaluation."""
from pathlib import Path
import json
import os
import re
import sys

root = Path(sys.argv[1])
allowlist = root / "tools/Codex/VersionNamingAllowlist.txt"
if not allowlist.is_file():
    sys.exit("version naming check: missing tools/Codex/VersionNamingAllowlist.txt")
allowed = [re.compile(line) for line in allowlist.read_text().splitlines()
           if line.strip() and not line.lstrip().startswith("#")]
# Only this policy's implementation and deliberately invalid fixture strings are
# outside the ordinary token scan. Other tests still have their declarations
# scanned; quoted test inputs can describe a rejected old format.
policy_files = {"tools/Codex/CheckVersionNaming.sh",
                "tools/Codex/VersionNamingAllowlist.txt"}
ignored_directories = {".git", "node_modules", "dist", "extra", "third_party",
                       "generated", "__pycache__"}
source_suffixes = {".h", ".hpp", ".ipp", ".c", ".cc", ".cpp", ".cxx",
                   ".ts", ".tsx", ".js", ".mjs", ".cmake", ".sh", ".py",
                   ".json", ".toml", ".yaml", ".yml"}
identifier = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")
versioned = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*V[0-9]+[A-Za-z0-9_]*|"
                       r"[a-z][a-z0-9_]*_v[0-9]+[a-z0-9_]*)\Z")
version_path = re.compile(r"V[0-9]+|(?:^|[/_.-])v[0-9]+(?:[/_.-]|$)")
# Comments never establish a boundary. Tests may intentionally quote prohibited
# names. Keep declaration identifiers in tests, including fixture classes.
lexical = re.compile(
    r'(?P<comment>/\*.*?\*/|//[^\n]*|\#[^\n]*)|'
    r'(?P<string>\"\"\".*?\"\"\"|\'\'\'.*?\'\'\'|'
    r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')', re.S)
violations = set()


def report(kind, relative, value):
    record = f"{kind}:{relative}:{value}"
    if not any(pattern.fullmatch(record) for pattern in allowed):
        violations.add(record)


def words(token):
    # CamelCase, ALL_CAPS and snake_case share the same structural grammar.
    return re.findall(r"[A-Z]+(?=[A-Z][a-z]|_|$)|[A-Z]?[a-z]+|[0-9]+", token)


def boundary_guard(token):
    parts = [part.lower() for part in words(token)]
    boundary = {"abi", "schema", "protocol", "contract", "format", "layout"}
    if boundary.intersection(parts) and {"version", "versions"}.intersection(parts):
        return True
    for left, right in zip(parts, parts[1:]):
        if ((left in boundary | {"compatibility"} and
             right in {"hash", "fingerprint", "signature", "checksum"}) or
            (right in boundary | {"compatibility"} and
             left in {"hash", "fingerprint", "signature", "checksum"})):
            return True
    return False


def scan(path):
    relative = path.relative_to(root).as_posix()
    if relative in policy_files:
        return
    # Paths are checked for every file, including non-source fixture assets.
    for component in path.relative_to(root).parts:
        if version_path.search(component):
            report("path", relative, component)
    if path.suffix not in source_suffixes and path.name != "CMakeLists.txt":
        return
    if path.is_symlink():
        report("input", relative, "symlinked-source")
        return
    if path.stat().st_size > 8 * 1024 * 1024:
        report("input", relative, "source-exceeds-8MiB-scan-bound")
        return
    text = path.read_text(encoding="utf-8")
    is_test = any(part in {"test", "tests"} for part in path.parts)
    def mask(match):
        comment = match.group("comment")
        cpp_directive = (comment is not None and comment.startswith("#") and
                         path.suffix in {".h", ".hpp", ".ipp", ".c", ".cc", ".cpp", ".cxx"})
        if (comment is not None and not cpp_directive) or (is_test and comment is None):
            return " " * len(match.group())
        return match.group()
    tokens = lexical.sub(mask, text)
    for token in set(identifier.findall(tokens)):
        if versioned.fullmatch(token):
            report("symbol", relative, token)
        if boundary_guard(token):
            report("guard", relative, token)
    if path.name in {"package.json", "package-lock.json"}:
        data = json.loads(text)
        if "version" in data:
            report("metadata", relative, "package-version")
        # Lockfiles also repeat the owned root package separately from external
        # dependency records, whose versions remain necessary and permitted.
        if "version" in data.get("packages", {}).get("", {}):
            report("metadata", relative, "root-package-version")
    if path.name == "CMakeLists.txt" or path.suffix == ".cmake":
        cmake = lexical.sub(lambda m: " " * len(m.group())
                            if m.group("comment") is not None else m.group(), text)
        for match in re.finditer(r"\bproject\s*\(([^()]*)\)", cmake, re.I):
            if re.search(r"\bVERSION\b", match.group(1), re.I):
                report("metadata", relative, "project-version")
        for match in re.finditer(r"\b(?:set_target_properties|set_property)\s*\(([^()]*)\)", cmake, re.I):
            if re.search(r"\b(?:VERSION|SOVERSION)\b", match.group(1), re.I):
                report("metadata", relative, "target-version")


try:
    roots = [root / name for name in ("src", "apps", "tools", "cmake", ".github")]
    file_count = 0
    for directory in roots:
        for parent, directories, files in os.walk(directory, followlinks=False):
            directories[:] = sorted(name for name in directories
                                    if name not in ignored_directories and
                                    not name.startswith("build") and
                                    not (Path(parent).name == "docs" and name == "results"))
            for name in directories:
                path = Path(parent) / name
                if path.is_symlink():
                    report("input", path.relative_to(root).as_posix(), "symlinked-source-tree")
            for name in sorted(files):
                file_count += 1
                if file_count > 250000:
                    raise ValueError("source tree exceeds 250000-file scan bound")
                scan(Path(parent) / name)
    scan(root / "CMakeLists.txt")
except (OSError, UnicodeError, ValueError) as error:
    sys.exit(f"version naming check: cannot inspect source: {error}")
if violations:
    print("version naming check: project-owned versions and compatibility fingerprints are forbidden", file=sys.stderr)
    for record in sorted(violations):
        print(f"  + {record}", file=sys.stderr)
    sys.exit(1)
PY
