"""Mcp regressions."""
from tools.Codex.tests.Support.toolbelt import (
    REPO_ROOT,
    TOOLS_DIR,
    ToolbeltFixture,
    importlib,
    json,
    load_module,
    mock,
    os,
    pathlib,
    re,
    shutil,
    subprocess,
    sys,
    tempfile,
    unittest,
)

class McpTests(ToolbeltFixture, unittest.TestCase):
    def test_static_handshake_does_not_change_with_tool_result_identity(self):
        mcp = load_module("cxet_mcp_static_handshake_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        baseline = [mcp.protocol.encode(mcp.handle_message(request)) for request in requests]
        payload = {"evidence": "static-only", "route_status": "selected", "scope": "ci"}
        # Checkout identity belongs to dynamic results, never to the reusable
        # instructions or descriptors. Clock access here would add unstable context.
        with mock.patch.object(mcp.time, "time", side_effect=AssertionError("clock in static response")), \
             mock.patch.object(mcp.time, "monotonic", side_effect=AssertionError("clock in static response")), \
             mock.patch.object(mcp.cxet_context, "build_context_map", return_value=payload):
            for checkout in ("/checkout/one", "/checkout/two"):
                identity = {"identity_status": "warning", "served_root": checkout,
                            "process_cwd": checkout, "script_root": checkout, "script": checkout + "/server.py"}
                with mock.patch.object(mcp, "checkout_identity", return_value=identity):
                    result = mcp.call_tool("cxet_context_map", {"scope": "ci", "task_hint": "workflow"})
                    self.assertEqual(result["structuredContent"]["identity"]["served_root"], checkout)
                    self.assertEqual(
                        [mcp.protocol.encode(mcp.handle_message(request)) for request in requests], baseline)

    def test_mcp_protocol_acceptance_checks_real_envelopes(self):
        mcp = load_module("cxet_mcp_acceptance_test", TOOLS_DIR / "CxetMcpServer.py")
        identity = {"identity_status": "ok", "served_root": str(REPO_ROOT),
                    "process_cwd": str(REPO_ROOT), "script_root": str(REPO_ROOT),
                    "script": str(TOOLS_DIR / "CxetMcpServer.py")}
        replies = [
            {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": mcp.PROTOCOL_VERSION}},
            {"jsonrpc": "2.0", "id": 2, "result": {"tools": mcp.tool_descriptors()}},
            {"jsonrpc": "2.0", "id": 3, "result": {"isError": False,
                "structuredContent": {"evidence": "static-only", "identity": identity},
                "content": [{"type": "text", "text": "static-only"}]}},
        ]
        wire = b"".join(json.dumps(reply).encode() + b"\n" for reply in replies)
        result = mcp.validate_protocol_trace(wire, REPO_ROOT)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["observation"], "subprocess_candidate")
        for broken in (b"debug output\n" + wire, wire.replace(b'"id": 2', b'"id": 9'),
                       wire.replace(b'"isError": false', b'"isError": true')):
            with self.subTest(wire=broken[:35]):
                self.assertEqual(mcp.validate_protocol_trace(broken, REPO_ROOT)["status"], "fail")

    def test_mcp_protocol_check_exercises_the_real_candidate_server(self):
        mcp = load_module("cxet_mcp_real_acceptance_test", TOOLS_DIR / "CxetMcpServer.py")
        result = mcp.protocol_check(REPO_ROOT)
        self.assertEqual(result["status"], "pass", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["observation"], "subprocess_candidate")

    def test_mcp_protocol_check_timeout_reaps_only_owned_child(self):
        mcp = load_module("cxet_mcp_timeout_test", TOOLS_DIR / "CxetMcpServer.py")
        child = mock.Mock()
        child.poll.return_value = None
        child.wait.return_value = 0
        with mock.patch.object(mcp.subprocess, "Popen", return_value=child), \
             mock.patch.object(mcp, "_exchange_protocol", side_effect=TimeoutError("fixture timeout")):
            result = mcp.protocol_check(REPO_ROOT)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["exit_code"], 2)
        child.kill.assert_called_once()
        child.wait.assert_called()

    def test_mcp_invalid_frames_and_params_recover_before_ping(self):
        frames = [
            b"{broken\n", b"null\n", b"[]\n", b"\xff\n",
            b"x" * (1024 * 1024 + 20) + b"\n",
            b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":[]}\n',
            b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":false}}\n',
            b'{"jsonrpc":"2.0","method":"ping"}\n',
            b'{"jsonrpc":"2.0","method":"tools/list"}\n',
            b'{"jsonrpc":"2.0","id":3,"method":"ping"}\n',
        ]
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "CxetMcpServer.py")], cwd=REPO_ROOT,
            input=b"".join(frames), capture_output=True, timeout=10,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        replies = [json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(replies), 8)
        self.assertEqual([reply["error"]["code"] for reply in replies[:5]],
                         [-32700, -32600, -32600, -32700, -32700])
        self.assertEqual([reply["error"]["code"] for reply in replies[5:7]], [-32602, -32602])
        self.assertEqual(replies[-1], {"jsonrpc": "2.0", "id": 3, "result": {}})

    def test_mcp_final_result_budget_includes_unicode_identity_and_structure(self):
        mcp = load_module("cxet_mcp_bound_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        payload = {"evidence": "static-only", "route_status": "selected", "scope": "ci",
                   "roots": ["директория😀" * 100 for _ in range(80)]}
        identity = {"identity_status": "warning", "served_root": "путь😀" * 1500,
                    "process_cwd": "cwd😀" * 1500, "script_root": "script😀" * 1500}
        with mock.patch.object(mcp.cxet_context, "build_context_map", return_value=payload), \
             mock.patch.object(mcp, "checkout_identity", return_value=identity):
            for output_format in ("json", "summary"):
                with self.subTest(output_format=output_format):
                    result = mcp.call_tool("cxet_context_map", {"task_hint": "ci", "format": output_format})
                    encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    self.assertLessEqual(len(encoded), 6144)
                    self.assertTrue(result["output_truncated"])
                    self.assertFalse(result["output_complete"])
                    self.assertEqual(result["identity"]["identity_status"], "warning")
                    self.assertEqual(result["structuredContent"]["evidence"], "static-only")
                    self.assertIn("static-only", result["content"][0]["text"])
                    if output_format == "json":
                        self.assertEqual(json.loads(result["content"][0]["text"])["evidence"], "static-only")

    def test_mcp_honors_manifest_output_limits_for_final_result(self):
        mcp = load_module("cxet_mcp_manifest_bound_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        payload = {"evidence": "static-only", "route_status": "selected", "scope": "ci",
                   "roots": ["root😀" * 100] * 20}
        manifest = json.loads((TOOLS_DIR / "CxetContextManifest.json").read_text())
        manifest["limits"]["map_bytes"] = 2048
        with mock.patch.object(mcp.cxet_context, "build_context_map", return_value=payload), \
             mock.patch.object(mcp.cxet_context, "_load_manifest_file", return_value=manifest):
            result = mcp.call_tool("cxet_context_map", {"task_hint": "ci", "format": "json"})
        self.assertEqual(result["output_limit_bytes"], 2048)
        self.assertLessEqual(len(mcp.protocol.encode(result)), 2048)

    def test_mcp_direct_tools_reject_invalid_manifest_limits_before_reading_sources(self):
        mcp = load_module("cxet_mcp_invalid_limits_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        original = json.loads((TOOLS_DIR / "CxetContextManifest.json").read_text())
        for tool in ("cxet_readiness_static_trace", "cxet_hotpath_static_surface"):
            for field, maximum in (("map_bytes", 6144), ("detail_bytes", 8192)):
                for value in (maximum + 1, True, 10.5, "4096", None, 0, -1):
                    with self.subTest(tool=tool, field=field, value=value):
                        manifest = {**original, "limits": {**original["limits"], field: value}}
                        with mock.patch.object(mcp.cxet_context, "_load_manifest_file", return_value=manifest), \
                             mock.patch.object(mcp.cxet_toolbelt, "build_readiness_report", return_value={"evidence": "static-only"}) as readiness, \
                             mock.patch.object(mcp.cxet_toolbelt, "build_hotpath_surface", return_value={"evidence": "static-only"}) as hotpath:
                            with self.assertRaisesRegex(mcp.cxet_context.ContextIndexError, "limits." + field):
                                mcp.call_tool(tool, {})
                            readiness.assert_not_called()
                            hotpath.assert_not_called()

    def test_mcp_direct_tools_do_not_validate_unrelated_scope_paths(self):
        mcp = load_module("cxet_mcp_direct_limits_test", TOOLS_DIR / "CxetMcpServer.py")
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            manifest = json.loads((TOOLS_DIR / "CxetContextManifest.json").read_text())
            # This checkout has no scope sources, but the canonical limits are
            # sufficient to answer the direct static tools without root scans.
            directory = root / "tools/Codex"
            directory.mkdir(parents=True)
            (directory / "CxetContextManifest.json").write_text(json.dumps(manifest))
            mcp.set_repo_root(root)
            for tool in ("cxet_readiness_static_trace", "cxet_hotpath_static_surface"):
                with self.subTest(tool=tool):
                    result = mcp.call_tool(tool, {})
                    self.assertFalse(result["isError"])
                    self.assertEqual(result["structuredContent"]["evidence"], "static-only")
                    self.assertLessEqual(len(mcp.protocol.encode(result)), 8192)

    def test_mcp_rejects_oversized_ids_without_unbounded_error(self):
        mcp = load_module("cxet_mcp_id_bound_test", TOOLS_DIR / "CxetMcpServer.py")
        reply = mcp.handle_message({"jsonrpc": "2.0", "id": "😀" * 20000, "method": "ping"})
        self.assertIsNone(reply["id"])
        self.assertEqual(reply["error"]["code"], -32600)
        self.assertLessEqual(len(mcp.protocol.encode(reply)), 1024)

    def test_mcp_detail_budget_and_errors_are_bounded(self):
        mcp = load_module("cxet_mcp_detail_bound_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        with mock.patch.object(mcp.cxet_toolbelt, "collect_sources", return_value={
                "evidence": "static-only", "anchors": ["😀" * 500] * 30}):
            result = mcp.call_tool("cxet_readiness_sources", {"format": "json"})
        self.assertLessEqual(len(mcp.protocol.encode(result)), 8192)
        self.assertTrue(result["output_truncated"])
        with mock.patch.object(mcp.cxet_toolbelt, "collect_sources", side_effect=ValueError("😀" * 20000)):
            reply = mcp.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                       "params": {"name": "cxet_readiness_sources"}})
        self.assertTrue(reply["result"]["isError"])
        self.assertLessEqual(len(mcp.protocol.encode(reply["result"])), 8192)
        self.assertIn("cxet_readiness_sources", reply["result"]["content"][0]["text"])

    def test_mcp_self_test_surfaces_original_tool_failure(self):
        import io
        from contextlib import redirect_stderr
        mcp = load_module("cxet_mcp_failure_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        stderr = io.StringIO()
        with mock.patch.object(mcp.cxet_toolbelt, "collect_sources", side_effect=ValueError("original fixture failure")), \
             redirect_stderr(stderr):
            status = mcp.self_test()
        self.assertEqual(status, 1)
        self.assertIn("cxet_readiness_sources", stderr.getvalue())
        self.assertIn("original fixture failure", stderr.getvalue())

    def test_mcp_wrapper_self_test(self):
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "CxetMcpServer.py"),
                "--self-test",
                "--repo-root",
                str(REPO_ROOT),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        self.assertIn("cxet_mcp_self_test ok", proc.stdout)

    def test_mcp_tool_result_exposes_checkout_identity(self):
        mcp = load_module("cxet_mcp_server_identity_test", TOOLS_DIR / "CxetMcpServer.py")
        mcp.set_repo_root(REPO_ROOT)
        result = mcp.call_tool(
            "cxet_context_map",
            {"task_hint": "WebSocket framing", "format": "summary"},
        )
        self.assertEqual(result["identity"]["served_root"], str(REPO_ROOT.resolve()))
        self.assertEqual(result["identity"]["identity_status"], "ok")
        self.assertEqual(
            result["structuredContent"]["identity"]["served_root"],
            str(REPO_ROOT.resolve()),
        )
        self.assertIn("cxet_local identity: ok", result["content"][0]["text"])

    def test_mcp_tool_result_surfaces_checkout_mismatch_in_content(self):
        mcp = load_module("cxet_mcp_server_identity_warning_test", TOOLS_DIR / "CxetMcpServer.py")
        previous_cwd = pathlib.Path.cwd()
        try:
            mcp.set_repo_root(REPO_ROOT)
            os.chdir(TOOLS_DIR)
            result = mcp.call_tool(
                "cxet_context_map",
                {"task_hint": "WebSocket framing", "format": "summary"},
            )
        finally:
            os.chdir(previous_cwd)
        self.assertEqual(result["identity"]["identity_status"], "warning")
        self.assertEqual(result["structuredContent"]["identity"]["identity_status"], "warning")
        self.assertIn("WARNING: cxet_local", result["content"][0]["text"])

    def test_mcp_stdio_uses_newline_json_rpc_transport(self):
        def message(method, request_id=None, params=None):
            payload = {"jsonrpc": "2.0", "method": method}
            if request_id is not None:
                payload["id"] = request_id
            if params is not None:
                payload["params"] = params
            return json.dumps(payload, separators=(",", ":")) + "\n"

        stdin = "".join(
            (
                message(
                    "initialize",
                    1,
                    {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "current"},
                    },
                ),
                message("notifications/initialized"),
                message("tools/list", 2),
                message(
                    "tools/call",
                    3,
                    {
                        "name": "cxet_readiness_sources",
                        "arguments": {"format": "json"},
                    },
                ),
            )
        )
        proc = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "CxetMcpServer.py")],
            cwd=REPO_ROOT,
            check=True,
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        replies = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual([reply["id"] for reply in replies], [1, 2, 3])
        self.assertEqual(replies[0]["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(replies[0]["result"]["serverInfo"]["version"], "current")
        names = {tool["name"] for tool in replies[1]["result"]["tools"]}
        self.assertIn("cxet_readiness_sources", names)
        self.assertIn("static-only", replies[2]["result"]["content"][0]["text"])
        self.assertNotIn("Content-Length:", proc.stdout)


if __name__ == '__main__':
    unittest.main()
