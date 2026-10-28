"""Exact provenance for active CMake filesystem side effects."""

from __future__ import annotations

from CMake.Flow.CmakeFamilyState import normalize_synthetic_binary_path
from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity


_BINARY = "__CXET_CMAKE_BINARY__"
_LIBURING = _BINARY + "/src/src/_deps/liburing/install"


def _one_path(raw: str, expand) -> str | None:
    values = expand([raw])
    return values[0] if len(values) == 1 else None


def _exact_binary(raw: str, expected: str, expand) -> bool:
    value = _one_path(raw, expand)
    return (
        value is not None and
        normalize_synthetic_binary_path(value) == expected
    )


def approved_file_side_effect(
    operation: str,
    raw_words: list[str],
    expand,
    origin: str,
) -> bool:
    """Allow only reviewed owner/output/content combinations."""
    relative = origin.split(":", 1)[0]
    if operation == "WRITE" and relative == "cmake/CxetExchangeSelection.cmake":
        return (reviewed_file_identity(relative) and len(raw_words) == 3 and
                _exact_binary(raw_words[1], _BINARY + "/.cxet-exchanges.json", expand) and
                raw_words[2] == "${CXET_EXCHANGE_RECORD}\\n")
    if operation == "WRITE" and relative == "src/src/CMakeLists.txt":
        return (
            len(raw_words) == 3 and
            _exact_binary(
                raw_words[1], _BINARY + "/.cxet_sanitizer_profile", expand) and
            raw_words[2] == "${CXET_SANITIZER_PROFILE}\\n"
        )
    if operation == "WRITE" and relative == "apps/trading-core/CMakeLists.txt":
        return (
            len(raw_words) == 3 and
            _exact_binary(
                raw_words[1],
                _BINARY + "/apps/trading-core/generated/trading_core/"
                "Strategy/StrategyHeaders.manifest",
                expand,
            ) and
            raw_words[2] in {
                "${TRADING_CORE_STRATEGY_HEADERS_ARG}\\n",
                "${TRADING_CORE_STRATEGY_HEADERS_MANIFEST_CONTENT}",
            }
        )
    if operation == "MAKE_DIRECTORY" and relative == "src/src/CMakeLists.txt":
        values = [_one_path(raw, expand) for raw in raw_words[1:]]
        return values == [_LIBURING + "/include"]
    if (operation == "MAKE_DIRECTORY" and
            relative == "apps/trading-core/CMakeLists.txt"):
        return (
            len(raw_words) == 2 and
            _exact_binary(
                raw_words[1],
                _BINARY + "/apps/trading-core/generated/trading_core/Strategy",
                expand,
            )
        )

    # Invoked registry scripts do not borrow generic writer authority. Their
    # complete helper/call/output recipe is owned by CmakeFamilyScriptPolicy.
    return False
