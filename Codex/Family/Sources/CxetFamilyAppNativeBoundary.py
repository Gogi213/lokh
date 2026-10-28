"""Keep exchange/protocol implementation behind CXET's application APIs.

This is a bounded source guard, not C++ type inference or runtime evidence.
It checks every source spelling below the two app src roots, independently of
the active CMake profile. Archive readers, config values, IPC protocols and
diagnostic values remain legal; none exempts a file from native include checks.
"""

from __future__ import annotations

import posixpath
import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path

from Family.Sources.CxetFamilyCppPolicy import (
    CPP_SCAN_SUFFIXES, cpp_code_view, cpp_include_syntax,
)
from Family.Sources.CxetFamilyHeaderContract import source_tree_files


APP_NATIVE_BOUNDARY_ROOTS = (
    "apps/hft-parser/src", "apps/trader/src",
)
_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_MAX_TOKENS = 500_000
_MAX_DECISION_TOKENS = 4096
_MAX_ALIASES = 256
_TOKEN = re.compile(rb'"[^"\r\n]*"|\'[\s\S]?\'|[A-Za-z_$][A-Za-z0-9_$]*|'
                    rb'::|==|!=|<=|>=|&&|\|\||->|[^\s]')
_PROTOCOL_TYPES = frozenset({
    b"RouteTransport", b"PublicMarketTransport", b"PublicMarketWireFormat",
    b"InstrumentUniverseSourceMode", b"NativeProtocol", b"WireProtocol",
    b"TransportProtocol", b"NetworkProtocol", b"ApiProtocol", b"Protocol", b"Transport",
})
_PROTOCOL_VALUES = frozenset({
    b"Grpc", b"GRPC", b"Rest", b"REST", b"Ws", b"WS", b"WebSocket",
    b"Websocket", b"Fix", b"FIX", b"FixSbe", b"Https", b"HTTP", b"Http",
    b"SbeBinary", b"FixSbeBinary", b"ProtobufBinary", b"JsonText",
    b"RestSnapshot", b"WsSnapshotDelta", b"GrpcSnapshot",
})
_NATIVE_CONTEXT = re.compile(
    rb"Grpc|GRPC|WebSocket|Websocket|(?:^|_)WS(?:_|$)|Rest|REST|FixSbe|"
    rb"(?:^|_)FIX(?:_|$)|Https|Http|TLS|Tls|native|Native|protocol|Protocol|"
    rb"transport|Transport|(?:^|[a-z0-9_])(?:Ws|Fix)(?:[A-Z_]|$)|"
    rb"^(?:grpc|ws|fix|rest|http|tls)[A-Z_]|^(?:grpc|ws|fix|rest|http|https|tls)$")
_NATIVE_INCLUDE = re.compile(
    r"(?:^|/)cxet/(?:Exchanges/|Network/(?:Grpc|Ws|Fix|Rest|Http|Tls|Tcp|Udp)/|"
    r"Runtime/Market/Transport/(?:Grpc|Ws|Fix|Rest|Http|Tls|Tcp|Udp)/)")
@dataclass(frozen=True)
class _Token:
    value: bytes
    offset: int


def _native_include(include: bytes) -> bool:
    spelling = posixpath.normpath(include.decode("utf-8", errors="replace").replace("\\", "/"))
    return _NATIVE_INCLUDE.search(spelling) is not None


def _pairs(tokens: list[_Token]) -> dict[int, int]:
    result: dict[int, int] = {}
    stack: list[int] = []
    closes = {b")": b"(", b"]": b"[", b"}": b"{"}
    for index, token in enumerate(tokens):
        if token.value in {b"(", b"[", b"{"}:
            stack.append(index)
        elif token.value in closes:
            if stack and tokens[stack[-1]].value == closes[token.value]:
                opening = stack.pop()
                result[opening] = index
                result[index] = opening
    return result


def _protocol_types(tokens: list[_Token], errors: list[str]) -> set[bytes]:
    """Recognize aliases of native enums, without treating IPC Protocol as one."""
    types = set(_PROTOCOL_TYPES)
    # Fixed point is bounded by the number of aliases, independent of file size.
    aliases: list[tuple[bytes, bytes]] = []
    for index in range(len(tokens) - 3):
        if tokens[index].value != b"using" or tokens[index + 2].value != b"=":
            continue
        end = index + 3
        while (end < len(tokens) and end - index < 256 and
               tokens[end].value not in {b";", b"{", b"}"}):
            end += 1
        if end - index >= 256:
            errors.append("app native boundary alias exceeds 256 token scan bound")
            continue
        if end > index + 3 and end < len(tokens) and tokens[end].value == b";":
            aliases.append((tokens[index + 1].value, tokens[end - 1].value))
            if len(aliases) > _MAX_ALIASES:
                errors.append("app native boundary source exceeds 256 alias scan bound")
                return types
    for _ in range(len(aliases) + 1):
        before = len(types)
        types.update(alias for alias, target in aliases if target in types)
        if len(types) == before:
            break
    return types


def _has_protocol(values: list[bytes], types: set[bytes]) -> bool:
    return any(values[index] in types and values[index + 1] == b"::" and
               values[index + 2] in _PROTOCOL_VALUES
               for index in range(len(values) - 2))


def _has_venue(values: list[bytes]) -> bool:
    return (any(value.startswith(b"kExchangeId") and value != b"kExchangeIdUnknown"
                for value in values) or any(
        values[index] in {b"ExchangeId", b"Exchange", b"Venue", b"VenueId"} and
        values[index + 1] == b"::" and
        values[index + 2] not in {b"Unknown", b"None", b"Invalid"}
        for index in range(len(values) - 2)))


def _literal_return(values: list[bytes]) -> bool:
    # Display switches may map an enum to a literal. An added runtime call or
    # nonliteral result immediately loses this narrow syntactic exemption.
    return (len(values) == 3 and values[0] == b"return" and
            values[1].startswith(b'"') and values[2] == b";")


def _literal_display_body(values: list[bytes]) -> bool:
    if values and values[0] == b")":
        values = values[1:]
    branches = [values]
    if b"else" in values:
        split = values.index(b"else")
        branches = [values[:split], values[split + 1:]]
    for branch in branches:
        if len(branch) >= 2 and branch[0] == b"{" and branch[-1] == b"}":
            branch = branch[1:-1]
        if not _literal_return(branch):
            return False
    return True


def _statement_end(tokens: list[_Token], start: int,
                   pairs: dict[int, int]) -> int:
    if start < len(tokens) and tokens[start].value == b"{" and start in pairs:
        return pairs[start] + 1
    index = start
    for _ in range(_MAX_DECISION_TOKENS):
        if index >= len(tokens):
            break
        if tokens[index].value in {b";", b"}"}:
            return index + 1
        if tokens[index].value in {b"(", b"[", b"{"} and index in pairs:
            index = pairs[index] + 1
        else:
            index += 1
    return index


def _lambda_bodies(tokens: list[_Token], pairs: dict[int, int]) -> set[int]:
    """Locate bodies separately from the expressions constructing callbacks.

    Only a capture followed by a lambda declarator is a candidate. Unsupported
    declarators remain in the expression scan and retain its fail-closed bound.
    """
    bodies: set[int] = set()
    capture_prefixes = {b"return", b"co_return", b"throw", b"=", b"(", b"{",
                        b",", b";", b":", b"?", b"+", b"-", b"!", b"~",
                        b"*", b"&", b"&&", b"||"}
    declarator_starts = {b"{", b"(", b"<", b"[", b"mutable", b"constexpr",
                         b"consteval", b"noexcept", b"->", b"requires"}
    for index, token in enumerate(tokens):
        if token.value != b"[" or index not in pairs:
            continue
        if index and tokens[index - 1].value not in capture_prefixes:
            continue
        cursor = pairs[index] + 1
        if cursor >= len(tokens) or tokens[cursor].value not in declarator_starts:
            continue
        angle_depth = 0
        for _ in range(_MAX_DECISION_TOKENS):
            if cursor >= len(tokens):
                break
            value = tokens[cursor].value
            if value == b"{":
                if cursor in pairs:
                    bodies.add(cursor)
                break
            if value in {b"(", b"["} and cursor in pairs:
                cursor = pairs[cursor] + 1
                continue
            if value == b"<":
                angle_depth += 1
            elif value == b">" and angle_depth:
                angle_depth -= 1
            elif not angle_depth and value in {
                    b";", b"}", b")", b"]", b"=", b"?", b":", b","}:
                break
            cursor += 1
    return bodies


def _lambda_body_evidence(tokens: list[_Token], pairs: dict[int, int],
                          bodies: set[int], types: set[bytes]) -> dict[int, list[bytes]]:
    """Summarize native evidence without repeatedly walking nested bodies.

    A callback can supply a value to an outer predicate, including through an
    immediate invocation. Keep one witness of each relevant kind; the full
    outer walk still owns decisions inside callback bodies.
    """
    values = [token.value for token in tokens]
    protocols = [index for index in range(len(values) - 2)
                 if _has_protocol(values[index:index + 3], types)]
    venues = [index for index, value in enumerate(values)
              if _has_venue(values[index:index + 3])]
    native = [index for index, value in enumerate(values)
              if _NATIVE_CONTEXT.search(value) is not None]
    result: dict[int, list[bytes]] = {}
    for opening in bodies:
        closing = pairs[opening]
        evidence: list[bytes] = []
        for positions, width in ((protocols, 3), (venues, 3), (native, 1)):
            selected = bisect_left(positions, opening + 1)
            if selected < len(positions) and positions[selected] < closing:
                start = positions[selected]
                # A kExchangeId token is a complete venue witness by itself.
                if positions is venues and values[start].startswith(b"kExchangeId"):
                    width = 1
                evidence.extend(values[start:start + width])
        result[opening] = evidence
    return result


def _return_expression_values(tokens: list[_Token], start: int, stop: int,
                              pairs: dict[int, int],
                              lambda_evidence: dict[int, list[bytes]]) -> list[bytes] | None:
    """Bound the returned expression, leaving callback bodies to their owners.

    The outer source walk still checks every decision/return inside each body.
    Capture initializers, aggregate fields and invocation arguments stay visible.
    """
    values: list[bytes] = []
    cursor = start
    while cursor < stop:
        # Include the return keyword in the same existing decision budget.
        if len(values) >= _MAX_DECISION_TOKENS - 1:
            return None
        values.append(tokens[cursor].value)
        if cursor in lambda_evidence:
            values.extend(lambda_evidence[cursor])
            values.append(b"}")
            cursor = pairs[cursor] + 1
        else:
            cursor += 1
    return values if len(values) < _MAX_DECISION_TOKENS else None


def app_native_source_errors(data: bytes) -> list[str]:
    """Return violations from one source, with logical phase-two line numbers."""
    if len(data) > _MAX_SOURCE_BYTES:
        return ["app native boundary source exceeds 8 MiB scan bound"]
    normalized, includes, lexical_errors = cpp_include_syntax(data)
    errors = [f"app native boundary: {error}" for error in lexical_errors]
    for include, _ in includes:
        if _native_include(include):
            errors.append("app native boundary: direct exchange/native transport include " +
                          include.decode("utf-8", errors="replace"))
    tokens: list[_Token] = []
    for match in _TOKEN.finditer(cpp_code_view(data)):
        if len(tokens) >= _MAX_TOKENS:
            return errors + ["app native boundary source exceeds 500000 token scan bound"]
        tokens.append(_Token(match.group(), match.start()))
    pairs = _pairs(tokens)
    lambda_bodies = _lambda_bodies(tokens, pairs)
    types = _protocol_types(tokens, errors)
    lambda_evidence = _lambda_body_evidence(tokens, pairs, lambda_bodies, types)
    newlines = [match.start() for match in re.finditer(b"\n", normalized)]
    reported: set[int] = set()

    def decision(start: int, stop: int, body_stop: int, *, label: bool = False,
                 conditional: bool = False,
                 values: list[bytes] | None = None) -> None:
        if values is None and stop - start > _MAX_DECISION_TOKENS:
            errors.append("app native boundary decision exceeds 4096 token scan bound")
            return
        if values is None:
            values = [token.value for token in tokens[start:stop]]
        protocol = _has_protocol(values, types)
        has_venue = _has_venue(values)
        if not protocol and not has_venue:
            return
        body = [token.value for token in tokens[
            stop + (1 if label or conditional else 0):min(body_stop, stop + _MAX_DECISION_TOKENS)]]
        if _literal_display_body(body):
            return
        if (conditional and len(body) == 4 and body[0].startswith(b'"') and
                body[1] == b":" and body[2].startswith(b'"') and body[3] == b";"):
            return
        venue = has_venue and (body_stop - stop >= _MAX_DECISION_TOKENS or any(
            _NATIVE_CONTEXT.search(value) is not None for value in values + body))
        if not (protocol or venue) or start in reported:
            return
        reported.add(start)
        line = bisect_right(newlines, tokens[start].offset) + 1
        kind = "protocol" if protocol else "venue/native"
        errors.append(f"{line}: app native boundary: explicit {kind} decision; "
                      "select the logical operation and let CXET route internally")

    for index, token in enumerate(tokens):
        if token.value in {b"if", b"while", b"switch", b"for"}:
            opening = index + 1
            if opening < len(tokens) and tokens[opening].value == b"constexpr":
                opening += 1
            if opening < len(tokens) and tokens[opening].value == b"(" and opening in pairs:
                closing = pairs[opening]
                end = _statement_end(tokens, closing + 1, pairs)
                if token.value == b"if" and end < len(tokens) and tokens[end].value == b"else":
                    end = _statement_end(tokens, end + 1, pairs)
                decision(opening + 1, closing, end)
        elif token.value == b"case":
            stop = index + 1
            while (stop < len(tokens) and stop - index < _MAX_DECISION_TOKENS and
                   tokens[stop].value not in {b":", b";", b"}"}):
                stop += 1
            if stop < len(tokens) and tokens[stop].value == b":":
                end = stop + 1
                while (end < len(tokens) and end - stop < _MAX_DECISION_TOKENS and
                       tokens[end].value not in {b"case", b"default", b"}"}):
                    end += 1
                decision(index + 1, stop, end, label=True)
        elif token.value in {b"?", b"return"}:
            if token.value == b"?":
                start = index - 1
                # Skip balanced subexpressions; a ternary can also initialize
                # a value, so its controlling expression is itself a decision.
                while (start >= 0 and index - start < _MAX_DECISION_TOKENS and
                       tokens[start].value not in {b";", b"{", b"}", b"=", b","}):
                    if tokens[start].value in {b")", b"]"} and start in pairs:
                        start = pairs[start] - 1
                    else:
                        start -= 1
                decision(start + 1, index, _statement_end(tokens, index + 1, pairs),
                         conditional=True)
            else:
                end = _statement_end(tokens, index + 1, pairs)
                values = _return_expression_values(
                    tokens, index + 1, end, pairs, lambda_evidence)
                if values is None:
                    errors.append("app native boundary return exceeds 4096 token scan bound")
                    continue
                if (b"?" not in values and any(
                        value in {b"==", b"!=", b"<", b">", b"<=", b">="}
                        for value in values)):
                    decision(index + 1, end, end, values=values)
    return errors


def validate_app_native_boundary(root: Path, errors: list[str]) -> None:
    for relative_root in APP_NATIVE_BOUNDARY_ROOTS:
        for path in source_tree_files(root, root / relative_root, errors,
                                      "app native boundary " + relative_root):
            if path.suffix.lower() not in CPP_SCAN_SUFFIXES:
                continue
            relative = path.relative_to(root).as_posix()
            try:
                with path.open("rb") as source:
                    data = source.read(_MAX_SOURCE_BYTES + 1)
            except OSError as exc:
                errors.append(f"{relative}: cannot read app native boundary source: {exc}")
                continue
            errors.extend(f"{relative}:{error}" for error in app_native_source_errors(data))


def validate_app_native_boundary_microcases(errors: list[str]) -> None:
    callback_body = b"value += amount;" * 1100
    cases = (
        ("leaf include", b'#include "cxet/Exchanges/Finam/TradeApiV1/Shared/X.hpp"', True),
        ("native transport include", b'#include <cxet/Network/Grpc/GrpcClient.hpp>', True),
        ("spliced include", b'#inc\\\nlude "cxet/Runtime/Market/Transport/Http/BoundedHttpsRequest.hpp"', True),
        ("obscured include", b'#include VENUE_HEADER', True),
        ("native protocol branch", b'if (route.transport == cxet::api::RouteTransport::Grpc) run();', True),
        ("native Protocol branch", b'if (route.protocol == Protocol::Grpc) run();', True),
        ("protocol alias", b'using Mode = cxet::api::InstrumentUniverseSourceMode; if(mode==Mode::GrpcSnapshot) run();', True),
        ("protocol switch", b'switch(wire){case RouteTransport::Rest: open(); break;}', True),
        ("protocol conditional", b'auto owner = route.transport==RouteTransport::Grpc ? grpc() : rest();', True),
        ("predicate return", b'return route.transport!=RouteTransport::Rest;', True),
        ("venue dispatch", b'if (exchange==canon::kExchangeIdFinam) grpcClient.start();', True),
        ("venue alternate", b'if (exchange==canon::kExchangeIdFinam) archive(); else wsClient.start();', True),
        ("venue conditional", b'auto owner=exchange==canon::kExchangeIdTbank ? nativeOwner : other;', True),
        ("enum display", b'switch(value){case RouteTransport::Grpc: return "grpc";}', False),
        ("conditional display", b'return value==RouteTransport::Grpc ? "grpc" : "rest";', False),
        ("if display", b'if(value==RouteTransport::Grpc) return "grpc"; else return "rest";', False),
        ("IPC protocol", b'if(frame.protocol==ipc::Protocol::Request) publish(frame);', False),
        ("canonical product", b'const Product product{canon::kExchangeIdFinam, market};', False),
        ("logical config", b'if(product.exchange==canon::kExchangeIdTbank) config.openingSignalPolicy=policy;', False),
        ("legacy archive", b'if(demand.exchangeRaw!=canon::kExchangeIdFinam.raw) return ArchiveStatus::Unsupported;', False),
        ("opaque diagnostic", b'diagnostic.transportRaw = raw; diagnostic.profileRaw=profile.raw;', False),
        ("comments and raw literals", b'// if(x==RouteTransport::Grpc) run();\nconst char* text=R"tag(if(x==RouteTransport::Rest) run();)tag";', False),
        ("commented include", b'/* #include "cxet/Network/Grpc/GrpcClient.hpp" */', False),
        ("native generic owner", b'#include "cxet/Runtime/Native/NativeCredentialRuntime.hpp"\nif(!owner.ready()) return false;', False),
        ("large returned callback", b"return [&]() noexcept {" + callback_body + b"return true;};", False),
        ("large callback aggregate", b"return Binding{.first=[] {" + callback_body +
         b"return true;},.second=[] {" + callback_body + b"return false;}};", False),
        ("nested callback protocol", b"return [] {" + callback_body +
         b"return [] {return route.transport == RouteTransport::Grpc;};};", True),
        ("invoked callback protocol result", b"return [] {return RouteTransport::Grpc;}() == route.transport;", True),
        ("nested invoked callback alias", b"using Wire=RouteTransport; return [] {" + callback_body +
         b"return [] {return Wire::Grpc;}();}() == route.transport;", True),
        ("callback literal display", b'return [] {return mode == RouteTransport::Grpc ? "grpc" : "rest";};', False),
        ("large actual predicate", b"return " + b"value || " * 2100 + b"value;", True),
    )
    for name, source, rejected in cases:
        actual = app_native_source_errors(source)
        if bool(actual) != rejected:
            errors.append(f"app native boundary microcase {name}: expected "
                          f"{'rejection' if rejected else 'acceptance'}, got {actual!r}")
