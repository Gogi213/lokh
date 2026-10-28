import sys
from pathlib import Path as _CodexPath
_CODEX_TOOLS = _CodexPath(__file__).resolve().parents[2]
if str(_CODEX_TOOLS) not in sys.path:
    sys.path.insert(0, str(_CODEX_TOOLS))

import importlib.util

import json

import os

import pathlib

import re

import shutil

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

class ToolbeltFixture:
    @classmethod
    def setUpClass(cls):
        cls.cpp_policy = load_module(
            "CxetFamilyCppPolicy",
            TOOLS_DIR / "Family/Sources/CxetFamilyCppPolicy.py",
        )
        cls.toolbelt = load_module("cxet_toolbelt", TOOLS_DIR / "CxetToolbelt.py")
        cls.parser_boundary = load_module(
            "check_parser_trading_boundary",
            TOOLS_DIR / "CheckParserTradingBoundary.py",
        )

    @staticmethod
    def _write_readiness_config_fixture(root):
        for relative in (
            "Binance/Routing/Futures/Config.cpp",
            "Binance/Routing/Spot/Config.cpp",
            "Other/Fapi/Config.cpp",
        ):
            path = root / "src/src/Core/src/Exchanges" / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// readiness fixture\n", encoding="utf-8")


