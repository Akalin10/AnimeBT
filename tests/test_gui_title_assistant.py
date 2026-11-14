from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
from time import sleep
import unittest
from unittest.mock import patch

from animebt.gui.title_spans import (
    BACKGROUNDS, INKS, parse_display_title, rich_title, validate_suggestions,
)

try:
    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
    from animebt.gui.title_assistant import TitleAssistant, endpoint_for
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error


NAMES = ("碧蓝之海", "ぐらんぶる", "Grand Blue", "Re：从零开始的异世界生活",
         "Re:Zero kara Hajimeru Isekai Seikatsu", "新世纪福音战士", "Neon Genesis Evangelion")


class TitleSpanTest(unittest.TestCase):
    def test_real_release_title_formats(self):
        samples = [
            ("[Nix-Raws] GRAND BLUE 碧藍之海 3 / ぐらんぶる Season 3 / Grand Blue S03E12 "
             "[CR WEB-DL 1080p AVC AAC][简繁内封]",
             {"group": "Nix-Raws", "anime": "碧藍之海", "season": "S03",
              "episode": "E12", "resolution": "1080p", "codec": "AVC", "language": "简繁内封"}),
            ("【動漫國字幕組】[Re:從零開始的異世界生活][OVA][02][冰凍的情誼]"
             "[BDRip][HEVC_FLAC][1080P_Ma10P][簡繁外掛]",
             {"group": "動漫國字幕組", "extra": "OVA", "episode": "02", "codec": "HEVC"}),
            ("[晚街與燈][Re：從零開始的異世界生活 第四季喪失篇合集 / "
             "Re:Zero kara Hajimeru Isekai Seikatsu 4th - 01~11][总第67~77][1080P_AVC_AAC]",
             {"season": "第四季", "arc": "喪失篇", "collection": "合集", "episode": "01~11"}),
            ("Shinseiki Evangelion Neon Genesis Evangelion TV [1-26] [BDRip 1440x1080 x264 10-bit FLAC]",
             {"anime": "Neon Genesis Evangelion", "episode": "1-26", "resolution": "1440x1080"}),
            ("悠哉日常大王 Nonstop 13 「のんのんびより のんすとっぷ OAD」",
             {"anime": "悠哉日常大王 Nonstop", "extra": "OAD"}),
        ]
        for title, expected in samples:
            with self.subTest(title=title):
                spans, _ = parse_display_title(title, (*NAMES, "悠哉日常大王 Nonstop"))
                actual = {(span.kind, title[span.start:span.end]) for span in spans}
                self.assertLessEqual(expected.items(), actual)
                self.assertTrue(all(first.end <= second.start for first, second in zip(spans, spans[1:])))

    def test_anime_brackets_are_not_mistaken_for_group(self):
        title = "【碧蓝之海】 [01] [1080p]"
        spans, ambiguous = parse_display_title(title, NAMES)
        self.assertFalse(ambiguous)
        self.assertFalse(any(span.kind == "group" for span in spans))
        self.assertIn("【", rich_title(title, spans, False))

    def test_ai_positions_and_semantics_are_checked(self):
        title = "🐟 | 碧蓝之海 07 [1080p HEVC] <b>&"
        spans, ambiguous = parse_display_title(title, NAMES)
        self.assertTrue(ambiguous)
        start = title.index("07")
        candidate = {"kind": "episode", "start": start, "end": start + 2, "text": "07"}
        wrong = [
            dict(candidate, start=start - 1),
            dict(candidate, text="08"),
            dict(candidate, kind="codec"),
            dict(candidate, kind="work_ids"),
        ]
        accepted = validate_suggestions(title, spans, [*wrong, candidate])
        self.assertEqual([(span.kind, title[span.start:span.end]) for span in accepted], [("episode", "07")])
        self.assertIn("&lt;b&gt;&amp;", rich_title(title, (*spans, *accepted), False))

    def test_all_title_colors_meet_wcag_aa_on_normal_and_hover_rows(self):
        def luminance(color):
            rgb = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
            return sum(weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear))

        for palette, backgrounds in zip(INKS, BACKGROUNDS):
            for background in backgrounds:
                for field, ink in palette.items():
                    low, high = sorted((luminance(background), luminance(ink)))
                    self.assertGreaterEqual((high + 0.05) / (low + 0.05), 4.5, (field, background))


@unittest.skipUnless(sys.platform == "win32", "DPAPI requires Windows")
class TitleAssistantTest(unittest.TestCase):
    def wait_for(self, condition, seconds=5):
        deadline = monotonic() + seconds
        while not condition() and monotonic() < deadline:
            loop = QEventLoop()
            QTimer.singleShot(25, loop.quit)
            loop.exec()
        self.assertTrue(condition())

    def test_batch_connection_fallback_and_encrypted_persistent_cache(self):
        # A real Qt event loop must not process deferred events left by the
        # fake QObjects in the other tests.
        if os.environ.get("ANIMEBT_AI_QT_TEST") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                "-p", Path(__file__).name, "-k", "test_batch_connection",
            ], env={**os.environ, "ANIMEBT_AI_QT_TEST": "1", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        self.app = QCoreApplication.instance() or QCoreApplication([])
        requests = []
        counts = Counter()
        secret = "unit-test-credential-123"

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization"), {}))
                body = b'{"data":[{"id":"model"}]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                counts[payload["model"]] += 1
                requests.append((self.path, self.headers.get("Authorization"), payload))
                if payload["model"] == "offline":
                    self.send_error(503)
                    return
                if payload["model"].startswith("http-"):
                    self.send_error(int(payload["model"].split("-")[1]))
                    return
                if payload["model"] == "slow":
                    sleep(0.25)
                titles = json.loads(payload["messages"][-1]["content"])
                data = {"items": []}
                for row in titles:
                    title = row["title"]
                    name = "Example Anime" if "Example" in title else "碧蓝之海"
                    fields = []
                    for kind, snippet in (("anime", name), ("episode", "01" if "Example" in title else "07"),
                                          ("resolution", "1080p" if "1080p" in title else "720p")):
                        start = title.index(snippet)
                        fields.append({"kind": kind, "start": start, "end": start + len(snippet), "text": snippet})
                    data["items"].append({"id": row["id"], "fields": fields})
                if payload["model"] == "invalid-fields":
                    data = {"items": [{"id": 0, "fields": [{"kind": "anime", "start": 0, "end": 5, "text": "Invented"}]}]}
                body = json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()
                if payload["model"] == "bad-json":
                    body = b'{"choices":[{"message":{"content":"not JSON"}}]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                try:
                    self.wfile.write(body)
                except (ConnectionError, OSError):
                    pass  # Expected when timeout/cancellation closes the socket.

        with TemporaryDirectory() as tmp, ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            settings, cache = Path(tmp) / "ai.json", Path(tmp) / "cache.db"
            assistant = TitleAssistant(settings, cache)
            base = f"http://127.0.0.1:{server.server_port}/v1"
            title = "碧蓝之海 07 [1080p HEVC]"
            second = "碧蓝之海 07 [720p AVC]"
            spans = [span.as_dict() for span in parse_display_title(title, NAMES)[0]]
            second_spans = [span.as_dict() for span in parse_display_title(second, NAMES)[0]]
            try:
                self.assertTrue(assistant.save(True, base, "model", secret, False))
                self.assertNotIn(secret, settings.read_text(encoding="utf-8"))
                self.assertEqual(assistant._key(base="https://different.example/v1"), "")
                self.assertEqual(endpoint_for("http://example.com/v1"), "")
                assistant.testConnection(base, "model", "", False)
                self.wait_for(lambda: not assistant.testing)
                self.assertIn("连接成功", assistant.status)
                assistant.request(title, spans)
                assistant.request(title, spans)
                assistant.request(second, second_spans)
                self.wait_for(lambda: ">[07]</span>" in assistant.render(title, spans, True, assistant.revision))
                self.assertEqual(counts["model"], 2)  # connection test plus one batch
                self.assertEqual(requests[1][0:2], ("/v1/chat/completions", "Bearer " + secret))
                self.assertEqual(len(json.loads(requests[1][2]["messages"][-1]["content"])), 2)
                revision = assistant.revision
                self.assertNotEqual(assistant.render(title, spans, False, revision),
                                    assistant.render(title, spans, True, revision))
                self.assertEqual(assistant.revision, revision)
                reopened = TitleAssistant(settings, cache)
                try:
                    reopened.request(title, [])
                    self.assertIn(">[07]</span>", reopened.render(title, spans, False, reopened.revision))
                    self.assertEqual(counts["model"], 2)
                    reopened.setEnabled(False)
                    self.assertEqual(reopened.render(title, spans, False, reopened.revision), title)
                    reopened.request(second, [])
                    self.assertFalse(reopened._pending)
                    reopened.setEnabled(True)
                    reopened.request(title, [])
                    self.assertIn(">[07]</span>", reopened.render(title, spans, True, reopened.revision))
                    self.assertEqual(counts["model"], 2)
                    self.assertTrue(reopened.save(True, base, "offline", "", False))
                    reopened.request(title, spans)
                    self.wait_for(lambda: "HTTP 503" in reopened.status)
                    self.assertEqual(title, reopened.render(title, spans, True, reopened.revision))
                    self.assertEqual(counts["offline"], 1)
                    for code, reason in ((401, "Key"), (402, "余额"), (404, "路径"), (429, "限流"), (500, "服务端")):
                        reopened.testConnection(base, f"http-{code}", "", False)
                        self.wait_for(lambda: not reopened.testing)
                        self.assertTrue(reopened.statusError)
                        self.assertIn(reason, reopened.status)
                    for model, reason in (("bad-json", "JSON"), ("invalid-fields", "原文校验")):
                        reopened.testConnection(base, model, "", False)
                        self.wait_for(lambda: not reopened.testing)
                        self.assertTrue(reopened.statusError)
                        self.assertIn(reason, reopened.status)
                    with patch("animebt.gui.title_assistant.is_deepseek", return_value=True):
                        reopened.testConnection(base, "does-not-exist", "", False)
                        self.wait_for(lambda: not reopened.testing)
                        self.assertIn("可用模型：model", reopened.status)
                        reopened.testConnection(base, "model", "", False)
                        self.wait_for(lambda: not reopened.testing)
                        self.assertFalse(reopened.statusError)
                        self.assertIn("连接成功", reopened.status)
                        self.assertTrue(any(request[0] == "/v1/models" for request in requests))
                    with patch("animebt.gui.title_assistant.REQUEST_TIMEOUT_MS", 80):
                        reopened.testConnection(base, "slow", "", False)
                        self.wait_for(lambda: not reopened.testing)
                        self.assertIn("超时", reopened.status)
                    reopened.save(True, base, "slow", "", False)
                    reopened.request(title, [])
                    self.wait_for(lambda: reopened._reply is not None)
                    reopened.setEnabled(False)
                    self.wait_for(lambda: reopened._reply is None)
                    self.assertEqual(reopened.render(title, [], True, reopened.revision), title)
                    self.assertFalse(reopened._inflight)
                    self.assertFalse(reopened._pending)
                    restored = TitleAssistant(settings, Path(tmp) / "other.db")
                    self.assertFalse(restored.enabled)
                    restored.shutdown()
                finally:
                    reopened.shutdown()
            finally:
                assistant.shutdown()
                server.shutdown()
                thread.join()
