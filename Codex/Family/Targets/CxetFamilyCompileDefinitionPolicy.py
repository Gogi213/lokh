"""Fail-closed lexical policy for family compile definitions."""

from __future__ import annotations

import re

from Family.Verification.CxetFamilyVerificationInventory import (
    VERIFICATION_FRIEND_DEFINE,
    VERIFICATION_FRIEND_IDENTIFIERS,
)


_ACCESS_OR_DECLARATION = re.compile(
    r"(?<![A-Za-z0-9_$])(?:private|protected|public|class|struct|friend)"
    r"(?![A-Za-z0-9_$])")
_EXECUTION_CARRIER = re.compile(
    r"(?<![A-Za-z0-9_$])(?:__asm__|__asm|asm)"
    r"(?![A-Za-z0-9_$])|"
    r"(?<![A-Za-z0-9_$])(?:import|module|_Pragma|__pragma)"
    r"(?![A-Za-z0-9_$])|"
    r"(?<![A-Za-z0-9_$])(?:__has_include_next|__has_include|"
    r"__has_embed|__CONCAT|__CONCAT1)(?![A-Za-z0-9_$])|"
    r"(?i:(?<![A-Za-z0-9_$])\.(?:include|incbin)"
    r"(?![A-Za-z0-9_$]))")


def dangerous_compile_definition(value: str) -> bool:
    """Inspect both macro name and replacement text after CMake expansion."""
    return (
        _ACCESS_OR_DECLARATION.search(value) is not None or
        _EXECUTION_CARRIER.search(value) is not None or
        any(identifier in value for identifier in (
            VERIFICATION_FRIEND_DEFINE,
            *VERIFICATION_FRIEND_IDENTIFIERS,
        )) or
        "\\" in value or "##" in value or "%:%:" in value
    )
