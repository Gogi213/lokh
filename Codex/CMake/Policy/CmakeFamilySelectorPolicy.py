"""Pin the canonical thin owner wrapper and source build driver."""
from __future__ import annotations

import hashlib
from pathlib import Path
from ..Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity

ROOT = Path(__file__).resolve().parents[4]
_OWNER_WRAPPER = '''#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$ROOT/tools/Build/CompileTargets.py" --owner CXETCPP "$@"
'''
_OWNER_DRIVER_SHA256 = "fca750b173d07f13485b80777cbdf8625819f9030877189de0eaab4a2b3c2e61"


def validate_compile_selector_authority(
    text: str | list[str],
    errors: list[str] | None = None,
) -> None:
    """Pin the thin wrapper and reviewed owner driver, without executing it."""
    if errors is None:
        errors = text
        if not isinstance(errors, list):
            raise TypeError("errors must be a list")
        try:
            text = (ROOT / "compile.sh").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(
                f"compile.sh: cannot verify aggregate selectors: {exc}")
            return
    if not isinstance(text, str):
        errors.append("compile.sh: selector authority received no shell text")
        return
    if text != _OWNER_WRAPPER:
        errors.append("compile.sh: owner wrapper authority changed")
    driver = ROOT / "tools/Build/CompileTargets.py"
    try:
        if driver.is_symlink() or not driver.is_file():
            errors.append("compile.sh: owner driver must be a regular source file")
        elif hashlib.sha256(driver.read_bytes()).hexdigest() != _OWNER_DRIVER_SHA256:
            errors.append("compile.sh: reviewed owner driver identity changed")
    except OSError as exc:
        errors.append(f"compile.sh: cannot read owner driver: {exc}")
    if not reviewed_file_identity("tools/Build/ParallelPolicy.py", root=ROOT):
        errors.append("compile.sh: reviewed parallel resource policy identity changed")
    if not reviewed_file_identity("tools/Build/ToolchainProfiles.py", root=ROOT):
        errors.append("compile.sh: reviewed toolchain profile/storage admission identity changed")
