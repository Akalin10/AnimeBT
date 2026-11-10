"""Public anime RSS feeds used by the GUI's optional sources."""

import asyncio
from dataclasses import replace
import re
from time import monotonic
from urllib.parse import urlsplit

from animebt.core.matching import _normalize, title_matches

from .adapters import RssSource, SourcePage, query_audit
from .web_results import parse_release_table


CHINESE = re.compile(
    r"简繁|简体|繁体|简中|繁中|简日|繁日|简英|繁英|中[日英](?:双语|字幕)|"
    r"中文(?:字幕|配音|内封|内嵌)|汉化|中字|国配|粤配|\[\s*[简繁]\s*\]|"
    r"(?<![a-z0-9])(?:chs|cht|gb2312|gbk|big5|zh[-_](?:cn|tw|hans|hant))(?![a-z0-9])"
    r"|\b(?:chinese|mandarin|cantonese)[ -]+(?:subs?|subtitles?|dub|audio)\b"
    r"|\[\s*(?:gb|chinese|mandarin|cantonese)\s*\]"
)
OTHER_SUBTITLES = re.compile(
    r"\b(?:english|eng|french|spanish|portuguese|russian)\s*(?:subs?|subtitles?|dub)\b"
    r"|\b(?:vostfr|multi[- ]?subs?)\b|\[\s*(?:english|eng|french|fra|spanish|spa|por|rus)\s*\]"
)


class ForeignAnimeRss(RssSource):
    category_parameter = ""
    categories = ()
    category_field = "category"
    cache_namespace = "zh-raw-v1"
    request_spacing = 0.4
    language_priority = ("jp", "latin", "cjk")

    def __init__(self, client, base_url=None, limit=50):
        super().__init__(client, base_url, limit)
        self._next_request_at = 0.0

    async def search(self, keyword):
        return [row async for page in self.search_pages(keyword) for row in page]

    def include_item(self, fields):
        category = fields.get(self.category_field)
        title = _normalize(fields.get("title", ""))
        raw, chinese = self.categories
        return bool(title and (
            (category == raw[1] and not OTHER_SUBTITLES.search(title))
            or (category == chinese[1] and CHINESE.search(title))
        ))

    async def request(self, method, path, **kwargs):
        now = monotonic()
        start = max(now, self._next_request_at)
        self._next_request_at = start + self.request_spacing
        if start > now:
            await asyncio.sleep(start - now)
        return await super().request(method, path, **kwargs)

    async def fetch_category(self, category, keyword):
        response = await self.request("GET", self.path, params={
            **self.parameters, self.category_parameter: category, self.parameter: keyword,
        })
        return self.parse(response.content)

    async def search_pages(self, keyword):
        async def read(value):
            try:
                return value, await self.fetch_category(value, keyword), None
            except Exception as error:
                return value, (), error

        jobs = [asyncio.create_task(read(value)) for value, _ in self.categories]
        errors = []
        need_web = []
        try:
            for job in asyncio.as_completed(jobs):
                category, rows, error = await job
                if error:
                    errors.append(error)
                    need_web.append(category)
                else:
                    if getattr(rows, "raw_count", len(rows)) >= self.rss_window:
                        need_web.append(category)
                    yield SourcePage((row for row in rows if row.info_hash or row.torrent_url),
                                     getattr(rows, "raw_count", len(rows)), getattr(rows, "incomplete", ""))
        finally:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
        if older := getattr(self, "search_older", None):
            for category in need_web:
                try:
                    async for page in older(keyword, category):
                        yield page
                except Exception as error:
                    errors.append(error)
        if errors:
            raise errors[0]


class Nyaa(ForeignAnimeRss):
    name = "Nyaa"
    base_url = "https://nyaa.si"
    path = "/"
    parameter = "q"
    parameters = {"page": "rss"}
    category_parameter = "c"
    category_field = "categoryid"
    categories = (("1_4", "1_4"), ("1_3", "1_3"))
    rss_window = 75
    coverage = "RAW/Non-English RSS and paged public search"

    async def search_older(self, keyword, category):
        audit = query_audit.get()
        if not audit or not audit.collect:
            return
        pages = min(6 if audit.page_budget >= 12 else 2, audit.page_budget)
        seen = set()
        for page in range(1, pages + 1):
            response = await self.request("GET", "/", params={"q": keyword, "c": category, "p": page})
            items, more = parse_release_table(response.text, self, "nyaa", page)
            signature = tuple(row.source_id for row in items)
            if signature in seen:
                yield SourcePage([], len(items), "网页分页响应重复")
                return
            seen.add(signature)
            yield SourcePage((row for row in items if (row.info_hash or row.torrent_url)
                              and self.include_item({self.category_field: category, "title": row.title})),
                             len(items), "达到网页分页预算" if more and page == pages else "")
            if not more:
                return


class TokyoToshokan(ForeignAnimeRss):
    name = "Tokyo Toshokan"
    base_url = "https://www.tokyotosho.info"
    path = "/rss.php"
    parameter = "terms"
    category_parameter = "filter"
    categories = (("7", "Raws"), ("10", "Non-English"))

    def parse(self, content):
        # The public feed emits only these closing tags for some empty searches.
        if re.fullmatch(rb"\s*</channel>\s*</rss>\s*", content):
            return []
        return super().parse(content)


class MioBT(RssSource):
    name = "MioBT"
    base_url = "https://miobt.com"
    path = "/rss.xml"
    cache_namespace = "recent-rss-v1"
    coverage = "recent snapshot only"

    def __init__(self, client, base_url=None, limit=50):
        super().__init__(client, base_url, limit)
        self._snapshot = None
        self._snapshot_lock = asyncio.Lock()
        self._snapshot_at = 0

    def include_item(self, fields):
        category = _normalize(fields.get("category", ""))
        title = _normalize(fields.get("title", ""))
        return bool((category == "raw" and not OTHER_SUBTITLES.search(title))
                    or (category == "动画" and CHINESE.search(title)))

    async def search(self, keyword):
        if self._snapshot is None or monotonic() - self._snapshot_at >= 45:
            async with self._snapshot_lock:
                if self._snapshot is None or monotonic() - self._snapshot_at >= 45:
                    # This subscription is a recent snapshot, not a server-side keyword search.
                    response = await self.request("GET", self.path)
                    rows = self.parse(response.content)
                    self._snapshot = SourcePage(
                        (self._secure_enclosure(row) for row in rows if row.info_hash
                         or urlsplit(row.torrent_url or "").scheme in {"https", "http"}),
                        rows.raw_count,
                    )
                    self._snapshot_at = monotonic()
        audit = query_audit.get()
        if audit and audit.collect:
            key = re.sub(r"[\W_]+", "", _normalize(keyword))
            items = [row for row in self._snapshot if key and key in re.sub(r"[\W_]+", "", _normalize(row.title))]
        else:
            items = [row for row in self._snapshot if title_matches(row.title, keyword)][:self.limit]
        return SourcePage(items, self._snapshot.raw_count, "仅支持近期 RSS")

    @staticmethod
    def _secure_enclosure(row):
        url = urlsplit(row.torrent_url or "")
        if url.scheme == "http" and url.netloc == "v2.uploadbt.com":
            return replace(row, torrent_url=url._replace(scheme="https").geturl())
        return row


EXTRA_SOURCE_TYPES = (Nyaa, TokyoToshokan, MioBT)
