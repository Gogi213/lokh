"""Bounded C++ source/include lexer for CXET family ownership checks."""

from __future__ import annotations

import re


CPP_SCAN_SUFFIXES = frozenset({
    ".asm", ".nasm", ".c", ".c++", ".c++m", ".cc", ".ccm", ".cpp", ".cppm",
    ".cxx", ".cxxm", ".def", ".h", ".hh", ".hpp", ".hxx", ".inc",
    ".inl", ".ipp", ".ixx", ".m", ".mm", ".mpp", ".s", ".tcc",
    ".tpp",
})
CPP_COMPILED_SUFFIXES = frozenset({
    ".c", ".c++", ".c++m", ".cc", ".ccm", ".cpp", ".cppm", ".cxx",
    ".cxxm", ".ixx", ".m", ".mm", ".mpp",
})
CPP_TEXTUAL_INCLUDE_SUFFIXES = frozenset({
    ".def", ".h", ".hh", ".hpp", ".hxx", ".inc", ".inl", ".ipp",
    ".tcc", ".tpp",
})
CPP_ASSEMBLY_SUFFIXES = frozenset({".asm", ".nasm", ".s"})
CPP_NON_TEXTUAL_INCLUDE_SUFFIXES = (
    CPP_COMPILED_SUFFIXES | CPP_ASSEMBLY_SUFFIXES
)

_INCLUDE_DIRECTIVE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*'
    rb'(include|include_next|import)(?=[ \t\v\f<"])[ \t\v\f]*'
    rb'([^\r\n]+)')
_LITERAL_INCLUDE = re.compile(
    rb'^(?:<([^>\r\n]+)>|"([^"\r\n]+)")')
_SUSPICIOUS_INCLUDE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*'
    rb'(?:include(?:_next)?|import)\b')
_INCLUDE_TAIL = re.compile(rb'^(?://[^\r\n]*|/\*[^\r\n]*\*/)?$')
_ACCESS_DEFINE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*define[ \t\v\f]+'
    rb'(?:private|protected|public|class|struct|friend)\b')
_SUSPICIOUS_ACCESS_DEFINE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*define[ \t\v\f]+'
    rb'\b(?:private|protected|public|class|struct|friend)\b')
_EMBED_DIRECTIVE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*embed'
    rb'(?=[ \t\v\f<"]|$)')
_ASM_KEYWORD = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:__asm__|__asm|asm)(?![A-Za-z0-9_$])')
_ASM_IDENTIFIER = re.compile(rb'[A-Za-z_$\x80-\xff][A-Za-z0-9_$\x80-\xff]*')
_ASM_FILE_DIRECTIVE = re.compile(
    rb'(?i)(?<![A-Za-z0-9_$])\.(?:include|incbin)'
    rb'(?![A-Za-z0-9_$])')
_ASM_QUALIFIERS = frozenset({
    b"volatile", b"__volatile", b"__volatile__",
    b"inline", b"__inline", b"__inline__",
    b"goto", b"__goto", b"__goto__",
})
_EXTERNAL_ANGLE_HEADERS = frozenset({
    "libpq-fe.h", "nghttp2/nghttp2.h",
    "boost/asio/bind_executor.hpp", "boost/asio/connect.hpp", "boost/asio/error.hpp",
    "boost/asio/io_context.hpp", "boost/asio/ip/address.hpp", "boost/asio/ip/tcp.hpp",
    "boost/asio/post.hpp", "boost/asio/ssl/context.hpp", "boost/asio/ssl/error.hpp",
    "boost/asio/ssl/host_name_verification.hpp", "boost/asio/ssl/stream.hpp",
    "boost/asio/steady_timer.hpp", "boost/beast/core.hpp",
    "boost/beast/core/buffers_to_string.hpp", "boost/beast/core/error.hpp",
    "boost/beast/core/flat_buffer.hpp", "boost/beast/core/tcp_stream.hpp",
    "boost/beast/http.hpp", "boost/beast/websocket.hpp", "boost/beast/websocket/error.hpp",
    "boost/beast/websocket/ssl.hpp", "boost/beast/zlib.hpp", "boost/crc.hpp",
    "boost/json.hpp", "boost/json/array.hpp", "boost/json/object.hpp",
    "boost/json/parse.hpp", "boost/json/serialize.hpp", "boost/json/string.hpp",
    "boost/json/value.hpp", "boost/system/error_code.hpp",
    "assert.h", "errno.h", "inttypes.h", "limits.h", "stdbool.h", "stddef.h",
    "stdint.h", "stdio.h", "stdlib.h", "string.h", "intrin.h",
    "algorithm", "array", "atomic", "bit", "bitset", "cctype", "cerrno",
    "charconv", "chrono", "cinttypes", "climits", "cmath", "compare",
    "concepts", "condition_variable", "coroutine", "cpuid.h", "csignal", "cstddef",
    "cstdint", "cstdio", "cstdarg", "cstdlib", "cstring", "ctime", "deque",
    "dirent.h", "emmintrin.h", "exception", "fcntl.h", "filesystem",
    "fstream", "functional", "future", "immintrin.h", "initializer_list",
    "iomanip", "iosfwd", "iostream", "iterator", "liburing.h", "limits",
    "map", "memory", "memory_resource", "mutex", "netdb.h", "net/if.h", "new", "nmmintrin.h", "numeric",
    "optional", "ostream", "poll.h", "pthread.h", "pwd.h", "sched.h", "secp256k1.h",
    "secp256k1_recovery.h", "set", "shared_mutex", "signal.h", "span",
    "spawn.h", "sstream", "stdexcept", "stop_token", "string",
    "string_view", "system_error", "thread", "time.h", "type_traits",
    "unistd.h", "unordered_map", "unordered_set", "utility", "vector", "tuple", "variant",
    "x86intrin.h", "tmmintrin.h", "wmmintrin.h",
})
_EXTERNAL_ANGLE_PREFIXES = (
    "absl/", "arpa/", "gtest/", "linux/", "netinet/", "openssl/",
    "sys/",
)
_DEFINE_DIRECTIVE = re.compile(
    rb'(?m)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*define[ \t\v\f]+'
    rb'([A-Za-z_$\x80-\xff][A-Za-z0-9_$\x80-\xff]*)([^\r\n]*)')
_TOKEN_PASTE = re.compile(rb'(?:##|%:%:)')
_TOKEN_PASTE_CHAIN = re.compile(
    rb'[A-Za-z_$][A-Za-z0-9_$]*'
    rb'(?:[ \t\v\f]*(?:##|%:%:)[ \t\v\f]*'
    rb'[A-Za-z_$][A-Za-z0-9_$]*)+')
_MODULE_KEYWORD = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:import|module)(?![A-Za-z0-9_$])')
_MODULE_TYPED_DECLARATOR = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:'
    rb'(?:[A-Za-z_$][A-Za-z0-9_$]*[ \t\v\f\r\n]*::[ \t\v\f\r\n]*)+'
    rb'[A-Za-z_$][A-Za-z0-9_$]*'
    rb'[ \t\v\f\r\n]*(?:[*&][ \t\v\f\r\n]*)*|'
    rb'(?:auto|bool|char|short|int|long|float|double)'
    rb'[ \t\v\f\r\n]*(?:[*&][ \t\v\f\r\n]*)+)$')
_PRAGMA_OPERATOR = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:_Pragma|__pragma)(?![A-Za-z0-9_$])')
_FILE_PROBE_OPERATOR = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:__has_include_next|__has_include|__has_embed)'
    rb'(?![A-Za-z0-9_$])')
_EXTERNAL_TOKEN_PASTE_CARRIER = re.compile(
    rb'(?<![A-Za-z0-9_$])(?:__CONCAT1|__CONCAT)(?![A-Za-z0-9_$])')
_MODULE_PRAGMA = re.compile(
    rb'(?i)^[ \t\v\f]*(?:#|%:)[ \t\v\f]*pragma[ \t\v\f]+'
    rb'(?:clang[ \t\v\f]+)?module[ \t\v\f]+import\b')
_UNSUPPORTED_CONTROL = re.compile(rb'[\x00-\x08\x0e-\x1f\x7f]')
_LONE_CR = re.compile(rb'\r(?!\n)')
_TRIGRAPH = re.compile(rb'\?\?[=/\x27()!<>-]')


def cpp_phase_two(data: bytes) -> bytes:
    """Apply C++23 BOM normalization and phase-two line splicing."""
    if data.startswith(b"\xef\xbb\xbf"):
        data = b"   " + data[3:]
    # Raw trigraph spellings are rejected because the inventory also scans C.
    # The %: digraph is recognized after masking.
    return data.replace(b"\\\r\n", b"").replace(
        b"\\\n", b"").replace(b"\\\r", b"")


def approved_external_angle_include(include: str) -> bool:
    """Pin the non-repository header namespaces admitted by family builds."""
    return (
        include in _EXTERNAL_ANGLE_HEADERS or
        any(include.startswith(prefix) for prefix in _EXTERNAL_ANGLE_PREFIXES)
    )


def _identifier_byte(value: int) -> bool:
    return (
        value == 0x24 or value == 0x5F or value >= 0x80 or
        0x30 <= value <= 0x39 or 0x41 <= value <= 0x5A or
        0x61 <= value <= 0x7A
    )


def _numeric_separator(data: bytes | bytearray, index: int) -> bool:
    """Distinguish a C++ digit separator from an ordinary character quote."""
    if data[index] != 0x27 or index == 0 or index + 1 >= len(data):
        return False
    hexadecimal = b"0123456789abcdefABCDEF"
    if (data[index - 1] not in hexadecimal or
            data[index + 1] not in hexadecimal):
        return False
    start = index - 1
    while start > 0 and (
            _identifier_byte(data[start - 1]) or
            data[start - 1] == 0x2E):
        start -= 1
    prefix = bytes(data[start:index])
    return bool(prefix) and (
        0x30 <= prefix[0] <= 0x39 or
        len(prefix) >= 2 and prefix[0] == 0x2E and
        0x30 <= prefix[1] <= 0x39
    )


def _raw_literal_span(
    data: bytes | bytearray,
    index: int,
) -> tuple[int, int, bool] | None:
    """Return a raw literal span beginning at its R quote."""
    if bytes(data[index:index + 2]) != b'R"':
        return None
    prefix_start = index
    if index >= 2 and bytes(data[index - 2:index]) == b"u8":
        prefix_start = index - 2
    elif index >= 1 and bytes(data[index - 1:index]) in {b"u", b"U", b"L"}:
        prefix_start = index - 1
    if (prefix_start != 0 and
            _identifier_byte(data[prefix_start - 1])):
        return None
    source = bytes(data)
    delimiter_end = source.find(b"(", index + 2, index + 19)
    if delimiter_end < 0:
        return None
    delimiter = source[index + 2:delimiter_end]
    if any(value in b" \t\v\f\r\n\\)" for value in delimiter):
        return None
    terminator = b")" + delimiter + b'"'
    raw_end = source.find(terminator, delimiter_end + 1)
    return (
        prefix_start,
        len(source) if raw_end < 0 else raw_end + len(terminator),
        raw_end >= 0,
    )


def _raw_literal_spans(
    data: bytes,
) -> tuple[tuple[int, int, bool], ...]:
    """Find raw literals while ignoring comments and ordinary literals."""
    spans: list[tuple[int, int, bool]] = []
    index = 0
    quote = 0
    while index < len(data):
        if quote:
            if data[index] == 0x5C and index + 1 < len(data):
                index += 2
                continue
            if data[index] == quote:
                quote = 0
            index += 1
            continue
        if data.startswith(b"//", index):
            newline = min(
                (position for position in (
                    data.find(b"\r", index + 2),
                    data.find(b"\n", index + 2),
                ) if position >= 0),
                default=len(data),
            )
            index = newline
            continue
        if data.startswith(b"/*", index):
            end = data.find(b"*/", index + 2)
            index = len(data) if end < 0 else end + 2
            continue
        span = _raw_literal_span(data, index)
        if span is not None:
            spans.append(span)
            _, index, _ = span
            continue
        if data[index] == 0x27 and _numeric_separator(data, index):
            index += 1
            continue
        if data[index] in (0x22, 0x27):
            quote = data[index]
        index += 1
    return tuple(spans)


def _spliced_with_origins(data: bytes) -> tuple[bytes, tuple[int, ...]]:
    if data.startswith(b"\xef\xbb\xbf"):
        data = b"   " + data[3:]
    result = bytearray()
    origins: list[int] = []
    index = 0
    while index < len(data):
        width = next((
            len(splice) for splice in (b"\\\r\n", b"\\\n", b"\\\r")
            if data.startswith(splice, index)
        ), 0)
        if width:
            index += width
            continue
        result.append(data[index])
        origins.append(index)
        index += 1
    return bytes(result), tuple(origins)


def _raw_phase_two_error(data: bytes) -> bool:
    """Reject raw literals whose phase-two reversion needs source mapping."""
    spliced, origins = _spliced_with_origins(data)
    for start, stop, terminated in _raw_literal_spans(spliced):
        if not terminated:
            return True
        if any(
                origins[index + 1] != origins[index] + 1
                for index in range(start, stop - 1)):
            return True
    return False


def _directive_view(data: bytes) -> bytes:
    """Apply phase-three comment replacement without touching literals."""
    result = bytearray(data)
    index = 0
    quote = 0
    size = len(data)
    while index < size:
        if quote:
            if data[index] == 0x5C and index + 1 < size:
                index += 2
                continue
            if data[index] == quote:
                quote = 0
            index += 1
            continue
        raw_span = _raw_literal_span(data, index)
        if raw_span is not None:
            prefix_start, raw_stop, _ = raw_span
            for cursor in range(prefix_start, raw_stop):
                if data[cursor] not in b"\r\n":
                    result[cursor] = 0x20
            index = raw_stop
            continue
        if data.startswith(b"//", index):
            cursor = index
            while cursor < size and data[cursor] not in b"\r\n":
                result[cursor] = 0x20
                cursor += 1
            index = cursor
            continue
        if data.startswith(b"/*", index):
            cursor = index
            while cursor < size:
                if data[cursor] not in b"\r\n":
                    result[cursor] = 0x20
                if data.startswith(b"*/", cursor):
                    if cursor + 1 < size:
                        result[cursor + 1] = 0x20
                    cursor += 2
                    break
                cursor += 1
            index = cursor
            continue
        if data[index] == 0x27 and _numeric_separator(data, index):
            index += 1
            continue
        if data[index] in (0x22, 0x27):
            quote = data[index]
        index += 1
    return bytes(result)


def _code_view(
    data: bytes,
    directive_view: bytes | None = None,
) -> bytes:
    """Mask literal payloads while retaining ordinary quote boundaries."""
    result = bytearray(
        _directive_view(data) if directive_view is None else directive_view)
    index = 0
    quote = 0
    while index < len(result):
        value = result[index]
        if quote:
            if value == 0x5C and index + 1 < len(result):
                result[index] = 0x20
                if result[index + 1] not in b"\r\n":
                    result[index + 1] = 0x20
                index += 2
                continue
            if value == quote:
                quote = 0
                index += 1
                continue
            if value not in b"\r\n":
                result[index] = 0x20
            index += 1
            continue
        if value == 0x27 and _numeric_separator(result, index):
            index += 1
            continue
        if value in (0x22, 0x27):
            quote = value
        index += 1
    return bytes(result)


def _declaration_view(
    data: bytes,
    code_view: bytes | None = None,
) -> bytes:
    """Mask preprocessing directives before scanning C++ declarations."""
    result = bytearray(
        _code_view(data) if code_view is None else code_view)
    for match in re.finditer(
            rb'(?m)^[ \t\v\f]*(?:#|%:)[^\r\n]*', result):
        for index in range(match.start(), match.end()):
            if result[index] not in b"\r\n":
                result[index] = 0x20
    return bytes(result)


def cpp_code_view(data: bytes) -> bytes:
    """Return phase-two code with comments, literals and directives masked.

    Consumers must also inspect ``cpp_include_syntax`` errors. Keeping this
    view here makes ownership policies share the include lexer's treatment of
    raw strings, escaped newlines and digit separators.
    """
    return _declaration_view(cpp_phase_two(data))


def _skip_masked_space(data: bytes, index: int) -> int:
    while index < len(data) and data[index] in b" \t\v\f\r\n":
        index += 1
    return index


def _plain_narrow_string(
    data: bytes,
    index: int,
) -> tuple[int, bytes, str | None]:
    """Parse one exact unprefixed string; escapes stay fail-closed."""
    if index >= len(data) or data[index] != 0x22:
        return index, b"", "inline asm template is not a narrow string literal"
    cursor = index + 1
    while cursor < len(data):
        value = data[cursor]
        if value == 0x22:
            return cursor + 1, data[index + 1:cursor], None
        if value == 0x5C:
            return cursor, b"", "inline asm template escape is unsupported"
        if value in b"\r\n":
            return cursor, b"", "unterminated inline asm template literal"
        cursor += 1
    return cursor, b"", "unterminated inline asm template literal"


def _inline_asm_errors(
    data: bytes,
    code_view: bytes | None = None,
    declaration_view: bytes | None = None,
) -> list[str]:
    """Reject assembler-side file ingestion and obscured asm templates."""
    if code_view is None:
        code_view = _code_view(data)
    if declaration_view is None:
        declaration_view = _declaration_view(data, code_view)
    failures: list[str] = []
    for match in _ASM_KEYWORD.finditer(code_view):
        if (declaration_view[match.start():match.end()] !=
                code_view[match.start():match.end()]):
            failures.append(
                "inline asm keyword in preprocessing directive is unsupported")
            continue
        cursor = _skip_masked_space(code_view, match.end())
        while cursor < len(code_view):
            qualifier = _ASM_IDENTIFIER.match(code_view, cursor)
            if qualifier is None or qualifier.group(0) not in _ASM_QUALIFIERS:
                break
            cursor = _skip_masked_space(code_view, qualifier.end())
        if cursor >= len(code_view) or code_view[cursor] != 0x28:
            failures.append(
                "inline asm keyword is not a direct literal invocation")
            continue
        cursor = _skip_masked_space(code_view, cursor + 1)
        template = bytearray()
        literal_count = 0
        literal_failure: str | None = None
        while cursor < len(data) and data[cursor] == 0x22:
            cursor, payload, literal_failure = _plain_narrow_string(
                data, cursor)
            if literal_failure is not None:
                break
            template.extend(payload)
            literal_count += 1
            cursor = _skip_masked_space(code_view, cursor)
        if literal_failure is not None:
            failures.append(literal_failure)
            continue
        if literal_count == 0:
            failures.append(
                "inline asm first operand is not an exact literal sequence")
            continue
        if cursor >= len(code_view) or code_view[cursor] not in b":)":
            failures.append(
                "inline asm first operand has nonliteral template tokens")
            continue
        if _ASM_FILE_DIRECTIVE.search(template) is not None:
            failures.append(
                "inline asm .include/.incbin file ingestion is forbidden")
    return failures


def _paste_can_form_forbidden_keyword(
    parts: tuple[bytes, ...],
    parameters: frozenset[bytes],
) -> bool:
    pattern = bytearray(b"^")
    for part in parts:
        if part in parameters or part == b"__VA_ARGS__":
            pattern.extend(b".*")
        else:
            pattern.extend(re.escape(part))
    pattern.extend(b"$")
    candidate = re.compile(bytes(pattern))
    return any(candidate.fullmatch(keyword) is not None for keyword in (
        b"asm", b"__asm", b"__asm__", b"import", b"module",
        b"StrategyRunnerRuntimeFamilyVerificationFriend",
        b"StrategyInstanceFamilyVerificationFriend",
        b"CXET_FAMILY_DIFFERENTIAL_TESTING",
        b"__has_include", b"__has_include_next", b"__has_embed",
        b"__CONCAT", b"__CONCAT1",
    ))


def _token_paste_errors(directive_view: bytes) -> list[str]:
    """Reject paste grammars able to manufacture forbidden C++ keywords."""
    failures: list[str] = []
    for directive in re.finditer(
            rb'(?m)^[ \t\v\f]*(?:#|%:)[^\r\n]*', directive_view):
        line = directive.group(0)
        if _TOKEN_PASTE.search(line) is None:
            continue
        definition = _DEFINE_DIRECTIVE.fullmatch(line)
        if definition is None:
            failures.append("token paste outside an exact macro definition")
            continue
        tail = definition.group(2)
        parameters: set[bytes] = set()
        replacement = tail
        if tail.startswith(b"("):
            close = tail.find(b")", 1)
            if close < 0:
                failures.append("unterminated token-paste macro signature")
                continue
            raw_parameters = tail[1:close]
            valid_parameters = True
            if raw_parameters.strip():
                for raw_parameter in raw_parameters.split(b","):
                    parameter = raw_parameter.strip()
                    if parameter == b"...":
                        parameters.add(b"__VA_ARGS__")
                    elif parameter.endswith(b"...") and _ASM_IDENTIFIER.fullmatch(
                            parameter[:-3]) is not None:
                        parameters.add(parameter[:-3])
                        parameters.add(b"__VA_ARGS__")
                    elif _ASM_IDENTIFIER.fullmatch(parameter) is not None:
                        parameters.add(parameter)
                    else:
                        valid_parameters = False
                        break
            if not valid_parameters:
                failures.append("unsupported token-paste macro parameters")
                continue
            replacement = tail[close + 1:]

        chains = tuple(_TOKEN_PASTE_CHAIN.finditer(replacement))
        operators = tuple(_TOKEN_PASTE.finditer(replacement))
        if any(not any(
                chain.start() <= operator.start() and
                operator.end() <= chain.end()
                for chain in chains) for operator in operators):
            failures.append("unsupported token-paste operand grammar")
            continue
        for chain in chains:
            parts = tuple(
                part.strip() for part in _TOKEN_PASTE.split(chain.group(0)))
            if _paste_can_form_forbidden_keyword(
                    parts, frozenset(parameters)):
                failures.append(
                    "preprocessor token paste can manufacture a forbidden "
                    "source carrier")
                break
    return failures


def _ordinary_module_identifier(data: bytes, match: re.Match[bytes]) -> bool:
    """Require local syntax that cannot be a module/import declaration."""
    previous = match.start()
    while previous and data[previous - 1] in b" \t\v\f\r\n":
        previous -= 1
    following = _skip_masked_space(data, match.end())
    # Bound declarator recognition; unsupported longer type spellings retain
    # the fail-closed keyword/carrier diagnostic.
    before = data[max(0, previous - 256):previous]
    if data.startswith((b"(", b".", b"->", b"::", b"="), following):
        return True
    if before.endswith((b".", b"->", b"::")):
        return True
    # A type token can also be an erasing macro. Require surviving punctuation:
    # a qualified type's ::, or a built-in pointer/reference declarator's * / &.
    return (data.startswith((b";", b",", b"=", b":", b")", b"[", b"{"), following) and
            _MODULE_TYPED_DECLARATOR.search(before) is not None)


def cpp_include_syntax(
    data: bytes,
) -> tuple[bytes, list[tuple[bytes, bool]], list[str]]:
    """Return literal include paths and fail closed on obscured grammar."""
    normalized = cpp_phase_two(data)
    directive_view = _directive_view(normalized)
    preprocessor_code_view = _code_view(normalized, directive_view)
    code_view = _declaration_view(normalized, preprocessor_code_view)
    records: list[tuple[bytes, bool]] = []
    errors: list[str] = []
    if _UNSUPPORTED_CONTROL.search(data) is not None:
        errors.append("unsupported C0/DEL byte in C++ source")
    if _LONE_CR.search(data) is not None:
        errors.append("lone CR source line ending is unsupported")
    if _TRIGRAPH.search(data) is not None:
        errors.append("C/pre-C++23 trigraph spelling is unsupported")
    if _raw_phase_two_error(data):
        errors.append(
            "raw literal with phase-two line splice is unsupported")
    if _EMBED_DIRECTIVE.search(directive_view) is not None:
        errors.append("preprocessor #embed is unsupported")
    errors.extend(_token_paste_errors(preprocessor_code_view))
    errors.extend(_inline_asm_errors(
        normalized, preprocessor_code_view, code_view))
    recognized = 0
    for match in _INCLUDE_DIRECTIVE.finditer(directive_view):
        recognized += 1
        keyword = match.group(1)
        operand = match.group(2).strip()
        literal = _LITERAL_INCLUDE.match(operand)
        if keyword != b"include" or literal is None:
            errors.append("nonliteral or include_next preprocessor include")
            continue
        tail = operand[literal.end():].strip()
        if _INCLUDE_TAIL.fullmatch(tail) is None:
            errors.append("include has trailing preprocessor tokens")
        records.append((
            literal.group(1) or literal.group(2),
            literal.group(2) is not None,
        ))
    suspicious = len(list(_SUSPICIOUS_INCLUDE.finditer(directive_view)))
    if suspicious != recognized:
        errors.append("obscured preprocessor include directive")
    access_defines = len(list(_ACCESS_DEFINE.finditer(directive_view)))
    suspicious_access = len(list(
        _SUSPICIOUS_ACCESS_DEFINE.finditer(directive_view)))
    if access_defines:
        errors.append("access-control keyword macro is forbidden")
    if suspicious_access != access_defines:
        errors.append("obscured access-control keyword macro")
    # Module directives cannot contain member access or an ordinary typed
    # declarator before their contextual keyword. Macro arguments such as
    # IDENTITY(import) provide neither proof and remain forbidden.
    if any(not _ordinary_module_identifier(code_view, match)
           for match in _MODULE_KEYWORD.finditer(code_view)):
        errors.append("C++ module keyword/carrier is unsupported")
    if _PRAGMA_OPERATOR.search(code_view) is not None:
        errors.append("C++ pragma operator carrier is unsupported")
    if _FILE_PROBE_OPERATOR.search(preprocessor_code_view) is not None:
        errors.append("preprocessor file-probe operator is unsupported")
    if _EXTERNAL_TOKEN_PASTE_CARRIER.search(
            preprocessor_code_view) is not None:
        errors.append(
            "external predefined token-paste carrier is unsupported")
    for directive in re.finditer(
            rb'(?m)^[ \t\v\f]*(?:#|%:)[^\r\n]*',
            preprocessor_code_view):
        line = directive.group(0)
        definition = _DEFINE_DIRECTIVE.fullmatch(line)
        if (definition is not None and (
                _MODULE_KEYWORD.search(line) is not None or
                _PRAGMA_OPERATOR.search(line) is not None)):
            errors.append("preprocessor module/pragma carrier is unsupported")
        if _MODULE_PRAGMA.search(line) is not None:
            errors.append("preprocessor module import pragma is unsupported")
    if (_ASM_FILE_DIRECTIVE.search(directive_view) is not None or any(
            _ASM_FILE_DIRECTIVE.search(normalized[start:stop]) is not None
            for start, stop, _ in _raw_literal_spans(normalized))):
        errors.append("assembler-side file directive token is forbidden")
    return normalized, records, errors
