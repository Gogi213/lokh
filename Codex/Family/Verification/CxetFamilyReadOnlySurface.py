"""Fail-closed physical surfaces for read-only CXET family consumers."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath

from Family.Sources.CxetFamilyHeaderContract import source_tree_files
from Family.Targets.CxetFamilyOwnershipPolicy import CANONICAL_EXACT_SOURCE_ATTACHMENTS


_CORE_INCLUDE = "src/src/Contracts/include"
_CORE_SOURCE = "src/src/Contracts/src"
_PARSER_CONTRACT_INCLUDE = "apps/hft-parser/src/Contracts/include"
_PARSER_CLIENT_INCLUDE = "apps/hft-parser/src/Clients/include"

_CORE_API_HEADERS = frozenset({
    "cxet/Api/Instrument/InstrumentAssetDomain.hpp",
    "cxet/Api/Instrument/InstrumentEconomicFacts.hpp",
    "cxet/Api/Instrument/InstrumentFinancialFacts.hpp",
    "cxet/Api/Instrument/InstrumentListingIdentity.hpp",
    "cxet/Api/Instrument/InstrumentUniverseTypes.hpp",
    "cxet/Api/Market/PublicMarketDataTypes.hpp",
    "cxet/Api/Order/OrderRejectHint.hpp",
    "cxet/Api/Order/OrderResponseEvidence.hpp",
    "cxet/Api/Reference/DeliveryReference.hpp",
    "cxet/Api/Resolve/InstrumentRouteInfo.hpp",
    "cxet/Api/Stream/RuntimeInstrumentNumericContext.hpp",
    "cxet/Api/Ticker/Ticker24hQualityTypes.hpp",
    "cxet/Api/Trading/NativePolicy.hpp",
    "cxet/Api/Trading/TradingInstrumentPermission.hpp",
    "cxet/Api/User/AccountObservation.hpp",
    "cxet/Api/User/AccountObservationSelection.hpp",
    "cxet/Api/User/AccountQuery.hpp",
    "cxet/Api/User/AccountQueryPage.hpp",
    "cxet/Api/User/AccountTransaction.hpp",
    "cxet/Api/User/FeeObservation.hpp",
    "cxet/Api/User/NativePnl.hpp",
    "cxet/Build/ExchangeSelection.hpp",
    "cxet/ExchangeContract/Contract.hpp",
    "cxet/ExchangeContract/Detail/Access.hpp",
    "cxet/ExchangeContract/Detail/AttributeAccess.hpp",
    "cxet/ExchangeContract/Detail/Attributes.hpp",
    "cxet/ExchangeContract/Detail/FixedString.hpp",
    "cxet/ExchangeContract/Field.hpp",
    "cxet/ExchangeContract/Locator.hpp",
    "cxet/ExchangeContract/Message.hpp",
    "cxet/ExchangeContract/Numeric.hpp",
    "cxet/ExchangeContract/Request.hpp",
    "cxet/ExchangeContract/Semantic/Demand.hpp",
    "cxet/ExchangeContract/Semantic/Roles.hpp",
    "cxet/ExchangeContract/Session.hpp",
    "cxet/Market/Depth.hpp",
    "cxet/Order/ClientIdFormat.hpp",
    "cxet/Order/PlacementAdmission.hpp",
    "cxet/Os/ResidentArena.hpp",
    "cxet/Os/ResidentMemory.hpp",
    "cxet/Runtime/Market/CommitContract.hpp",
    "cxet/Runtime/SpscRing.hpp",
})
_CORE_HEADER_PREFIXES = ("cxet/Canon/", "cxet/Parse/", "cxet/Primitives/")
_CORE_SOURCES = frozenset(
    PurePosixPath(source).relative_to(_CORE_SOURCE).as_posix()
    for source in CANONICAL_EXACT_SOURCE_ATTACHMENTS[
        "cxet_read_only_contracts"]
)
_PARSER_CLIENT_HEADERS = frozenset({
    "hft_parser/History/HistoryClient.hpp",
    "hft_parser/History/HistorySourceOwner.hpp",
    "hft_parser/Projection/ProjectionClient.hpp",
    "hft_parser/Projection/ProjectionSource.hpp",
    "hft_parser/Projection/ReferenceProjectionSource.hpp",
    "hft_parser/Market/PublicMarketClient.hpp",
    "hft_parser/Market/CatalogPreparation.hpp",
    "hft_parser/Market/MarketDemandClient.hpp",
    "hft_parser/Market/PublicMarketSourceOwner.hpp",
    "hft_parser/History/HistoryTransportProtocol.hpp",
    "hft_parser/History/MarketHistoryProtocol.hpp",
    "hft_parser/Ipc/LocalDataPlane.hpp",
    "hft_parser/Projection/ProjectionPublisher.hpp",
    "hft_parser/Projection/ReferenceProjectionPublisher.hpp",
    "hft_parser/Reference/CurrentReferenceClient.hpp",
    "hft_parser/Session/SessionClient.hpp",
    "hft_parser/Session/Private/Capacity.hpp",
    "hft_parser/Session/Private/Client.hpp",
})

_HEADER_SUFFIXES = frozenset({".h", ".hpp", ".ipp"})
_QUOTED_INCLUDE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
_TERMINAL_CAPABILITY_PATTERNS = (
    re.compile(r"\bHotOrderPath\b"),
    re.compile(r"\bOrder(?:Rest|Ws)Session"),
    re.compile(r"\bUserSession"),
    re.compile(r"\bsendPreparedOrder\b"),
    re.compile(r"\b(?:wolfSSL|SSL)_write\b"),
    re.compile(r"\btls::(?:Client|SocketState|TerminalWriter)\b"),
    re.compile(r"\b(?:send|sendto|sendmsg|write|writev)\s*\("),
    re.compile(r'^\s*#\s*include\s+<(?:sys/socket\.h|unistd\.h)>',
               re.MULTILINE),
    re.compile(r'^\s*#\s*include\s+[<"](?:api/(?:hotpath|order|user)/|'
               r'network/)', re.MULTILINE),
)
_PARSER_FORBIDDEN_INCLUDES = (
    "hft_parser/Transport/",
    "hft_parser/History/FundingHistoryIpc.hpp",
    "hft_parser/History/MarketHistoryIpc.hpp",
)

_LEGACY_CORE_PATHS = (
    "src/src/canon",
    "src/src/parse",
    "src/src/primitives",
    "src/src/api/instrument/InstrumentAssetDomain.hpp",
    "src/src/api/instrument/InstrumentUniverseTypes.hpp",
    "src/src/api/market/PublicMarketDataTypes.hpp",
    "src/src/api/resolve/InstrumentRouteInfo.hpp",
    "src/src/api/ticker/Ticker24hQualityTypes.hpp",
    "src/src/Core/include/cxet/canon",
    "src/src/Core/include/cxet/parse",
    "src/src/Core/include/cxet/primitives",
    "src/src/Core/include/cxet/Api/Instrument/InstrumentAssetDomain.hpp",
    "src/src/Core/include/cxet/Api/Instrument/InstrumentListingIdentity.hpp",
    "src/src/Core/include/cxet/Api/Instrument/InstrumentUniverseTypes.hpp",
    "src/src/Core/include/cxet/Api/Market/PublicMarketDataTypes.hpp",
    "src/src/Core/include/cxet/Api/Reference/DeliveryReference.hpp",
    "src/src/Core/include/cxet/Api/Resolve/InstrumentRouteInfo.hpp",
    "src/src/Core/include/cxet/Api/Market/Ticker/Ticker24hQualityTypes.hpp",
)


def _relative_files(
    root: Path,
    relative_root: str,
    errors: list[str],
) -> dict[str, Path]:
    base = root / relative_root
    return {
        path.relative_to(base).as_posix(): path
        for path in source_tree_files(
            root, base, errors, f"read-only surface {relative_root}")
    }


def _read(path: Path, root: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(
            f"cannot read read-only surface "
            f"{path.relative_to(root).as_posix()}: {exc}")
        return ""


def _include_candidates(
    source: str,
    include: str,
) -> tuple[str, ...]:
    source_parent = PurePosixPath(source).parent.as_posix()
    relative = posixpath.normpath(posixpath.join(source_parent, include))
    logical = posixpath.normpath(include)
    return tuple(dict.fromkeys((relative, logical)))


def _validate_include_closure(
    *,
    files: dict[str, Path],
    inventories: tuple[frozenset[str], ...],
    root: Path,
    errors: list[str],
) -> None:
    combined = frozenset().union(*inventories)
    for relative, path in sorted(files.items()):
        text = _read(path, root, errors)
        for include in _QUOTED_INCLUDE.findall(text):
            candidates = _include_candidates(relative, include)
            if not any(candidate in combined for candidate in candidates):
                errors.append(
                    f"{path.relative_to(root).as_posix()}: quoted include "
                    f"escapes the reviewed read-only roots: {include}")


def _validate_terminal_capabilities(
    files: dict[str, Path],
    root: Path,
    errors: list[str],
) -> None:
    for path in files.values():
        text = _read(path, root, errors)
        for pattern in _TERMINAL_CAPABILITY_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"{path.relative_to(root).as_posix()}: terminal exchange "
                    f"capability leaked into a read-only physical surface")


def validate_read_only_physical_surfaces(
    root: Path,
    errors: list[str],
) -> None:
    """Prove that diagnostic consumers cannot include terminal CXET APIs."""
    core_headers = _relative_files(root, _CORE_INCLUDE, errors)
    core_sources = _relative_files(root, _CORE_SOURCE, errors)
    parser_contracts = _relative_files(root, _PARSER_CONTRACT_INCLUDE, errors)
    parser_clients = _relative_files(root, _PARSER_CLIENT_INCLUDE, errors)

    unexpected_core = sorted(
        relative for relative in core_headers
        if (relative not in _CORE_API_HEADERS and
            not relative.startswith(_CORE_HEADER_PREFIXES))
    )
    if unexpected_core:
        errors.append(
            "read-only CXET include root gained unreviewed paths: " +
            ", ".join(unexpected_core))
    missing_core = sorted(_CORE_API_HEADERS - frozenset(core_headers))
    if missing_core:
        errors.append(
            "read-only CXET include root lost required value contracts: " +
            ", ".join(missing_core))
    non_headers = sorted(
        relative for relative in core_headers
        if PurePosixPath(relative).suffix not in _HEADER_SUFFIXES)
    if non_headers:
        errors.append(
            "read-only CXET include root gained non-header files: " +
            ", ".join(non_headers))
    parser_contract_non_headers = sorted(
        relative for relative in parser_contracts
        if PurePosixPath(relative).suffix not in _HEADER_SUFFIXES)
    if parser_contract_non_headers:
        errors.append(
            "Parser contract include root gained non-header files: " +
            ", ".join(parser_contract_non_headers))
    if frozenset(core_sources) != _CORE_SOURCES:
        errors.append(
            "read-only CXET compiled-source inventory changed: expected="
            f"{sorted(_CORE_SOURCES)}, actual={sorted(core_sources)}")
    if frozenset(parser_clients) != _PARSER_CLIENT_HEADERS:
        errors.append(
            "Parser producer-client header inventory changed: expected="
            f"{sorted(_PARSER_CLIENT_HEADERS)}, "
            f"actual={sorted(parser_clients)}")

    duplicate_parser_headers = sorted(
        frozenset(parser_contracts) & frozenset(parser_clients))
    if duplicate_parser_headers:
        errors.append(
            "Parser contract/client roots duplicate logical headers: " +
            ", ".join(duplicate_parser_headers))

    for relative in _LEGACY_CORE_PATHS:
        if (root / relative).exists():
            errors.append(
                f"legacy full-core contract path still exists: {relative}")
    for backend_root in (
            "apps/hft-parser/src/Runtime/include",
            "apps/hft-parser/src/Process/include"):
        for relative in _PARSER_CLIENT_HEADERS:
            if (root / backend_root / relative).exists():
                errors.append(
                    "Parser producer-client header remains duplicated under "
                    f"{backend_root}: {relative}")

    _validate_terminal_capabilities(core_headers, root, errors)
    _validate_terminal_capabilities(core_sources, root, errors)
    _validate_terminal_capabilities(parser_contracts, root, errors)
    _validate_terminal_capabilities(parser_clients, root, errors)
    _validate_include_closure(
        files=core_headers,
        inventories=(frozenset(core_headers),),
        root=root,
        errors=errors,
    )
    _validate_include_closure(
        files=core_sources,
        inventories=(frozenset(core_headers),),
        root=root,
        errors=errors,
    )
    _validate_include_closure(
        files=parser_contracts,
        inventories=(
            frozenset(parser_contracts),
            frozenset(core_headers),
        ),
        root=root,
        errors=errors,
    )
    _validate_include_closure(
        files=parser_clients,
        inventories=(
            frozenset(parser_clients),
            frozenset(parser_contracts),
            frozenset(core_headers),
        ),
        root=root,
        errors=errors,
    )

    for surface, files in (
            ("contract", parser_contracts),
            ("client", parser_clients)):
        for relative, path in sorted(files.items()):
            text = _read(path, root, errors)
            for forbidden in _PARSER_FORBIDDEN_INCLUDES:
                if forbidden in text:
                    errors.append(
                        f"{path.relative_to(root).as_posix()}: Parser "
                        f"{surface} surface includes backend transport "
                        f"{forbidden}")
