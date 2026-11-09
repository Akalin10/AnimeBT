from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import httpx

try:
    from animebt.gui.bt_resources import collect_resources, resource_rows
    from animebt.gui.series_resources import SeriesMatcher, load_series
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.models import Resource
from animebt.sources.adapters import Source


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


class SeriesSearchTest(unittest.IsolatedAsyncioTestCase):
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
        self.assertEqual(queries, [OVA1["title"], TV["title"]])
        self.assertEqual(len(relation_calls), 3)
        rows, statuses, _ = updates[-1]
        self.assertEqual([row["category"] for row in rows], ["合集资源"])
        self.assertEqual(statuses[FixtureSource.name]["count"], 1)
        self.assertNotIn("returned", statuses[FixtureSource.name])
