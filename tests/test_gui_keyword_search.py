"""Keyword mode replays real adapter formats without contacting Bangumi."""

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

import httpx

try:
    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine, QJSValue
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.gui.bangumi import BangumiSearch
from animebt.gui.bt_resources import BTResources, SearchJob
from animebt.gui.keyword_search import collect_keyword_resources, keyword_queries
from animebt.gui.resource_list import ResourceFilterModel, ResourceListModel
from animebt.gui.title_assistant import TitleAssistant
from animebt.gui.typography import apply_system_typography
from animebt.models import Resource
from animebt.sources import SOURCE_TYPES
from animebt.sources.adapters import AnimeGarden, Source
from animebt.sources.foreign_anime import EXTRA_SOURCE_TYPES
from test_gui_bangumi import ControlledNetwork


SOURCES = [*SOURCE_TYPES, *EXTRA_SOURCE_TYPES]
SAMPLE = "AKIRA [BDRip][1080p][简繁]"


def feed(rows, field="category", category=""):
    return "<rss><channel>" + "".join(
        f"<item><title>{escape(title)}</title><{field}>{category}</{field}>"
        f"<guid>{key}</guid><infoHash>{key}</infoHash>"
        f'<enclosure url="https://media.test/{key}.torrent" length="100"/>'
        "</item>" for key, title in rows
    ) + "</channel></rss>"


class KeywordPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_all_eleven_real_adapters_page_filter_and_deduplicate_without_bangumi(self):
        requests = []
        indexed = [("a" * 40, SAMPLE), ("b" * 40, SAMPLE),
                   ("c" * 40, "Other anime [1080p][简繁]"), ("d" * 40, "AKIRA OVA [720p][简繁]")]

        def respond(request):
            requests.append(request)
            self.assertNotIn(request.url.host, {"api.bgm.tv", "bgm.tv", "lain.bgm.tv"})
            host = request.url.host
            if host == "api.animes.garden":
                page = int(request.url.params["page"])
                rows = indexed[:1] if page == 1 else indexed[1:]
                return httpx.Response(200, json={
                    "status": "OK", "pagination": {"page": page, "complete": page == 2},
                    "resources": [{"title": title, "infoHash": key, "size": 100} for key, title in rows],
                })
            if host == "bangumi.moe":
                page = json.loads(request.content)["p"]
                rows = indexed[:1] if page == 1 else indexed[1:]
                return httpx.Response(200, json={
                    "success": True, "page_count": 2,
                    "torrents": [{"title": title, "infoHash": key, "_id": key[:24], "size": 100}
                                 for key, title in rows],
                })
            if host == "nyaa.si":
                return httpx.Response(200, text=feed(indexed, "categoryId", request.url.params["c"]))
            if host == "www.tokyotosho.info":
                category = "Raws" if request.url.params["filter"] == "7" else "Non-English"
                return httpx.Response(200, text=feed(indexed, "category", category))
            return httpx.Response(200, text=feed(indexed, "category", "动画"))

        with TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                service = SearchService(Settings(sources=[source.name for source in SOURCES], limit=1),
                                        Path(directory), client, SOURCES)
                for source in service.sources:
                    if hasattr(source, "request_spacing"):
                        source.request_spacing = 0
                updates = []
                rows = await collect_keyword_resources(service, "AKIRA", lambda *args: updates.append(args))
                call_count = len(requests)
                cached = await collect_keyword_resources(service, "AKIRA", lambda *_: None)
                self.assertEqual(len(requests), call_count)
        self.assertEqual(len({request.url.host for request in requests}), 11)
        self.assertEqual({row["info_hash"] for row in rows}, {"a" * 40, "b" * 40, "d" * 40})
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["key"] for row in rows}, {row["key"] for row in cached})
        for row, cached_row in zip(rows, cached):
            self.assertEqual(set(row["sources"].split(" / ")), set(cached_row["sources"].split(" / ")))
        self.assertEqual(set(rows[0]["sources"].split(" / ")), {source.name for source in SOURCES})
        self.assertEqual(rows[0]["title"], SAMPLE)
        self.assertTrue(all(not row["work_ids"] for row in rows))
        self.assertEqual(updates[-1][1]["MioBT"]["status"], "部分结果")
        garden_pages = [request.url.params["page"] for request in requests if request.url.host == "api.animes.garden"]
        self.assertEqual(garden_pages, ["1", "2"])

    async def test_incremental_results_and_cancellation_stop_pending_pages(self):
        gate, visible, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class PagedSource(Source):
            name = "test"
            base_url = "https://test.invalid"

            async def search_pages(self, keyword):
                try:
                    yield [Resource(SAMPLE, info_hash="a" * 40, source=self.name)]
                    await gate.wait()
                    yield [Resource("AKIRA OVA", info_hash="b" * 40, source=self.name)]
                finally:
                    stopped.set()

        with TemporaryDirectory() as directory:
            service = SearchService(Settings(sources=["test"]), Path(directory), source_types=[PagedSource])
            try:
                updates = []
                def update(rows, *_):
                    updates.append(rows)
                    if rows:
                        visible.set()
                task = asyncio.create_task(collect_keyword_resources(service, "AKIRA", update))
                await asyncio.wait_for(visible.wait(), 1)
                self.assertFalse(task.done())
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(stopped.is_set())
                count = len(updates)
                gate.set()
                await asyncio.sleep(0.12)
                self.assertEqual(len(updates), count)
            finally:
                await service.close()

    async def test_network_timeout_limited_and_empty_are_distinct(self):
        def respond(request):
            host = request.url.host
            if host == "failed.test":
                raise httpx.ConnectError("offline", request=request)
            if host == "timeout.test":
                raise httpx.ReadTimeout("offline", request=request)
            if host == "limited.test":
                return httpx.Response(200, text="<rss><channel><item><title>Other</title></item></channel></rss>")
            if host == "rate.test":
                return httpx.Response(429, headers={"Retry-After": "1"})
            return httpx.Response(200, text="<rss><channel></channel></rss>")

        from animebt.sources.adapters import RssSource
        classes = [type(name, (RssSource,), {"name": name, "base_url": f"https://{name}.test",
                                           "path": "/", "parameter": "q",
                                           "rss_window": 1 if name == "limited" else 50})
                   for name in ("failed", "timeout", "limited", "empty", "rate")]
        with TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                service = SearchService(Settings(sources=[cls.name for cls in classes]),
                                        Path(directory), client, classes)
                updates = []
                with self.assertLogs("animebt", level="ERROR"):
                    await collect_keyword_resources(service, "AKIRA", lambda *args: updates.append(args))
        states = updates[-1][1]
        self.assertEqual({name: state["status"] for name, state in states.items()}, {
            "failed": "来源失败", "timeout": "超时", "limited": "检索范围有限",
            "empty": "来源返回零条", "rate": "来源失败",
        })
        self.assertIn("429", states["rate"]["error"])

    async def test_deep_search_reuses_pagination_and_bypasses_normal_cache(self):
        pages = []
        def respond(request):
            page = int(request.url.params["page"])
            pages.append(page)
            return httpx.Response(200, json={
                "status": "OK", "pagination": {"page": page, "complete": page == 9},
                "resources": [{"title": f"AKIRA [0{page}]", "infoHash": f"{page:040x}"}],
            })
        with TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
                service = SearchService(Settings(sources=["Anime Garden"]), Path(directory), client, [AnimeGarden])
                normal = await collect_keyword_resources(service, "AKIRA", lambda *_: None)
                deep = await collect_keyword_resources(service, "AKIRA", lambda *_: None, refresh=True)
        self.assertEqual(len(normal), 6)
        self.assertEqual(len(deep), 9)
        self.assertEqual(pages, list(range(1, 7)) + list(range(1, 10)))

    async def test_gui_worker_selects_keyword_path_and_closes_service(self):
        with TemporaryDirectory() as directory:
            service = SearchService(Settings(sources=["Anime Garden"]), Path(directory),
                                    httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
                                        200, json={"status": "OK", "pagination": {"complete": True},
                                                   "resources": [{"title": SAMPLE, "infoHash": "a" * 40}]}))),
                                    [AnimeGarden])
            from unittest.mock import Mock
            progress = Mock()
            job = SearchJob(Path(directory), {}, [], False, {}, {}, 1, progress, Mock(), {}, keyword="AKIRA")
            try:
                with patch("animebt.gui.bt_resources.SearchService", return_value=service), patch(
                    "animebt.gui.bt_resources.collect_resources", side_effect=AssertionError("Bangumi path entered")
                ):
                    await job.search()
                self.assertEqual(progress.emit.call_args.args[0], 1)
                self.assertEqual(progress.emit.call_args.args[1][0][0]["title"], SAMPLE)
            finally:
                await service.client.aclose()

    async def test_keyword_rows_keep_torrent_resolution_and_save_operations(self):
        from animebt.gui.resource_actions import fetch_action
        from animebt.sources.adapters import Mikan
        from test_gui_resource_actions import DIGEST, TORRENT
        with TemporaryDirectory() as directory:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(
                200, text=feed([(DIGEST, SAMPLE)])
            ))) as client:
                service = SearchService(Settings(sources=["Mikan"]), Path(directory), client, [Mikan])
                rows = await collect_keyword_resources(service, "AKIRA", lambda *_: None)
            # Also exercise a source that supplies only a Torrent URL.
            torrent_only = dict(rows[0], magnet="", info_hash="")
            factory = httpx.AsyncClient
            transport = httpx.MockTransport(lambda request: httpx.Response(200, content=TORRENT))
            with patch("animebt.gui.resource_actions.httpx.AsyncClient",
                       side_effect=lambda **kwargs: factory(transport=transport, **kwargs)):
                self.assertEqual(await fetch_action(rows[0]), "magnet:?xt=urn:btih:" + DIGEST)
                self.assertEqual(await fetch_action(torrent_only), "magnet:?xt=urn:btih:" + DIGEST)
                saved = await fetch_action(torrent_only, str(Path(directory) / "saved.torrent"))
                self.assertEqual(Path(saved).read_bytes(), TORRENT)

    def test_written_language_variants_never_invent_an_alias(self):
        queries = keyword_queries("尸体派对 / Corpse Party")
        self.assertIn("屍體派對", queries)
        self.assertIn("Corpse Party", queries)
        self.assertNotIn("Tortured Souls", queries)
        self.assertEqual(keyword_queries("進撃の巨人"), ["進撃の巨人"])
        self.assertIn("阿基拉", keyword_queries("阿基拉 / AKIRA"))


class KeywordModelTest(unittest.TestCase):
    def test_incremental_sort_and_filter_preserve_distinct_hashes(self):
        model = ResourceListModel(None)
        proxy = ResourceFilterModel(model, model)
        rows = [{"key": str(i), "title": SAMPLE, "sort_size": size, "sort_time": time,
                 "resolution": resolution} for i, size, time, resolution in
                ((1, 200, 30, "1080p"), (2, 100, 10, "720p"), (3, None, None, "1080p"))]
        model.update_rows(rows)
        proxy.setSortOrder("size_desc")
        self.assertEqual([proxy.index(i, 0).data(model.resource_role)["key"] for i in range(3)], ["1", "2", "3"])
        proxy.setSortOrder("time_asc")
        self.assertEqual([proxy.index(i, 0).data(model.resource_role)["key"] for i in range(3)], ["2", "1", "3"])
        proxy.setFilters("", "", "1080p", "")
        self.assertEqual(proxy.rowCount(), 2)
        model.update_rows([dict(rows[1], resolution="1080p"), rows[0], rows[2]])
        self.assertEqual(proxy.rowCount(), 3)


class KeywordWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("ANIMEBT_MODE_QT_TEST") != "1":
            return
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        QQuickStyle.setStyle("Basic")

    def make_window(self, folder):
        engine = QQmlApplicationEngine()
        network = ControlledNetwork()
        catalog = BangumiSearch(engine, manager=network)
        resources = BTResources(folder, engine)
        assistant = TitleAssistant(folder / "assistant.json", folder / "spans.db", engine)
        engine.setInitialProperties({
            "catalog": catalog, "resourceSearch": resources, "titleAssistant": assistant,
            "typography": apply_system_typography(self.app),
            "appearanceLocation": QUrl.fromLocalFile(str(folder / "appearance.ini")),
            "startupMotionAllowed": False,
        })
        engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parents[1] /
                                              "animebt/gui/qml/Main.qml")))
        self.assertTrue(engine.rootObjects())
        return engine, engine.rootObjects()[0], catalog, resources, assistant, network

    def test_mode_switch_cancels_old_jobs_keeps_keyword_and_persists(self):
        # Other tests use fake network replies with deferred QObject deletion.
        # Keep the actual QML event loop in its own process, as in the AI GUI test.
        if os.environ.get("ANIMEBT_MODE_QT_TEST") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                "-p", Path(__file__).name, "-k", "test_mode_switch",
            ], env={**os.environ, "ANIMEBT_MODE_QT_TEST": "1", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            engine, window, catalog, resources, assistant, network = self.make_window(folder)
            try:
                self.assertFalse(window.property("listMode"))
                catalog.search("AKIRA")
                old_reply = network.replies[-1]
                field = window.findChild(QObject, "searchField")
                field.setProperty("text", "AKIRA")
                window.changeSearchMode(QJSValue("list"))
                self.assertTrue(old_reply.aborted)
                self.assertEqual(catalog.status, "idle")
                self.assertTrue(resources.listMode)
                self.assertEqual(field.property("text"), "AKIRA")
                self.assertIn("searchMode=list", (folder / "appearance.ini").read_text())
                with patch.object(resources._pool, "start") as start:
                    window.submitSearch()
                    job = start.call_args.args[0]
                    self.assertEqual(job.keyword, "AKIRA")
                    self.assertEqual(len(resources.sources), 11)
                    generation = resources._generation
                    resources._receive_progress(generation, ([{
                        "key": "a" * 40, "title": SAMPLE, "category": "搜索资源", "episode": "1",
                        "resolution": "1080p", "fansub": "test", "works": [],
                        "size": "1 GB", "date": "", "sources": "Anime Garden",
                        "magnet": "magnet:?xt=urn:btih:" + "a" * 40, "info_hash": "a" * 40,
                    }], {}, False))
                    QTest.qWait(50)
                    page = window.findChild(QObject, "resourcePage")
                    self.assertIsNotNone(page)
                    self.assertEqual(str(page.property("coverSource").toString()), "")
                    self.assertEqual(page.findChild(QObject, "resourceList").property("count"), 1)
                    self.assertEqual(len(network.replies), 1)
                    resources.actions.copyMagnet(resources._resource_list.rows[0])
                    self.assertEqual(self.app.clipboard().text(), "magnet:?xt=urn:btih:" + "a" * 40)
                    resources.actions.copyTitle(resources._resource_list.rows[0])
                    self.assertEqual(self.app.clipboard().text(), SAMPLE)
                    window.changeSearchMode(QJSValue("poster"))
                    self.assertTrue(job.cancelled.is_set())
                    self.assertEqual(resources.facets["total"], 0)
                    resources._receive_progress(generation, ([{"key": "stale"}], {}, True))
                    resources._receive_finished(generation, "old failure")
                    self.assertEqual(resources.facets["total"], 0)
                    self.assertEqual(resources.error, "")
                    self.assertEqual(field.property("text"), "AKIRA")
                    window.submitSearch()
                    self.assertEqual(network.keywords, ["AKIRA", "AKIRA"])
                    window.changeSearchMode(QJSValue("list"))
            finally:
                assistant.shutdown()
                resources.shutdown()
                window.close()
                engine.deleteLater()
                self.app.processEvents()
            engine2, window2, catalog2, resources2, assistant2, network2 = self.make_window(folder)
            try:
                self.assertTrue(window2.property("listMode"))
                self.assertTrue(resources2.listMode)
                self.assertTrue(window2.findChild(QObject, "listModeOption").property("checked"))
                self.assertFalse(window2.findChild(QObject, "posterModeOption").property("checked"))
                self.assertEqual(network2.replies, [])
                self.assertEqual(resources2.facets["total"], 0)
            finally:
                assistant2.shutdown()
                resources2.shutdown()
                window2.close()
                engine2.deleteLater()
                self.app.processEvents()
