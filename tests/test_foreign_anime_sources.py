import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from xml.sax.saxutils import escape

import httpx

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.gui.source_settings import load_extra_sources
from animebt.sources import SOURCE_TYPES
from animebt.sources.foreign_anime import MioBT, Nyaa, TokyoToshokan


def rss(rows, category_field):
    items = "".join(
        f"<item><title>{escape(title)}</title><{category_field}>{category}</{category_field}>"
        f"<link>https://nyaa.si/download/{i}.torrent</link>"
        f"<infoHash>{hash_value}</infoHash></item>"
        for i, (title, category, hash_value) in enumerate(rows)
    )
    return f"<rss><channel>{items}</channel></rss>"


class ForeignAnimeSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_miobt_searches_one_recent_snapshot_and_returns_secure_torrent(self):
        calls = []
        rows = [
            ("Anime [简繁内封]", "动画", "a" * 40),
            ("Anime RAW", "Raw", "b" * 40),
            ("Anime English subs", "Raw", "c" * 40),
            ("Anime", "动画", "d" * 40),
            ("Anime [简繁]", "漫画", "e" * 40),
        ]
        xml = "<rss><channel>" + "".join(
            f"<item><title>{title}</title><category>{category}</category>"
            f'<enclosure url="http://v2.uploadbt.com/?r=down&amp;hash={hash_value}"'
            f' type="application/x-bittorrent"/></item>'
            for title, category, hash_value in rows
        ) + "</channel></rss>"

        def respond(request):
            calls.append(str(request.url))
            return httpx.Response(200, text=xml)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            source = MioBT(client)
            results = await source.search("Anime")
            self.assertEqual(await source.search("absent"), [])
        self.assertEqual(calls, ["https://miobt.com/rss.xml"])
        self.assertEqual([row.info_hash for row in results], ["a" * 40, "b" * 40])
        self.assertTrue(all(row.torrent_url.startswith("https://v2.uploadbt.com/") for row in results))

    async def test_only_chinese_and_raw_then_deduplicate_by_hash(self):
        raw, zh, foreign = ("a" * 40, "b" * 40, "c" * 40)
        calls = set()

        def respond(request):
            if request.url.host == "nyaa.si":
                category = request.url.params["c"]
                self.assertEqual(request.url.params["page"], "rss")
                self.assertEqual(request.url.params["q"], "Anime")
                calls.add(("Nyaa", category))
                rows = ([("Anime [BDRip]", "1_4", raw)] if category == "1_4" else [
                    ("Anime [CHT]", "1_3", zh),
                    ("Anime VOSTFR", "1_3", foreign),
                    ("Anime Chinese Story VOSTFR", "1_3", foreign),
                    ("Anime [CHT] comic", "3_1", foreign),
                ])
                return httpx.Response(200, text=rss(rows, "categoryId"))
            category = request.url.params["filter"]
            self.assertEqual(request.url.params["terms"], "Anime")
            calls.add(("Tokyo Toshokan", category))
            rows = ([("Anime [BDRip]", "Raws", raw)] if category == "7" else [
                ("Anime [简繁字幕]", "Non-English", zh),
                ("Anime [MultiSubs]", "Non-English", foreign),
            ])
            return httpx.Response(200, text=rss(rows, "category"))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=["Nyaa", "Tokyo Toshokan"]), Path(directory),
                                        client, [Nyaa, TokyoToshokan])
                result = await service.search("Anime")
                cached = await service.search("Anime")
        self.assertEqual(len(calls), 4)
        self.assertEqual({row.info_hash for row in result.resources}, {raw, zh})
        self.assertTrue(all(set(row.sources) == {"Nyaa", "Tokyo Toshokan"} for row in result.resources))
        self.assertCountEqual(cached.cached, ["Nyaa", "Tokyo Toshokan"])

    async def test_one_feed_failure_preserves_the_other_feed(self):
        def respond(request):
            if request.url.params["c"] == "1_3":
                return httpx.Response(403)
            return httpx.Response(200, text=rss([("Anime RAW", "1_4", "a" * 40)], "categoryId"))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=["Nyaa"]), Path(directory), client, [Nyaa])
                with self.assertLogs("animebt", level="ERROR"):
                    result = await service.search("Anime")
        self.assertEqual(len(result.resources), 1)
        self.assertEqual(result.statuses["Nyaa"], "部分结果")
        self.assertIn("403", result.errors["Nyaa"])

    async def test_cancelling_search_cancels_both_category_requests(self):
        started = asyncio.Event()
        cancelled = []
        requests = []

        async def respond(request):
            requests.append(request)
            if len(requests) == 2:
                started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.append(request.url.params["c"])

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            task = asyncio.create_task(Nyaa(client).search("Anime"))
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertCountEqual(cancelled, ["1_3", "1_4"])

    async def test_retry_after_survives_creating_a_new_source_for_the_next_search(self):
        class LimitedNyaa(Nyaa):
            request_spacing = 0.001

        calls = []

        def respond(request):
            calls.append(request.url)
            return httpx.Response(429, headers={"Retry-After": "60"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            for _ in range(2):
                with self.assertRaises(httpx.HTTPStatusError):
                    await LimitedNyaa(client).search("Anime")
        self.assertEqual(len(calls), 1)

    def test_gui_configuration_uses_all_default_sources(self):
        self.assertEqual(Settings().sources, [source.name for source in SOURCE_TYPES])
        self.assertEqual(len(Settings().sources), 8)
        with TemporaryDirectory() as directory:
            config = Path(directory) / "bt-sources.json"
            config.write_text('{"Nyaa":{"enabled":false},"Tokyo Toshokan":{"timeout":7}}', encoding="utf-8")
            self.assertEqual(load_extra_sources(config), {"Tokyo Toshokan": 7, "MioBT": 9.0})

    def test_tokyo_empty_feed_sentinel_is_not_a_generic_html_fallback(self):
        source = TokyoToshokan(None)
        self.assertEqual(source.parse(b"</channel>\n</rss>\n"), [])
        with self.assertRaises(ValueError):
            source.parse(b"<html><title>Just a moment...</title></html>")
