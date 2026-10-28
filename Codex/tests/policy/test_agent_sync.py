#!/usr/bin/env python3
"""Fixture tests for the explicitly invoked global configuration synchronizer."""
from __future__ import annotations

import contextlib
import errno
import io
import os
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "tools/Codex"
sys.path.insert(0, str(TOOLS))
import SyncAgentConfig as sync  # noqa: E402


class AgentSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "codex"

    def test_fresh_install_and_second_apply_are_idempotent(self):
        changes = sync.plan(ROOT, self.home)
        self.assertFalse(self.home.exists())
        self.assertEqual({c.path.name for c in changes}, {"config.toml", "AGENTS.md"})
        sync.apply(changes)
        self.assertEqual(sync.plan(ROOT, self.home), [])
        config = tomllib.loads((self.home / "config.toml").read_text())
        self.assertEqual(config, {"model": "gpt-6.1-sol"})
        self.assertNotIn("model_reasoning_effort", config)
        self.assertNotIn("plan_mode_reasoning_effort", config)
        self.assertIn(sync.BEGIN, (self.home / "AGENTS.md").read_text())
        self.assertFalse(list(self.home.glob("*.bak.*")))

    def test_preserves_unrelated_bytes_modes_and_personal_hooks(self):
        self.home.mkdir()
        config = self.home / "config.toml"
        original = (b'# private header\nmodel = "legacy" # keep comment\n'
                    b'service_tier = "priority"\n[agents]\nmax_concurrent_threads_per_session = 7\n'
                    b'[features]\ngoals = false\ncustom = "private"\n'
                    b'[projects."/secret/path"]\ntrust_level = "trusted"\n')
        config.write_bytes(original)
        os.chmod(config, 0o640)
        hooks = self.home / "hooks.json"
        hooks.write_bytes(b'{"hooks":{"Custom":[{"command":"private"}]}}\n')
        instructions = self.home / "AGENTS.md"
        instructions.write_text("# Personal\n\nKeep this.\n", encoding="utf-8")
        changes = sync.plan(ROOT, self.home)
        sync.apply(changes)
        result = config.read_bytes()
        self.assertIn(b'# private header\n', result)
        self.assertIn(b' # keep comment\n', result)
        self.assertIn(b'[projects."/secret/path"]\ntrust_level = "trusted"\n', result)
        parsed = tomllib.loads(result.decode())
        self.assertIn(b'model = "legacy" # keep comment\n', result)
        self.assertEqual(parsed["model"], "legacy")
        self.assertEqual(parsed["service_tier"], "priority")
        self.assertEqual(parsed["agents"]["max_concurrent_threads_per_session"], 7)
        self.assertEqual(parsed["features"]["custom"], "private")
        self.assertEqual(hooks.read_bytes(), b'{"hooks":{"Custom":[{"command":"private"}]}}\n')
        self.assertEqual(config.stat().st_mode & 0o777, 0o640)
        self.assertTrue(instructions.read_text().startswith("# Personal\n\nKeep this.\n"))
        self.assertEqual(result, original)
        self.assertFalse(list(self.home.glob("config.toml.bak.*")))
        self.assertEqual(sync.plan(ROOT, self.home), [])

    def test_plan_needs_only_generic_instructions_without_project_routing(self):
        root = Path(self.temp.name) / "source"
        instructions = root / "tools/Codex/GlobalAgentInstructions.md"
        instructions.parent.mkdir(parents=True)
        instructions.write_bytes(b"Generic instructions.\n")
        changes = sync.plan(root, self.home)
        self.assertEqual({change.path.name for change in changes}, {"config.toml", "AGENTS.md"})
        block = next(change.after for change in changes if change.path.name == "AGENTS.md")
        self.assertIn(b"Generic instructions.\n", block)

    def test_optional_model_initialization_preserves_every_other_byte(self):
        original = (b'# personal settings\r\nservice_tier = "priority"\r\n'
                    b'features = { fast_mode = false, custom = true }\r\n'
                    b'agents = { enabled = false, max_concurrent_threads_per_session = 0 }')
        self.assertEqual(sync.update_config(original, preferred_primary=None), (original, []))
        updated, changes = sync.update_config(original)
        self.assertEqual(updated, b'model = "gpt-6.1-sol"\r\n' + original)
        self.assertEqual(changes, ["model"])
        before = tomllib.loads(original.decode())
        after = tomllib.loads(updated.decode())
        self.assertEqual(after, {"model": "gpt-6.1-sol", **before})
        self.assertEqual(sync.update_config(updated), (updated, []))

    def test_valid_unrelated_nan_value_survives_initialization(self):
        original = b'custom = nan\n[features]\nfast_mode = false\n'
        self.assertEqual(sync.update_config(original),
                         (b'model = "gpt-6.1-sol"\n' + original, ["model"]))

    def test_existing_primary_selection_is_byte_preserved_without_completing_it(self):
        cases = (
            b"model = 'future-model' # personal choice\nmodel_reasoning_effort = 'ultra'\n"
            b'plan_mode_reasoning_effort = "ultra" # independent choice\n',
            b'model = "future-model"\n',
            b'model_reasoning_effort = "ultra"\n',
            b'plan_mode_reasoning_effort = "ultra"\n',
            b'model_reasoning_effort = "ultra"\nplan_mode_reasoning_effort = "high"\n',
        )
        for original in cases:
            with self.subTest(original=original):
                result, _ = sync.update_config(original)
                self.assertEqual(result, original)
                before = tomllib.loads(original.decode())
                after = tomllib.loads(result.decode())
                for key in sync.PRIMARY_FIELDS:
                    self.assertEqual(key in before, key in after)
                    if key in before:
                        self.assertEqual(before[key], after[key])
                again, changes = sync.update_config(result)
                self.assertEqual(again, result)
                self.assertEqual(changes, [])

    def test_profiles_prevent_default_primary_selection(self):
        cases = (b'profile = "future"\n',
                 b'[profiles.future]\nmodel = "future-model"\nmodel_reasoning_effort = "ultra"\n',
                 b'profile = "future"\n[profiles.future]\nmodel = "future-model"\n',
                 b'profiles = {}\n')
        for original in cases:
            with self.subTest(original=original):
                result, _ = sync.update_config(original)
                self.assertEqual(result, original)
                before = tomllib.loads(original.decode())
                parsed = tomllib.loads(result.decode())
                for key in ("profile", "profiles"):
                    if key in before:
                        self.assertEqual(parsed[key], before[key])
                for key in sync.PRIMARY_FIELDS:
                    self.assertNotIn(key, parsed)
                self.assertEqual(sync.update_config(result),
                                 (result, []))

    def test_provider_selection_prevents_default_primary_selection(self):
        cases = (b'model_provider = "alternative" # personal provider\n',
                 b'oss_provider = "local-provider"\n',
                 b'[model_providers.alternative]\nname = "Alternative"\n'
                 b'base_url = "http://127.0.0.1:1234/v1"\n',
                 b'model_providers = {}\n')
        for original in cases:
            with self.subTest(original=original):
                result, _ = sync.update_config(original)
                self.assertEqual(result, original)
                before = tomllib.loads(original.decode())
                after = tomllib.loads(result.decode())
                for key in before:
                    self.assertEqual(after[key], before[key])
                for key in sync.PRIMARY_FIELDS:
                    self.assertNotIn(key, after)
                self.assertEqual(sync.update_config(result),
                                 (result, []))

    def test_model_initialization_preserves_multiline_values_and_arrays(self):
        original = (b'note = """before\n[agents]\n[features]\nafter"""\n'
                    b'root_array = [\n["[agents]", "[features]"],\n'
                    b'"""array text\n[agents]\n[features]\n""",\n]\n'
                    b'[agents]\nagent_array = [\n["[features]"],\n]\n'
                    b'[features]\nfeature_array = [\n["[agents]"],\n]\n'
                    b'[desktop]\nfollowUpQueueMode = "steer"\n')
        result, _ = sync.update_config(original)
        before = tomllib.loads(original.decode())
        after = tomllib.loads(result.decode())
        self.assertEqual(after["note"], before["note"])
        self.assertEqual(after["root_array"], before["root_array"])
        self.assertEqual(after["agents"]["agent_array"], before["agents"]["agent_array"])
        self.assertEqual(after["features"]["feature_array"], before["features"]["feature_array"])
        self.assertEqual(after["desktop"], before["desktop"])
        self.assertNotIn("enabled", after["agents"])
        self.assertNotIn("fast_mode", after["features"])
        self.assertEqual(result, b'model = "gpt-6.1-sol"\n' + original)
        self.assertIn(b'note = """before\n[agents]\n[features]\nafter"""\n', result)
        self.assertIn(b'agent_array = [\n["[features]"],\n]\n', result)
        self.assertEqual(sync.update_config(result),
                         (result, []))

    def test_preserves_personal_features_desktop_and_mcp_including_absent_values(self):
        mcp = (b'[mcp_servers.local]\ncommand = "/usr/bin/python3"\n'
               b'cwd = "/home/person/private-project"\nargs = ["server.py", "--local"]\n'
               b'enabled = true\n')
        desktop = b'[desktop]\nfollowUpQueueMode = "steer"\n'
        cases = (
            (b'goals = true\nhooks = false\ninstant_interrupt = true\n',
             {"goals": True, "hooks": False, "instant_interrupt": True}),
            (b'goals = false\nhooks = true\ninstant_interrupt = false\n',
             {"goals": False, "hooks": True, "instant_interrupt": False}),
            (b'instant_interrupt = false\n', {"instant_interrupt": False}),
        )
        for features, expected_features in cases:
            with self.subTest(features=features):
                original = desktop + b'[features]\n' + features + mcp
                result, _ = sync.update_config(original)
                parsed = tomllib.loads(result.decode("utf-8"))
                self.assertIn(desktop, result)
                self.assertIn(mcp, result)
                self.assertEqual(parsed["desktop"]["followUpQueueMode"], "steer")
                self.assertEqual(parsed["mcp_servers"]["local"]["cwd"],
                                 "/home/person/private-project")
                for name in ("goals", "hooks", "instant_interrupt"):
                    if name in expected_features:
                        self.assertIs(parsed["features"][name], expected_features[name])
                    else:
                        self.assertNotIn(name, parsed["features"])
                self.assertEqual(parsed["features"], expected_features)
                self.assertEqual(result, b'model = "gpt-6.1-sol"\n' + original)

    def test_legacy_section_migrates_and_preserves_adjacent_content(self):
        old = ("# Personal\n\n## Выбор моделей Codex\n\n" + sync.LEGACY_ROUTING + "\n\n"
               "Keep this personal paragraph.\n\n"
               "## Other\nKeep this exactly.\n")
        portable = b"## Current routing\nRouting instructions.\n"
        result, changed = sync.update_instructions(old.encode(), portable)
        self.assertTrue(changed)
        self.assertTrue(result.startswith(b"# Personal\n\n"))
        self.assertTrue(result.endswith(b"## Other\nKeep this exactly.\n"))
        self.assertIn(b"Keep this personal paragraph.\n\n", result)
        self.assertNotIn("Основная модель".encode(), result)
        self.assertEqual(sync.update_instructions(result, portable), (result, False))

    def test_personal_model_mentions_survive_initial_and_existing_block_updates(self):
        before = b"# Personal\nI choose gpt-6-luna for my work.\n\n"
        after = b"\n## Notes\nA prior example used gpt-6.1-sol.\n"
        portable = b"## Current routing\nPortable instructions.\n"
        initial = before + after
        created, changed = sync.update_instructions(initial, portable)
        self.assertTrue(changed)
        self.assertTrue(created.startswith(initial))
        self.assertEqual(sync.update_instructions(created, portable), (created, False))
        existing = before + sync.BEGIN.encode() + b"\nOld text\n" + sync.END.encode() + after
        updated, changed = sync.update_instructions(existing, portable)
        self.assertTrue(changed)
        self.assertEqual(updated, before + sync.BEGIN.encode() + b"\n" + portable.rstrip()
                         + b"\n" + sync.END.encode() + after)
        self.assertEqual(sync.update_instructions(updated, portable), (updated, False))
        legacy = ("## Выбор моделей Codex\n\n" + sync.LEGACY_ROUTING + "\n\n").encode()
        with self.assertRaisesRegex(sync.SyncError, "legacy routing section conflicts"):
            sync.update_instructions(legacy + existing, portable)

    def test_ambiguous_routing_and_toml_are_refused_without_writes(self):
        unknown = "## Выбор моделей Codex\nUnknown.\n".encode()
        known = ("## Выбор моделей Codex\n\n" + sync.LEGACY_ROUTING + "\n\n").encode()
        block = (sync.BEGIN + "\nold\n" + sync.END).encode()
        for text in (unknown,
                     unknown + block,
                     known + known,
                     known + block + b"\n" + known,
                     sync.BEGIN.encode(),
                     (sync.END + "\n" + sync.BEGIN).encode(),
                     (sync.BEGIN + "\n" + sync.BEGIN + "\n" + sync.END).encode(),
                     ):
            with self.subTest(text=text):
                with self.assertRaises(sync.SyncError):
                    sync.update_instructions(text, b"Current instructions\n")
        for config in (b'model = "one"\nmodel = "two"\n', b'\xff', b'[agents\n'):
            with self.subTest(config=config):
                with self.assertRaises(sync.SyncError):
                    sync.update_config(config)

    def test_changed_file_between_plan_and_apply_is_preserved(self):
        self.home.mkdir()
        path = self.home / "config.toml"
        path.write_bytes(b'# original config\n')
        changes = sync.plan(ROOT, self.home)
        path.write_bytes(b'model = "concurrent"\n')
        with self.assertRaisesRegex(sync.SyncError, "changed since preview"):
            sync.apply(changes)
        self.assertEqual(path.read_bytes(), b'model = "concurrent"\n')
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_check_neither_creates_home_nor_acquires_a_lock(self):
        with mock.patch.object(sync, "fcntl", None), contextlib.redirect_stdout(io.StringIO()):
            result = sync.main(["--check", "--root", str(ROOT), "--codex-home", str(self.home)])
        self.assertEqual(result, 1)
        self.assertFalse(self.home.exists())

    def test_apply_refuses_unsupported_platform_without_creating_home(self):
        changes = sync.plan(ROOT, self.home)
        with mock.patch.object(sync, "fcntl", None):
            with self.assertRaisesRegex(sync.SyncError, "requires POSIX directory flock"):
                sync.apply(changes)
        self.assertFalse(self.home.exists())

    @unittest.skipIf(sync.fcntl is None or not hasattr(os, "O_DIRECTORY"), "requires directory flock")
    def test_apply_refuses_an_overlapping_sync_without_writing(self):
        self.home.mkdir()
        config = self.home / "config.toml"
        config.write_bytes(b'# original config\n')
        changes = sync.plan(ROOT, self.home)
        other_fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            sync.fcntl.flock(other_fd, sync.fcntl.LOCK_EX | sync.fcntl.LOCK_NB)
            with self.assertRaisesRegex(sync.SyncError, "holds the directory lock"):
                sync.apply(changes)
        finally:
            os.close(other_fd)
        self.assertEqual(config.read_bytes(), b'# original config\n')
        self.assertFalse((self.home / "AGENTS.md").exists())
        self.assertFalse(list(self.home.glob("*.bak.*")))

    @unittest.skipIf(sync.fcntl is None or not hasattr(os, "O_DIRECTORY"), "requires directory flock")
    def test_lock_remains_held_during_failure_rollback(self):
        self.home.mkdir()
        config, agents = self.home / "config.toml", self.home / "AGENTS.md"
        config.write_bytes(b'# original config\n')
        agents.write_bytes(b"# Personal\n")
        changes = sync.plan(ROOT, self.home)
        real_replace = os.replace
        count = 0
        rollback_was_locked = False

        def fail_then_probe(source, destination):
            nonlocal count, rollback_was_locked
            count += 1
            if count == 2:
                raise OSError("injected failure")
            if count == 3:
                probe_fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    with self.assertRaises(OSError) as error:
                        sync.fcntl.flock(probe_fd, sync.fcntl.LOCK_EX | sync.fcntl.LOCK_NB)
                    self.assertIn(error.exception.errno, (errno.EAGAIN, errno.EACCES))
                    rollback_was_locked = True
                finally:
                    os.close(probe_fd)
            return real_replace(source, destination)

        with mock.patch.object(sync.os, "replace", side_effect=fail_then_probe):
            with self.assertRaises(OSError):
                sync.apply(changes)
        self.assertTrue(rollback_was_locked)
        self.assertEqual(config.read_bytes(), b'# original config\n')
        self.assertEqual(agents.read_bytes(), b"# Personal\n")
        probe_fd = os.open(self.home, os.O_RDONLY | os.O_DIRECTORY)
        try:
            sync.fcntl.flock(probe_fd, sync.fcntl.LOCK_EX | sync.fcntl.LOCK_NB)
        finally:
            os.close(probe_fd)

    def test_failure_after_first_replacement_restores_original(self):
        self.home.mkdir()
        config, agents = self.home / "config.toml", self.home / "AGENTS.md"
        config.write_bytes(b'# original config\n')
        agents.write_bytes(b"# Personal\n")
        changes = sync.plan(ROOT, self.home)
        real_replace = os.replace
        count = 0

        def fail_second(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("injected failure")
            return real_replace(source, destination)

        with mock.patch.object(sync.os, "replace", side_effect=fail_second):
            with self.assertRaises(OSError):
                sync.apply(changes)
        self.assertEqual(config.read_bytes(), b'# original config\n')
        self.assertEqual(agents.read_bytes(), b"# Personal\n")
        self.assertTrue(list(self.home.glob("config.toml.bak.*")))

    def test_rollback_does_not_overwrite_a_concurrent_edit(self):
        self.home.mkdir()
        config, agents = self.home / "config.toml", self.home / "AGENTS.md"
        config.write_bytes(b'# original config\n')
        agents.write_bytes(b"# Personal\n")
        changes = sync.plan(ROOT, self.home)
        real_replace = os.replace
        count = 0

        def race_then_fail(source, destination):
            nonlocal count
            count += 1
            if count == 2:
                config.write_bytes(b'model = "concurrent"\n')
                raise OSError("injected failure")
            return real_replace(source, destination)

        with mock.patch.object(sync.os, "replace", side_effect=race_then_fail):
            with self.assertRaisesRegex(sync.SyncError, "rollback refused"):
                sync.apply(changes)
        self.assertEqual(config.read_bytes(), b'model = "concurrent"\n')
        self.assertEqual(agents.read_bytes(), b"# Personal\n")


if __name__ == "__main__":
    unittest.main()
