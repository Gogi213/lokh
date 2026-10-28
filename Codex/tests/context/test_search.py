"""Search regressions."""
from tools.Codex.tests.Support.context import (
    ContextFixture,
    REPO_ROOT,
    TOOLS_DIR,
    importlib,
    json,
    load_module,
    mock,
    pathlib,
    subprocess,
    sys,
    tempfile,
    unittest,
)

class SearchTests(ContextFixture, unittest.TestCase):
    def test_search_bounds_empty_directory_traversal(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root, max_entries=3)
            for index in range(8):
                (source / f"empty{index}").mkdir()
            payload = self.index.search_context(root, "demo", "needle")
            self.assertEqual(payload["scanned_entries"], 3)
            self.assertEqual(payload["scanned_files"], 0)
            self.assertFalse(payload["search_complete"])
            self.assertEqual(payload["stop_reason"], "max_entries")

    def test_search_limits_actual_read_after_size_check(self):
        import io
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root, max_file_bytes=8)
            file = source / "growing.cpp"
            file.write_text("needle", encoding="utf-8")
            reads = []
            class GrowingFile(io.BytesIO):
                def read(self, size=-1):
                    reads.append(size)
                    return super().read(size)
            original_open = pathlib.Path.open
            def open_file(path, *args, **kwargs):
                if path == file:
                    return GrowingFile(b"needle" + b"x" * 100)
                return original_open(path, *args, **kwargs)
            with mock.patch.object(pathlib.Path, "open", open_file):
                payload = self.index.search_context(root, "demo", "needle")
            self.assertEqual(reads, [9])
            self.assertEqual(payload["matches"], [])
            self.assertFalse(payload["search_complete"])
            self.assertEqual(payload["skipped_files"][0]["reason"], "oversized")

    def test_search_reports_directory_errors_as_incomplete(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            self._search_fixture(root)
            with mock.patch.object(self.index.os, "scandir", side_effect=PermissionError("fixture denied")):
                payload = self.index.search_context(root, "demo", "needle")
            self.assertEqual(payload["scan_error_count"], 1)
            self.assertFalse(payload["search_complete"])

    def test_search_invalid_utf8_is_an_explicit_skip(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            source = self._search_fixture(root)
            (source / "broken.cpp").write_bytes(b"needle\xff")
            payload = self.index.search_context(root, "demo", "needle")
            self.assertEqual(payload["matches"], [])
            self.assertFalse(payload["search_complete"])
            self.assertEqual(payload["skipped_files"][0]["reason"], "invalid_utf8")

    def test_ci_search_reads_active_trading_core_capital_and_vetron_policy_owners(self):
        for relative in (
            "apps/trading-core/AGENTS.md",
            "apps/trading-core/capital/AGENTS.md",
            "apps/vetron/AGENTS.md",
        ):
            with self.subTest(policy=relative):
                # Search for current producer text, then require that exact
                # owner file: another policy quoting it is not its coverage.
                query = (REPO_ROOT / relative).read_text(encoding="utf-8").splitlines()[0]
                payload = self.index.search_context(REPO_ROOT, "ci", query)
                self.assertIn(relative, {row["path"] for row in payload["matches"]})

    def test_context_search_is_bounded_and_stays_inside_declared_roots(self):
        payload = self.index.search_context(
            REPO_ROOT,
            "transport",
            "Ws",
            max_results=20,
        )
        self.assertEqual(payload["evidence"], "static-only")
        self.assertEqual(payload["scope"], "transport")
        self.assertLessEqual(len(payload["matches"]), 20)
        for match in payload["matches"]:
            self.assertFalse(pathlib.Path(match["path"]).is_absolute())
            self.assertIn("line", match)
            self.assertIn("text", match)
        self.assertLessEqual(
            len(self.index.render_payload(payload, "json").encode("utf-8")),
            8192,
        )

    def test_context_search_rejects_invalid_scope_and_result_limit(self):
        with self.assertRaises(self.index.ContextIndexError):
            self.index.search_context(REPO_ROOT, "unknown", "x")
        with self.assertRaises(self.index.ContextIndexError):
            self.index.search_context(REPO_ROOT, "transport", "x", max_results=21)

    def test_context_search_clips_long_lines_before_rendering(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            tools_dir = root / "tools" / "Codex"
            source_dir = root / "src"
            tools_dir.mkdir(parents=True)
            source_dir.mkdir()
            (tools_dir / "CxetContextManifest.json").write_text(
                json.dumps(
                    {
                        "limits": {
                            "map_bytes": 6144,
                            "detail_bytes": 8192,
                            "max_results": 20,
                            "max_files": 2000,
                            "max_entries": 20000,
                            "max_file_bytes": 1048576,
                        },
                        "common": {"route_docs": [], "rules": ["static"]},
                        "scopes": {
                            "transport": {
                                "owner": "transport",
                                "keywords": ["transport"],
                                "roots": ["src"],
                                "route_docs": [],
                                "anchors": [],
                                "static_checks": [
                                    "python3 tools/Codex/CxetToolbelt.py hotpath --surface transport"
                                ],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "long.cpp").write_text("needle " + "x" * 20000, encoding="utf-8")
            payload = self.index.search_context(root, "transport", "needle", max_results=1)
            rendered = self.index.render_payload(payload, "json")
            self.assertLessEqual(len(rendered.encode("utf-8")), 8192)
            self.assertLess(len(payload["matches"][0]["text"]), 1000)

    def test_context_search_reports_file_limit_without_false_complete_result(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            tools_dir = root / "tools" / "Codex"
            source_dir = root / "src"
            tools_dir.mkdir(parents=True)
            source_dir.mkdir()
            (tools_dir / "CxetContextManifest.json").write_text(
                json.dumps(
                    {
                        "limits": {
                            "map_bytes": 6144,
                            "detail_bytes": 8192,
                            "max_results": 20,
                            "max_files": 1,
                            "max_entries": 20000,
                            "max_file_bytes": 1048576,
                        },
                        "common": {"route_docs": [], "rules": ["static"]},
                        "scopes": {
                            "transport": {
                                "owner": "transport",
                                "keywords": ["transport"],
                                "roots": ["src"],
                                "route_docs": [],
                                "anchors": [],
                                "static_checks": ["python3 tools/Codex/CxetContextIndex.py validate"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "a.cpp").write_text("ordinary text\n", encoding="utf-8")
            (source_dir / "b.cpp").write_text("needle only in the second file\n", encoding="utf-8")

            payload = self.index.search_context(root, "transport", "needle")

            self.assertEqual(payload["matches"], [])
            self.assertTrue(payload["truncated"])
            self.assertFalse(payload["search_complete"])
            self.assertEqual(payload["scanned_files"], 1)
            self.assertEqual(payload["stop_reason"], "max_files")

    def test_context_search_reports_skipped_files_after_complete_scan(self):
        with tempfile.TemporaryDirectory() as raw:
            root = pathlib.Path(raw)
            tools_dir = root / "tools" / "Codex"
            source_dir = root / "src"
            tools_dir.mkdir(parents=True)
            source_dir.mkdir()
            (tools_dir / "CxetContextManifest.json").write_text(
                json.dumps(
                    {
                        "limits": {
                            "map_bytes": 6144,
                            "detail_bytes": 8192,
                            "max_results": 20,
                            "max_files": 10,
                            "max_entries": 20000,
                            "max_file_bytes": 4,
                        },
                        "common": {"route_docs": [], "rules": ["static"]},
                        "scopes": {
                            "transport": {
                                "owner": "transport",
                                "keywords": ["transport"],
                                "roots": ["src"],
                                "route_docs": [],
                                "anchors": [],
                                "static_checks": ["python3 tools/Codex/CxetContextIndex.py validate"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (source_dir / "large.cpp").write_text("needle is too large\n", encoding="utf-8")
            (source_dir / "binary.cpp").write_bytes(b"n\x00")

            payload = self.index.search_context(root, "transport", "needle")

            self.assertEqual(payload["matches"], [])
            self.assertFalse(payload["truncated"])
            self.assertFalse(payload["search_complete"])
            self.assertEqual(payload["stop_reason"], "complete")
            self.assertEqual(payload["skipped_file_count"], 2)
            self.assertEqual(
                {item["reason"] for item in payload["skipped_files"]},
                {"oversized", "binary"},
            )


if __name__ == '__main__':
    unittest.main()
