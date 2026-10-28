#!/usr/bin/env python3
"""Bounded, static-only context routing for the CXET Codex workflow.

The index is deliberately a small manifest plus lazy file lookup. It does not
run Git, builds, tests, services, live tools, network calls, or model calls.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Iterable


MANIFEST_NAME = "CxetContextManifest.json"
EVIDENCE = "static-only"
DEFAULT_MAP_BYTES = 6144
DEFAULT_DETAIL_BYTES = 8192
DEFAULT_MAX_RESULTS = 20
DEFAULT_MAX_FILES = 2000
DEFAULT_MAX_ENTRIES = 20000
DEFAULT_MAX_FILE_BYTES = 1024 * 1024
LIMIT_MAXIMA = {
    "map_bytes": DEFAULT_MAP_BYTES,
    "detail_bytes": DEFAULT_DETAIL_BYTES,
    "max_results": DEFAULT_MAX_RESULTS,
    "max_files": DEFAULT_MAX_FILES,
    "max_entries": DEFAULT_MAX_ENTRIES,
    "max_file_bytes": DEFAULT_MAX_FILE_BYTES,
}
MAX_MATCH_TEXT_CHARS = 240
MAX_SKIPPED_FILE_SAMPLES = 20
FORBIDDEN_CHECK_WORDS = re.compile(
    r"\b(?:git|cmake|make|ninja|ctest|pytest|curl|wget|docker|ssh|kubectl)\b",
    re.IGNORECASE,
)
ALLOWED_CHECK_PREFIXES = (
    "python3 tools/Codex/",
    "/usr/bin/python3 tools/Codex/",
    "/usr/bin/python3 -I -S tools/Codex/",
    "bash tools/Codex/",
)
SHELL_OPERATOR = re.compile(r"(?:&&|\|\||[;|><]|`|\$\()")


class ContextIndexError(ValueError):
    """Raised when the index cannot safely answer a context request."""


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_root(repo_root: Path | None) -> Path:
    root = Path(repo_root or default_repo_root()).resolve()
    if not root.is_dir():
        raise ContextIndexError(f"repository root is not a directory: {root}")
    return root


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _load_manifest_file(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "tools" / "Codex" / MANIFEST_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextIndexError(f"context manifest is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ContextIndexError(f"context manifest is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContextIndexError("context manifest root must be an object")
    return payload


def _path_error(repo_root: Path, raw: Any, label: str) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return f"{label} must be a non-empty relative path"
    value = raw.strip()
    path = Path(value)
    if path.is_absolute():
        return f"{label} uses an absolute path: {value}"
    if ".." in path.parts:
        return f"{label} escapes the repository: {value}"
    resolved = (repo_root / path).resolve()
    if not _within(resolved, repo_root):
        return f"{label} escapes the repository: {value}"
    if not resolved.exists():
        return f"{label} does not exist: {value}"
    return None


def _validate_path_list(
    repo_root: Path,
    values: Any,
    label: str,
    errors: list[str],
    *,
    required: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        errors.append(f"{label} must be a list")
        return []
    if required and not values:
        errors.append(f"{label} must not be empty")
    normalized: list[str] = []
    for index, value in enumerate(values):
        error = _path_error(repo_root, value, f"{label}[{index}]")
        if error:
            errors.append(error)
        elif isinstance(value, str):
            normalized.append(value.strip())
    return normalized


def _validate_string_list(
    values: Any,
    label: str,
    errors: list[str],
    *,
    required: bool = False,
) -> list[str]:
    if not isinstance(values, list):
        errors.append(f"{label} must be a list")
        return []
    if required and not values:
        errors.append(f"{label} must not be empty")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}[{index}] must be a non-empty string")
        else:
            normalized.append(value.strip())
    return normalized


def _limit_errors(limits: Any) -> list[str]:
    if not isinstance(limits, dict):
        return ["limits must be an object"]
    errors = _field_errors(limits, set(LIMIT_MAXIMA), "limits")
    for name, maximum in LIMIT_MAXIMA.items():
        value = limits.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            errors.append(f"limits.{name} must be a positive integer")
        elif value > maximum:
            errors.append(f"limits.{name} must be <= {maximum}")
    return errors


def _field_errors(value: dict[str, Any], fields: set[str], name: str) -> list[str]:
    missing = fields - set(value)
    unexpected = set(value) - fields
    if missing or unexpected:
        return [f"{name} has invalid fields; missing: {sorted(missing)}, unexpected: {sorted(unexpected)}"]
    return []


def validate_manifest(
    repo_root: Path | None = None,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the manifest and return a static-only report."""

    root = _resolve_root(repo_root)
    errors: list[str] = []
    if manifest is None:
        try:
            manifest = _load_manifest_file(root)
        except ContextIndexError as exc:
            return {
                "evidence": EVIDENCE,
                "valid": False,
                "scopes": [],
                "errors": [str(exc)],
            }
    if not isinstance(manifest, dict):
        return {
            "evidence": EVIDENCE,
            "valid": False,
            "scopes": [],
            "errors": ["context manifest root must be an object"],
        }

    errors.extend(_field_errors(manifest, {"limits", "common", "scopes"}, "manifest"))

    errors.extend(_limit_errors(manifest.get("limits")))

    common = manifest.get("common")
    if not isinstance(common, dict):
        errors.append("common must be an object")
        common = {}
    errors.extend(_field_errors(common, {"route_docs", "rules"}, "common"))
    _validate_path_list(root, common.get("route_docs"), "common.route_docs", errors)
    _validate_string_list(common.get("rules"), "common.rules", errors, required=True)

    scopes = manifest.get("scopes")
    if not isinstance(scopes, dict) or not scopes:
        errors.append("scopes must be a non-empty object")
        scopes = {}
    scope_names: list[str] = []
    for scope_name, entry in scopes.items():
        if not isinstance(scope_name, str) or not scope_name.strip():
            errors.append("scope names must be non-empty strings")
            continue
        scope_name = scope_name.strip()
        scope_names.append(scope_name)
        if scope_name == "all":
            errors.append("scope name all is reserved")
        if not isinstance(entry, dict):
            errors.append(f"scope {scope_name} must be an object")
            continue
        errors.extend(_field_errors(entry, {"owner", "keywords", "roots", "route_docs", "anchors", "static_checks"}, f"scope {scope_name}"))
        owner = entry.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            errors.append(f"scope {scope_name}.owner must be a non-empty string")
        _validate_string_list(
            entry.get("keywords"),
            f"scope {scope_name}.keywords",
            errors,
            required=True,
        )
        _validate_path_list(
            root,
            entry.get("roots"),
            f"scope {scope_name}.roots",
            errors,
            required=True,
        )
        _validate_path_list(
            root,
            entry.get("route_docs"),
            f"scope {scope_name}.route_docs",
            errors,
        )
        _validate_path_list(
            root,
            entry.get("anchors"),
            f"scope {scope_name}.anchors",
            errors,
        )
        checks = _validate_string_list(
            entry.get("static_checks"),
            f"scope {scope_name}.static_checks",
            errors,
            required=True,
        )
        for index, check in enumerate(checks):
            if (
                not check.startswith(ALLOWED_CHECK_PREFIXES)
                or SHELL_OPERATOR.search(check)
            ):
                errors.append(
                    f"scope {scope_name}.static_checks[{index}] is not an allowlisted static helper"
                )
            elif FORBIDDEN_CHECK_WORDS.search(check):
                errors.append(
                    f"scope {scope_name}.static_checks[{index}] contains a non-static command"
                )
            else:
                try:
                    parts = shlex.split(check)
                except ValueError:
                    errors.append(f"scope {scope_name}.static_checks[{index}] has invalid quoting")
                    continue
                if any("install" in part.casefold() or "bootstrap" in part.casefold() for part in parts):
                    errors.append(f"scope {scope_name}.static_checks[{index}] is not an allowlisted static recipe")

    return {
        "evidence": EVIDENCE,
        "valid": not errors,
        "scopes": sorted(scope_names),
        "errors": errors,
    }


def _validated(repo_root: Path | None = None) -> tuple[Path, dict[str, Any]]:
    root = _resolve_root(repo_root)
    manifest = _load_manifest_file(root)
    report = validate_manifest(root, manifest)
    if not report["valid"]:
        errors = "; ".join(report["errors"])
        raise ContextIndexError(f"context manifest validation failed: {errors}")
    return root, manifest


def _scope_entry(manifest: dict[str, Any], scope: str) -> dict[str, Any]:
    scopes = manifest.get("scopes", {})
    if scope not in scopes:
        raise ContextIndexError(f"unknown context scope: {scope}")
    entry = scopes[scope]
    if not isinstance(entry, dict):
        raise ContextIndexError(f"context scope is not an object: {scope}")
    return entry


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _common_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    common = manifest.get("common", {})
    return {
        "route_docs": list(common.get("route_docs", [])),
        "rules": list(common.get("rules", [])),
    }


def _route(manifest: dict[str, Any], task_hint: str) -> tuple[str | None, list[dict[str, Any]]]:
    hint = task_hint.casefold()
    scored: list[tuple[int, int, int, str, dict[str, Any]]] = []
    for order, (scope, entry) in enumerate(manifest["scopes"].items()):
        keywords = entry.get("keywords", [])
        matches = [keyword.casefold() for keyword in keywords if keyword.casefold() in hint]
        # Preserve stem/identifier matching, but prefer whole keywords on a tie:
        # "api" inside "capital" must not compete with the explicit name.
        whole_matches = sum(
            1 for keyword in matches
            if re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", hint)
        )
        scored.append((len(matches), whole_matches, -order, scope, entry))
    scored.sort(reverse=True)
    if not scored:
        return None, []
    top_score = scored[0][:2]
    second_score = scored[1][:2] if len(scored) > 1 else (-1, -1)
    if top_score[0] <= 0 or top_score == second_score:
        candidates = [
            {
                "scope": scope,
                "owner": entry.get("owner", ""),
                "score": score,
            }
            for score, _, _, scope, entry in scored[:3]
        ]
        return None, candidates
    return scored[0][3], []


def _selected_payload(
    manifest: dict[str, Any],
    scope: str,
    *,
    route_status: str,
) -> dict[str, Any]:
    entry = _scope_entry(manifest, scope)
    common = _common_payload(manifest)
    return {
        "evidence": EVIDENCE,
        "route_status": route_status,
        "scope": scope,
        "owner": entry["owner"],
        "common_route_docs": common["route_docs"],
        "route_docs": _unique(common["route_docs"] + list(entry.get("route_docs", []))),
        "roots": list(entry.get("roots", [])),
        "anchors": list(entry.get("anchors", [])),
        "static_checks": list(entry.get("static_checks", [])),
        "rules": common["rules"],
    }


def build_context_map(
    repo_root: Path | None,
    task_hint: str,
    scope: str | None = None,
) -> dict[str, Any]:
    """Return a compact context route without file excerpts."""

    _, manifest = _validated(repo_root)
    if not isinstance(task_hint, str) or not task_hint.strip():
        raise ContextIndexError("task_hint must be a non-empty string")
    if scope == "all":
        return {
            "evidence": EVIDENCE,
            "route_status": "inventory",
            "scope": "all",
            "common": _common_payload(manifest),
            "scopes": [
                {"scope": name, "owner": entry["owner"]}
                for name, entry in manifest["scopes"].items()
            ],
        }
    if scope is not None:
        return _selected_payload(manifest, scope, route_status="selected")

    selected, candidates = _route(manifest, task_hint.strip())
    if selected is None:
        return {
            "evidence": EVIDENCE,
            "route_status": "ambiguous",
            "scope": None,
            "candidates": candidates,
            "common": _common_payload(manifest),
        }
    return _selected_payload(manifest, selected, route_status="selected")


def _manifest_limits(manifest: dict[str, Any]) -> dict[str, int]:
    """Validate only canonical limits; direct tools need no context path scan."""
    limits = manifest.get("limits")
    errors = _limit_errors(limits)
    if errors:
        raise ContextIndexError("context limits validation failed: " + "; ".join(errors))
    return {name: limits[name] for name in LIMIT_MAXIMA}


def _summary_lines(payload: dict[str, Any]) -> list[str]:
    lines = [f"evidence: {payload.get('evidence', EVIDENCE)}"]
    if "valid" in payload:
        lines.append(f"valid: {str(payload['valid']).lower()}")
        if payload.get("scopes"):
            lines.append("scopes: " + ", ".join(payload["scopes"]))
        for error in payload.get("errors", []):
            lines.append(f"error: {error}")
        return lines
    if "route_status" in payload:
        lines.append(f"route: {payload['route_status']}")
        if payload.get("scope") is not None:
            lines.append(f"scope: {payload['scope']}")
        if payload.get("owner"):
            lines.append(f"owner: {payload['owner']}")
        if payload.get("candidates"):
            lines.append(
                "candidates: "
                + ", ".join(item["scope"] for item in payload["candidates"])
            )
        for key in ("route_docs", "roots", "anchors", "static_checks", "rules"):
            values = payload.get(key)
            if values:
                lines.append(f"{key}: " + " | ".join(str(value) for value in values))
        if payload.get("scopes") and payload.get("scope") == "all":
            lines.append(
                "scopes: " + ", ".join(item["scope"] for item in payload["scopes"])
            )
        return lines
    if "references" in payload:
        lines.extend([f"scope: {payload['scope']}", f"status: {payload['status']}",
                      f"search_complete: {str(payload['search_complete']).lower()}",
                      f"stop_reason: {payload['stop_reason']}",
                      "caller/build/runtime proof: not_observed"])
        for row in payload["references"]:
            lines.append(f"{row['category']} {row['path']}:{row['line']}: {row['text']}")
        for path in payload["retired_paths_present"]:
            lines.append(f"retired path still present: {path}")
        for path in payload["stale_anchors"]:
            lines.append(f"stale anchor: {path}")
        return lines
    if "matches" in payload:
        lines.append(f"scope: {payload['scope']}")
        lines.append(f"matches: {len(payload['matches'])}")
        if "search_complete" in payload:
            lines.append(f"search_complete: {str(payload['search_complete']).lower()}")
        if "scanned_files" in payload:
            lines.append(f"scanned_files: {payload['scanned_files']}")
        if "stop_reason" in payload:
            lines.append(f"stop_reason: {payload['stop_reason']}")
        for match in payload["matches"]:
            lines.append(f"{match['path']}:{match['line']}: {match['text']}")
        if payload.get("truncated"):
            lines.append("truncated: true")
        if payload.get("skipped_file_count"):
            lines.append(f"skipped_files: {payload['skipped_file_count']}")
        if payload.get("scan_error_count"):
            lines.append(f"scan_errors: {payload['scan_error_count']}")
        return lines
    if "mapped" in payload:
        lines.append(f"status: {payload['status']}")
        lines.append(f"mapped: {len(payload['mapped'])}")
        for item in payload["mapped"]:
            lines.append(f"{item['path']}: {', '.join(item['scopes'])}")
        if payload.get("unmapped"):
            lines.append("unmapped: " + ", ".join(payload["unmapped"]))
        if payload.get("static_checks"):
            lines.append("static_checks: " + " | ".join(payload["static_checks"]))
        return lines
    lines.extend(f"{key}: {value}" for key, value in payload.items() if key != "evidence")
    return lines


def render_payload(payload: dict[str, Any], output_format: str = "summary") -> str:
    if output_format not in {"summary", "json"}:
        raise ContextIndexError("format must be summary or json")
    if output_format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    else:
        rendered = "\n".join(_summary_lines(payload))
    limit = DEFAULT_MAP_BYTES if "route_status" in payload else DEFAULT_DETAIL_BYTES
    if len(rendered.encode("utf-8")) > limit:
        raise ContextIndexError(
            f"context response exceeds {limit} bytes; request a narrower scope or query"
        )
    return rendered


@dataclass
class _SearchScanState:
    scanned_entries: int = 0
    scanned_files: int = 0
    skipped_file_count: int = 0
    skipped_files: list[dict[str, str]] = field(default_factory=list)
    scan_error_count: int = 0
    scan_errors: list[str] = field(default_factory=list)
    stop_reason: str = "complete"

    def skip_file(self, root: Path, path: Path, reason: str) -> None:
        self.skipped_file_count += 1
        if len(self.skipped_files) < MAX_SKIPPED_FILE_SAMPLES:
            self.skipped_files.append(
                {"path": path.relative_to(root).as_posix(), "reason": reason}
            )

    def scan_error(self, path: Path, reason: str) -> None:
        self.scan_error_count += 1
        if len(self.scan_errors) < MAX_SKIPPED_FILE_SAMPLES:
            self.scan_errors.append(f"{path}: {reason}")


def _walk_context_tree(
    root: Path, state: _SearchScanState, max_entries: int, repo_root: Path,
) -> Iterable[Path]:
    # Sort only a budget-bounded directory. Small fully scanned trees preserve
    # stable order; a budget-limited subset follows the filesystem enumeration.
    def directory(path: Path) -> Iterable[Any]:
        entries = []
        try:
            with os.scandir(path) as iterator:
                while state.scanned_entries < max_entries:
                    try:
                        item = next(iterator)
                    except StopIteration:
                        return iter(sorted(entries, key=lambda item: item.name))
                    state.scanned_entries += 1
                    entries.append(item)
                state.stop_reason = "max_entries"
        except OSError as exc:
            state.scan_error(path, str(exc))
        return iter(sorted(entries, key=lambda item: item.name))

    pending = [directory(root)]
    while pending:
        try:
            item = next(pending[-1])
        except StopIteration:
            pending.pop()
            continue
        path = Path(item.path)
        try:
            if item.is_symlink():
                state.skip_file(repo_root, path, "symlink")
            elif item.is_dir(follow_symlinks=False):
                if state.scanned_entries < max_entries:
                    pending.append(directory(path))
            elif item.is_file(follow_symlinks=False):
                yield path
            else:
                state.skip_file(repo_root, path, "non_regular")
        except OSError as exc:
            state.scan_error(path, str(exc))


def _iter_context_files(
    repo_root: Path,
    entry: dict[str, Any],
    *,
    max_files: int,
    max_file_bytes: int,
    max_entries: int,
    state: _SearchScanState,
) -> Iterable[Path]:
    seen: set[Path] = set()
    for relative in entry.get("roots", []):
        if state.stop_reason != "complete":
            return
        candidate = (repo_root / relative).resolve()
        if not _within(candidate, repo_root):
            state.scan_error(candidate, "outside repository")
            continue
        if (repo_root / relative).is_symlink():
            state.skip_file(repo_root, repo_root / relative, "symlink")
            continue
        if candidate.is_file():
            if state.scanned_entries >= max_entries:
                state.stop_reason = "max_entries"
                return
            state.scanned_entries += 1
            candidates = [candidate]
        else:
            candidates = _walk_context_tree(candidate, state, max_entries, repo_root)
        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            if state.scanned_files >= max_files:
                state.stop_reason = "max_files"
                return
            if not _within(resolved, repo_root):
                state.skip_file(repo_root, path, "outside_repository")
                continue
            seen.add(resolved)
            state.scanned_files += 1
            try:
                if resolved.stat().st_size > max_file_bytes:
                    state.skip_file(repo_root, resolved, "oversized")
                    continue
            except OSError as exc:
                state.skip_file(repo_root, resolved, "stat_error")
                state.scan_error(resolved, str(exc))
                continue
            yield resolved


def search_context(
    repo_root: Path | None,
    scope: str,
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict[str, Any]:
    """Search only declared scope roots and return bounded line excerpts."""

    root, manifest = _validated(repo_root)
    entry = _scope_entry(manifest, scope)
    limits = _manifest_limits(manifest)
    if not isinstance(max_results, int) or isinstance(max_results, bool):
        raise ContextIndexError("max_results must be an integer")
    if not 1 <= max_results <= limits["max_results"]:
        raise ContextIndexError(f"max_results must be between 1 and {limits['max_results']}")
    if not isinstance(query, str) or not query.strip():
        raise ContextIndexError("query must be a non-empty string")
    needle = query.strip().casefold()
    matches: list[dict[str, Any]] = []
    state = _SearchScanState()
    for path in _iter_context_files(
        root,
        entry,
        max_files=limits["max_files"],
        max_file_bytes=limits["max_file_bytes"],
        max_entries=limits["max_entries"],
        state=state,
    ):
        try:
            with path.open("rb") as stream:
                data = stream.read(limits["max_file_bytes"] + 1)
            if len(data) > limits["max_file_bytes"]:
                state.skip_file(root, path, "oversized")
                continue
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            state.skip_file(root, path, "invalid_utf8")
            continue
        except OSError as exc:
            state.skip_file(root, path, "read_error")
            state.scan_error(path, str(exc))
            continue
        if "\x00" in text:
            state.skip_file(root, path, "binary")
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(text.splitlines(), start=1):
            if needle not in line.casefold():
                continue
            line_text = line.strip()
            if len(line_text) > MAX_MATCH_TEXT_CHARS:
                line_text = line_text[: MAX_MATCH_TEXT_CHARS - 3] + "..."
            matches.append({"path": relative, "line": line_number, "text": line_text})
            if len(matches) >= max_results:
                state.stop_reason = "max_results"
                break
        if state.stop_reason == "max_results":
            break
    truncated = state.stop_reason != "complete"
    return {
        "evidence": EVIDENCE,
        "scope": scope,
        "query": query.strip(),
        "matches": matches,
        "truncated": truncated,
        "search_complete": (state.stop_reason == "complete"
                            and not state.skipped_file_count and not state.scan_error_count),
        "scanned_entries": state.scanned_entries,
        "scanned_files": state.scanned_files,
        "stop_reason": state.stop_reason,
        "skipped_files": state.skipped_files,
        "skipped_file_count": state.skipped_file_count,
        "scan_errors": state.scan_errors,
        "scan_error_count": state.scan_error_count,
    }


def _reference_category(path: str) -> str:
    value = Path(path)
    if value.name == "CMakeLists.txt" or value.suffix == ".cmake":
        return "build"
    if value.suffix in {".md", ".rst", ".txt"}:
        return "docs"
    if any(part.casefold() in {"tests", "test"} for part in value.parts) or "test" in value.stem.casefold():
        return "tests"
    if value.suffix in {".py", ".sh", ".mjs", ".yaml", ".yml"}:
        return "CLI/recipes"
    return "source"


def build_closure(repo_root: Path | None, scope: str, retired_symbols: list[str],
                  retired_paths: list[str]) -> dict[str, Any]:
    """Find retirement references, never infer caller reachability from text."""
    root, manifest = _validated(repo_root)
    entry = _scope_entry(manifest, scope)
    limits = _manifest_limits(manifest)
    if (not isinstance(retired_symbols, list) or not isinstance(retired_paths, list)
            or not retired_symbols and not retired_paths
            or len(retired_symbols) + len(retired_paths) > 64):
        raise ContextIndexError("provide 1..64 explicit retired symbols/paths")
    if any(not isinstance(value, str) or len(value) > 128 or
           re.fullmatch(r"[A-Za-z_]\w*(?:::[A-Za-z_]\w*)*", value) is None
           for value in retired_symbols):
        raise ContextIndexError("retired symbols must be bounded C++ identifiers")
    paths = [_input_relative_path(value) for value in retired_paths]
    if any(path == "." or len(path) > 512 for path in paths):
        raise ContextIndexError("retired paths must name bounded repository paths")
    patterns = [(value, re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)"))
                for value in _unique(retired_symbols)]
    state = _SearchScanState()
    references = []
    scan_entry = dict(entry)
    scan_entry["roots"] = _unique(entry["roots"] + entry.get("anchors", []) + entry.get("route_docs", []))
    for path in _iter_context_files(root, scan_entry, max_files=limits["max_files"],
                                   max_file_bytes=limits["max_file_bytes"],
                                   max_entries=limits["max_entries"], state=state):
        try:
            with path.open("rb") as stream:
                data = stream.read(limits["max_file_bytes"] + 1)
            if len(data) > limits["max_file_bytes"]:
                state.skip_file(root, path, "oversized")
                continue
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            state.skip_file(root, path, "invalid_utf8")
            continue
        except OSError as exc:
            state.skip_file(root, path, "read_error")
            state.scan_error(path, str(exc))
            continue
        if "\x00" in text:
            state.skip_file(root, path, "binary")
            continue
        relative = path.relative_to(root).as_posix()
        for number, line in enumerate(text.splitlines(), 1):
            matched = [value for value, pattern in patterns if pattern.search(line)]
            matched.extend(value for value in paths if value in line)
            if not matched:
                continue
            references.append({"path": relative, "line": number,
                               "text": line.strip()[:MAX_MATCH_TEXT_CHARS],
                               "category": _reference_category(relative), "retired": matched})
            if len(references) >= limits["max_results"]:
                state.stop_reason = "max_results"
                break
        if state.stop_reason != "complete":
            break
    complete = state.stop_reason == "complete" and not state.skipped_file_count and not state.scan_error_count
    present = [value for value in paths if (root / value).exists() or (root / value).is_symlink()]
    stale = [value for value in entry.get("anchors", []) if not (root / value).exists()]
    return {"evidence": EVIDENCE, "scope": scope,
            "status": ("incomplete" if not complete else "references_remaining" if references or present or stale
                       else "no_references_observed"),
            "search_complete": complete, "stop_reason": state.stop_reason,
            "scanned_files": state.scanned_files, "references": references,
            "retired_paths_present": present, "stale_anchors": stale,
            "skipped_file_count": state.skipped_file_count, "skipped_files": state.skipped_files,
            "scan_error_count": state.scan_error_count, "scan_errors": state.scan_errors,
            "caller_proof": "not_observed", "build_proof": "not_observed", "runtime_proof": "not_observed"}


def _input_relative_path(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ContextIndexError("changed paths must be non-empty strings")
    path = Path(raw.strip())
    if path.is_absolute() or ".." in path.parts:
        raise ContextIndexError(f"changed path must stay inside the repository: {raw}")
    return path.as_posix().removeprefix("./")


def _path_matches_entry(relative: str, entry: dict[str, Any]) -> bool:
    candidate = Path(relative)
    for field in ("roots", "anchors", "route_docs"):
        for declared in entry.get(field, []):
            declared_path = Path(declared)
            if candidate == declared_path or declared_path in candidate.parents:
                return True
    return False


def build_postcheck(
    repo_root: Path | None,
    changed_paths: list[str],
    scope: str | None = None,
) -> dict[str, Any]:
    """Map a final changed-path set without reading Git or running checks."""

    _, manifest = _validated(repo_root)
    if not isinstance(changed_paths, list) or not changed_paths:
        raise ContextIndexError("changed_paths must be a non-empty list")
    if scope == "all":
        selected_scopes = list(manifest["scopes"])
    elif scope is not None:
        _scope_entry(manifest, scope)
        selected_scopes = [scope]
    else:
        selected_scopes = list(manifest["scopes"])

    mapped: list[dict[str, Any]] = []
    unmapped: list[str] = []
    check_commands: list[str] = []
    for raw_path in changed_paths:
        relative = _input_relative_path(raw_path)
        matches = [
            candidate
            for candidate in selected_scopes
            if _path_matches_entry(relative, manifest["scopes"][candidate])
        ]
        if not matches:
            unmapped.append(relative)
            continue
        mapped.append(
            {
                "path": relative,
                "scopes": matches,
                "owners": [manifest["scopes"][candidate]["owner"] for candidate in matches],
            }
        )
        for candidate in matches:
            check_commands.extend(manifest["scopes"][candidate].get("static_checks", []))

    return {
        "evidence": EVIDENCE,
        "status": "ok" if not unmapped else "needs_manifest_review",
        "scope": scope or "auto",
        "mapped": mapped,
        "unmapped": unmapped,
        "static_checks": _unique(check_commands),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded static CXET context index")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate the context manifest")
    validate.add_argument("--format", choices=("summary", "json"), default="summary")

    context_map = sub.add_parser("map", help="route a task to a bounded context")
    context_map.add_argument("--task-hint", required=True)
    context_map.add_argument("--scope")
    context_map.add_argument("--format", choices=("summary", "json"), default="summary")

    search = sub.add_parser("search", help="search one declared context scope")
    search.add_argument("--scope", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS)
    search.add_argument("--format", choices=("summary", "json"), default="summary")

    closure = sub.add_parser("closure", help="bounded static retirement-reference report")
    closure.add_argument("--scope", required=True)
    closure.add_argument("--retired-symbol", action="append", default=[])
    closure.add_argument("--retired-path", action="append", default=[])
    closure.add_argument("--format", choices=("summary", "json"), default="summary")

    postcheck = sub.add_parser("postcheck", help="check final changed paths")
    postcheck.add_argument("--scope")
    postcheck.add_argument("--changed-path", action="append", required=True)
    postcheck.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            payload = validate_manifest(default_repo_root())
        elif args.command == "map":
            payload = build_context_map(default_repo_root(), args.task_hint, args.scope)
        elif args.command == "search":
            payload = search_context(
                default_repo_root(),
                args.scope,
                args.query,
                max_results=args.max_results,
            )
        elif args.command == "closure":
            payload = build_closure(default_repo_root(), args.scope, args.retired_symbol, args.retired_path)
        else:
            payload = build_postcheck(default_repo_root(), args.changed_path, args.scope)
        print(render_payload(payload, args.format))
        if args.command == "closure":
            return 2 if not payload["search_complete"] else 1 if payload["status"] == "references_remaining" else 0
        return 0 if payload.get("valid", True) else 1
    except (ContextIndexError, OSError) as exc:
        print(f"cxet_context_index error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
