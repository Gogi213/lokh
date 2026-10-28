#!/usr/bin/env python3
"""Minimal stdio MCP server for CXET read-only Codex helpers."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

if __package__:
    from . import CxetContextIndex as cxet_context, CxetToolbelt as cxet_toolbelt
    from .Context import CxetMcpProtocol as protocol
else:
    import importlib.util
    def _sibling(name: str):
        spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / ("Context/CxetMcpProtocol.py" if name == "CxetMcpProtocol" else name + ".py"))
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    cxet_context = _sibling("CxetContextIndex")
    cxet_toolbelt = _sibling("CxetToolbelt")
    protocol = _sibling("CxetMcpProtocol")


SERVER_NAME = "cxet_local"
PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = {"2024-11-05", "2025-03-26", "2025-06-18"}
_REPO_ROOT: Path | None = None


def set_repo_root(root: Path) -> None:
    global _REPO_ROOT
    resolved = root.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"repository root is not a directory: {resolved}")
    _REPO_ROOT = resolved


def repo_root() -> Path:
    return _REPO_ROOT or Path.cwd().resolve()


def checkout_identity() -> dict[str, str]:
    served_root = repo_root()
    process_cwd = Path.cwd().resolve()
    script_path = Path(__file__).resolve()
    script_root = script_path.parents[2]
    status = (
        "ok"
        if served_root == process_cwd == script_root
        else "warning"
    )
    return {
        "identity_status": status,
        "served_root": str(served_root),
        "process_cwd": str(process_cwd),
        "script": str(script_path),
        "script_root": str(script_root),
    }


def tool_descriptors() -> list[dict[str, Any]]:
    return [
        {
            "name": "cxet_context_map",
            "description": (
                "Route a non-trivial CXET task to a compact, bounded context. "
                "Use before broad reads; it is static-only and returns no file excerpts."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_hint": {"type": "string"},
                    "scope": {"type": "string"},
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "required": ["task_hint"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cxet_context_search",
            "description": (
                "Search bounded line excerpts inside one declared CXET context scope. "
                "It never searches outside the manifest roots or runs commands."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string"},
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "required": ["scope", "query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cxet_context_postcheck",
            "description": (
                "Run one final static ownership/context postcheck for changed paths. "
                "It reports unmapped paths and suggests narrow static checks without executing them."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string"},
                    "changed_paths": {"type": "array", "items": {"type": "string"}},
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "required": ["changed_paths"],
                "additionalProperties": False,
            },
        },
        {
            "name": "cxet_hotpath_static_surface",
            "description": (
                "Read-only static production surface for CXET hot-path review. "
                "Reports build-profile evidence and token candidates, not violations, speedups, or runtime proof."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "surface": {"type": "string", "enum": list(cxet_toolbelt.HOTPATH_SURFACES)},
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "cxet_readiness_static_trace",
            "description": (
                "Read-only static exchange/trader readiness trace for CXET. "
                "Does not run builds, tests, Git, live tools, or network calls."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "exchange": {"type": "string"},
                    "market": {"type": "string"},
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "cxet_readiness_sources",
            "description": "List static CXET readiness source anchors and registered exchanges.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "format": {"type": "string", "enum": ["summary", "json"]},
                },
                "additionalProperties": False,
            },
        },
    ]


def render_payload(payload: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True)
    return cxet_toolbelt.render_summary(payload)


def render_identity_notice(identity: dict[str, str]) -> str:
    if identity.get("identity_status") == "warning":
        prefix = "WARNING: cxet_local checkout identity mismatch"
    else:
        prefix = "cxet_local identity: ok"
    return f"{prefix}; served_root={identity.get('served_root', 'unavailable')}"


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    args = arguments if arguments is not None else {}
    _validate_arguments(name, args)
    output_format = args.get("format") or "summary"
    if output_format not in {"summary", "json"}:
        raise ValueError("format must be summary or json")

    root = repo_root()
    limits = cxet_context._manifest_limits(cxet_context._load_manifest_file(root))
    limit = limits["map_bytes" if name == "cxet_context_map" else "detail_bytes"]
    if name == "cxet_context_map":
        payload = cxet_context.build_context_map(
            root,
            args.get("task_hint"),
            args.get("scope"),
        )
        rendered = (json.dumps(payload, ensure_ascii=False) if output_format == "json"
                    else "\n".join(cxet_context._summary_lines(payload)))
    elif name == "cxet_context_search":
        payload = cxet_context.search_context(
            root,
            args.get("scope"),
            args.get("query"),
            max_results=args.get("max_results", 20),
        )
        rendered = (json.dumps(payload, ensure_ascii=False) if output_format == "json"
                    else "\n".join(cxet_context._summary_lines(payload)))
    elif name == "cxet_context_postcheck":
        payload = cxet_context.build_postcheck(
            root,
            args.get("changed_paths"),
            args.get("scope"),
        )
        rendered = (json.dumps(payload, ensure_ascii=False) if output_format == "json"
                    else "\n".join(cxet_context._summary_lines(payload)))
    elif name == "cxet_hotpath_static_surface":
        payload = cxet_toolbelt.build_hotpath_surface(root, args.get("surface") or "all")
        rendered = render_payload(payload, output_format)
    elif name == "cxet_readiness_static_trace":
        payload = cxet_toolbelt.build_readiness_report(
            root,
            args.get("exchange"),
            args.get("market"),
        )
        rendered = render_payload(payload, output_format)
    elif name == "cxet_readiness_sources":
        payload = cxet_toolbelt.collect_sources(root)
        rendered = render_payload(payload, output_format)
    else:
        raise ValueError(f"unknown tool: {name}")
    identity = checkout_identity()
    structured_content = dict(payload)
    structured_content["identity"] = identity
    if output_format == "json":
        rendered = render_payload(structured_content, output_format)
    else:
        rendered = f"{render_identity_notice(identity)}\n{rendered}"
    return protocol.bound_result(payload, identity, rendered, limit,
                                 json_format=output_format == "json")


def _validate_arguments(name: str, args: Any) -> None:
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    descriptor = next((item for item in tool_descriptors() if item["name"] == name), None)
    if descriptor is None:
        raise ValueError(f"unknown tool: {name}")
    schema = descriptor["inputSchema"]
    if any(key not in schema["properties"] for key in args):
        raise ValueError("unknown tool argument")
    if any(key not in args for key in schema.get("required", [])):
        raise ValueError("required tool argument is missing")
    for key, value in args.items():
        rule = schema["properties"][key]
        kind = rule["type"]
        valid = ((kind == "string" and isinstance(value, str)) or
                 (kind == "integer" and isinstance(value, int) and not isinstance(value, bool)) or
                 (kind == "array" and isinstance(value, list) and
                  all(isinstance(item, str) for item in value)))
        if not valid:
            raise ValueError(f"invalid type for {key}")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"invalid value for {key}")
        if kind == "integer" and not rule["minimum"] <= value <= rule["maximum"]:
            raise ValueError(f"out of range: {key}")
    protocol.encode(args).decode("utf-8")


def response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": protocol.clip(message, 512)}}


def handle_message(message: Any) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return error_response(None, -32600, "request must be an object")
    request_id = message.get("id")
    method = message.get("method")
    if (message.get("jsonrpc") != "2.0" or not isinstance(method, str)
            or ("id" in message and (isinstance(request_id, bool) or
                not isinstance(request_id, (int, str, type(None))) or
                len(protocol.encode(request_id)) > 256))):
        return error_response(None, -32600, "invalid JSON-RPC request")
    # Notifications never produce responses or execute read-heavy tool calls.
    if "id" not in message:
        return None
    params = message.get("params", {})
    if not isinstance(params, dict):
        return error_response(request_id, -32602, "params must be an object")
    if method == "initialize":
        requested_protocol = params.get("protocolVersion")
        if requested_protocol is not None and not isinstance(requested_protocol, str):
            return error_response(request_id, -32602, "protocolVersion must be a string")
        protocol_version = (requested_protocol if requested_protocol in
                            SUPPORTED_PROTOCOL_VERSIONS else PROTOCOL_VERSION)
        return response(request_id, {
            "protocolVersion": protocol_version, "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": "current"},
            "instructions": "CXET local helper. Tools are read-only/static-only. "
                            "Never treat output as build, runtime, or live proof.",
        })
    if method == "ping":
        return response(request_id, {})
    if method == "tools/list":
        return response(request_id, {"tools": tool_descriptors()})
    if method == "tools/call":
        if (not isinstance(params.get("name"), str) or
                not isinstance(params.get("arguments", {}), dict)):
            return error_response(request_id, -32602, "invalid tool name or arguments")
        try:
            return response(request_id, call_tool(params["name"], params.get("arguments")))
        except Exception as exc:  # Expose the original failure, bounded.
            name = protocol.clip(params["name"], 128)
            text = f"cxet_local error ({name}): {protocol.clip(str(exc), 1024)}"
            return response(request_id, protocol.bound_result(
                {"evidence": "static-only", "tool": name, "error": text},
                checkout_identity(), text, cxet_context.DEFAULT_DETAIL_BYTES,
                is_error=True))
    return error_response(request_id, -32601, f"method not found: {method}")


def read_message() -> Any:
    return protocol.read_frame(sys.stdin.buffer)


def write_message(message: dict[str, Any]) -> None:
    sys.stdout.buffer.write(protocol.encode(message) + b"\n")
    sys.stdout.buffer.flush()


def run_server() -> int:
    while True:
        try:
            message = read_message()
        except protocol.FrameError as exc:
            write_message(error_response(None, -32700, str(exc)))
            continue
        if message is protocol.EOF:
            return 0
        reply = handle_message(message)
        if reply is not None:
            write_message(reply)


def self_test() -> int:
    init_reply = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    tools_reply = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    source_call_reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "cxet_readiness_sources", "arguments": {"format": "json"}},
        }
    )
    hotpath_call_reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "cxet_hotpath_static_surface",
                "arguments": {"surface": "transport", "format": "json"},
            },
        }
    )
    context_map_reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "cxet_context_map",
                "arguments": {"task_hint": "WebSocket framing", "format": "summary"},
            },
        }
    )
    context_search_reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "cxet_context_search",
                "arguments": {"scope": "transport", "query": "Ws", "format": "summary"},
            },
        }
    )
    context_postcheck_reply = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "cxet_context_postcheck",
                "arguments": {
                    "changed_paths": [
                        "src/src/Core/include/cxet/Network/Ws/Runtime/WsRuntime.hpp"
                    ],
                    "format": "summary",
                },
            },
        }
    )
    if not all(
        (
            init_reply,
            tools_reply,
            source_call_reply,
            hotpath_call_reply,
            context_map_reply,
            context_search_reply,
            context_postcheck_reply,
        )
    ):
        print("cxet_mcp_self_test failed: missing reply", file=sys.stderr)
        return 1
    tool_names = {tool["name"] for tool in tools_reply["result"]["tools"]}
    required = {
        "cxet_context_map",
        "cxet_context_search",
        "cxet_context_postcheck",
        "cxet_hotpath_static_surface",
        "cxet_readiness_static_trace",
        "cxet_readiness_sources",
    }
    if not required.issubset(tool_names):
        print("cxet_mcp_self_test failed: missing tools", file=sys.stderr)
        return 1
    for name, reply in (("cxet_readiness_sources", source_call_reply),
                        ("cxet_hotpath_static_surface", hotpath_call_reply),
                        ("cxet_context_map", context_map_reply),
                        ("cxet_context_search", context_search_reply),
                        ("cxet_context_postcheck", context_postcheck_reply)):
        if reply.get("result", {}).get("isError"):
            original = reply["result"]["content"][0]["text"]
            print(f"cxet_mcp_self_test failed: {name}: {original}", file=sys.stderr)
            return 1
    source_text = source_call_reply["result"]["content"][0]["text"]
    hotpath_text = hotpath_call_reply["result"]["content"][0]["text"]
    context_texts = [
        context_map_reply["result"]["content"][0]["text"],
        context_search_reply["result"]["content"][0]["text"],
        context_postcheck_reply["result"]["content"][0]["text"],
    ]
    if (
        "static-only" not in source_text
        or "static-only" not in hotpath_text
        or any("static-only" not in text for text in context_texts)
    ):
        print("cxet_mcp_self_test failed: missing static-only marker", file=sys.stderr)
        return 1
    print("cxet_mcp_self_test ok")
    return 0


def validate_protocol_trace(stdout: bytes, root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"observation": "subprocess_candidate", "status": "fail", "exit_code": 1,
                              "trace": ["initialize", "notifications/initialized", "tools/list", "tools/call"]}
    try:
        if not stdout.endswith(b"\n") or len(stdout) > 32768:
            raise ValueError("stdout is incomplete or exceeds the protocol budget")
        replies = [json.loads(line) for line in stdout.splitlines()]
        if len(replies) != 3:
            raise ValueError("unexpected reply count or notification response")
        for ident, reply in enumerate(replies, 1):
            if (not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0"
                    or type(reply.get("id")) is not int or reply["id"] != ident
                    or "error" in reply or not isinstance(reply.get("result"), dict)):
                raise ValueError("invalid JSON-RPC reply identity or error")
        if replies[0]["result"].get("protocolVersion") != PROTOCOL_VERSION:
            raise ValueError("unexpected protocolVersion")
        tools = replies[1]["result"].get("tools")
        if (not isinstance(tools, list) or not tools or
                any(not isinstance(tool, dict) or not isinstance(tool.get("name"), str)
                    or not isinstance(tool.get("inputSchema"), dict)
                    or tool["inputSchema"].get("type") != "object" for tool in tools)
                or not any(tool["name"] == "cxet_context_map" for tool in tools)):
            raise ValueError("invalid tools/list schema")
        call = replies[2]["result"]
        structured = call.get("structuredContent")
        if (call.get("isError") is True or call.get("output_complete") is False
                or not isinstance(structured, dict) or structured.get("evidence") != "static-only"
                or not isinstance(call.get("content"), list) or not call["content"]):
            raise ValueError("context tool failed or returned incomplete evidence")
        identity = structured.get("identity")
        expected = {"served_root": str(root.resolve()), "script_root": str(Path(__file__).resolve().parents[2]),
                    "script": str(Path(__file__).resolve()), "process_cwd": str(root.resolve()),
                    "identity_status": "ok"}
        if not isinstance(identity, dict) or any(identity.get(key) != value for key, value in expected.items()):
            raise ValueError("served checkout identity mismatch")
        result.update(status="pass", exit_code=0, identity=identity)
    except (ValueError, UnicodeDecodeError, TypeError) as exc:
        result["reason"] = str(exc) if not isinstance(exc, json.JSONDecodeError) else "non-JSON stdout contamination"
    return result


def _exchange_protocol(child: subprocess.Popen, request: bytes, timeout: float) -> tuple[bytes, bytes]:
    assert child.stdin is not None and child.stdout is not None and child.stderr is not None
    deadline = time.monotonic() + timeout
    child.stdin.write(request)
    child.stdin.close()
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    with selectors.DefaultSelector() as selector:
        for label, stream in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("protocol check timed out")
            for key, _ in selector.select(remaining):
                data = os.read(key.fd, 4096)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                destination = streams[key.data]
                destination.extend(data)
                if len(destination) > (32768 if key.data == "stdout" else 4096):
                    raise ValueError("protocol output budget exceeded")
    child.wait(timeout=max(0.001, deadline - time.monotonic()))
    return bytes(streams["stdout"]), bytes(streams["stderr"])


def protocol_check(root: Path) -> dict[str, Any]:
    root = root.resolve()
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                    "clientInfo": {"name": "cxet-protocol-check", "version": "current"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "cxet_context_map", "arguments": {"task_hint": "workflow policy", "scope": "ci"}}},
    ]
    request = b"".join(protocol.encode(message) + b"\n" for message in messages)
    child = None
    try:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--repo-root", str(root)],
                                 cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = _exchange_protocol(child, request, 10.0)
        result = validate_protocol_trace(stdout, root)
        result["stderr_bytes"] = len(stderr)
        if child.returncode != 0:
            result.update(status="fail", exit_code=1, reason="server subprocess exited unsuccessfully")
        return result
    except (OSError, TimeoutError, subprocess.TimeoutExpired) as exc:
        return {"observation": "subprocess_candidate", "status": "unavailable", "exit_code": 2,
                "reason": type(exc).__name__}
    except ValueError as exc:
        return {"observation": "subprocess_candidate", "status": "fail", "exit_code": 1, "reason": str(exc)}
    finally:
        if child is not None:
            if child.poll() is None:
                child.kill()
            child.wait()
            for stream in (child.stdin, child.stdout, child.stderr):
                if stream is not None:
                    stream.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CXET local stdio MCP server")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--protocol-check", action="store_true")
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--format", choices=("summary", "json"), default="summary")
    args = parser.parse_args(argv)
    set_repo_root(args.repo_root or Path.cwd())
    if args.protocol_check:
        result = protocol_check(repo_root())
        print(json.dumps(result, sort_keys=True) if args.format == "json" else
              "\n".join(f"{key}: {value}" for key, value in result.items()))
        return result["exit_code"]
    if args.self_test:
        return self_test()
    return run_server()


if __name__ == "__main__":
    raise SystemExit(main())
