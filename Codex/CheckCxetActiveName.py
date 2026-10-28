#!/usr/bin/env python3
"""Fail closed on ambiguous CXETCPP naming in the active root identity surface."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

TEXT_FILES = (
    ".github/workflows/benchmarks.yml",
    ".github/workflows/cpp.yml",
    ".gitignore",
    "CMakeLists.txt",
    "README.md",
    "compile.sh",
    "server/AWS_TOKYO_LOW_LATENCY_RUNBOOK.md",
    "server/README.md",
    "server/opt.sh",
    "src/src/Core/src/Exchanges/Gate/ApiV4/Spot/Routing/Config.cpp",
    "src/src/Core/src/Exchanges/Gate/ApiV4/Futures/Routing/Market/MarketRoutes.ipp",
    "src/src/Core/src/Exchanges/Okx/Routing/Futures/Market/MarketRoutes.ipp",
    "src/src/Core/src/Network/Rest/Detail/NativeHttpCodec.cpp",
    "src/src/Core/src/Network/Ws/Handshake/WsHandshake.cpp",
    "tools/Benchmarks/TraderBinaryWeightReport.py",
    "tools/Codex/CxetLocal.config.toml",
    "tools/Codex/CxetMcpServer.py",
    "tools/Codex/CxetToolbelt.py",
)

REQUIRED: dict[str, tuple[str, ...]] = {
    ".github/workflows/benchmarks.yml": ("Checkout CXET",),
    ".github/workflows/cpp.yml": ("Checkout CXET",),
    "CMakeLists.txt": (
        "project(CXET LANGUAGES C CXX)",
        'OUTPUT_NAME "cxet-bench"',
        "CXET is Clang-only",
    ),
    "README.md": ("# CXET",),
    "compile.sh": (
        "tools/Build/CompileTargets.py",
        "--owner CXETCPP",
    ),
    "server/opt.sh": (
        "# CXET unified trading-stack host setup (Ubuntu 24.04).",
    ),
    "src/src/Core/src/Exchanges/Gate/ApiV4/Spot/Routing/Config.cpp": ('"CXET/1.0"',),
    "src/src/Core/src/Exchanges/Gate/ApiV4/Futures/Routing/Market/MarketRoutes.ipp": (
        '.restHeaderValue = "CXET/1.0"',
    ),
    "src/src/Core/src/Exchanges/Okx/Routing/Futures/Market/MarketRoutes.ipp": (
        '.restHeaderValue = "CXET/1.0"',
    ),
    "src/src/Core/src/Network/Rest/Detail/NativeHttpCodec.cpp": (
        "User-Agent: CXET/1.0",
    ),
    "src/src/Core/src/Network/Ws/Handshake/WsHandshake.cpp": (
        "User-Agent: cxet-ws",
    ),
    "tools/Codex/CxetLocal.config.toml": (
        'cwd = "/mnt/c/Users/be0h/PycharmProjects/CXET"',
    ),
}

# These strings are deliberately retained solely to recognize/ignore artifacts
# produced by the former name and to clean an already-managed legacy chrony line.
LEGACY_ALLOWLIST: dict[str, frozenset[str]] = {
    ".gitignore": frozenset(
        {
            "CXETCPP_FULL_DISASM.*",
            "CXETCPP_FULL_DISASM_2026-07-08T16-40-25+0300.asm",
        }
    ),
    "server/opt.sh": frozenset(
        {
            "  cleaned=\"$(printf '%s\\n' \"$existing\" | awk "
            "'!/169[.]254[.]169[.]123/ && "
            "!/^# CXET AWS Time Sync source[.]$/ && "
            "!/^# CXETCPP AWS Time Sync source[.]$/')\""
        }
    ),
}


def read_text(relative: str, errors: list[str]) -> str | None:
    path = ROOT / relative
    if not path.is_file():
        errors.append(f"missing active identity file: {relative}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"cannot read {relative}: {exc}")
        return None


def main() -> int:
    errors: list[str] = []
    texts: dict[str, str] = {}

    for relative in TEXT_FILES:
        text = read_text(relative, errors)
        if text is not None:
            texts[relative] = text

    for relative, fragments in REQUIRED.items():
        text = texts.get(relative)
        if text is None:
            continue
        for fragment in fragments:
            if fragment not in text:
                errors.append(f"{relative}: missing CXET identity: {fragment!r}")

    for relative, text in texts.items():
        allowed = LEGACY_ALLOWLIST.get(relative, frozenset())
        observed_allowed: set[str] = set()
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "CXETCPP" not in line and "cxetcpp" not in line:
                continue
            if line in allowed:
                observed_allowed.add(line)
                continue
            errors.append(
                f"{relative}:{line_number}: ambiguous legacy product name: {line!r}"
            )
        missing_allowlist = allowed - observed_allowed
        for line in sorted(missing_allowlist):
            errors.append(
                f"{relative}: missing exact legacy-compatibility allowlist line: {line!r}"
            )

    if errors:
        print("CXET active-name check: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "CXET active-name check: PASS "
        f"({len(TEXT_FILES)} active identity files, 3 legacy artifacts allowed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
