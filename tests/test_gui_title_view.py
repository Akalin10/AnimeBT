"""Actual shared resource view and popup checks with a deterministic local API."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import monotonic
import unittest
from unittest.mock import patch


class TitleViewTest(unittest.TestCase):
    def test_shared_view_toggle_popup_layout_and_large_list(self):
        if os.environ.get("ANIMEBT_TITLE_VIEW_TEST") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                "-p", Path(__file__).name,
            ], env={**os.environ, "ANIMEBT_TITLE_VIEW_TEST": "1", "PYTHONUTF8": "1",
                    "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software"},
                capture_output=True, text=True, encoding="utf-8", timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from PySide6.QtCore import QObject, QMetaObject, QPointF, QTimer
        from PySide6.QtQml import QJSValue, QQmlExpression
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        import test_gui_keyword_search as fixtures
        from test_gui_title_format import fragment

        os.environ["ANIMEBT_MODE_QT_TEST"] = "1"
        fixtures.KeywordWindowTest.setUpClass()
        app = fixtures.KeywordWindowTest.app
        requests = []
        name = "Re:從零開始的異世界生活 / Re:ゼロ / Re:Zero &lt;img src=x&gt;"
        group = "喵萌奶茶屋&amp;LoliHouse"
        title = f"[{group}] {name} [02][OVA][BDRip][1080p][HEVC][FLAC][簡繁外掛]"
        values = [fragment(title, kind, text) for kind, text in (
            ("group", group), ("anime", name), ("episode", "02"),
            ("type", "OVA"), ("source", "BDRip"), ("resolution", "1080p"),
            ("video", "HEVC"), ("audio", "FLAC"), ("language", "簡繁外掛"),
        )]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                rows = json.loads(payload["messages"][-1]["content"])
                requests.append(rows)
                data = {"items": [{"id": row["id"], "fields": values} for row in rows]}
                body = json.dumps({"choices": [{"message": {"content": json.dumps(data)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def items(root):
            yield root
            if isinstance(root, QQuickItem):
                for child in root.childItems():
                    yield from items(child)

        def wait(condition, seconds=4):
            end = monotonic() + seconds
            while not condition() and monotonic() < end:
                QTest.qWait(20)
            self.assertTrue(condition())

        with TemporaryDirectory() as directory, ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            folder = Path(directory)
            engine, window, catalog, backend, assistant, network = fixtures.KeywordWindowTest().make_window(folder)
            warnings = []
            engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
            try:
                assistant.save(True, f"http://127.0.0.1:{server.server_port}/v1", "fixture", "", False)
                row = {"key": "a" * 40, "title": title, "category": "独立资源", "episode": "02",
                       "resolution": "1080p", "fansub": "LoliHouse", "works": [], "size": "1 GB",
                       "date": "", "sources": "Anime Garden", "magnet": "magnet:?xt=urn:btih:" + "a" * 40}

                def texts():
                    return [item for item in items(window.contentItem()) if item.objectName() == "resourceTitle"]

                for mode in ("list", "poster"):
                    window.changeSearchMode(QJSValue(mode))
                    with patch.object(backend._pool, "start"):
                        if mode == "list":
                            backend.searchKeyword("Re")
                        else:
                            backend.openSubject({"id": 1, "title": "Re", "original": "Re", "cover": ""}, [])
                    backend._receive_progress(backend._generation, ([row], {}, False))
                    wait(lambda: bool(texts()) and "<span" in texts()[0].property("text"))
                    rendered = texts()[0].property("text")
                    self.assertIn(">[02]</span>", rendered)
                    self.assertNotIn("background", rendered)
                    self.assertNotIn("border", rendered)
                    self.assertNotIn("&amp;amp;", rendered)
                    self.assertNotIn("<img", rendered)
                    from PySide6.QtGui import QTextDocument
                    from PySide6.QtCore import Qt
                    document = QTextDocument()
                    document.setHtml(rendered)
                    self.assertIn("喵萌奶茶屋&LoliHouse", document.toPlainText())
                    self.assertIn("<img src=x>", document.toPlainText())
                    block = document.begin()
                    while block.isValid():
                        iterator = block.begin()
                        while not iterator.atEnd():
                            self.assertEqual(iterator.fragment().charFormat().background().style(), Qt.BrushStyle.NoBrush)
                            iterator += 1
                        block = block.next()
                    self.assertEqual(backend._resource_list.rows[0]["title"], title)
                    for _ in range(3):
                        assistant.setEnabled(False)
                        QTest.qWait(10)
                        off = texts()[0].property("text")
                        self.assertNotIn("<span", off)
                        document.setHtml(off)
                        self.assertEqual(document.toPlainText(), assistant.originalTitle(title))
                        sanitized, undefined = QQmlExpression(engine.rootContext(), texts()[0], "textFormat === 1").evaluate()
                        self.assertTrue(sanitized)
                        before = len(requests)
                        assistant.request(title, [])
                        self.assertEqual(len(requests), before)
                        assistant.setEnabled(True)
                        wait(lambda: "<span" in texts()[0].property("text"))
                    self.assertEqual(len(requests), 1)  # Same cache across modes and toggles.
                    page = window.findChild(QObject, "resourcePage")
                    season_combo = window.findChild(QQuickItem, "季度Filter")
                    self.assertTrue(season_combo.property("visible"))
                    category_combo = window.findChild(QQuickItem, "分类Filter")
                    episode_combo = window.findChild(QQuickItem, "集数Filter")
                    self.assertLess(category_combo.mapToScene(QPointF()).x(), season_combo.mapToScene(QPointF()).x())
                    self.assertLess(season_combo.mapToScene(QPointF()).x(), episode_combo.mapToScene(QPointF()).x())
                    page.setProperty("seasonFilter", "未知")
                    self.assertEqual(backend.resourceModel.rowCount(), 1)
                    page.setProperty("seasonFilter", "S02")
                    self.assertEqual(backend.resourceModel.rowCount(), 0)
                    page.setProperty("seasonFilter", "")
                    self.assertEqual(backend.resourceModel.rowCount(), 1)
                    if app.platformName() == "windows":
                        window.requestActivate()
                        QTest.qWait(150)
                    backend.actions.copyTitle(row)
                    self.assertEqual(app.clipboard().text(), title)
                    QTest.qWait(80)
                    backend.actions.copyMagnet(row)
                    self.assertEqual(app.clipboard().text(), row["magnet"])

                popup = window.findChild(QObject, "titleSettingsDialog")
                dark_switch = window.findChild(QObject, "darkModeSwitch")
                window.setMinimumWidth(400)
                window.setMinimumHeight(360)
                for dark in (False, True):
                    dark_switch.setProperty("checked", dark)
                    QMetaObject.invokeMethod(dark_switch, "toggled")
                    QTest.qWait(180)
                    if os.environ.get("ANIMEBT_AI_SCREENSHOTS"):
                        window.grabWindow().save(str(Path(os.environ["ANIMEBT_AI_SCREENSHOTS"]) / f"ai-title-{'dark' if dark else 'light'}.png"))
                    for size in ((1100, 740), (680, 520), (440, 380)):
                        window.resize(*size)
                        QMetaObject.invokeMethod(popup, "open")
                        QTest.qWait(80)
                        self.assertLessEqual(popup.property("height"), size[1] - 32)
                        buttons = window.findChild(QQuickItem, "aiSettingsButtons")
                        scroll = window.findChild(QQuickItem, "aiSettingsScroll")
                        self.assertGreater(scroll.height(), 0)
                        self.assertLessEqual(buttons.y() + buttons.height(), popup.property("height") - 40 + 1)
                        self.assertGreaterEqual(buttons.y(), scroll.y() + scroll.height())
                        self.assertTrue(window.findChild(QObject, "saveAiSettings").property("enabled"))
                        QMetaObject.invokeMethod(popup, "close")
                        QTest.qWait(30)

                window.resize(1100, 740)
                assistant.setEnabled(False)
                many = [dict(row, key=f"{index:040x}") for index in range(1000)]
                backend._receive_progress(backend._generation, (many, {}, False))
                wait(lambda: backend.resourceModel.rowCount() == 1000)
                assistant.setEnabled(True)
                wait(lambda: bool(texts()) and "<span" in texts()[0].property("text"))
                beats = []
                timer = QTimer()
                timer.setInterval(10)
                timer.timeout.connect(lambda: beats.append(monotonic()))
                timer.start()
                listing = window.findChild(QObject, "resourceList")
                for index in range(0, 500, 25):
                    listing.setProperty("contentY", index * 100)
                    QTest.qWait(12)
                timer.stop()
                self.assertGreater(len(beats), 10)
                max_gap = max(second - first for first, second in zip(beats, beats[1:]))
                self.assertLess(max_gap, 0.5)
                print(f"AI view: 1000 rows, {len(beats)} event-loop beats, max gap {max_gap * 1000:.1f}ms; API batches {len(requests)}")
                self.assertEqual(backend._resource_list.rows[0]["magnet"], row["magnet"])
                self.assertFalse(warnings, warnings)
            finally:
                assistant.shutdown()
                backend.shutdown()
                window.close()
                engine.deleteLater()
                QTest.qWait(10)
                server.shutdown()
                thread.join()

