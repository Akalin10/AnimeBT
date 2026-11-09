import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

try:
    from animebt.gui.bt_resources import collect_resources
    from animebt.gui.resource_match import SubjectMatcher, episode_label, search_names
except ModuleNotFoundError as error:
    if error.name != "PySide6":
        raise
    raise unittest.SkipTest("GUI dependencies are optional") from error

from animebt.models import Resource
from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.sources.adapters import Source


class ResourceMatchTest(unittest.TestCase):
    first = {
        "id": 278826, "title": "Re：从零开始的异世界生活 第二季",
        "original": "Re:ゼロから始める異世界生活 2nd season",
        "aliases": ["Re:Zero -Starting Life in Another World- Season 2", "Re0 第二季"],
    }
    second = {
        "id": 316247, "title": "Re：从零开始的异世界生活 第二季 后半部分",
        "original": "Re:ゼロから始める異世界生活 2nd season 後半クール",
    }
    episodes = [
        {"sort": 26, "ep": 1, "airdate": "2020-07-08"},
        {"sort": 27, "ep": 2, "airdate": "2020-07-15"},
    ]

    def test_split_season_checks_markers_and_broadcast_window(self):
        matcher = SubjectMatcher(self.first, [self.first, self.second], self.episodes)
        title = "[组] Re：从零开始的异世界生活 S02E01 [1080p]"
        self.assertTrue(matcher.matches(Resource(title, publish_time="2020-07-08T23:30:00+08:00")))
        self.assertFalse(matcher.matches(Resource(title, publish_time="2021-01-06T23:30:00+08:00")))
        self.assertFalse(matcher.matches(Resource(title)))
        self.assertFalse(matcher.matches(Resource(
            "[组] Re：从零开始的异世界生活 [01] [1080p]", publish_time="2020-07-08"
        )))
        self.assertFalse(matcher.matches(Resource(title.replace("S02", "S03"), publish_time="2020-07-08")))
        self.assertFalse(matcher.matches(Resource(
            "[组] Re：从零开始的异世界生活 第二季 后半部分 [01][1080p]", publish_time="2020-07-08"
        )))
        self.assertEqual(episode_label(Resource(title)), "01")

    def test_cumulative_ranges_cannot_span_another_subject(self):
        matcher = SubjectMatcher(self.first, [self.first, self.second], self.episodes)
        self.assertTrue(matcher.matches(Resource("[组] Re0 第二季 [总第26~27] [1080p]")))
        self.assertFalse(matcher.matches(Resource("[组] Re0 第二季 [总第26~50] [1080p]")))

    def test_explicit_part_synonyms_work_without_schedule(self):
        matcher = SubjectMatcher(self.second, [self.first, self.second], [])
        self.assertTrue(matcher.matches(Resource("[组] Re：从零开始的异世界生活 第二季 下半 [01]")))
        self.assertFalse(matcher.matches(Resource("[组] Re：从零开始的异世界生活 第二季 上半 [01]")))

    def test_split_season_can_continue_episode_numbering(self):
        first = dict(self.first, date="2020-07-08", episodes=13)
        second = dict(self.second, date="2021-01-06")
        matcher = SubjectMatcher(second, [first, second], [{"sort": 39, "ep": 1, "airdate": "2021-01-06"}])
        title = "[组] Re：从零开始的异世界生活 S02E14"
        self.assertTrue(matcher.matches(Resource(title, publish_time="2021-01-06")))
        self.assertFalse(matcher.matches(Resource(title, publish_time="2020-07-08")))

    def test_prefers_qualified_title_and_keeps_multilingual_fallbacks(self):
        names = search_names(self.first)
        self.assertIn("第二季", names[0])
        self.assertTrue(any("ゼロ" in name for name in names))
        self.assertTrue(any("starting life" in name for name in names))
        self.assertEqual(len(names), len(set(names)))

    def test_old_full_tv_archive_does_not_require_a_premiere_week_upload(self):
        subject = {
            "id": 265, "title": "新世纪福音战士", "original": "新世紀エヴァンゲリオン",
            "aliases": ["Neon Genesis Evangelion", "EVA", "2000天鹰战士"],
            "date": "1995-10-04", "episodes": 26,
        }
        film = {
            "id": 6049, "title": "新世纪福音战士剧场版 Air/真心为你",
            "original": "新世紀エヴァンゲリオン劇場版", "aliases": ["The End of Evangelion"],
        }
        matcher = SubjectMatcher(subject, [subject, film], [])
        tv_pack = Resource("[组] 新世纪福音战士 Neon Genesis Evangelion 1-26 [BD 1080p]",
                           publish_time="2020-08-23")
        self.assertEqual(episode_label(tv_pack), "1-26")
        self.assertTrue(matcher.matches(tv_pack))
        self.assertTrue(matcher.matches(Resource("[组] 2000天鹰战士 初版 [全26集][总11G]")))
        self.assertFalse(matcher.matches(Resource("[组] EVA [1-26]")))
        self.assertFalse(matcher.matches(Resource("[组] 新世纪福音战士 [1-24]")))
        self.assertFalse(matcher.matches(Resource("[组] 新世纪福音战士 [1-26] + MOVIE")))
        self.assertFalse(matcher.matches(Resource("[组] 新世纪福音战士 [1-26] + The End of Evangelion")))


class ResourceSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_one_source_failure_keeps_other_source_results(self):
        class TestSource(Source):
            async def search(self, keyword):
                response = await self.request("GET", "/search", params={"q": keyword})
                return [Resource(title, source=self.name) for title in response.json()["titles"]]

        class Unavailable(TestSource):
            name = "失败来源"
            base_url = "https://unavailable.example"

        class Available(TestSource):
            name = "正常来源"
            base_url = "https://available.example"

        def respond(request):
            if request.url.host == "api.bgm.tv":
                return httpx.Response(200, json={"data": [{"ep": 1, "sort": 1}], "total": 1})
            if request.url.host == "unavailable.example":
                return httpx.Response(503)
            return httpx.Response(200, json={"titles": ["[组] 动画名 第二季 [01] [1080p]"]})

        updates = []
        subject = {"id": 10, "title": "动画名 第二季", "original": ""}
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[Unavailable.name, Available.name]), Path(directory),
                                        client, [Unavailable, Available])
                with self.assertLogs("animebt", level="ERROR"):
                    await collect_resources(service, subject, [], lambda *state: updates.append(state))

        rows, statuses, _ = updates[-1]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sources"], Available.name)
        self.assertIn("503", statuses[Unavailable.name]["error"])
        self.assertEqual(statuses[Available.name]["count"], 1)
