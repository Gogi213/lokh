"""Fail-closed structural context for the restricted active CMake graph."""

from __future__ import annotations

from dataclasses import dataclass, replace

from CMake.Syntax.CmakeFamilyLexer import cmake_list_words


@dataclass(frozen=True)
class StructuralArm:
    kind: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class StructuralFrame:
    kind: str
    relative: str
    line: int
    ordinal: int
    opener: tuple[str, ...]
    arm: StructuralArm
    prior_arms: tuple[StructuralArm, ...] = ()


StructuralContext = tuple[StructuralFrame, ...]

_OPENERS = {
    "function": "endfunction",
    "macro": "endmacro",
    "foreach": "endforeach",
    "while": "endwhile",
    "block": "endblock",
}
_CLOSERS = {value: key for key, value in _OPENERS.items()}


class StructuralTracker:
    """Track lexical blocks without guessing whether arbitrary conditions hold."""

    def __init__(
        self,
        relative: str,
        inherited: StructuralContext,
        errors: list[str],
    ) -> None:
        self.relative = relative
        self._frames = list(inherited)
        self._base_depth = len(inherited)
        self._errors = errors

    def context(self) -> StructuralContext:
        return tuple(self._frames)

    def _error(self, line: int, detail: str) -> None:
        self._errors.append(f"{self.relative}:{line}: {detail}")

    def advance(
        self,
        name: str,
        tokens: tuple[str, ...],
        line: int,
        ordinal: int,
    ) -> None:
        if name == "if":
            self._frames.append(StructuralFrame(
                "if", self.relative, line, ordinal, tokens,
                StructuralArm("if", tokens)))
            return
        if name in {"elseif", "else"}:
            if (len(self._frames) <= self._base_depth or
                    self._frames[-1].kind != "if"):
                self._error(line, f"unmatched/cross-file {name}()")
                return
            frame = self._frames[-1]
            if frame.arm.kind == "else":
                self._error(line, f"{name}() follows else()")
                return
            arm = StructuralArm(name, tokens if name == "elseif" else ())
            self._frames[-1] = replace(
                frame,
                arm=arm,
                prior_arms=frame.prior_arms + (frame.arm,),
            )
            return
        if name == "endif":
            self._close("if", name, line)
            return
        if name in _OPENERS:
            self._frames.append(StructuralFrame(
                name, self.relative, line, ordinal, tokens,
                StructuralArm("body", tokens)))
            return
        if name in _CLOSERS:
            self._close(_CLOSERS[name], name, line)

    def _close(self, expected: str, closer: str, line: int) -> None:
        if (len(self._frames) <= self._base_depth or
                self._frames[-1].kind != expected):
            self._error(line, f"unmatched/cross-file {closer}()")
            return
        self._frames.pop()

    def finish(self) -> None:
        if len(self._frames) != self._base_depth:
            frames = self._frames[self._base_depth:]
            detail = ", ".join(
                f"{frame.kind}@{frame.relative}:{frame.line}"
                for frame in frames)
            self._errors.append(
                f"{self.relative}: unterminated structural blocks {detail}")


def exact_context(
    context: StructuralContext,
    expected: tuple[
        tuple[str, str, int, tuple[str, ...], str,
              tuple[str, ...],
              tuple[tuple[str, tuple[str, ...]], ...]], ...
    ],
) -> bool:
    """Compare full opener identity and ordered if-arm history."""
    actual = tuple(
        (
            frame.kind,
            frame.relative,
            frame.line,
            frame.opener,
            frame.arm.kind,
            frame.arm.tokens,
            tuple((arm.kind, arm.tokens) for arm in frame.prior_arms),
        )
        for frame in context
    )
    return actual == expected


def first_if(
    relative: str,
    line: int,
    tokens: tuple[str, ...],
) -> tuple[str, str, int, tuple[str, ...], str,
           tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    return ("if", relative, line, tokens, "if", tokens, ())


def first_body(
    kind: str,
    relative: str,
    line: int,
    tokens: tuple[str, ...],
) -> tuple[str, str, int, tuple[str, ...], str,
           tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    return (kind, relative, line, tokens, "body", tokens, ())


def alternate_if(
    relative: str,
    opener_line: int,
    opener: tuple[str, ...],
    tokens: tuple[str, ...],
) -> tuple[str, str, int, tuple[str, ...], str,
           tuple[str, ...], tuple[tuple[str, tuple[str, ...]], ...]]:
    return (
        "if", relative, opener_line, opener, "elseif", tokens,
        (("if", opener),),
    )


def structural_contexts(
    relative: str,
    commands,
    tokenize,
    errors: list[str],
) -> tuple[StructuralContext, ...]:
    """Annotate one parsed file for exact block-policy validation."""
    tracker = StructuralTracker(relative, (), errors)
    result: list[StructuralContext] = []
    for ordinal, command in enumerate(commands):
        result.append(tracker.context())
        tracker.advance(
            command.name, tuple(tokenize(command.body)), command.line, ordinal)
    tracker.finish()
    return tuple(result)


# Current canonical producer edges. Removed safety/family/test roots are not
# required by any owner profile. Exact source/context/argument guards remain.
_PROJECT_EDGES = {
    ("src/src/CMakeLists.txt", 8, "include", "cmake/CxetExchangeSelection.cmake"):
        ("src/src/CMakeLists.txt", ()),
    ("src/src/CMakeLists.txt", 391, "include", "cmake/CxetHotOptions.cmake"):
        ("src/src/CMakeLists.txt", ()),
    ("apps/trading-core/CMakeLists.txt", 50, "add_subdirectory", "apps/trading-core/capital/CMakeLists.txt"):
        ("apps/trading-core/CMakeLists.txt", ()),
    ("apps/trader/tests/offline/CMakeLists.txt", 3, "add_subdirectory", "apps/trader/tests/startup/CMakeLists.txt"):
        ("apps/trader/tests/offline/CMakeLists.txt", (
            first_if("apps/trader/tests/offline/CMakeLists.txt", 2,
                     ("CXET_SELECTION_ALL", "OR", "CXET_EXCHANGE_FINAM")),)),
    ("apps/hft-parser/CMakeLists.txt", 117, "add_subdirectory", "apps/hft-parser/src/Contracts/CMakeLists.txt"):
        ("apps/hft-parser/CMakeLists.txt", ()),
    ("apps/trading-core/CMakeLists.txt", 253, "add_subdirectory", "apps/trading-core/tests/offline/Execution/CMakeLists.txt"):
        ("apps/trading-core/CMakeLists.txt", ()),
    ("apps/trading-core/CMakeLists.txt", 252, "add_subdirectory", "apps/trading-core/tests/offline/Math/CMakeLists.txt"):
        ("apps/trading-core/CMakeLists.txt", ()),
    ("src/src/CMakeLists.txt", 222, "include", "src/src/cmake/Sources/CxetExchangeSources.cmake"):
        ("src/src/CMakeLists.txt", ()),
    ("src/src/CMakeLists.txt", 223, "include", "src/src/cmake/Sources/CxetCoreSources.cmake"):
        ("src/src/CMakeLists.txt", ()),
    ("src/src/CMakeLists.txt", 224, "include", "src/src/cmake/Sources/CxetNetworkSources.cmake"):
        ("src/src/CMakeLists.txt", ()),
    ("apps/hft-parser/CMakeLists.txt", 118, "include", "apps/hft-parser/cmake/HftpLibraries.cmake"):
        ("apps/hft-parser/CMakeLists.txt", ()),
    ("apps/hft-parser/CMakeLists.txt", 119, "include", "apps/hft-parser/cmake/HftpProcesses.cmake"):
        ("apps/hft-parser/CMakeLists.txt", ()),
    ("apps/trader/CMakeLists.txt", 260, "include", "apps/trader/cmake/PublicAnalytics.cmake"):
        ("apps/trader/CMakeLists.txt", ()),
    ("apps/vetron/CMakeLists.txt", 218, "add_subdirectory", "apps/vetron/wasm/CMakeLists.txt"):
        ("apps/vetron/CMakeLists.txt", ()),
    ("apps/hft-recorder/CMakeLists.txt", 11, "add_subdirectory", "apps/hft-recorder/src/Contracts/CMakeLists.txt"):
        ("apps/hft-recorder/CMakeLists.txt", (
            first_if("apps/hft-recorder/CMakeLists.txt", 9, ("CXET_LOCAL_TESTS",)),
            first_if("apps/hft-recorder/CMakeLists.txt", 10, ("NOT", "TARGET", "hftrec::corpus_contract")))),
    ("apps/hft-recorder/CMakeLists.txt", 48, "add_subdirectory", "apps/hft-recorder/src/Contracts/CMakeLists.txt"):
        ("apps/hft-recorder/CMakeLists.txt", (
            first_if("apps/hft-recorder/CMakeLists.txt", 47, ("NOT", "TARGET", "hftrec::corpus_contract")),)),
    ("apps/hft-recorder/CMakeLists.txt", 50, "add_subdirectory", "apps/hft-recorder/src/CMakeLists.txt"):
        ("apps/hft-recorder/CMakeLists.txt", ()),
    ("apps/hft-recorder/src/CMakeLists.txt", 4, "add_subdirectory", "apps/hft-recorder/src/Runtime/CMakeLists.txt"):
        ("apps/hft-recorder/CMakeLists.txt", ()),
}

_PROJECT_EDGE_ARGUMENTS = {
    ("src/src/CMakeLists.txt", 8): ("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/CxetExchangeSelection.cmake",),
    ("src/src/CMakeLists.txt", 391): ("${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/CxetHotOptions.cmake",),
    ("apps/trading-core/CMakeLists.txt", 50): ("capital",),
    ("apps/trader/tests/offline/CMakeLists.txt", 3): ("../startup", "${CMAKE_CURRENT_BINARY_DIR}/startup"),
    ("apps/hft-parser/CMakeLists.txt", 117, "add_subdirectory"): ("src/Contracts", "EXCLUDE_FROM_ALL"),
    ("apps/trading-core/CMakeLists.txt", 253): ("tests/offline/Execution",),
    ("apps/trading-core/CMakeLists.txt", 252): ("tests/offline/Math",),
    ("src/src/CMakeLists.txt", 222): ("${CMAKE_CURRENT_SOURCE_DIR}/cmake/Sources/CxetExchangeSources.cmake",),
    ("src/src/CMakeLists.txt", 223): ("${CMAKE_CURRENT_SOURCE_DIR}/cmake/Sources/CxetCoreSources.cmake",),
    ("src/src/CMakeLists.txt", 224): ("${CMAKE_CURRENT_SOURCE_DIR}/cmake/Sources/CxetNetworkSources.cmake",),
    ("apps/hft-parser/CMakeLists.txt", 118): ("${CMAKE_CURRENT_SOURCE_DIR}/cmake/HftpLibraries.cmake",),
    ("apps/hft-parser/CMakeLists.txt", 119): ("${CMAKE_CURRENT_SOURCE_DIR}/cmake/HftpProcesses.cmake",),
    ("apps/trader/CMakeLists.txt", 260): ("cmake/PublicAnalytics.cmake",),
    ("apps/vetron/CMakeLists.txt", 218): ("wasm",),
    ("apps/hft-recorder/CMakeLists.txt", 11): ("src/Contracts",),
    ("apps/hft-recorder/CMakeLists.txt", 48): ("src/Contracts",),
    ("apps/hft-recorder/CMakeLists.txt", 50): ("src",),
    ("apps/hft-recorder/src/CMakeLists.txt", 4): ("Runtime",),
}


def validate_project_edge(
    active,
    child_relative: str,
    seen: set[tuple[str, int, str, str]],
    errors: list[str],
) -> None:
    candidates = [key for key in _PROJECT_EDGES
                  if (key[0], key[2], key[3]) ==
                  (active.relative, active.command.name, child_relative)]
    if len(candidates) > 1:
        candidates = [key for key in candidates
                      if exact_context(active.structural_context, _PROJECT_EDGES[key][1])]
    if len(candidates) != 1:
        errors.append(
            f"{active.relative}:{active.command.line}: unreviewed active "
            f"project edge to {child_relative}")
        return
    key = candidates[0]
    contract = _PROJECT_EDGES[key]
    _, expected = contract
    if key in seen:
        errors.append(
            f"{active.relative}:{active.command.line}: duplicate reviewed "
            f"project edge to {child_relative}")
    seen.add(key)
    if tuple(cmake_list_words(active.command.body)) != (
            _PROJECT_EDGE_ARGUMENTS.get(
                (key[0], key[1], key[2]),
                _PROJECT_EDGE_ARGUMENTS.get((key[0], key[1]), ()))):
        errors.append(
            f"{active.relative}:{active.command.line}: reviewed project edge "
            "arguments changed")
    if not exact_context(active.structural_context, expected):
        errors.append(
            f"{active.relative}:{active.command.line}: project edge to "
            f"{child_relative} escaped its exact structural context")


def require_project_edges(
    family_roots: tuple[str, ...],
    seen: set[tuple[str, int, str, str]],
    errors: list[str],
    *,
    initial_values_by_scope=None,
    active_origins=None,
) -> None:
    roots = set(family_roots)
    from CMake.Flow.CmakeFamilyFlow import structural_context_possible
    required = set()
    for key, (owner, expected) in _PROJECT_EDGES.items():
        if owner not in roots or (active_origins is not None and key[0] not in active_origins):
            continue
        context = tuple(StructuralFrame(kind, relative, line, -1, opener,
            StructuralArm(arm, tokens), tuple(StructuralArm(*prior) for prior in priors))
            for kind, relative, line, opener, arm, tokens, priors in expected)
        if structural_context_possible(context, (initial_values_by_scope or {}).get(owner)):
            required.add(key)
    missing = sorted(required - seen)
    if missing:
        errors.append(
            "active family graph misses reviewed project edges: " +
            ", ".join(
                f"{relative}:{line}->{child}"
                for relative, line, _name, child in missing))


def reviewed_source_return(active, source_text, source_commands, initial_values) -> bool:
    """The reviewed Recorder corpus lane ends this source-list invocation."""
    from pathlib import Path
    from CMake.Flow.CmakeFamilyExecutionIdentity import ROOT, reviewed_file_identity
    from CMake.Syntax.CmakeFamilyLexer import scan_commands
    relative = "apps/hft-recorder/CMakeLists.txt"
    directory = (relative,)
    if (active.scope != relative or active.relative != relative or
            active.command.name != "return" or active.command.line != 13 or
            cmake_list_words(active.command.body) or
            active.source_base != Path(relative).parent or active.binary_base != Path(relative).parent or
            active.directory != directory or active.execution_chain != ((directory, relative),) or
            not exact_context(active.structural_context,
                (first_if(relative, 9, ("CXET_LOCAL_TESTS",)),)) or
            (initial_values or {}).get("CXET_LOCAL_TESTS") != ("ON",) or
            not reviewed_file_identity(relative)):
        return False
    try:
        if source_text != (ROOT / relative).read_text(encoding="utf-8"):
            return False
    except (OSError, UnicodeError):
        return False
    errors = []
    parsed = scan_commands(relative, source_text, errors,
        lambda name, body, line, _offset: (name, body, line))
    return not errors and parsed == [(item.name, item.body, item.line) for item in source_commands]


def recorder_contract_context(active, local_context=()) -> bool:
    """Exact corpus-provider evaluation, preserving its canonical caller guards."""
    from pathlib import Path
    relative = "apps/hft-recorder/src/Contracts/CMakeLists.txt"
    root = "apps/hft-recorder/CMakeLists.txt"
    base = Path(relative).parent
    if active.relative != relative or active.source_base != base or active.binary_base != base:
        return False
    if active.scope == relative:
        directory = (relative,)
        return (active.directory == directory and active.execution_chain == ((directory, relative),) and
                exact_context(active.structural_context, local_context))
    directory = (root, relative)
    if (active.scope != root or active.directory != directory or
            active.execution_chain != (((root,), root), (directory, relative))):
        return False
    prefixes = (
        (first_if(root, 9, ("CXET_LOCAL_TESTS",)),
         first_if(root, 10, ("NOT", "TARGET", "hftrec::corpus_contract"))),
        (first_if(root, 47, ("NOT", "TARGET", "hftrec::corpus_contract")),),
    )
    return any(exact_context(active.structural_context, prefix + local_context) for prefix in prefixes)
