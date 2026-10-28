"""Restricted policy roots for scripts invoked by active custom commands."""

from __future__ import annotations

import posixpath
from pathlib import Path

from CMake.Syntax.CmakeFamilyLexer import words
from CMake.Policy.CmakeFamilyProgramPolicy import reviewed_file_identity
from CMake.Policy.CmakeFamilyStrategyPolicy import proven_strategy_headers


_BINARY = "__CXET_CMAKE_BINARY__"
_LIBURING_SOURCE = _BINARY + "/src/src/_deps/liburing/source"
_REGISTRY_SCRIPT = "apps/trading-core/cmake/GenerateStrategyRegistry.cmake"
_SANITIZE_SCRIPT = "cmake/SanitizeCRLF.cmake"
_X509_SCRIPT = "cmake/Vendor/mbedtls-cold/AdaptX509.cmake"
_ROOT = Path(__file__).resolve().parents[4]
SCRIPT_POLICY_FILES = frozenset({
    _REGISTRY_SCRIPT,
    _SANITIZE_SCRIPT,
    _X509_SCRIPT,
})
_CUSTOM_KEYWORDS = frozenset({
    "APPEND", "BYPRODUCTS", "CODEGEN", "COMMAND", "COMMAND_EXPAND_LISTS",
    "COMMENT", "DEPENDS", "DEPENDS_EXPLICIT_ONLY", "DEPFILE",
    "IMPLICIT_DEPENDS", "JOB_POOL", "JOB_SERVER_AWARE", "MAIN_DEPENDENCY",
    "OUTPUT", "TARGET", "USES_TERMINAL", "VERBATIM", "WORKING_DIRECTORY",
})


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _normalized(value: str) -> str:
    return posixpath.normpath(value.replace("\\", "/"))


def _tokens(body: str) -> list[str]:
    return [
        token[1:-1]
        if len(token) >= 2 and token[0] == token[-1] == '"' else token
        for token in words(body)
    ]


def _command_sections(instance) -> list[list[str]]:
    commands: list[list[str]] = []
    current = None
    for group in instance.token_groups:
        for value in group:
            upper = value.upper()
            if upper == "COMMAND":
                current = []
                commands.append(current)
            elif upper in _CUSTOM_KEYWORDS:
                current = None
            elif current is not None:
                current.append(value)
    return commands


def _defines(command: list[str], origin: str, errors: list[str]):
    if command[:1] != ["${CMAKE_COMMAND}"] or command.count("-P") != 1:
        errors.append(f"{origin}: malformed CMake script invocation")
        return None
    script_index = command.index("-P")
    if script_index + 2 != len(command):
        errors.append(f"{origin}: opaque arguments after CMake -P script")
        return None
    result: dict[str, str] = {}
    for token in command[1:script_index]:
        if not token.startswith("-D") or "=" not in token[2:]:
            errors.append(f"{origin}: untyped CMake -P argument {token}")
            return None
        name, value = token[2:].split("=", 1)
        if not name or name in result:
            errors.append(f"{origin}: ambiguous CMake -P definition {name}")
            return None
        result[name] = value
    return _normalized(command[-1]), result


def _script_commands(
    path: str,
    files,
    errors: list[str],
    *,
    invoked_policy_root: bool = True,
):
    entry = files.get(path)
    if entry is None:
        errors.append(f"missing invoked CMake policy root: {path}")
        return []
    if invoked_policy_root and not reviewed_file_identity(path):
        errors.append(f"invoked CMake policy root identity changed: {path}")
    return entry[1]


def _counts(commands) -> dict[str, int]:
    result: dict[str, int] = {}
    for command in commands:
        result[command.name] = result.get(command.name, 0) + 1
    return result


def _validate_sanitize(defines, files, errors: list[str]) -> None:
    if defines != {"SANITIZE_CRLF_DIR": _LIBURING_SOURCE}:
        errors.append(f"{_SANITIZE_SCRIPT}: unapproved invocation bindings")
    commands = _script_commands(_SANITIZE_SCRIPT, files, errors)
    expected_counts = {
        "continue": 1, "endforeach": 1, "endif": 3,
        "execute_process": 1, "file": 1, "foreach": 1,
        "if": 3, "message": 2,
    }
    if _counts(commands) != expected_counts:
        errors.append(f"{_SANITIZE_SCRIPT}: restricted command shape changed")
    patterns = [
        "${SANITIZE_CRLF_DIR}/*.c", "${SANITIZE_CRLF_DIR}/*.cc",
        "${SANITIZE_CRLF_DIR}/*.cpp", "${SANITIZE_CRLF_DIR}/*.h",
        "${SANITIZE_CRLF_DIR}/*.hpp", "${SANITIZE_CRLF_DIR}/*.S",
        "${SANITIZE_CRLF_DIR}/*.sh", "${SANITIZE_CRLF_DIR}/*.in",
        "${SANITIZE_CRLF_DIR}/*.m4", "${SANITIZE_CRLF_DIR}/*.mk",
        "${SANITIZE_CRLF_DIR}/Makefile", "${SANITIZE_CRLF_DIR}/configure",
    ]
    allowed = set(expected_counts)
    for command in commands:
        tokens = _tokens(command.body)
        origin = f"{_SANITIZE_SCRIPT}:{command.line}"
        if command.name not in allowed:
            errors.append(f"{origin}: command is outside script dialect")
        elif command.name == "file" and tokens != [
                "GLOB_RECURSE", "_cxet_crlf_files", "LIST_DIRECTORIES",
                "false", *patterns]:
            errors.append(f"{origin}: CRLF input glob escaped reviewed copy")
        elif command.name == "foreach" and tokens != [
                "_cxet_crlf_file", "IN", "LISTS", "_cxet_crlf_files"]:
            errors.append(f"{origin}: unapproved CRLF iteration owner")
        elif command.name == "continue" and tokens:
            errors.append(f"{origin}: unapproved continue grammar")
        elif command.name == "execute_process" and tokens != [
                "COMMAND", "/usr/bin/perl", "-0pi", "-e",
                "[[s/\\r\\n?/\\n/g]]", "${_cxet_crlf_file}",
                "RESULT_VARIABLE", "_cxet_crlf_status"]:
            errors.append(f"{origin}: unapproved CRLF executable/write form")
        elif command.name == "message" and (
                not tokens or tokens[0] != "FATAL_ERROR"):
            errors.append(f"{origin}: non-fatal script message is unreviewed")


def _validate_registry(defines, files, errors: list[str]) -> None:
    generated = _BINARY + "/apps/trading-core/generated"
    headers = defines.get("STRATEGY_HEADERS", "").split("|")
    expected_headers = proven_strategy_headers()
    if (set(defines) != {"STRATEGY_ROOT", "OUT_DIR", "STRATEGY_HEADERS"} or
            _normalized(defines.get("STRATEGY_ROOT", "")) !=
            "apps/trading-core/src/Strategy/include/strategy" or
            defines.get("OUT_DIR") != generated or
            len(headers) != len(expected_headers) or
            set(map(_normalized, headers)) != expected_headers):
        errors.append(f"{_REGISTRY_SCRIPT}: unapproved invocation bindings")
    commands = _script_commands(_REGISTRY_SCRIPT, files, errors)
    # Bind both the parsed commands and generated C++ payloads to the reviewed
    # source snapshot. The recipe below independently closes helper call paths,
    # discovery, descriptor admission and stale-output removal; it grants no
    # generic function/file writer authority to another script.
    from CMake.Flow.CmakeFamilyGraph import parse_commands
    try:
        text = (_ROOT / _REGISTRY_SCRIPT).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{_REGISTRY_SCRIPT}: cannot read reviewed script snapshot: {exc}")
        return
    parsed = parse_commands(_REGISTRY_SCRIPT, text, errors)
    if files.get(_REGISTRY_SCRIPT, (None,))[0] != text or commands != parsed:
        errors.append(f"{_REGISTRY_SCRIPT}: reviewed script text/AST snapshot changed")
        return
    payload = object()
    output = "${OUT_DIR}/trading_core/Strategy/GeneratedStrategyRegistry"
    helper = "write_strategy_registry_if_changed"
    expected = (
        ("set", ("OUT_HPP", output + ".hpp")),
        ("set", ("OUT_CPP", output + ".cpp")),
        ("file", ("MAKE_DIRECTORY", "${OUT_DIR}/trading_core/Strategy")),
        ("function", (helper, "path", "content")),
        ("if", ("EXISTS", "${path}")),
        ("file", ("READ", "${path}", "previous_content")),
        ("if", ("${previous_content}", "STREQUAL", "${content}")),
        ("return", ()), ("endif", ()), ("endif", ()),
        ("file", ("WRITE", "${path}", "${content}")),
        ("endfunction", ()),
        ("if", ("NOT", "DEFINED", "STRATEGY_HEADERS")),
        ("file", ("GLOB", "STRATEGY_HEADERS", "${STRATEGY_ROOT}/hft-trader/*/Strategy.hpp",
                  "${STRATEGY_ROOT}/trader/*/Strategy.hpp")),
        ("else", ()),
        ("string", ("REPLACE", "|", ";", "STRATEGY_HEADERS", "${STRATEGY_HEADERS}")),
        ("endif", ()), ("list", ("SORT", "STRATEGY_HEADERS")),
        ("set", ("ENTRIES", "")), ("set", ("EXTERNS", "")),
        ("set", ("CURRENT_STRATEGY_REGISTRY_SOURCES", "")),
        ("foreach", ("header", "IN", "LISTS", "STRATEGY_HEADERS")),
        ("get_filename_component", ("strategy_dir", "${header}", "DIRECTORY")),
        ("get_filename_component", ("strategy_folder", "${strategy_dir}", "NAME")),
        ("file", ("RELATIVE_PATH", "strategy_include", "${STRATEGY_ROOT}", "${header}")),
        ("string", ("REGEX", "REPLACE", "([a-z0-9])([A-Z])", r"\\1_\\2", "strategy_name", "${strategy_folder}")),
        ("string", ("TOLOWER", "${strategy_name}", "strategy_name")),
        ("file", ("READ", "${header}", "strategy_header_text")),
        ("set", ("strategy_descriptor_text", "${strategy_header_text}")),
        ("if", ("EXISTS", "${strategy_dir}/Descriptor.hpp")),
        ("file", ("READ", "${strategy_dir}/Descriptor.hpp", "strategy_descriptor_header_text")),
        ("string", ("APPEND", "strategy_descriptor_text", r"\n", "${strategy_descriptor_header_text}")),
        ("endif", ()),
        ("if", ("NOT", "strategy_descriptor_text", "MATCHES", r"${strategy_name}StrategyDescriptor[ \\t\\r\\n]*\\(")),
        ("continue", ()), ("endif", ()),
        ("string", ("APPEND", "EXTERNS", payload)),
        ("string", ("APPEND", "ENTRIES", payload)),
        ("set", ("strategy_registry_source", output + "_${strategy_name}.cpp")),
        ("list", ("APPEND", "CURRENT_STRATEGY_REGISTRY_SOURCES", "${strategy_registry_source}")),
        (helper, ("${strategy_registry_source}", payload)), ("endforeach", ()),
        (helper, ("${OUT_HPP}", payload)), (helper, ("${OUT_CPP}", payload)),
        ("file", ("GLOB", "OLD_STRATEGY_REGISTRY_SOURCES", output + "_*.cpp")),
        ("foreach", ("old_source", "IN", "LISTS", "OLD_STRATEGY_REGISTRY_SOURCES")),
        ("list", ("FIND", "CURRENT_STRATEGY_REGISTRY_SOURCES", "${old_source}", "current_index")),
        ("if", ("current_index", "EQUAL", "-1")),
        ("file", ("REMOVE", "${old_source}")), ("endif", ()), ("endforeach", ()),
    )
    records = [(command.name, tuple(_tokens(command.body))) for command in commands]
    if len(records) != len(expected) or any(
            name != required_name or len(tokens) != len(required_tokens) or any(
                required is not payload and actual != required
                for actual, required in zip(tokens, required_tokens))
            for (name, tokens), (required_name, required_tokens) in zip(records, expected)):
        errors.append(f"{_REGISTRY_SCRIPT}: exact registry helper/output recipe changed")


def validate_invoked_script_policies(
    instances,
    files,
    _tokenize,
    errors: list[str],
    *, active_origins=None,
) -> None:
    """Validate script bodies and bound invocation variables, not just paths."""
    invocations: dict[str, list[dict[str, str]]] = {
        _REGISTRY_SCRIPT: [], _SANITIZE_SCRIPT: [], _X509_SCRIPT: []}
    registry_roles = []
    origins = (set(active_origins) if active_origins is not None else
               {instance.body.relative for instance in instances})
    owners = {
        _REGISTRY_SCRIPT: "apps/trading-core/CMakeLists.txt",
        _SANITIZE_SCRIPT: "src/src/CMakeLists.txt",
        _X509_SCRIPT: "src/src/CMakeLists.txt",
    }
    for instance in instances:
        if instance.body.command.name not in {
                "add_custom_command", "add_custom_target"}:
            continue
        for command in _command_sections(instance):
            if "-P" in command:
                parsed = _defines(command, _origin(instance), errors)
                if parsed is None:
                    continue
                script, defines = parsed
                prefix = _ROOT.as_posix() + "/"
                if script.startswith(prefix):
                    script = script[len(prefix):]
                if script == _X509_SCRIPT:
                    prefix = _ROOT.as_posix() + "/"
                    defines = {name: normalized[len(prefix):]
                               if normalized.startswith(prefix) else normalized
                               for name, value in defines.items()
                               for normalized in (_normalized(value),)}
                if script not in invocations:
                    errors.append(
                        f"{_origin(instance)}: unreviewed CMake -P script {script}")
                    continue
                invocations[script].append(defines)
                if script == _REGISTRY_SCRIPT:
                    tokens = [value for group in instance.token_groups for value in group]
                    registry_roles.append((
                        instance.body.relative,
                        instance.evaluation.source_base,
                        instance.evaluation.binary_base,
                        instance.body.command.name,
                        tokens[0] if tokens else "",
                    ))
    for script, bindings in invocations.items():
        expected_count = int(owners[script] in origins) * (2 if script == _REGISTRY_SCRIPT else 1)
        if len(bindings) != expected_count:
            errors.append(
                f"{script}: expected {expected_count} active reviewed invocation(s), "
                f"found {len(bindings)}")
            continue
        if not bindings:
            continue
        if script == _SANITIZE_SCRIPT:
            _validate_sanitize(bindings[0], files, errors)
        elif script == _X509_SCRIPT:
            expected = {
                "SOURCE": "extra/mbedtls-cold/library/x509.c",
                "PIN_MANIFEST": "cmake/Vendor/mbedtls-cold/UPSTREAM.sha256",
                "BUILD_ROOT": _BINARY,
                "OUTPUT": _BINARY + "/src/src/generated/mbedtls-cold/x509.c",
            }
            if bindings[0] != expected:
                errors.append(f"{script}: unapproved cold X.509 generator bindings")
            # The complete script identity, not a generic writer grammar,
            # authorizes only its two anchored edits and atomic publication.
            _script_commands(script, files, errors)
        else:
            base = Path("apps/trading-core")
            expected_roles = [
                (owners[script], base, base, "add_custom_command", "OUTPUT"),
                (owners[script], base, base, "add_custom_target", "trading_core_generate_strategy_registry"),
            ]
            if registry_roles != expected_roles or bindings[0] != bindings[1]:
                errors.append(f"{script}: registry stamp/repair invocation contract changed")
            # Both calls run the same generator with the same bindings. The
            # stamp producer and repair target recipes are validated separately
            # by the custom-command policy; one script proof covers its body.
            _validate_registry(bindings[0], files, errors)
