#!/usr/bin/env python3
"""Tests for the read-only CXET Codex environment doctor."""

from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock


TOOLS_DIR = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = TOOLS_DIR.parent.parent


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CxetDoctorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doctor = load_module("cxet_doctor", TOOLS_DIR / "CxetDoctor.py")

    def test_malformed_mcp_container_has_controlled_cli_diagnostic(self):
        for value in ('[]', '"invalid"'):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as raw:
                root = pathlib.Path(raw)
                config = root / "project.toml"
                config.write_text(f"mcp_servers = {value}\n", encoding="utf-8")
                errors = io.StringIO()
                with mock.patch.object(self.doctor, "_git_root", return_value=root), \
                        mock.patch.object(self.doctor, "_git_identity", return_value={}), \
                        mock.patch.object(self.doctor, "_client_version", return_value="fixture"), \
                        contextlib.redirect_stderr(errors):
                    status = self.doctor.main([
                        "--session-cwd", str(root), "--codex-home", str(root),
                        "--project-config", str(config), "--global-config", str(root / "absent"),
                    ])
                self.assertEqual(status, 2)
                self.assertIn("mcp_servers", errors.getvalue())
                self.assertNotIn("Traceback", errors.getvalue())

    def test_observed_mcp_response_is_distinct_from_configuration(self):
        response = {"content": [{"type": "text", "text": "static-only"}],
                    "structuredContent": {"evidence": "static-only", "identity": {
                        "served_root": str(REPO_ROOT), "script_root": str(REPO_ROOT),
                        "script": str(TOOLS_DIR / "CxetMcpServer.py"),
                        "process_cwd": str(REPO_ROOT), "identity_status": "ok"}}}
        with mock.patch.object(self.doctor, "_client_version", return_value="fixture"):
            report = self.doctor.build_report(session_cwd=REPO_ROOT, observed_response=response)
        self.assertEqual(report["identity_status"], "ok")
        self.assertEqual(report["mcp"]["observation"], "supplied_active_response")
        self.assertEqual(report["mcp"]["provenance"]["served_root"], "observed_response")
        self.assertEqual(report["mcp"]["process_cwd"], str(REPO_ROOT))

    def test_correct_observed_response_does_not_hide_stale_configuration(self):
        response = {"content": [{"type": "text", "text": "static-only"}],
                    "structuredContent": {"evidence": "static-only", "identity": {
                        "served_root": str(REPO_ROOT), "script_root": str(REPO_ROOT),
                        "script": str(TOOLS_DIR / "CxetMcpServer.py"),
                        "process_cwd": str(REPO_ROOT), "identity_status": "ok"}}}
        with mock.patch.object(self.doctor, "_merged_server_config", return_value=({}, [], {}, {})), \
                mock.patch.object(self.doctor, "_client_version", return_value="fixture"):
            missing = self.doctor.build_report(session_cwd=REPO_ROOT, observed_response=response)
        self.assertEqual(missing["identity_status"], "ok")
        self.assertEqual(missing["configured_identity_status"], "unavailable")
        server = {"command": "python3", "args": ["/tmp/stale/tools/Codex/CxetMcpServer.py",
                                                    "--repo-root", "/tmp/stale"]}
        with mock.patch.object(self.doctor, "_merged_server_config", return_value=(server, [], {}, {})), \
                mock.patch.object(self.doctor, "_client_version", return_value="fixture"):
            stale = self.doctor.build_report(session_cwd=REPO_ROOT, observed_response=response)
        self.assertEqual(stale["identity_status"], "ok")
        self.assertEqual(stale["configured_identity_status"], "warning")
        self.assertTrue(any("configured" in warning for warning in stale["warnings"]))

    def test_error_or_missing_identity_cannot_establish_active_mcp(self):
        for response in ({}, {"isError": True, "structuredContent": {"identity": {}}},
                         {"structuredContent": {"identity": {"served_root": "/tmp"}}}):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    self.doctor.build_report(session_cwd=REPO_ROOT, observed_response=response)

    def test_project_config_binds_mcp_to_the_session_checkout(self):
        config = self.doctor.load_toml(REPO_ROOT / ".codex/config.toml")
        server = config["mcp_servers"]["cxet_local"]
        self.assertIn("--repo-root", server["args"])
        self.assertIn(".", server["args"])
        self.assertNotIn("cwd", server)

    def test_doctor_warns_when_served_checkout_differs_from_session(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            session_root = root / "session"
            served_root = root / "served"
            script_root = root / "script"
            session_root.mkdir()
            served_root.mkdir()
            script_root.mkdir()
            # The fixture is a standalone checkout even when TMPDIR is inside
            # the task workspace's actual Git root.
            with mock.patch.object(self.doctor, "_git_root", return_value=session_root):
                report = self.doctor.build_report(
                    session_cwd=session_root,
                    served_root=served_root,
                    server_script=script_root / "tools/Codex/CxetMcpServer.py",
                    active_model=None,
                    client_version="codex-cli test",
                    hook_file=None,
                )

            self.assertEqual(report["identity_status"], "warning")
            self.assertIn(str(session_root), report["warnings"][0])
            self.assertIn(str(served_root), report["warnings"][0])
            self.assertTrue(any(str(script_root) in warning for warning in report["warnings"]))
            self.assertIsNone(report["model"]["active"])

    def test_doctor_same_checkout_is_ok_and_summary_is_bounded(self):
        report = self.doctor.build_report(
            session_cwd=REPO_ROOT,
            served_root=REPO_ROOT,
            server_script=TOOLS_DIR / "CxetMcpServer.py",
            active_model="gpt-6.1-sol",
            client_version="codex-cli test",
            hook_file=None,
        )
        self.assertEqual(report["identity_status"], "ok")
        self.assertEqual(report["model"]["active"], "gpt-6.1-sol")
        rendered = self.doctor.render_report(report, "json")
        self.assertLessEqual(len(rendered.encode("utf-8")), 8192)

    def test_doctor_never_claims_hook_trust_from_a_present_record(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            session = root / "session"
            session.mkdir()
            hook_file = root / "hooks.json"
            hook_file.write_text(
                '{"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"true"}]}]}}',
                encoding="utf-8",
            )
            global_config = root / "global.toml"
            state_key = f"{hook_file}:session_start:0:0"
            global_config.write_text(
                "[hooks.state]\n"
                f"{json.dumps(state_key)} = {{ trusted_hash = \"sha256:{'a' * 64}\" }}\n",
                encoding="utf-8",
            )

            report = self.doctor.build_report(
                session_cwd=session,
                client_version="codex-cli test",
                hook_file=hook_file,
                global_config=global_config,
            )

            self.assertEqual(report["hooks"]["status"], "configured_trust_unconfirmed")
            self.assertTrue(report["hooks"]["trust_hash_present"])
            self.assertNotEqual(report["hooks"]["status"], "configured_and_trusted")
            self.assertTrue(any("/hooks" in warning for warning in report["warnings"]))

    def test_doctor_reports_project_model_before_global_model(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            session = root / "session"
            session.mkdir()
            project_config = root / "project.toml"
            project_config.write_text('model = "project-model"\n', encoding="utf-8")
            global_config = root / "global.toml"
            global_config.write_text('model = "global-model"\n', encoding="utf-8")

            report = self.doctor.build_report(
                session_cwd=session,
                active_model="active-model",
                client_version="codex-cli test",
                project_config=project_config,
                global_config=global_config,
            )

            self.assertEqual(report["model"]["configured"], "project-model")
            self.assertEqual(report["model"]["configured_source"], "project")
            self.assertEqual(report["model"]["active"], "active-model")
            self.assertEqual(report["model"]["client_resolution"], "not_observed")

    def test_doctor_default_served_root_matches_mcp_process_cwd(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            launch = root / "launch"
            launch.mkdir()
            script = root / "other/tools/Codex/CxetMcpServer.py"
            server = {"cwd": str(launch), "args": [str(script)]}
            served, configured_script, cwd, _ = self.doctor._resolve_server_paths(root, server)
            self.assertEqual(served, launch)
            self.assertEqual(cwd, launch)
            self.assertEqual(configured_script, script)

    def test_doctor_relative_repo_root_resolves_from_launch_cwd(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            server = {"cwd": "launch", "args": ["server.py", "--repo-root", "../served"]}
            served, _, _, _ = self.doctor._resolve_server_paths(root, server)
            self.assertEqual(served, root / "served")
            server["args"] += ["--repo-root=../last"]
            served, _, _, _ = self.doctor._resolve_server_paths(root, server)
            self.assertEqual(served, root / "last")

    def test_doctor_configuration_provenance_does_not_claim_observed_identity(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            session = root / "session"
            nested = session / "nested"
            nested.mkdir(parents=True)
            project = root / "project.toml"
            global_config = root / "global.toml"
            project.write_text('[mcp_servers.cxet_local]\nargs = ["/other/tools/Codex/CxetMcpServer.py"]\n', encoding="utf-8")
            global_config.write_text('[mcp_servers.cxet_local]\ncommand = "python3"\n', encoding="utf-8")
            with mock.patch.object(self.doctor, "_git_root", return_value=session), \
                 mock.patch.object(self.doctor, "_git_identity", return_value={"branch": None, "sha": None}):
                report = self.doctor.build_report(
                    session_cwd=nested, project_config=project, global_config=global_config,
                    client_version="fixture", codex_home=root,
                )
            self.assertEqual(report["mcp"]["served_root"], str(nested))
            self.assertEqual(report["identity_status"], "not_observed")
            self.assertEqual(report["mcp"]["field_sources"],
                             {"command": str(global_config), "args": str(project)})
            self.assertEqual(report["mcp"]["provenance"]["process_cwd"], "assumed_session_cwd")
            self.assertEqual(report["mcp"]["client_resolution"], "not_observed")


if __name__ == "__main__":
    unittest.main()
