"""Codex tooling tests; implementation modules retain their CLI import root."""
from pathlib import Path
import sys

_CODEX_TOOLS = Path(__file__).resolve().parents[1]
if str(_CODEX_TOOLS) not in sys.path:
    sys.path.insert(0, str(_CODEX_TOOLS))
