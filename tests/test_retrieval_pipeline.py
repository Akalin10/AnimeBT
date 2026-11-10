"""Offline replay of public title samples through the real source adapters."""

import asyncio
import json
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, time
import unittest
from xml.sax.saxutils import escape

import httpx

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.sources import SOURCE_TYPES
from animebt.sources.adapters import AnimeGarden, BangumiMoe, Mikan
from animebt.sources.extended import DMHY
from animebt.sources.foreign_anime import EXTRA_SOURCE_TYPES, Nyaa

try:
    from animebt.gui.bangumi import subject_summary
    from animebt.gui.bt_resources import collect_resources
    from animebt.gui.series_resources import SeriesMatcher
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error


SOURCES = [*SOURCE_TYPES, *EXTRA_SOURCE_TYPES]
CASES = [
    (
        {"id": 58957, "title": "尸体派对 Tortured Souls", "original": "コープスパーティー Tortured Souls -暴虐された魂の呪叫-",
         "platform": "OVA", "episodes": 4, "aliases": ["尸体派对TS"]},
        "【動漫國字幕組】[屍體派對 Tortured Souls -受折磨的靈魂-][01-04][BDRip][720P][繁體][MP4]",
        "【白恋字幕组】[OVA]尸体派对-受暴虐亡魂之咒叫 /Corpse Party-Tortured Souls [01-04][BDRip][1080P][简繁外挂][MKV]",
        "【流雲字幕組&BBA字幕組】 ◆屍體派對 迷失的舞步_Corpse Party Missing Footage◇OVA BIG5 PSP 480P MP4",
    ),
    (
        {"id": 369304, "title": "咒术回战 怀玉･玉折 / 涩谷事变", "original": "呪術廻戦 懐玉・玉折／渋谷事変",
         "platform": "TV", "episodes": 23, "aliases": ["咒术回战 第二季", "Jujutsu Kaisen 2nd Season", "呪術廻戦 第2期"]},
        "[GJ.Y] 咒术回战 第二季 / Jujutsu Kaisen 2nd Season - 23 (B-Global 1920x1080 HEVC AAC MKV)",
        "[猎户不鸽压制] 咒术回战 第二季 Jujutsu Kaisen S2 [25-47] [WebRip] [1080p] [简日内嵌]",
        "咒术回战 第三季 / Jujutsu Kaisen S3 - 01 [1080p][简繁]",
    ),
    (
        {"id": 508708, "title": "剧场版 进击的巨人 完结篇 THE LAST ATTACK",
         "original": "劇場版 進撃の巨人 完結編 THE LAST ATTACK", "platform": "剧场版", "episodes": 1},
        "劇場版「進擊的巨人」完結篇 THE LAST ATTACK / Shingeki no Kyojin Movie [1080p]",
        "[组] 剧场版 进击的巨人 完结篇 THE LAST ATTACK [1080p][简繁]",
        "进击的巨人 最终季 Part.2 [87][1080p][简繁]",
    ),
    (
        {"id": 376739, "title": "进击的巨人 最终季 完结篇 前篇",
         "original": "進撃の巨人 The Final Season 完結編 前編", "platform": "TV", "episodes": 1},
        "进击的巨人 最终季 完结篇 前篇 [1080p][简繁]",
        "進撃の巨人 The Final Season 完結編 前編 [WEBRip][1080p][简繁]",
        "[拨雪寻春] 進擊的巨人 The Final Season 完結篇(後篇) / Shingeki no Kyojin [WEBRip][1080p]",
    ),
    (
        {"id": 80993, "title": "进击的巨人 OAD", "original": "進撃の巨人 OAD", "platform": "OVA", "episodes": 3},
        "[组] 進撃の巨人 OAD イルゼの手帳 [1080p]",
        "[组] 进击的巨人 OAD [01-03][1080p]",
        "[组] 进击的巨人 LOST GIRLS [01][1080p]",
    ),
]


def _rss(rows, category_field, category):
    entries = "".join(
        f"<item><title>{escape(title)}</title><{category_field}>{category}</{category_field}>"
        f"<guid>{key}</guid><infoHash>{key}</infoHash></item>"
        for key, title in rows
    )
    return "<rss><channel>" + entries + "</channel></rss>"


async def replay():
    output = []
    for subject, first, second, wrong in CASES:
        calls = Counter()
        received = set()
        indexed = set()
        updates = []
        known = {"a" * 40, "b" * 40}

        class Trace(SearchService):
            async def search(self, keyword, selected=None, refresh=False, **options):
                result = await super().search(keyword, selected, refresh, **options)
                received.update((name, row.info_hash) for name in selected for row in result.candidates)
                return result

        def respond(request):
            host = request.url.host
            if host == "api.bgm.tv":
                if request.url.path == "/v0/episodes":
                    episodes = [{"ep": i, "sort": i + 24} for i in range(1, 24)] if subject["id"] == 369304 else []
                    if subject["id"] == 80993:
                        episodes = [{"ep": 1, "sort": 1, "name": "イルゼの手帳"}]
                    return httpx.Response(200, json={"data": episodes, "total": len(episodes)})
                return httpx.Response(200, json=[])
            calls[host] += 1
            rows = [("a" * 40, first), ("b" * 40, second), ("c" * 40, wrong)]
            if subject["id"] == 508708 and host != "bangumi.moe":
                rows.pop(1)
            if host == "bangumi.moe":
                page = json.loads(request.content)["p"]
                rows = rows[:1] + rows[2:] if page == 1 else rows[1:2]
                indexed.update(("萌番组", key) for key, _ in rows)
                return httpx.Response(200, json={"success": True, "page_count": 2, "torrents": [
                    {"title": title, "_id": key[:24], "infoHash": key} for key, title in rows
                ]})
            if host == "api.animes.garden":
                page = int(request.url.params["page"])
                rows = rows[:-1] if page == 1 else rows[-1:]
                indexed.update(("Anime Garden", key) for key, _ in rows)
                return httpx.Response(200, json={"status": "OK", "pagination": {"page": page, "complete": page == 2},
                                                 "resources": [{"title": title, "magnet": "magnet:?xt=urn:btih:" + key}
                                                               for key, title in rows]})
            source = next(cls for cls in SOURCES if httpx.URL(cls.base_url).host == host)
            if host == "nyaa.si":
                category = request.url.params["c"]
                rows = rows if category == "1_3" else []
                field = "categoryId"
            elif host == "www.tokyotosho.info":
                category = "Non-English" if request.url.params["filter"] == "10" else "Raws"
                rows = rows if category == "Non-English" else []
                field = "category"
            elif host == "miobt.com":
                # MioBT still sees only its snapshot. All other posts remain outside it.
                rows = rows[:1]
                category, field = "动画", "category"
            else:
                category, field = "", "category"
            indexed.update((source.name, key) for key, _ in rows)
            if host == "miobt.com":
                return httpx.Response(200, text="<rss><channel>" + "".join(
                    f'<item><title>{escape(title)} [简繁]</title><category>动画</category>'
                    f'<enclosure url="https://miobt.com/{key}.torrent"/><infoHash>{key}</infoHash></item>'
                    for key, title in rows
                ) + "</channel></rss>")
            if host in {"nyaa.si", "www.tokyotosho.info"}:
                rows = [(key, title + " [简繁]") for key, title in rows]
            return httpx.Response(200, text=_rss(rows, field, category))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = Trace(Settings(sources=[source.name for source in SOURCES]), Path(directory), client, SOURCES)
                # Keep the real request/adapter code but remove pacing from deterministic replay.
                for source in service.sources:
                    if hasattr(source, "request_spacing"):
                        source.request_spacing = 0
                start = monotonic()
                await collect_resources(service, subject, [subject], lambda *args: updates.append(args))
                elapsed = monotonic() - start
        expected = {(source.name, key) for source in SOURCES for key in known if key == "a" * 40
                    or (source.name != "MioBT" and (subject["id"] != 508708 or source.name == "萌番组"))}
        title_truth = {first: "a" * 40, second: "b" * 40}
        final = {row["info_hash"] or title_truth.get(row["title"], "") for row in updates[-1][0]}
        output.append({
            "id": subject["id"], "sources": len(calls), "requests": sum(calls.values()),
            "expected_candidate_pairs": len(expected), "captured_candidate_pairs": len(expected & received),
            "raw_candidate_pairs": len(indexed), "normalized_candidate_pairs": len(received),
            "expected": len(known), "valid": len(final & known), "false": len(final - known),
            "missing": len(known - final), "milliseconds": round(elapsed * 1000, 1),
        })
    return output


class RetrievalPipelineTest(unittest.IsolatedAsyncioTestCase):
    def test_query_plan_keeps_verified_language_variants_independent(self):
        from animebt.gui.search_plan import plan_queries

        work = subject_summary({
            "id": 58957, "name_cn": "尸体派对 Tortured Souls",
            "name": "コープスパーティー Tortured Souls -暴虐された魂の呪叫-", "platform": "OVA",
            "infobox": [
                {"key": "英文名", "value": "Corpse Party Tortured Souls"},
                {"key": "罗马音", "value": "Bougyaku Sareta Tamashii no Jukyou"},
            ],
        })
        matcher = SeriesMatcher(work, {work["id"]: work}, work, [])
        terms = plan_queries(AnimeGarden(None), matcher, [], "ova", initial=work["title"], budget=6)
        self.assertIn("尸体派对", terms)
        self.assertIn("屍體派對", terms)
        self.assertIn("Bougyaku Sareta Tamashii no Jukyou", terms)
        self.assertTrue(any(name.startswith("コープスパーティー") for name in terms))
        self.assertEqual(len(terms), len(set(terms)))

    async def test_same_source_concurrency_and_cancellation_are_bounded(self):
        entered = asyncio.Queue()
        release = asyncio.Event()

        async def respond(request):
            await entered.put(request.url.params["search"])
            await release.wait()
            return httpx.Response(200, json={"status": "OK", "resources": []})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[AnimeGarden.name]), Path(directory), client)
                tasks = [asyncio.create_task(service.search(word, collect=True)) for word in ("one", "two", "three")]
                try:
                    self.assertEqual(await asyncio.wait_for(entered.get(), 1), "one")
                    self.assertEqual(await asyncio.wait_for(entered.get(), 1), "two")
                    self.assertTrue(entered.empty())
                    tasks[0].cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await tasks[0]
                    self.assertEqual(await asyncio.wait_for(entered.get(), 1), "three")
                    self.assertFalse(list(service.directory.iterdir()))
                finally:
                    release.set()
                    await asyncio.gather(*tasks, return_exceptions=True)

    async def test_verified_web_paths_extend_saturated_feeds(self):
        class SmallMikan(Mikan):
            rss_window = 1

        class SmallDMHY(DMHY):
            rss_window = 1

        class SmallNyaa(Nyaa):
            rss_window = 1
            request_spacing = 0

        hosts = {httpx.URL(source.base_url).host: source for source in (SmallMikan, SmallDMHY, SmallNyaa)}
        calls = []

        def respond(request):
            calls.append((request.url.host, request.url.path, dict(request.url.params)))
            host, path = request.url.host, request.url.path
            rss = _rss([("a" * 40, "番剧 [简繁]")], "categoryId", "1_3")
            if path in ("/RSS/Search", "/topics/rss/rss.xml") or request.url.params.get("page") == "rss":
                if request.url.params.get("c") == "1_4":
                    rss = _rss([], "categoryId", "1_4")
                return httpx.Response(200, text=rss)
            link = f'<a href="magnet:?xt=urn:btih:{"b" * 40}">磁链</a>'
            if host == "nyaa.si":
                page = int(request.url.params["p"])
                title = f'<td>动画</td><td><a href="/view/{page}">番剧 [简繁]</a></td><td>{link}</td>'
                next_link = '<a href="/?c=1_3&amp;p=2">2</a>' if page == 1 else ""
                html = f'<table class="torrent-list"><tr>{title}<td>1 GiB</td><td>2025-01-01</td></tr></table>{next_link}'
            elif host == "share.dmhy.org":
                second = path.endswith("/2")
                title = f'<td>2025/01/01</td><td>动画</td><td><a href="/topics/view/{2 if second else 1}_title.html">番剧</a></td>'
                next_link = '<a href="/topics/list/page/2?keyword=test">2</a>' if not second else ""
                html = f'<table id="topic_list"><tr>{title}<td>{link}</td><td>1 GB</td></tr></table>{next_link}'
            else:
                title = '<td></td><td><a href="/Home/Episode/2">番剧</a></td><td>1 GB</td><td>2025/01/01</td>'
                html = f'<table><tr>{title}<td>{link}</td></tr></table>'
            return httpx.Response(200, text=html)

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                names = [source.name for source in hosts.values()]
                service = SearchService(Settings(sources=names), Path(directory), client, list(hosts.values()))
                result = await service.search("番剧", collect=True)
        self.assertEqual({row.source for row in result.candidates if row.info_hash == "b" * 40}, set(names))
        self.assertTrue(any(path == "/topics/list/page/2" for _, path, _ in calls))
        self.assertTrue(any(host == "nyaa.si" and params.get("p") == "2" for host, _, params in calls))

    async def test_expired_empty_cache_does_not_hide_new_candidates(self):
        calls = 0

        def respond(_):
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={"status": "OK", "resources": [] if calls == 1 else [{"title": "异语资源"}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[AnimeGarden.name]), Path(directory), client)
                await service.search("title", collect=True)
                path, = service.directory.glob("*.json")
                cached = json.loads(path.read_text(encoding="utf-8"))
                cached["time"] = time() - 46
                path.write_text(json.dumps(cached), encoding="utf-8")
                result = await service.search("title", collect=True)
        self.assertEqual(calls, 2)
        self.assertEqual([row.title for row in result.candidates], ["异语资源"])

    async def test_public_title_replay_covers_all_sources_without_false_attribution(self):
        results = await replay()
        for row in results:
            with self.subTest(subject=row["id"]):
                self.assertEqual(row["sources"], 11)
                self.assertEqual(row["missing"], 0)
                self.assertEqual(row["false"], 0)
                self.assertGreaterEqual(row["captured_candidate_pairs"], row["expected_candidate_pairs"] - 1)

    async def test_page_budget_marks_partial_cache_and_deep_search_uses_a_different_key(self):
        pages = []

        def respond(request):
            page = int(request.url.params["page"])
            pages.append(page)
            return httpx.Response(200, json={"status": "OK", "pagination": {"page": page, "complete": page == 2},
                                             "resources": [{"title": f"alternate {page}", "id": page}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[AnimeGarden.name]), Path(directory), client)
                initial = await service.search("本地标题", collect=True, page_budget=1)
                cached = await service.search("本地标题", collect=True, page_budget=1)
                complete = await service.search("本地标题", collect=True, page_budget=2)
        self.assertEqual(pages, [1, 1, 2])
        self.assertEqual(initial.incomplete[AnimeGarden.name], "达到分页预算")
        self.assertEqual(cached.incomplete, initial.incomplete)
        self.assertFalse(complete.incomplete)
        self.assertEqual([row.origins for row in complete.candidates], [
            [[AnimeGarden.name, "本地标题", "1"]], [[AnimeGarden.name, "本地标题", "2"]],
        ])

    async def test_moe_keeps_valid_rows_after_a_malformed_record_and_detects_repeated_page(self):
        def respond(_):
            return httpx.Response(200, json={"success": True, "page_count": 4, "torrents": [
                {"_id": "a"}, {"title": "valid title", "_id": "b", "infoHash": "b" * 40},
            ]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[BangumiMoe.name]), Path(directory), client)
                result = await service.search("valid", collect=True)
        self.assertEqual(result.raw_counts[BangumiMoe.name], 4)
        self.assertEqual([row.source_id for row in result.candidates], ["b"])
        self.assertIn("重复", result.incomplete[BangumiMoe.name])


if __name__ == "__main__":
    print(json.dumps(asyncio.run(replay()), ensure_ascii=False, indent=2))
