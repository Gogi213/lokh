"""Bounded newline framing and serialized MCP tool results."""

from __future__ import annotations

import json
from typing import Any, BinaryIO

MAX_FRAME_BYTES = 1024 * 1024
EOF = object()


class FrameError(ValueError):
    pass


def read_frame(stream: BinaryIO) -> Any:
    while True:
        line = stream.readline(MAX_FRAME_BYTES + 1)
        if not line:
            return EOF
        if len(line) > MAX_FRAME_BYTES:
            # Drain only this frame with bounded reads; the next line survives.
            while not line.endswith(b"\n"):
                line = stream.readline(MAX_FRAME_BYTES + 1)
                if not line:
                    break
            raise FrameError("frame exceeds 1048576 bytes")
        if not line.strip():
            continue
        try:
            return json.loads(line.decode("utf-8"), parse_constant=_invalid_constant)
        except (ValueError, RecursionError) as exc:
            raise FrameError("invalid JSON or UTF-8 frame") from exc


def _invalid_constant(value: str) -> None:
    raise ValueError("non-JSON constant")


def encode(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8", errors="replace")


def clip(text: str, max_bytes: int) -> str:
    return text.encode("utf-8", errors="replace")[:max(0, max_bytes)].decode(
        "utf-8", errors="ignore")


def _shrink(value: dict[str, Any]) -> bool:
    candidates = []

    def visit(container: Any) -> None:
        items = container.items() if isinstance(container, dict) else enumerate(container)
        for key, child in items:
            if key in {"identity", "evidence", "route_status", "scope"}:
                continue
            if isinstance(child, list) and child:
                candidates.append((len(encode(child)), container, key, "list"))
            elif isinstance(child, str) and len(encode(child)) > 80:
                candidates.append((len(encode(child)), container, key, "str"))
            elif isinstance(child, dict):
                if child:
                    visit(child)
                if len(encode(child)) > 80:
                    candidates.append((len(encode(child)), container, key, "dict"))
    visit(value)
    if not candidates:
        return False
    _, parent, key, kind = max(candidates, key=lambda item: item[0])
    child = parent[key]
    if kind == "list":
        parent[key] = child[:len(child) // 2]
    elif kind == "str":
        parent[key] = clip(child, len(child.encode("utf-8", errors="replace")) // 2)
    else:
        # A bounded omission preserves the surrounding tool schema.
        parent[key] = {"omitted": True}
    return True


def bound_result(payload: dict[str, Any], identity: dict[str, str], text: str,
                 limit: int, *, json_format: bool = False,
                 is_error: bool = False) -> dict[str, Any]:
    structured = json.loads(encode(payload))
    identity = json.loads(encode(identity))
    structured["identity"] = identity
    result = {
        "content": [{"type": "text", "text": text}],
        "isError": is_error, "identity": identity, "structuredContent": structured,
        "output_limit_bytes": limit, "output_truncated": False,
        "output_complete": not is_error and structured.get("search_complete", True),
    }
    if len(encode(result)) <= limit:
        return result
    result["output_truncated"] = True
    result["output_complete"] = False
    structured["output_truncated"] = True
    structured["output_complete"] = False
    if "search_complete" in structured:
        structured["search_complete"] = False
        structured["truncated"] = True
    result["content"][0]["text"] = ""
    # Preserve enough space for a readable notice and text. All accounting is
    # for the final result, including repeated identity and JSON escaping.
    while len(encode(result)) > limit * 2 // 3 and _shrink(structured):
        pass
    if len(encode(result)) > limit * 2 // 3:
        for key in identity:
            if key != "identity_status":
                identity[key] = clip(identity[key], 128)
        structured["identity_truncated"] = True
        result["identity_truncated"] = True
    if json_format:
        result["content"][0]["text"] = encode(structured).decode("utf-8")
        while len(encode(result)) > limit and _shrink(structured):
            result["content"][0]["text"] = encode(structured).decode("utf-8")
    else:
        notice = "\noutput_truncated: true; output_complete: false"
        header = (f"evidence: {structured.get('evidence', 'static-only')}\n"
                  f"identity_status: {identity.get('identity_status', 'unavailable')}\n")
        low, high = 0, len(text.encode("utf-8", errors="replace"))
        while low < high:
            middle = (low + high + 1) // 2
            result["content"][0]["text"] = header + clip(text, middle) + notice
            if len(encode(result)) <= limit:
                low = middle
            else:
                high = middle - 1
        result["content"][0]["text"] = header + clip(text, low) + notice
    if len(encode(result)) > limit:
        raise ValueError("response limit is too small for MCP identity metadata")
    return result
