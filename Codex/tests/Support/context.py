"""Tests for the bounded CXET context index and static postcheck."""

from __future__ import annotations
import sys
from pathlib import Path as _CodexPath
_CODEX_TOOLS = _CodexPath(__file__).resolve().parents[2]
if str(_CODEX_TOOLS) not in sys.path:
    sys.path.insert(0, str(_CODEX_TOOLS))


import importlib.util

import json

import pathlib

import subprocess

import sys

import tempfile

import unittest

from unittest import mock

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[2]

REPO_ROOT = TOOLS_DIR.parent.parent

def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

class ContextFixture:
    @classmethod
    def setUpClass(cls):
        cls.index = load_module(
            "cxet_context_index",
            TOOLS_DIR / "CxetContextIndex.py",
        )

    @staticmethod
    def _search_fixture(root, **limits):
        source = root / "src"
        source.mkdir()
        tools = root / "tools/Codex"
        tools.mkdir(parents=True)
        settings = {"map_bytes": 6144, "detail_bytes": 8192, "max_results": 20,
                    "max_files": 2000, "max_entries": 20000, "max_file_bytes": 1048576}
        settings.update(limits)
        (tools / "CxetContextManifest.json").write_text(json.dumps({
            "limits": settings, "common": {"route_docs": [], "rules": ["static"]},
            "scopes": {"demo": {"owner": "demo", "keywords": ["demo"], "roots": ["src"],
                        "route_docs": [], "anchors": [],
                        "static_checks": ["python3 tools/Codex/CxetContextIndex.py validate"]}},
        }), encoding="utf-8")
        return source


