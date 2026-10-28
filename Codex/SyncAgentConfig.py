#!/usr/bin/env python3
"""Explicitly synchronize the owned part of a global Codex configuration.

Only the marked instruction block is synchronized. A fresh model selection may
be initialized to gpt-6.1-sol; all other settings and hook files are untouched.
No action is taken by import.
Apply holds a nonblocking advisory lock on the Codex home directory throughout
the transaction, serializing cooperating instances of this tool only. External
editors need not honor it: byte/mode rechecks detect observed changes but do
not provide atomic compare-and-swap against arbitrary writers.
"""
from __future__ import annotations

import argparse
import errno
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import tomllib
from dataclasses import dataclass

try:
    import fcntl
except ImportError:  # The synchronizer has no safe lock on this platform.
    fcntl = None

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "<!-- BEGIN CXET CODEX ROUTING -->"
END = "<!-- END CXET CODEX ROUTING -->"
DEFAULT_PRIMARY = "gpt-6.1-sol"
PRIMARY_FIELDS = ("model", "model_reasoning_effort", "plan_mode_reasoning_effort")
PRIMARY_SELECTION_CONTEXT = ("profile", "profiles", "model_provider", "oss_provider", "model_providers")
LEGACY_ROUTING = " ".join("""Основная модель и содержательные агенты — `gpt-6.1-terra` с `xhigh`;
для критически сложной интеграции, H0/H1, live/order и security — `max`.
Узкие механические задачи выполняй на Terra `high`. Для особенно сложной
задачи, повторного непонимания или неразрешённого противоречия привлекай
`gpt-6-astra` с `high`, передавая конкретный вопрос и проверенный контекст.
Sol используй только по явному запросу пользователя. Сохраняй независимые
профильные ревью и подтверждай фактическую модель и уровень, не предполагая,
что настройки меняют уже работающий поток.""".split())


class SyncError(ValueError):
    """A refusal which must not expose unrelated configuration values."""


def _parse(data: bytes) -> dict:
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise SyncError("config.toml is not valid UTF-8 TOML") from exc


def update_config(data: bytes, *,
                  preferred_primary: str | None = DEFAULT_PRIMARY) -> tuple[bytes, list[str]]:
    """Initialize an absent model selection without managing any other setting."""
    original = _parse(data)
    selection = PRIMARY_FIELDS + PRIMARY_SELECTION_CONTEXT
    if preferred_primary is None or any(field in original for field in selection):
        return data, []
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", preferred_primary):
        raise SyncError("unsupported initial model")
    newline = b"\r\n" if b"\r\n" in data else b"\n"
    result = b'model = "' + preferred_primary.encode("ascii") + b'"' + newline + data
    _parse(result)
    return result, ["model"]


def update_instructions(data: bytes, portable: bytes) -> tuple[bytes, bool]:
    try:
        text, body = data.decode("utf-8"), portable.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise SyncError("instructions must be UTF-8") from exc
    if not body or BEGIN in body or END in body:
        raise SyncError("portable instruction block is invalid")
    block = BEGIN + "\n" + body + "\n" + END
    if text.count(BEGIN) != text.count(END) or text.count(BEGIN) > 1:
        raise SyncError("ambiguous instruction block markers")
    if BEGIN in text:
        start, finish = text.index(BEGIN), text.index(END)
        if finish < start:
            raise SyncError("reversed instruction block markers")
        segments = (text[:start], text[finish + len(END):])
    else:
        segments = (text,)
    legacy = [(segment, match) for segment in segments
              for match in re.finditer(r"(?m)^## Выбор моделей Codex[ \t]*\r?$", segment)]
    if len(legacy) > 1:
        raise SyncError("multiple legacy routing sections")
    if legacy and BEGIN in text:
        raise SyncError("legacy routing section conflicts with managed block")
    legacy_end = None
    if legacy:
        segment, heading = legacy[0]
        paragraph = re.match(r"\s*([^\r\n]+(?:\r?\n[^\r\n]+)*)", segment[heading.end():])
        if paragraph is None or " ".join(paragraph.group(1).split()) != LEGACY_ROUTING:
            raise SyncError("unrecognized legacy routing section")
        legacy_end = heading.end() + paragraph.end()
    if BEGIN in text:
        updated = text[:start] + block + text[finish + len(END):]
    else:
        if legacy:
            start = legacy[0][1].start()
            assert legacy_end is not None
            updated = text[:start] + block + text[legacy_end:]
        else:
            separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
            updated = text + separator + block + "\n"
    result = updated.encode("utf-8")
    return result, result != data


@dataclass
class Change:
    path: Path
    before: bytes | None
    after: bytes
    mode: int
    labels: list[str]


def _read(path: Path) -> tuple[bytes | None, int]:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None, 0o600
    if not stat.S_ISREG(info.st_mode):
        raise SyncError("refusing non-regular file: " + path.name)
    return path.read_bytes(), stat.S_IMODE(info.st_mode)


def plan(root: Path, home: Path) -> list[Change]:
    portable = (root / "tools/Codex/GlobalAgentInstructions.md").read_bytes()
    config_path, instructions_path = home / "config.toml", home / "AGENTS.md"
    config, config_mode = _read(config_path)
    instructions, instruction_mode = _read(instructions_path)
    new_config, keys = update_config(config or b"")
    new_instructions, changed = update_instructions(instructions or b"", portable)
    changes = []
    if config != new_config:
        changes.append(Change(config_path, config, new_config, config_mode, keys))
    if changed or instructions is None:
        changes.append(Change(instructions_path, instructions, new_instructions, instruction_mode, ["managed instruction block"]))
    return changes


def _write_temp(parent: Path, data: bytes, mode: int, prefix: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, dir=parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        os.unlink(name)
        raise
    return Path(name)


def apply(changes: list[Change]) -> None:
    if not changes:
        return
    if fcntl is None or not hasattr(os, "O_DIRECTORY"):
        raise SyncError("apply requires POSIX directory flock support")
    home = changes[0].path.parent
    if any(change.path.parent != home for change in changes):
        raise SyncError("managed files must share one Codex home directory")
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directory_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY)
    except OSError as exc:
        raise SyncError("unable to open Codex home directory for locking") from exc
    try:
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                raise SyncError("another Codex sync apply holds the directory lock") from exc
            raise SyncError("apply requires working POSIX directory flock support") from exc
        _apply_locked(changes, home)
    finally:
        # Closing releases the lock, including on backup, replacement or rollback failure.
        os.close(directory_fd)


def _apply_locked(changes: list[Change], home: Path) -> None:
    staged: list[tuple[Change, Path]] = []
    installed: list[Change] = []
    try:
        for change in changes:
            current, mode = _read(change.path)
            if current != change.before or (current is not None and mode != change.mode):
                raise SyncError("file changed since preview: " + change.path.name)
            if current is not None:
                # Exclusive uniquely named backup; never overwrite an existing backup.
                _write_temp(home, current, change.mode, change.path.name + ".bak.")
            staged.append((change, _write_temp(home, change.after, change.mode, ".codex-sync.")))
        for change, temporary in staged:
            current, mode = _read(change.path)
            if current != change.before or (current is not None and mode != change.mode):
                raise SyncError("file changed before replacement: " + change.path.name)
            os.replace(temporary, change.path)
            installed.append(change)
    except BaseException as exc:
        failures = []
        for change in reversed(installed):
            try:
                current, mode = _read(change.path)
                if current != change.after or mode != change.mode:
                    failures.append(change.path.name)
                    continue
                if change.before is None:
                    change.path.unlink()
                else:
                    rollback = _write_temp(home, change.before, change.mode, ".codex-rollback.")
                    try:
                        # Check again immediately before restoring; preserve external edits.
                        if _read(change.path) != (change.after, change.mode):
                            failures.append(change.path.name)
                        else:
                            os.replace(rollback, change.path)
                    finally:
                        rollback.unlink(missing_ok=True)
            except (OSError, SyncError):
                failures.append(change.path.name)
        if failures:
            raise SyncError("rollback refused or failed for: " + ", ".join(failures)) from exc
        raise
    finally:
        for _, temporary in staged:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="report drift without writing")
    mode.add_argument("--apply", action="store_true", help="apply managed changes with backups")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    args = parser.parse_args(argv)
    try:
        changes = plan(args.root, args.codex_home)
        for change in changes:
            print(change.path.name + ": " + ", ".join(change.labels))
        if args.apply:
            apply(changes)
            print("Applied." if changes else "Already synchronized.")
            return 0
        print("Drift found." if changes else "Already synchronized.")
        return 1 if changes else 0
    except (SyncError, OSError, ValueError) as exc:
        # Do not print exception text from TOML or filesystem: it may contain secrets.
        if isinstance(exc, SyncError):
            print("Sync refused: " + str(exc), file=sys.stderr)
        else:
            print("Sync refused: unable to read, validate or update managed files.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
