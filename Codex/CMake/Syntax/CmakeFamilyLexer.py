"""Deterministic CMake command/comment/list lexer shared by family checks."""

from __future__ import annotations

import re


def scan_commands(relative: str, text: str, errors: list[str], factory):
    result = []
    index = 0
    while index < len(text):
        if text[index] == "#":
            bracket_comment = re.match(r"#\[(=*)\[", text[index:])
            if bracket_comment is not None:
                closing = "]" + bracket_comment.group(1) + "]"
                end = text.find(
                    closing, index + len(bracket_comment.group(0)))
                if end < 0:
                    errors.append(
                        f"{relative}:{text.count(chr(10), 0, index) + 1}: "
                        "unterminated CMake bracket comment")
                    break
                index = end + len(closing)
                continue
            newline = text.find("\n", index)
            if newline < 0:
                break
            index = newline + 1
            continue
        if not (text[index].isalpha() or text[index] == "_"):
            index += 1
            continue
        start = index
        index += 1
        while index < len(text) and (
                text[index].isalnum() or text[index] == "_"):
            index += 1
        name = text[start:index].lower()
        probe = index
        interstitial_comment = False
        while probe < len(text):
            while probe < len(text) and text[probe].isspace():
                probe += 1
            if probe >= len(text) or text[probe] != "#":
                break
            bracket_comment = re.match(r"#\[(=*)\[", text[probe:])
            interstitial_comment = True
            if bracket_comment is not None:
                closing = "]" + bracket_comment.group(1) + "]"
                end = text.find(
                    closing, probe + len(bracket_comment.group(0)))
                if end < 0:
                    errors.append(
                        f"{relative}:{text.count(chr(10), 0, probe) + 1}: "
                        "unterminated CMake bracket comment")
                    return result
                probe = end + len(closing)
                continue
            newline = text.find("\n", probe)
            probe = len(text) if newline < 0 else newline + 1
        if probe >= len(text) or text[probe] != "(":
            index = probe
            continue
        if interstitial_comment:
            errors.append(
                f"{relative}:{text.count(chr(10), 0, start) + 1}: "
                f"comment between command name {name} and '(' is forbidden")
        depth = 1
        cursor = probe + 1
        quoted = False
        bracket_end = ""
        while cursor < len(text) and depth:
            char = text[cursor]
            if bracket_end:
                if text.startswith(bracket_end, cursor):
                    cursor += len(bracket_end)
                    bracket_end = ""
                else:
                    cursor += 1
            elif quoted:
                if char == "\\":
                    cursor += 2
                elif char == '"':
                    quoted = False
                    cursor += 1
                else:
                    cursor += 1
            elif char == "\\" and cursor + 1 < len(text):
                # In an unquoted argument CMake uses the backslash to escape
                # the following byte.  In particular, \( and \) are data and
                # must never alter the command-parenthesis depth.
                cursor += 2
            elif (comment := re.match(
                    r"#\[(=*)\[", text[cursor:])) is not None:
                closing = "]" + comment.group(1) + "]"
                end = text.find(closing, cursor + len(comment.group(0)))
                if end < 0:
                    errors.append(
                        f"{relative}:{text.count(chr(10), 0, cursor) + 1}: "
                        "unterminated CMake bracket comment")
                    return result
                cursor = end + len(closing)
            elif (bracket := re.match(
                    r"\[(=*)\[", text[cursor:])) is not None:
                bracket_end = "]" + bracket.group(1) + "]"
                cursor += len(bracket.group(0))
            elif char == '"':
                quoted = True
                cursor += 1
            elif char == "#":
                newline = text.find("\n", cursor)
                cursor = len(text) if newline < 0 else newline + 1
            elif char == "(":
                depth += 1
                cursor += 1
            elif char == ")":
                depth -= 1
                cursor += 1
            else:
                cursor += 1
        if depth:
            errors.append(
                f"{relative}:{text.count(chr(10), 0, start) + 1}: "
                f"unterminated CMake command {name}")
            return result
        result.append(factory(
            name,
            text[probe + 1:cursor - 1],
            text.count("\n", 0, start) + 1,
            start,
        ))
        index = cursor
    return result


def validate_cmake_lexer_microcases(errors: list[str]) -> None:
    """Keep executable commands visible across comment whitespace tricks."""
    def factory(name, body, line, offset):
        return name, body, line, offset

    for label, text in (
            ("line", "target_sources # comment\n(t PRIVATE x.cpp)"),
            ("bracket", "target_sources #[[comment]]\n(t PRIVATE x.cpp)")):
        local_errors: list[str] = []
        commands = scan_commands(
            f"microcase-{label}.cmake", text, local_errors, factory)
        if (len(commands) != 1 or commands[0][0] != "target_sources" or
                not local_errors):
            errors.append(
                "CMake lexer self-check missed interstitial "
                f"{label} comment")


def strip_cmake_comments(value: str) -> str:
    result: list[str] = []
    index = 0
    quoted = False
    while index < len(value):
        char = value[index]
        if quoted:
            result.append(char)
            if char == "\\" and index + 1 < len(value):
                index += 1
                result.append(value[index])
            elif char == '"':
                quoted = False
            index += 1
            continue
        if char == "\\" and index + 1 < len(value):
            result.append(char)
            index += 1
            result.append(value[index])
            index += 1
            continue
        if char == '"':
            quoted = True
            result.append(char)
            index += 1
            continue
        bracket = re.match(r"\[(=*)\[", value[index:])
        if bracket is not None:
            closing = "]" + bracket.group(1) + "]"
            end = value.find(closing, index + len(bracket.group(0)))
            if end < 0:
                result.append(value[index:])
                break
            end += len(closing)
            result.append(value[index:end])
            index = end
            continue
        comment = re.match(r"#\[(=*)\[", value[index:])
        if comment is not None:
            closing = "]" + comment.group(1) + "]"
            end = value.find(closing, index + len(comment.group(0)))
            if end < 0:
                break
            result.append("\n" * value.count("\n", index, end))
            index = end + len(closing)
            continue
        if char == "#":
            newline = value.find("\n", index)
            if newline < 0:
                break
            result.append("\n")
            index = newline + 1
            continue
        result.append(char)
        index += 1
    return "".join(result)


def words(body: str) -> list[str]:
    """Split CMake arguments; only double and bracket arguments quote text."""
    value = strip_cmake_comments(body)
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index].isspace():
            index += 1
            continue
        start = index
        bracket = re.match(r"\[(=*)\[", value[index:])
        if bracket is not None:
            closing = "]" + bracket.group(1) + "]"
            end = value.find(closing, index + len(bracket.group(0)))
            index = len(value) if end < 0 else end + len(closing)
            result.append(value[start:index])
            continue
        quoted = False
        while index < len(value):
            char = value[index]
            if char == "\\" and index + 1 < len(value):
                index += 2
                continue
            if char == '"':
                quoted = not quoted
                index += 1
                continue
            if char.isspace() and not quoted:
                break
            index += 1
        result.append(value[start:index])
    return result


def cmake_argument_value(token: str) -> str:
    """Return the value of one quoted, bracket, or unquoted CMake token.

    The raw token is retained by :func:`words` for grammar policies.  Value
    expansion uses this helper so ``NAME=\"${value}\"`` becomes one CMake
    argument without leaving quote bytes in the modeled value.  Backslash
    escapes remain intact: downstream policies still need to distinguish
    escaped semicolons, parentheses and regular-expression syntax.
    """
    bracket = re.fullmatch(r"\[(=*)\[([\s\S]*)\]\1\]", token)
    if bracket is not None:
        return bracket.group(2)
    result: list[str] = []
    index = 0
    while index < len(token):
        char = token[index]
        if char == "\\" and index + 1 < len(token):
            result.extend((char, token[index + 1]))
            index += 2
            continue
        if char != '"':
            result.append(char)
        index += 1
    return "".join(result)


def split_top_level(value: str, delimiter: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            index += 2
            continue
        if value.startswith("$<", index):
            depth += 1
            index += 2
            continue
        if value[index] == ">" and depth:
            depth -= 1
        elif value[index] == delimiter and depth == 0:
            result.append(value[start:index])
            start = index + 1
        index += 1
    result.append(value[start:])
    return result


def cmake_list_words(body: str) -> list[str]:
    result: list[str] = []
    for token in words(body):
        value = cmake_argument_value(token)
        # A quoted argument is one argument even when its value contains a
        # semicolon.  Unquoted list syntax is split without dropping explicit
        # empty elements: empty data and a zero-iteration list are different
        # states in foreach().
        if '"' in token or re.fullmatch(
                r"\[(=*)\[[\s\S]*\]\1\]", token) is not None:
            result.append(value)
        else:
            result.extend(split_top_level(value, ";"))
    return result
