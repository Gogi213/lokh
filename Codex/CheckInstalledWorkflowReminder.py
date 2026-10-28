#!/usr/bin/env python3
"""Check installed global Codex routing; retained under its historical filename.

This read-only host check does not invoke hooks, models, or other executables.
The absence of the obsolete workflow reminder is valid.
"""
from pathlib import Path
import os
import unittest

import SyncAgentConfig

ROOT = Path(__file__).resolve().parents[2]
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))


class InstalledRoutingTests(unittest.TestCase):
    def test_owned_global_routing_and_instructions_are_synchronized(self):
        changes = SyncAgentConfig.plan(ROOT, CODEX_HOME)
        summary = "; ".join(change.path.name + ": " + ", ".join(change.labels)
                            for change in changes)
        self.assertFalse(changes, "Global Codex routing drift: " + summary)


if __name__ == "__main__":
    unittest.main()
