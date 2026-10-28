#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


LINK = re.compile(r"!?(?:\[[^\]]*\])\((<[^>]+>|[^)\s]+)(?:\s+[^)]*)?\)")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def markdown_files(arguments: list[str]) -> list[Path]:
    paths: set[Path] = set()
    for value in arguments:
        path = Path(value)
        if path.is_dir():
            paths.update(item for item in path.rglob("*.md") if item.is_file())
        elif path.suffix.casefold() == ".md":
            paths.add(path)
        else:
            raise ValueError(f"not a Markdown path: {value}")
    return sorted(paths)


def local_destinations(path: Path) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    fenced = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        for match in LINK.finditer(line):
            destination = match.group(1)
            if destination.startswith("<") and destination.endswith(">"):
                destination = destination[1:-1]
            destination = unquote(destination.split("#", 1)[0])
            if (
                not destination
                or destination.startswith(("#", "//", "/"))
                or SCHEME.match(destination)
            ):
                continue
            result.append((number, destination))
    return result


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: CheckDocLinks.py PATH...", file=sys.stderr)
        return 2
    try:
        paths = markdown_files(sys.argv[1:])
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    missing: list[str] = []
    for path in paths:
        if not path.is_file():
            missing.append(f"{path}: file does not exist")
            continue
        for line, destination in local_destinations(path):
            target = (path.parent / destination).resolve()
            if not target.exists():
                missing.append(f"{path}:{line}: {destination}")
    if missing:
        print("broken local Markdown links:", file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1
    print(f"checked {len(paths)} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
