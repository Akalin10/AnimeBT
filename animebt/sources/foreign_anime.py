"""Public anime RSS feeds used by the GUI's optional sources."""

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from time import monotonic
from urllib.parse import urlsplit

import httpx

from animebt.core.matching import _normalize, title_matches

from .adapters import RssSource


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
    _rate_limit = None

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

    async def fetch_category(self, category, keyword):
        now = monotonic()
        start = max(now, self._next_request_at)
        self._next_request_at = start + self.request_spacing
        if start > now:
            await asyncio.sleep(start - now)
        if self._rate_limit:
            until, response = self._rate_limit
            if until > monotonic():
                raise httpx.HTTPStatusError("来源仍在 Retry-After 冷却期", request=response.request,
                                            response=response)
        try:
            response = await self.request("GET", self.path, params={
                **self.parameters, self.category_parameter: category, self.parameter: keyword,
            })
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 429:
                value = error.response.headers.get("Retry-After", "")
                try:
                    if value.isdecimal():
                        delay = int(value)
                    else:
                        delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = 30
                type(self)._rate_limit = (monotonic() + max(1, delay), error.response)
            raise
        return self.parse(response.content)

    async def search_pages(self, keyword):
        jobs = [asyncio.create_task(self.fetch_category(value, keyword)) for value, _ in self.categories]
        errors = []
        try:
            for job in asyncio.as_completed(jobs):
                try:
                    rows = await job
                except Exception as error:
                    errors.append(error)
                else:
                    yield [row for row in rows if row.info_hash or row.torrent_url]
        finally:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
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

    def __init__(self, client, base_url=None, limit=50):
        super().__init__(client, base_url, limit)
        self._snapshot = None
        self._snapshot_lock = asyncio.Lock()

    def include_item(self, fields):
        category = _normalize(fields.get("category", ""))
        title = _normalize(fields.get("title", ""))
        return bool((category == "raw" and not OTHER_SUBTITLES.search(title))
                    or (category == "动画" and CHINESE.search(title)))

    async def search(self, keyword):
        if self._snapshot is None:
            async with self._snapshot_lock:
                if self._snapshot is None:
                    # This subscription is a recent snapshot, not a server-side keyword search.
                    response = await self.request("GET", self.path)
                    rows = self.parse(response.content)
                    self._snapshot = [self._secure_enclosure(row) for row in rows
                                      if row.info_hash and row.torrent_url
                                      and urlsplit(row.torrent_url).scheme in {"https", "http"}]
        return [row for row in self._snapshot if title_matches(row.title, keyword)][:self.limit]

    @staticmethod
    def _secure_enclosure(row):
        url = urlsplit(row.torrent_url)
        if url.scheme == "http" and url.netloc == "v2.uploadbt.com":
            return replace(row, torrent_url=url._replace(scheme="https").geturl())
        return row


EXTRA_SOURCE_TYPES = (Nyaa, TokyoToshokan, MioBT)
