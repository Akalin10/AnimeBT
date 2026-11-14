import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from animebt.gui.resource_seasons import (
    known_seasons, local_seasons, season_identity, season_labels, validate_ai_seasons,
)


class SeasonRulesTest(unittest.TestCase):
    def test_explicit_markers_ranges_and_non_season_numbers(self):
        samples = {
            "[Nix-Raws] GRAND BLUE 碧藍之海 S03E12 [1080p]": (3,),
            "Re:Zero Season 2 [01-12]": (2,), "作品 第二季 [2024][1080p]": (2,),
            "作品 第一至三季 全集": (1, 2, 3), "作品 S01-S03 Complete": (1, 2, 3),
            "作品 第一、三季": (1, 3), "作品 Seasons 1–3 Complete": (1, 2, 3), "作品 全三季": (1, 2, 3),
            "作品 [S01+S03]": (1, 3), "作品 Season 1 & Season 2": (1, 2),
            "作品 OVA 02": (), "作品 Part 2": (), "作品 2024 [1080p][01-12]": (),
            "作品 Final Season 完结篇 后篇": (), "[S02-Raws] 作品 [01]": (),
        }
        for title, expected in samples.items():
            with self.subTest(title=title):
                self.assertEqual(local_seasons(title), expected)

    def test_metadata_and_bundles_do_not_invent_missing_seasons(self):
        self.assertEqual(known_seasons({"title": "作品 最终章", "verifiedSeasons": [4]}), (4,))
        self.assertEqual(known_seasons({"title": "作品 S02", "verifiedSeasons": [3]}), ())
        self.assertEqual(known_seasons({"title": "作品 S01-S03", "verifiedSeasons": [2]}), (1, 2, 3))
        self.assertEqual(season_labels(()), ["未知"])
        self.assertEqual(season_identity("[组A] Example Anime Arc Season II [01][1080p]", "组A"),
                         season_identity("[组B] Example Anime Arc Season II [02][720p]", "组B"))
        self.assertNotEqual(season_identity("Example Anime 雪之篇 [01]"), season_identity("Example Anime 冰之篇 [01]"))

    def test_model_evidence_is_required_not_just_a_confidence_number(self):
        title = "Example Anime Season II [01]"
        start = title.index("Season II")
        result = {"work": "Example Anime", "arc": "", "seasons": [2],
                  "evidence": [{"text": "Season II", "start": start, "end": start + 9}]}
        self.assertEqual(validate_ai_seasons(title, result), (2,))
        for wrong in (dict(result, seasons=[3]), dict(result, seasons=[True]), dict(result, seasons=[99]),
                      dict(result, work="Other Anime"), dict(result, evidence=[])):
            self.assertEqual(validate_ai_seasons(title, wrong), ())
        arc = "Example Anime 游郭篇"
        unsupported = {"work": "Example Anime", "arc": "游郭篇", "seasons": [2],
                       "evidence": [{"text": "游郭篇", "start": 14, "end": 17}]}
        self.assertEqual(validate_ai_seasons(arc, unsupported), ())

    def test_filter_composes_with_all_other_filters_and_sorting(self):
        from animebt.gui.resource_list import ResourceFilterModel, ResourceListModel
        source = ResourceListModel(None)
        proxy = ResourceFilterModel(source, source)
        base = {"title": "作品", "category": "合集资源", "episode": "01-12", "resolution": "1080p", "fansub": "字幕组"}
        source.update_rows([dict(base, key="bundle", seasons=["S01", "S02"], sort_size=300),
                            dict(base, key="single", category="独立资源", seasons=["S02"], sort_size=100),
                            dict(base, key="unknown", seasons=["未知"], sort_size=200)])
        proxy.setSeasonFilter("S01")
        self.assertEqual(proxy.rowCount(), 1)
        proxy.setSeasonFilter("S02")
        self.assertEqual(proxy.rowCount(), 2)
        proxy.setFilters("合集资源", "01-12", "1080p", "字幕组")
        self.assertEqual(proxy.rowCount(), 1)
        proxy.setSeasonFilter("未知")
        self.assertEqual(proxy.index(0, 0).data(source.resource_role)["key"], "unknown")
        proxy.setSeasonFilter("")
        proxy.setSortOrder("size_asc")
        self.assertEqual(proxy.index(0, 0).data(source.resource_role)["key"], "unknown")

    def test_confirmed_bangumi_metadata_stays_out_of_keyword_attribution(self):
        from test_gui_series_resources import matcher, TV, SEQUEL
        from animebt.gui.resource_rows import resource_rows
        from animebt.models import Resource
        title = "系列动画 第二季 [01][1080p]"
        verified = resource_rows([Resource(title, info_hash="a" * 40)], matcher(SEQUEL))
        self.assertEqual(verified[0]["verifiedSeasons"], [2])
        keyword = resource_rows([Resource(title, info_hash="a" * 40)])
        self.assertEqual(keyword[0]["verifiedSeasons"], [])
        self.assertEqual(keyword[0]["work_ids"], [])
        self.assertEqual(matcher(TV).seasons[TV["id"]], set())
        self.assertEqual(known_seasons({"title": "系列动画 [01][1080p]", "verifiedSeasons": []}), ())


class SeasonAsyncTest(unittest.TestCase):
    def test_async_cache_failure_and_cancellation_without_bangumi(self):
        if os.environ.get("ANIMEBT_SEASON_QT_TEST") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                "-p", Path(__file__).name, "-k", "test_async_cache",
            ], env={**os.environ, "ANIMEBT_SEASON_QT_TEST": "1", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread
        from time import monotonic
        from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
        from animebt.gui.title_assistant import TitleAssistant
        from animebt.gui.season_assistant import SeasonAssistant
        app = QCoreApplication.instance() or QCoreApplication([])
        requests = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                requests.append(payload)
                if payload["model"] == "offline":
                    self.send_error(503)
                    return
                titles = json.loads(payload["messages"][-1]["content"])
                items = []
                for row in titles:
                    title = row["title"]
                    evidence = "Season II" if "Season II" in title else "游郭篇"
                    start = title.index(evidence)
                    items.append({"id": row["id"], "work": "Example Anime", "arc": "", "seasons": [2],
                                  "evidence": [{"start": start, "end": start + len(evidence), "text": evidence}]})
                body = json.dumps({"choices": [{"message": {"content": json.dumps({"items": items})}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def wait(condition):
            deadline = monotonic() + 4
            while not condition() and monotonic() < deadline:
                loop = QEventLoop()
                QTimer.singleShot(20, loop.quit)
                loop.exec()
            self.assertTrue(condition())

        with TemporaryDirectory() as tmp, ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            folder = Path(tmp)
            assistant = TitleAssistant(folder / "config.json", folder / "cache.db")
            seasons = SeasonAssistant(assistant)
            base = f"http://127.0.0.1:{server.server_port}/v1"
            row = {"title": "Example Anime Season II [01][1080p]"}
            try:
                assistant.save(True, base, "model", "", False)
                self.assertEqual(seasons.resolve(row), ())
                wait(lambda: bool(seasons.resolve(row)))
                self.assertEqual(seasons.resolve(row), (2,))
                self.assertEqual(seasons.resolve({"title": "Example Anime Season II [02][720p]"}), (2,))
                self.assertEqual(len(requests), 1)
                reopened = SeasonAssistant(assistant)
                self.assertEqual(reopened.resolve(row), (2,))
                self.assertEqual(len(requests), 1)
                reopened.cancel()
                uncertain = {"title": "Example Anime 游郭篇 [01]"}
                seasons.resolve(uncertain)
                wait(lambda: seasons._key(uncertain) in seasons._resolved)
                self.assertEqual(seasons.resolve(uncertain), ())
                count = len(requests)
                seasons.resolve({"title": "Example Anime 游郭篇 [02]"})
                self.assertEqual(len(requests), count)
                from animebt.gui.bt_resources import BTResources
                backend = BTResources(folder / "bt")
                try:
                    backend.attachTitleAssistant(assistant)
                    backend.setListMode(True)
                    incremental = {"key": "resource", "title": "Example Anime Extra Season II [01]",
                                   "category": "独立资源", "episode": "01", "resolution": "1080p", "fansub": "组"}
                    backend._update_rows([incremental])
                    backend.resourceModel.setSeasonFilter("未知")
                    self.assertEqual(backend.resourceModel.rowCount(), 1)
                    wait(lambda: backend._resource_list.rows[0]["seasons"] == ["S02"])
                    self.assertEqual(backend.resourceModel.rowCount(), 0)
                    backend.resourceModel.setSeasonFilter("S02")
                    self.assertEqual(backend.resourceModel.rowCount(), 1)
                    self.assertEqual(backend.facets["total"], 1)
                    self.assertEqual(backend._resource_list.rows[0]["title"], incremental["title"])
                finally:
                    backend.shutdown()
                assistant.save(True, base, "offline", "", False)
                with self.assertLogs("animebt.gui.seasons", level="WARNING"):
                    seasons.resolve(row)
                    wait(lambda: seasons._retry_after > 0)
                self.assertEqual(seasons.resolve(row), ())
                self.assertEqual(seasons.resolve({"title": "Example Anime S03"}), (3,))
                self.assertEqual(seasons.resolve({"title": "Example Anime S02", "verifiedSeasons": [3]}), ())
                assistant.setEnabled(False)
                self.assertEqual(seasons.resolve(row), ())
                self.assertFalse(seasons._pending)
                assistant.save(True, base, "new-model", "", False)
                seasons.resolve(row)
                seasons._timer.stop()
                seasons._start()
                self.assertIsNotNone(seasons._reply)
                seasons.cancel()
                self.assertIsNone(seasons._reply)
                self.assertFalse(seasons._inflight)
            finally:
                seasons.cancel()
                assistant.shutdown()
                server.shutdown()
                thread.join()
