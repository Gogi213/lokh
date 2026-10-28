#!/usr/bin/env python3
"""Read-only diagnostics for the Codex/CXET local working environment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ is canonical.
    tomllib = None  # type: ignore[assignment]


MAX_REPORT_BYTES = 8192
SERVER_NAME = "cxet_local"
SERVER_SCRIPT = "tools/Codex/CxetMcpServer.py"


def load_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        raise RuntimeError("Python tomllib is required")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _run(command: list[str], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_root(cwd: Path) -> Path | None:
    value = _run(["git", "--no-optional-locks", "-C", str(cwd), "rev-parse", "--show-toplevel"])
    if not value:
        return None
    root = Path(value).resolve()
    return root if root.is_dir() else None


def _git_identity(root: Path) -> dict[str, str | None]:
    return {
        "branch": _run(["git", "--no-optional-locks", "-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"]),
        "sha": _run(["git", "--no-optional-locks", "-C", str(root), "rev-parse", "HEAD"]),
    }


def _config(path: Path) -> dict[str, Any]:
    try:
        value = load_toml(path)
    except (OSError, RuntimeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _merged_server_config(
    session_root: Path,
    codex_home: Path,
    project_config: Path | None,
    global_config: Path | None,
) -> tuple[dict[str, Any], list[str], dict[str, Any], dict[str, Any]]:
    project_path = project_config or session_root / ".codex" / "config.toml"
    global_path = global_config or codex_home / "config.toml"
    merged: dict[str, Any] = {}
    used: list[str] = []
    global_data = _config(global_path)
    project_data = _config(project_path)
    for path, data in ((global_path, global_data), (project_path, project_data)):
        servers = data.get("mcp_servers", {})
        if not isinstance(servers, Mapping):
            raise ValueError(f"{path}: mcp_servers must be a table")
        server = servers.get(SERVER_NAME)
        if isinstance(server, Mapping):
            merged.update(server)
            used.append(str(path))
    return merged, used, global_data, project_data


def _resolve_server_paths(
    session_root: Path,
    server: Mapping[str, Any],
) -> tuple[Path | None, Path | None, Path, str | None]:
    raw_cwd = server.get("cwd")
    if isinstance(raw_cwd, str) and raw_cwd:
        launch_cwd = Path(raw_cwd).expanduser()
        if not launch_cwd.is_absolute():
            launch_cwd = session_root / launch_cwd
    else:
        launch_cwd = session_root
    launch_cwd = launch_cwd.resolve()

    args = server.get("args", [])
    args = args if isinstance(args, list) else []
    script_value = next(
        (value for value in args if isinstance(value, str) and value.endswith(".py")),
        SERVER_SCRIPT,
    )
    script = Path(script_value).expanduser()
    if not script.is_absolute():
        script = launch_cwd / script
    script = script.resolve()

    configured_root: Path | None = None
    for index, value in enumerate(args):
        if value == "--repo-root" and index + 1 < len(args) and isinstance(args[index + 1], str):
            configured_root = Path(args[index + 1]).expanduser()
            if not configured_root.is_absolute():
                configured_root = launch_cwd / configured_root
            configured_root = configured_root.resolve()
        elif isinstance(value, str) and value.startswith("--repo-root="):
            configured_root = Path(value.split("=", 1)[1]).expanduser()
            if not configured_root.is_absolute():
                configured_root = launch_cwd / configured_root
            configured_root = configured_root.resolve()
    served_root = configured_root or launch_cwd
    command = server.get("command")
    return served_root, script, launch_cwd, command if isinstance(command, str) else None


def _hook_report(
    hook_file: Path,
    global_config: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _load_json(hook_file)
    hooks = payload.get("hooks") if isinstance(payload, Mapping) else None
    events = sorted(hooks) if isinstance(hooks, Mapping) else []
    hooks_config = global_config.get("hooks", {})
    state = hooks_config.get("state", {}) if isinstance(hooks_config, Mapping) else {}
    state_prefix = f"{hook_file}:"
    records = (
        [value for key, value in state.items()
         if str(key) == str(hook_file) or str(key).startswith(state_prefix)]
        if isinstance(state, Mapping) else []
    )
    trust_hash_present = any(
        isinstance(record, Mapping)
        and isinstance(record.get("trusted_hash"), str)
        and re.fullmatch(r"sha256:[0-9a-fA-F]{64}", record["trusted_hash"]) is not None
        for record in records
    )
    trust_record_present = bool(records)
    if payload is None:
        status = "unavailable"
    elif trust_record_present:
        status = "configured_trust_unconfirmed"
    else:
        status = "configured_no_trust_record"
    return {
        "file": str(hook_file),
        "status": status,
        "events": events,
        "trust_record_present": trust_record_present,
        "trust_hash_present": trust_hash_present,
        "load_proof": "configuration_only",
        "trust_status": "not_observed",
    }


def _client_version() -> str | None:
    executable = shutil.which("codex")
    return _run([executable, "--version"]) if executable else None


def build_report(
    *,
    session_cwd: Path,
    served_root: Path | None = None,
    server_script: Path | None = None,
    active_model: str | None = None,
    client_version: str | None = None,
    hook_file: Path | None = None,
    codex_home: Path | None = None,
    project_config: Path | None = None,
    global_config: Path | None = None,
    observed_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observed_identity = None
    if observed_response is not None:
        if (not isinstance(observed_response, dict) or observed_response.get("isError") is True
                or observed_response.get("output_complete") is False):
            raise ValueError("observed MCP response is invalid or failed")
        structured = observed_response.get("structuredContent")
        observed_identity = structured.get("identity") if isinstance(structured, dict) else None
        if (not isinstance(structured, dict) or structured.get("evidence") != "static-only"
                or not isinstance(observed_response.get("content"), list) or not observed_response["content"]
                or not isinstance(observed_identity, dict)
                or any(not isinstance(observed_identity.get(key), str) or not Path(observed_identity[key]).is_absolute()
                       for key in ("served_root", "script", "script_root", "process_cwd"))
                or observed_identity.get("identity_status") not in {"ok", "warning"}):
            raise ValueError("observed MCP response lacks complete checkout identity")
        served_root = Path(observed_identity["served_root"])
        server_script = Path(observed_identity["script"])
    observed_root = served_root is not None
    observed_script = server_script is not None
    version_supplied = client_version is not None
    session_cwd = session_cwd.expanduser().resolve()
    session_root = _git_root(session_cwd) or session_cwd
    codex_home = (codex_home or Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()).resolve()
    server, config_files, global_data, project_data = _merged_server_config(
        session_root, codex_home, project_config, global_config
    )

    configured_root, configured_script, launch_cwd, command = _resolve_server_paths(
        session_cwd, server
    ) if server else (None, None, session_cwd, None)
    configured_script_root = (configured_script.parents[2]
                              if configured_script is not None and len(configured_script.parents) >= 3 else None)
    configured_identity_status = "unavailable" if configured_root is None else (
        "ok" if configured_root == session_root and configured_script_root == configured_root
        else "warning")
    served_root = served_root.expanduser().resolve() if served_root else configured_root
    server_script = server_script.expanduser().resolve() if server_script else configured_script

    identity_status = "unavailable"
    warnings: list[str] = []
    script_root = (
        server_script.parents[2]
        if server_script is not None and len(server_script.parents) >= 3
        else None
    )
    if served_root is not None:
        if served_root == session_root:
            identity_status = "ok"
        else:
            identity_status = "warning"
            warnings.append(
                f"session root {session_root} differs from served MCP root {served_root}"
            )
        if script_root is not None and script_root != served_root:
            identity_status = "warning"
            warnings.append(
                f"MCP script root {script_root} differs from served MCP root {served_root}"
            )
    else:
        warnings.append("cxet_local served root is unavailable from the candidate configuration")
    if configured_identity_status == "warning":
        warnings.append("configured MCP checkout identity differs from the session or script root")
    if active_model is None:
        warnings.append("active model is unavailable from this doctor invocation")
    if not client_version:
        client_version = _client_version()
    if not client_version:
        warnings.append("Codex client version is unavailable")

    hook_file = (hook_file or codex_home / "hooks.json").expanduser().resolve()
    hooks = _hook_report(hook_file, global_data)
    if hooks["status"] == "unavailable":
        warnings.append(f"hooks file is unavailable: {hook_file}")
    elif hooks["status"] == "configured_trust_unconfirmed":
        warnings.append(f"hook trust is not confirmed for {hook_file}; review with /hooks")
    elif hooks["status"] == "configured_no_trust_record":
        warnings.append(f"hook file exists without a matching trust record; trust is not observed for {hook_file}")

    if "model" in project_data:
        configured_model = project_data.get("model")
        configured_model_source = "project"
    else:
        configured_model = global_data.get("model")
        configured_model_source = "global" if "model" in global_data else None

    if not observed_root:
        identity_status = "not_observed"
    field_sources = {}
    for path in config_files:
        for field in _config(Path(path)).get("mcp_servers", {}).get(SERVER_NAME, {}):
            field_sources[field] = path

    report = {
        "evidence": "static-only",
        "identity_status": identity_status,
        "configured_identity_status": configured_identity_status,
        "client": {"version": client_version,
                   "version_source": "caller_supplied" if version_supplied else "local_cli_probe"},
        "session": {"cwd": str(session_cwd), "root": str(session_root), **_git_identity(session_root)},
        "model": {
            "configured": configured_model,
            "configured_source": configured_model_source,
            "active": active_model,
            "active_source": "caller_supplied" if active_model else "not_observed",
            "configured_resolution": "global_then_project_candidate",
            "client_resolution": "not_observed",
        },
        "hooks": hooks,
        "mcp": {
            "server": SERVER_NAME,
            "observation": "supplied_active_response" if observed_identity else "not_observed",
            "config_files": config_files,
            "configuration_resolution": "global_then_project_candidate",
            "client_resolution": "not_observed",
            "field_sources": field_sources,
            "provenance": {
                "served_root": "caller_supplied" if observed_root else "derived_from_candidate_args_or_cwd",
                "script": "caller_supplied" if observed_script else "derived_from_candidate_args",
                "process_cwd": "candidate_cwd" if "cwd" in server else "assumed_session_cwd",
            },
            "command": command,
            "process_cwd": str(launch_cwd),
            "script": str(server_script) if server_script else None,
            "script_root": str(script_root) if script_root else None,
            "script_identity": _git_identity(script_root) if script_root else {"branch": None, "sha": None},
            "served_root": str(served_root) if served_root else None,
            "served_identity": _git_identity(served_root) if served_root else {"branch": None, "sha": None},
        },
        "warnings": warnings,
    }
    if observed_identity:
        report["mcp"]["process_cwd"] = observed_identity["process_cwd"]
        report["mcp"]["provenance"] = {"served_root": "observed_response", "script": "observed_response",
                                       "process_cwd": "observed_response"}
        if (Path(observed_identity["process_cwd"]).resolve() != served_root or
                Path(observed_identity["script_root"]).resolve() != script_root or
                observed_identity["identity_status"] != "ok"):
            report["identity_status"] = "warning"
            warnings.append("observed process/script checkout identity mismatch")
    return report


def render_report(report: dict[str, Any], output_format: str = "summary") -> str:
    if output_format not in {"summary", "json"}:
        raise ValueError("format must be summary or json")
    if output_format == "json":
        rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False)
    else:
        rendered = "\n".join(
            [
                f"evidence: {report['evidence']}",
                f"identity_status: {report['identity_status']}",
                f"configured_identity_status: {report['configured_identity_status']}",
                f"mcp_provenance: {report['mcp']['provenance']['served_root']}",
                f"mcp_observation: {report['mcp']['observation']}",
                "config_client_resolution: not_observed",
                f"session_root: {report['session']['root']}",
                f"session_sha: {report['session']['sha'] or 'unavailable'}",
                f"served_root: {report['mcp']['served_root'] or 'unavailable'}",
                f"served_sha: {report['mcp']['served_identity']['sha'] or 'unavailable'}",
                f"client_version: {report['client']['version'] or 'unavailable'}",
                f"configured_model: {report['model']['configured'] or 'unavailable'}",
                f"active_model: {report['model']['active'] or 'unavailable'}",
                f"hooks: {', '.join(report['hooks']['events']) or 'unavailable'}",
                *[f"warning: {warning}" for warning in report["warnings"]],
            ]
        )
    if len(rendered.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError(f"doctor response exceeds {MAX_REPORT_BYTES} bytes")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only CXET Codex environment doctor")
    parser.add_argument("--session-cwd", type=Path, default=Path.cwd())
    parser.add_argument("--active-model")
    parser.add_argument("--codex-home", type=Path)
    parser.add_argument("--project-config", type=Path)
    parser.add_argument("--global-config", type=Path)
    parser.add_argument("--observed-response", type=Path)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    try:
        observed = None
        if args.observed_response:
            with args.observed_response.open("rb") as stream:
                data = stream.read(MAX_REPORT_BYTES + 1)
            if len(data) > MAX_REPORT_BYTES:
                raise ValueError("observed response exceeds the input budget")
            observed = json.loads(data)
        report = build_report(
            session_cwd=args.session_cwd,
            active_model=args.active_model,
            codex_home=args.codex_home,
            project_config=args.project_config,
            global_config=args.global_config,
            observed_response=observed,
        )
        print(render_report(report, args.format))
    except (ValueError, OSError) as exc:
        print(f"cxet doctor: invalid input: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
