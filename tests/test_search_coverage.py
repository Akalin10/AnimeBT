import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest

import httpx

from animebt.config import Settings
from animebt.core.search import SearchService
from animebt.sources import AnimeGarden, DMHY


class SearchCoverageTest(unittest.IsolatedAsyncioTestCase):
    keyword = "碧蓝之海"

    async def test_old_cache_is_replaced_by_results_from_all_pages(self):
        titles = ["碧蓝之海 第三季", "碧藍之海 第二季", "碧蓝之海 [01-12]"]
        requested_pages = []

        def respond(request):
            page = int(request.url.params["page"])
            requested_pages.append(page)
            return httpx.Response(200, json={
                "status": "OK",
                "pagination": {"page": page, "complete": page == len(titles)},
                "resources": [{"title": titles[page - 1]}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                settings = Settings(sources=[AnimeGarden.name], limit=1)
                service = SearchService(settings, Path(directory), client)
                old_key = [AnimeGarden.name, AnimeGarden.base_url, self.keyword, 1]
                old_hash = hashlib.sha256(json.dumps(old_key).encode()).hexdigest()
                (service.directory / f"{old_hash}.json").write_text(json.dumps({
                    "time": time.time(), "resources": [{"title": titles[0]}],
                }), encoding="utf-8")

                result = await service.search(self.keyword)
                cached = await service.search(self.keyword)

        self.assertEqual(requested_pages, [1, 2, 3])
        self.assertEqual([row.title for row in result.resources], titles)
        self.assertEqual([row.title for row in cached.resources], titles)
        self.assertEqual(cached.cached, [AnimeGarden.name])

    async def test_later_page_failure_keeps_previous_rows_without_caching(self):
        def respond(request):
            if request.url.params["page"] == "2":
                raise httpx.ReadTimeout("test timeout", request=request)
            return httpx.Response(200, json={
                "status": "OK", "pagination": {"complete": False},
                "resources": [{"title": self.keyword}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[AnimeGarden.name]), Path(directory), client)
                with self.assertLogs("animebt", level="ERROR"):
                    result = await service.search(self.keyword)
                self.assertEqual(list(service.directory.iterdir()), [])

        self.assertEqual([row.title for row in result.resources], [self.keyword])
        self.assertEqual(result.statuses[AnimeGarden.name], "部分结果")
        self.assertEqual(result.errors[AnimeGarden.name], "搜索超时")

    async def test_rss_keeps_later_matches_and_filters_unrelated_titles(self):
        rss = """<rss><channel>
        <item><title>碧蓝之海 第三季</title></item>
        <item><title>其他动画</title><description>碧蓝之海</description></item>
        <item><title>碧藍之海 [01-12]</title></item>
        </channel></rss>"""
        transport = httpx.MockTransport(lambda _: httpx.Response(200, text=rss))
        async with httpx.AsyncClient(transport=transport) as client:
            with TemporaryDirectory() as directory:
                service = SearchService(Settings(sources=[DMHY.name], limit=1), Path(directory), client)
                result = await service.search(self.keyword)

        self.assertEqual([row.title for row in result.resources], ["碧蓝之海 第三季", "碧藍之海 [01-12]"])
