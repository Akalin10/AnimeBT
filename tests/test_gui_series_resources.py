from pathlib import Path
import asyncio
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx

try:
    from animebt.gui.bt_resources import BTResources, _CatalogSearchService, collect_resources, resource_rows, subject_episodes
    from PySide6.QtCore import QPersistentModelIndex
    from animebt.gui.series_resources import SeriesMatcher, load_series
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.models import Resource
from animebt.sources.adapters import AnimeGarden, Source
from animebt.gui.bangumi import subject_summary


TV = {"id": 1, "title": "系列动画", "original": "", "platform": "TV", "episodes": 12}
SEQUEL = {"id": 2, "title": "系列动画 第二季", "original": "", "platform": "TV", "episodes": 12}
OVA1 = {"id": 3, "title": "系列动画 雪之章", "original": "", "platform": "OVA"}
OVA2 = {"id": 4, "title": "系列动画 冰之章", "original": "", "platform": "OVA"}
SP = {"id": 5, "title": "系列动画 特别篇 星之章", "original": "", "platform": "SP"}
WORKS = {work["id"]: work for work in (TV, SEQUEL, OVA1, OVA2, SP)}
BUNDLE = "[组] 系列动画 [S1+S2] + 系列动画 雪之章 + 系列动画 冰之章 [1080p]"


def matcher(subject):
    return SeriesMatcher(subject, WORKS, TV, [])


class SeriesAttributionTest(unittest.TestCase):
    def test_conan_four_digit_episode_requires_matching_broadcast_metadata(self):
        conan = dict(TV, id=899, title="名侦探柯南", original="名探偵コナン", episodes=0)
        schedule = [{"ep": 1219, "sort": 1219, "airdate": "2026-11-07"}]
        context = SeriesMatcher(conan, {899: conan}, conan, schedule)
        title = "[银色子弹字幕组][名侦探柯南][第1219集 规矩很多的咖啡店][WEBRIP][简日双语MP4][1080P]"
        release = Resource(title, publish_time="2026-11-07T18:26:00.000Z")
        self.assertEqual(context.classify(release).work_ids, {899})
        self.assertEqual(resource_rows([release], context)[0]["episode"], "1219")
        self.assertFalse(context.classify(Resource(title, publish_time="2026-01-01")).work_ids)
        self.assertFalse(context.classify(Resource(title.replace("1219", "1229"),
                                                   publish_time=release.publish_time)).work_ids)

    def test_final_chapters_require_an_explicit_half_or_both_named_halves(self):
        front = dict(TV, id=376739, title="进击的巨人 最终季 完结篇 前篇",
                     original="進撃の巨人 The Final Season 完結編 前編", episodes=1)
        rear = dict(TV, id=415779, title="进击的巨人 最终季 完结篇 后篇",
                    original="進撃の巨人 The Final Season 完結編 後編", episodes=1)
        works = {1: TV, front["id"]: front, rear["id"]: rear}
        context = SeriesMatcher(rear, works, TV, [])
        dual = "[芝士动物朋友] 进击的巨人 最终季 完结篇 前篇 + 后篇 [BDRip][1080p]"
        self.assertEqual(context.classify(Resource(dual)).work_ids, {376739, 415779})
        self.assertEqual(context.classify(Resource(
            "[拨雪寻春] 進擊的巨人 The Final Season 完結篇(後篇) / Shingeki no Kyojin [WEBRip][1080p]"
        )).work_ids, {415779})
        for title in ("进击的巨人 The Final Season 完结篇(前篇) [1080p]",
                      "进击的巨人 最终季 Part.2 [87][1080p]",
                      "进击的巨人 最终季 完结篇 Complete [1080p]",
                      "剧场版 进击的巨人 完结篇 THE LAST ATTACK [1080p]"):
            self.assertEqual(resource_rows([Resource(title)], context), [])

    def test_movie_bilingual_title_and_video_tags_do_not_admit_bonus_only(self):
        movie = dict(TV, id=508708, title="剧场版 进击的巨人 完结篇 THE LAST ATTACK",
                     original="劇場版 進撃の巨人 完結編 THE LAST ATTACK", platform="剧场版", episodes=1)
        context = SeriesMatcher(movie, {1: TV, movie["id"]: movie}, TV, [])
        self.assertEqual(context.classify(Resource(
            "劇場版「進擊的巨人」完結篇 THE LAST ATTACK / Shingeki no Kyojin Movie [1080p]"
        )).work_ids, {508708})
        self.assertEqual(resource_rows([Resource(movie["title"] + "[片尾彩蛋][1080p]")], context), [])

    def test_mini_and_bonus_do_not_match_tv_or_another_mini_season(self):
        first = {"id": 7, "title": "系列动画 休息时间", "original": "Series Break Time",
                 "platform": "WEB", "episodes": 10}
        second = {"id": 8, "title": "系列动画 休息时间 第二季", "original": "Series Break Time 2nd Season",
                  "platform": "WEB", "aliases": ["Series Mini Anime Season 2"], "episodes": 10}
        works = {**WORKS, 7: first, 8: second}
        context = SeriesMatcher(second, works, TV, [])
        good = Resource("[组] Series Mini Anime Season 2 [01] [1080p]")
        self.assertEqual(context.classify(good).work_ids, {8})
        for title in ("系列动画 S2E01 [1080p]", "系列动画 休息时间 [01]", "系列动画 [Bonus]"):
            self.assertEqual(resource_rows([Resource(title)], context), [])
        self.assertEqual(resource_rows([Resource("系列动画 S2E01 [Bonus]")],
                                      SeriesMatcher(SEQUEL, works, TV, [])), [])

    def test_mini_subtitle_with_series_and_bonus_tag_identifies_real_bd_extra(self):
        main = dict(TV, id=55770, title="进击的巨人", original="進撃の巨人")
        mini = dict(OVA1, id=82510, title="进击的巨人 Q版剧场 飞起来！训练兵团",
                    original="ちみキャラ劇場 とんでけ！訓練兵団", episodes=25)
        context = SeriesMatcher(mini, {55770: main, 82510: mini}, main, [])
        title = "[进击的巨人_BD特典Vol_1][Shingeki_no_Kyojin_Special][飞起来_训练兵团][第1天&第2天][MP4][1080p]"
        self.assertEqual(context.classify(Resource(title)).work_ids, {82510})
        for wrong in ("[进击的巨人_BD特典Vol_1][训练兵团][1080p]",
                      "[飞起来_训练兵团][1080p]", "[进击的巨人][飞起来_训练兵团][1080p]"):
            self.assertEqual(resource_rows([Resource(wrong)], context), [])

    def test_unique_extra_suffix_can_follow_a_verified_romanized_series_title(self):
        main = dict(TV, title="系列动画", original="シリーズ", aliases=["Verified Series Name"])
        snow = dict(OVA1, title="系列动画 雪之回忆", original="シリーズ Memory Snow")
        context = SeriesMatcher(snow, {**WORKS, 1: main, 3: snow}, main, [])
        self.assertEqual(context.classify(Resource("Verified Series Name - Memory Snow [1080p]")).work_ids, {3})
        self.assertEqual(context.classify(Resource("[Verified Series Name][OVA][01][Memory Snow][1080p]")).work_ids, {3})
        self.assertEqual(resource_rows([Resource("Verified Series Name OVA Complete")], context), [])

    def test_in_the_dome_is_distinct_from_tv_other_movies_and_ova(self):
        main = {"id": 55770, "title": "进击的巨人", "original": "進撃の巨人",
                "platform": "TV", "episodes": 25, "aliases": ["Attack on Titan"]}
        dome = {"id": 499144, "title": "进击的巨人 IN THE DOME -士兵们的星空-",
                "original": "進撃の巨人 IN THE DOME-兵士たちの星空-", "platform": "剧场版",
                "episodes": 1, "aliases": ["Attack on Titan"]}
        film = {"id": 394303, "title": "进击的巨人 剧场版 完结篇",
                "original": "進撃の巨人 THE LAST ATTACK", "platform": "剧场版", "episodes": 1}
        ova = {"id": 80993, "title": "进击的巨人 OAD", "original": "進撃の巨人 OAD",
               "platform": "OVA", "episodes": 3}
        other_ova = {"id": 236667, "title": "进击的巨人 LOST GIRLS", "original": "進撃の巨人 LOST GIRLS",
                     "platform": "OVA", "episodes": 3}
        works = {work["id"]: work for work in (main, dome, film, ova, other_ova)}
        dome_matcher = SeriesMatcher(dome, works, main, [{"sort": 1, "ep": 1, "airdate": "2017-05-20"}])
        tv = "[组] 进击的巨人 S01E01 [1080p]"
        dome_title = "[组] 進撃の巨人 IN THE DOME-兵士たちの星空- [1080p]"
        for title in (tv, "[组] Attack on Titan S01E01", "[组] 进击的巨人 Complete Collection",
                      "[组] 進撃の巨人 THE LAST ATTACK [1080p]", "[组] 进击的巨人 OAD [01-03]",
                      dome_title + " [TV]", "[进击的巨人 IN THE DOME -士兵们的星空-] " + tv):
            with self.subTest(title=title):
                self.assertEqual(resource_rows([Resource(title, publish_time="2017-05-20")], dome_matcher), [])
        self.assertEqual(dome_matcher.classify(Resource(dome_title)).work_ids, {499144})
        self.assertEqual(resource_rows([
            Resource(tv, info_hash="c" * 40), Resource(dome_title, info_hash="c" * 40),
        ], dome_matcher), [])
        bundle = dome_title + " + 進撃の巨人 THE LAST ATTACK [1080p]"
        self.assertEqual(dome_matcher.classify(Resource(bundle)).work_ids, {499144, 394303})

        ova_matcher = SeriesMatcher(ova, works, main, [{"sort": 1, "name": "#3.5 イルゼの手帳 ―記録―"}])
        for title in (tv, "[组] 进击的巨人 OAD Complete", "[组] 进击的巨人 OAD [01-03]",
                      "[组] 进击的巨人 LOST GIRLS [01]", "[组] 进击的巨人 OAD [LOST GIRLS]"):
            with self.subTest(title=title):
                self.assertEqual(resource_rows([Resource(title)], ova_matcher), [])
        self.assertEqual(ova_matcher.classify(Resource("[组] 進撃の巨人 OAD イルゼの手帳 [1080p]")).work_ids, {80993})

    def test_season_pack_cannot_assign_ambiguous_parts_or_another_title(self):
        second_part = dict(SEQUEL, id=6, title="系列动画 第二季 后半部分")
        works = dict(WORKS)
        works[6] = second_part
        context = SeriesMatcher(second_part, works, TV, [])
        self.assertEqual(context.classify(Resource("[组] 系列动画 [S1+S2] Complete")).work_ids, {1})
        self.assertEqual(context.classify(Resource("[组] 系列动画 [1080p] + 不相关作品 [S1+S2]")).work_ids, set())
        self.assertEqual(context.classify(Resource("[组] 系列动画 S1 + 不相关作品 [S2+S3]")).work_ids, set())

    def test_explicit_tv_season_still_respects_metadata_episode_count(self):
        context = matcher(SEQUEL)
        self.assertEqual(context.classify(Resource("[组] 系列动画 S02E03 [1080p]")).work_ids, {2})
        self.assertEqual(context.classify(Resource("[组] 系列动画 S02E99 [1080p]")).work_ids, set())

    def test_same_bundle_has_same_members_on_each_page(self):
        for work in (TV, SEQUEL, OVA1, OVA2):
            result = matcher(work).classify(Resource(BUNDLE))
            self.assertEqual(result.work_ids, {1, 2, 3, 4})
            self.assertEqual(result.category(work["id"]), "合集资源")
        self.assertEqual(matcher(SP).classify(Resource(BUNDLE)).category(5), "")

    def test_named_ova_and_sp_do_not_match_main_title_prefix(self):
        result = matcher(TV).classify(Resource("[组] 系列动画 雪之章 [BDRip 1080p]"))
        self.assertEqual(result.work_ids, {3})
        self.assertEqual(result.category(1), "")
        result = matcher(SP).classify(Resource("[组] 系列动画 特别篇 星之章 [1080p]"))
        self.assertEqual(result.work_ids, {5})
        self.assertEqual(result.category(5), "独立资源")

    def test_generic_ova_numbers_never_identify_ova_entries(self):
        for markers in ("OVA1", "OVA1+OVA2", "OVA1-2"):
            result = matcher(OVA1).classify(Resource(f"[组] 系列动画 [S1+S2+{markers}] [1080p]"))
            self.assertEqual(result.work_ids, {1, 2})
            self.assertEqual(result.category(3), "")

    def test_full_tv_and_named_sp_can_share_a_release(self):
        result = matcher(TV).classify(Resource("[组] 系列动画 S1 [01-12] + 系列动画 特别篇 星之章 [1080p]"))
        self.assertEqual(result.work_ids, {1, 5})
        self.assertEqual(result.category(1), "合集资源")

    def test_ambiguous_partial_season_range_and_cumulative_coverage(self):
        context = matcher(TV)
        partial = Resource("[组] 系列动画 [S1-S2] [01-04]")
        self.assertEqual(context.classify(partial).category(1), "")
        pack = Resource("[组] 系列动画 [S1-S2] [总第11-14]")
        context.add_schedule(1, [{"sort": 11}, {"sort": 12}])
        self.assertFalse(context.classify(pack).work_ids)
        context.add_schedule(2, [{"sort": 13}, {"sort": 14}])
        self.assertEqual(context.classify(pack).work_ids, {1, 2})
        context.add_schedule(2, [{"sort": 12}, {"sort": 13}, {"sort": 14}])
        self.assertFalse(context.classify(pack).work_ids)

    def test_distinct_hashes_remain_separate_after_classification(self):
        rows = resource_rows(
            [Resource(BUNDLE, info_hash="a" * 40, size=1, source="A"),
             Resource(BUNDLE, info_hash="a" * 40, size=1, source="B"),
             Resource(BUNDLE, info_hash="b" * 40, size=1, source="C")],
            matcher(OVA1),
        )
        self.assertEqual({row["info_hash"] for row in rows}, {"a" * 40, "b" * 40})
        self.assertEqual(len(rows), 2)
        self.assertIn("A / B", {row["sources"] for row in rows})

    def test_mirrors_supply_evidence_but_conflicts_are_excluded(self):
        hash_value = "a" * 40
        vague = Resource("[组] 系列动画 [合集]", source="A", info_hash=hash_value)
        exact = Resource(BUNDLE, source="B", info_hash=hash_value)
        rows = resource_rows([vague, exact], matcher(OVA1))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "合集资源")
        self.assertEqual(rows[0]["title"], BUNDLE)
        first = Resource("[组] 系列动画 雪之章 [1080p]", source="A", info_hash=hash_value)
        second = Resource("[组] 系列动画 冰之章 [1080p]", source="B", info_hash=hash_value)
        rows = resource_rows([first, second], matcher(OVA1))
        self.assertEqual(rows, [])


class CatalogPosterModelTest(unittest.TestCase):
    def test_catalog_appends_later_candidates_without_resetting_confirmed_posters(self):
        with TemporaryDirectory() as directory:
            backend = BTResources(Path(directory))
            first, second = {"id": 1}, {"id": 2}
            with patch.object(backend._catalog_pool, "start") as start:
                backend.extendCatalog([first], False)
                generation = backend._catalog_generation
                job = backend._catalog_job
                backend._receive_catalog_progress(generation, (1, [{}], False))
                model = backend.catalogModel
                first_index = QPersistentModelIndex(model.index(0, 0))
                backend.extendCatalog([first, second], True)
                start.assert_called_once_with(job)
                self.assertEqual(backend._catalog_generation, generation)
                self.assertEqual(list(job._remaining), [first, second])
                self.assertTrue(job._complete)
                self.assertTrue(first_index.isValid())
                self.assertEqual(backend.catalogResults, [first])
            backend.shutdown()

    def test_confirmed_posters_append_and_stale_generation_cannot_modify_model(self):
        with TemporaryDirectory() as directory:
            backend = BTResources(Path(directory))
            first, second = {"id": 1}, {"id": 2}
            backend._catalog_by_id = {1: first, 2: second}
            generation = backend._catalog_generation
            model = backend.catalogModel
            backend._receive_catalog_progress(generation, (2, [{}], False))
            original = QPersistentModelIndex(model.index(0, 0))
            backend._receive_catalog_progress(generation, (1, [{}], False))
            backend._receive_catalog_progress(generation, (2, [{}], False))
            self.assertEqual(backend.catalogResults, [second, first])
            self.assertTrue(original.isValid())
            self.assertEqual(original.data(model.subject_role), second)
            backend.verifyCatalog([])
            backend._receive_catalog_progress(generation, (2, [{}], False))
            self.assertEqual(model.count, 0)
            backend.shutdown()


class SeriesSearchTest(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_title_appears_while_bangumi_schedule_is_pending(self):
        schedule_gate = asyncio.Event()
        page_gate = asyncio.Event()
        title_published = asyncio.Event()
        date_published = asyncio.Event()
        explicit = "[组] 系列动画 第二季 [01][1080p]"
        dated = "[组] 系列动画 第二季 [总第13集][1080p]"

        class PagedSource(Source):
            name = "test"
            base_url = "https://example.test"

            async def search_pages(self, keyword):
                yield [Resource(title, source=self.name, info_hash=char * 40)
                       for title, char in ((explicit, "a"), (dated, "b"))]
                await page_gate.wait()

        async def respond(request):
            if request.url.path == "/v0/episodes":
                await schedule_gate.wait()
                return httpx.Response(200, json={"data": [{"ep": 1, "sort": 13}], "total": 1})
            return httpx.Response(200, json=[])

        updates = []

        def update(rows, statuses, schedule):
            titles = {row["title"] for row in rows}
            updates.append((titles, statuses, schedule))
            if explicit in titles:
                title_published.set()
            if dated in titles:
                date_published.set()

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=["test"]), Path(directory), client, [PagedSource])
                task = asyncio.create_task(collect_resources(service, SEQUEL, [SEQUEL], update))
                try:
                    await asyncio.wait_for(title_published.wait(), 2)
                    self.assertEqual(updates[-1][0], {explicit})
                    self.assertEqual(updates[-1][1]["test"]["status"], "搜索中")
                    schedule_gate.set()
                    await asyncio.wait_for(date_published.wait(), 2)
                    self.assertEqual(updates[-1][0], {explicit, dated})
                    self.assertTrue(updates[-1][2])
                finally:
                    schedule_gate.set()
                    page_gate.set()
                    await asyncio.wait_for(task, 2)

    async def test_catalog_recovers_conan_proof_when_first_episode_page_fails(self):
        conan = dict(TV, id=899, title="名侦探柯南", original="名探偵コナン", episodes=0)
        episode_offsets = []

        class FixtureSource(Source):
            name = "test"
            base_url = "https://example.test"

            async def search(self, keyword):
                title = "[银色子弹字幕组][名侦探柯南][第1219集 规矩很多的咖啡店][WEBRIP][1080P]"
                return [Resource(title, publish_time="2026-11-07T18:26:00Z", source=self.name,
                                 magnet="magnet:?xt=urn:btih:" + "a" * 40)]

        def respond(request):
            if request.url.path == "/v0/episodes":
                offset = int(request.url.params["offset"])
                episode_offsets.append(offset)
                if offset == 1200:
                    return httpx.Response(200, json={"total": 1230, "data": [
                        {"ep": 1219, "sort": 1219, "airdate": "2026-11-07"},
                    ]})
                return httpx.Response(503)
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = _CatalogSearchService(Settings(sources=["test"]), Path(directory), client, [FixtureSource])
                proof = await collect_resources(service, conan, [conan], lambda *_: None, first_match=True)
        self.assertEqual(episode_offsets, [0, 0, 1200])
        self.assertEqual([(row["work_ids"], row["episode"]) for row in proof], [([899], "1219")])

    async def test_catalog_confirms_from_first_page_without_waiting_for_pagination(self):
        second_page = asyncio.Event()
        cancelled = asyncio.Event()
        schedule_wait = asyncio.Event()
        schedule_cancelled = asyncio.Event()

        class PagedSource(Source):
            name = "test"
            base_url = "https://example.test"

            async def search_pages(self, keyword):
                yield [Resource("系列动画 第二季 [01][1080p]", source=self.name,
                                magnet="magnet:?xt=urn:btih:" + "a" * 40)]
                try:
                    await second_page.wait()
                finally:
                    cancelled.set()

        async def respond(request):
            if request.url.path == "/v0/episodes":
                try:
                    await schedule_wait.wait()
                finally:
                    schedule_cancelled.set()
            return httpx.Response(200, json=[])

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = _CatalogSearchService(Settings(sources=["test"]), Path(directory), client, [PagedSource])
                proof = await asyncio.wait_for(
                    collect_resources(service, SEQUEL, list(WORKS.values()), lambda *_: None, first_match=True),
                    timeout=2,
                )
                self.assertEqual([row["work_ids"] for row in proof], [[2]])
                self.assertTrue(cancelled.is_set())
                self.assertTrue(schedule_cancelled.is_set())
                self.assertFalse(list(service.directory.glob("*.json")))

    async def test_long_series_episode_lookup_keeps_early_and_recent_metadata(self):
        offsets = []

        def respond(request):
            offset = int(request.url.params["offset"])
            offsets.append(offset)
            return httpx.Response(200, json={"total": 1234, "data": [
                {"sort": number + 1} for number in range(offset, min(1234, offset + 100))
            ]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            rows = await subject_episodes(client, 899)
        self.assertCountEqual(offsets, [0, 100, 200, 300, 400, 1100, 1200])
        self.assertEqual([rows[0]["sort"], rows[499]["sort"], rows[-1]["sort"]], [1, 500, 1234])

    async def test_failed_recent_episode_page_is_retried_and_does_not_poison_cache(self):
        attempts = 0
        cache = {}

        def respond(request):
            nonlocal attempts
            offset = int(request.url.params["offset"])
            if offset == 1200:
                attempts += 1
                if attempts <= 3:
                    return httpx.Response(503)
            return httpx.Response(200, json={"total": 1219, "data": [
                {"sort": number + 1} for number in range(offset, min(1219, offset + 100))
            ]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            rows = await subject_episodes(client, 899, cache)
            self.assertEqual(rows[-1]["sort"], 1200)
            self.assertEqual(attempts, 2)
            self.assertNotIn(899, cache)
            rows = await subject_episodes(client, 899, cache)
            self.assertEqual(rows[-1]["sort"], 1219)
            self.assertEqual(attempts, 4)
            self.assertIs(cache[899], rows)

    async def test_real_corpse_party_titles_survive_independent_queries_and_source_error(self):
        target = {"id": 58957, "name_cn": "尸体派对 Tortured Souls",
                  "name": "コープスパーティー Tortured Souls -暴虐された魂の呪叫-", "platform": "OVA", "eps": 4}
        prequel = {"id": 40286, "name_cn": "尸体派对 迷失的舞步",
                   "name": "コープスパーティー Missing Footage", "platform": "OVA", "type": 2}
        titles = [
            "[DBD-Raws][尸体派对/屍體派對/Corpse Party][OVA][受暴虐亡魂之咒叫/Tortured Souls][01-04全集][1080P][BDRip]",
            "【動漫國字幕組】[屍體派對 Tortured Souls -受折磨的靈魂-][01-04][BDRip][AVC_AAC][720P][繁體][MP4]",
            "【流雲字幕組&BBA字幕組】 ◆屍體派對 迷失的舞步_Corpse Party Missing Footage◇OVA BIG5 PSP 480P MP4",
            "[囧夏字幕组&WiKi] 尸体派对2：影之书 コープスパーティー Book of Shadows [1080p]",
            "无关标题 [1080p]",
        ]
        queries = []

        def respond(request):
            path = request.url.path
            if path == "/resources":
                keyword = request.url.params["search"]
                queries.append(keyword)
                if len(queries) == 1:
                    return httpx.Response(500)
                rows = [{"title": title, "magnet": f"magnet:?xt=urn:btih:{index + 1:040x}"}
                        for index, title in enumerate(titles)] if keyword in {"尸体派对", "屍體派對"} else []
                return httpx.Response(200, json={"status": "OK", "resources": rows})
            if path == "/v0/subjects/58957/subjects":
                return httpx.Response(200, json=[dict(prequel, relation="前传")])
            if path == "/v0/subjects/58957":
                return httpx.Response(200, json=target)
            if path == "/v0/episodes":
                return httpx.Response(200, json={"data": [], "total": 0})
            return httpx.Response(200, json=[])

        updates = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory, self.assertLogs("animebt", "INFO") as logs:
                service = SearchService(Settings(sources=["Anime Garden"]), Path(directory), client, [AnimeGarden])
                await collect_resources(service, subject_summary(target), [subject_summary(prequel)],
                                        lambda *args: updates.append(args))
        self.assertIn("尸体派对", queries)
        self.assertIn("屍體派對", queries)
        self.assertIn("コープスパーティー", queries)
        rows, statuses, _ = updates[-1]
        self.assertCountEqual([row["title"] for row in rows], titles[:2])
        self.assertTrue(all(row["episode"] == "01-04" for row in rows))
        self.assertEqual(statuses["Anime Garden"]["status"], "部分结果")
        self.assertTrue(any("raw=5 candidates=5 matched=2 dedup=2" in line for line in logs.output))
        self.assertTrue(any("HTTP 500" in line for line in logs.output))
        subject = subject_summary(target)
        without_relations = SeriesMatcher(subject, {58957: subject}, subject, [])
        self.assertEqual(without_relations.classify(Resource(titles[0])).work_ids, {58957})
        for title in ("尸体派对 OVA 01-04全集 [1080p]",
                      "尸体派对 Tortured Souls [01-05全集][1080p]",
                      "尸体派对 Tortured Souls [剧场版][1080p]"):
            self.assertEqual(without_relations.classify(Resource(title)).work_ids, set())

    async def test_jjk_season_two_catalog_probe_uses_verified_aliases_and_total_episode_numbers(self):
        target = {"id": 369304, "name_cn": "咒术回战 怀玉･玉折 / 涩谷事变",
                  "name": "呪術廻戦 懐玉・玉折／渋谷事変", "platform": "TV", "eps": 23}
        prequel = {"id": 294993, "name_cn": "咒术回战", "name": "呪術廻戦", "platform": "TV", "type": 2}
        aliases = ["咒术回战 第二季", "Jujutsu Kaisen 2nd Season", "呪術廻戦 第2期"]
        titles = [
            "[GJ.Y] 咒術迴戰 第二季 / Jujutsu Kaisen 2nd Season - 47 (CR 1920x1080 AVC AAC MKV)",
            "[GJ.Y] 咒术回战 第二季 / Jujutsu Kaisen 2nd Season - 23 (B-Global 1920x1080 HEVC AAC MKV)",
            "[2023.07.07]TVアニメ『呪術廻戦』第2期OPテーマ「青のすみか」キタニタツヤ[MP3 320K]",
            "[GJ.Y] 咒术回战 第二季 / Jujutsu Kaisen 2nd Season - 48 (CR 1920x1080 AVC AAC MKV)",
            "剧场版 咒术回战 怀玉·玉折 总集篇 [1080p]",
            "咒术回战 第三季 / Jujutsu Kaisen S3 - 01 [1080p]",
            "咒术回战 全集 [1080p]",
        ]
        queries = []

        def respond(request):
            path = request.url.path
            if path == "/resources":
                keyword = request.url.params["search"]
                queries.append(keyword)
                rows = [{"title": title, "magnet": f"magnet:?xt=urn:btih:{index + 1:040x}"}
                        for index, title in enumerate(titles)] if keyword in {*aliases, "咒术回战"} else []
                return httpx.Response(200, json={"status": "OK", "resources": rows})
            if path == "/v0/subjects/369304":
                return httpx.Response(200, json=dict(target, infobox=[{"key": "别名", "value": aliases}]))
            if path == "/v0/subjects/369304/subjects":
                return httpx.Response(200, json=[dict(prequel, relation="前传")])
            if path == "/v0/episodes":
                episodes = [{"ep": index, "sort": index + 24} for index in range(1, 24)]
                return httpx.Response(200, json={"data": episodes, "total": len(episodes)})
            return httpx.Response(200, json=[])

        updates = []
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=["Anime Garden"]), Path(directory), client, [AnimeGarden])
                await collect_resources(service, subject_summary(target), [subject_summary(prequel)],
                                        lambda *args: updates.append(args))
                proof = await collect_resources(service, subject_summary(target), [subject_summary(prequel)],
                                                lambda *_: None, first_match=True)
        self.assertTrue(set(aliases) <= set(queries))
        self.assertCountEqual([row["title"] for row in updates[-1][0]], titles[:2])
        self.assertCountEqual([row["work_ids"] for row in proof], [[369304], [369304]])
        subject = subject_summary(dict(target, infobox=[{"key": "别名", "value": aliases}]))
        schedule = [{"ep": index, "sort": index + 24} for index in range(1, 24)]
        matcher = SeriesMatcher(subject, {369304: subject}, subject, schedule)
        for number, expected in ((47, {369304}), (48, set())):
            title = f"[GJ.Y] Jujutsu Kaisen S2 - {number} [1080p]"
            self.assertEqual(matcher.classify(Resource(title)).work_ids, expected)
        movie = dict(subject, id=331559, title="剧场版 咒术回战 0", original="", platform="剧场版", aliases=[])
        predecessor = subject_summary(dict(prequel, platform=""))
        partial = SeriesMatcher(subject, {369304: subject, 294993: predecessor, 331559: movie}, movie, schedule)
        self.assertEqual(partial.classify(Resource(titles[1])).work_ids, {369304})

    async def test_catalog_probe_requires_strict_ownership_and_a_bt_link(self):
        class FixtureSource(Source):
            name = "test"
            base_url = "https://example.test"

            async def search(self, keyword):
                return [Resource("系列动画 雪之章 [1080p]", source=self.name),
                        Resource("系列动画 冰之章 [1080p]", source=self.name,
                                 magnet="magnet:?xt=urn:btih:" + "a" * 40)]

        def respond(request):
            if request.url.path == "/v0/episodes":
                return httpx.Response(200, json={"data": [], "total": 0})
            return httpx.Response(200, json=[{"id": 1, "type": 2, "relation": "主线故事",
                                              "name": TV["title"]}])

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=["test"]), Path(directory), client, [FixtureSource])
                for work in (OVA1, OVA2):
                    proof = await collect_resources(
                        service, work, list(WORKS.values()), lambda *_: None, first_match=True,
                    )
                    self.assertEqual([row["work_ids"] for row in proof], [] if work == OVA1 else [[4]])

    async def test_ova_page_queries_main_title_but_excludes_unconfirmed(self):
        class FixtureSource(Source):
            name = "测试来源"
            base_url = "https://example.test"

            async def search(self, keyword):
                response = await self.request("GET", "/search", params={"q": keyword})
                return [Resource(title, source=self.name) for title in response.json()]

        queries = []
        relation_calls = []

        def edge(entry_id, relation):
            work = WORKS[entry_id]
            return {"id": entry_id, "type": 2, "relation": relation,
                    "name": work["title"], "name_cn": work["title"]}

        def respond(request):
            path = request.url.path
            if path == "/v0/subjects/3/subjects":
                relation_calls.append(path)
                return httpx.Response(200, json=[edge(1, "主线故事")])
            if path == "/v0/subjects/1/subjects":
                relation_calls.append(path)
                return httpx.Response(200, json=[edge(2, "续集"), edge(3, "番外篇"), edge(4, "番外篇")])
            if path == "/v0/subjects/2/subjects":
                relation_calls.append(path)
                return httpx.Response(200, json=[])
            if path == "/v0/episodes":
                return httpx.Response(200, json={"data": [], "total": 0})
            if path == "/v0/subjects/3":
                return httpx.Response(404)
            keyword = request.url.params["q"]
            queries.append(keyword)
            return httpx.Response(200, json=[BUNDLE, "[组] 系列动画 OVA"] if keyword == TV["title"] else [])

        updates, cache = [], {}
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[FixtureSource.name]), Path(directory),
                                        client, [FixtureSource])
                await collect_resources(service, OVA1, list(WORKS.values()),
                                        lambda *args: updates.append(args), series_cache=cache)
                await load_series(client, OVA1, list(WORKS.values()), cache)
        self.assertEqual(queries[:2], [OVA1["title"], TV["title"]])
        self.assertEqual(len(relation_calls), 3)
        rows, statuses, _ = updates[-1]
        self.assertEqual([row["category"] for row in rows], ["合集资源"])
        self.assertEqual(statuses[FixtureSource.name]["count"], 1)
        self.assertNotIn("returned", statuses[FixtureSource.name])
