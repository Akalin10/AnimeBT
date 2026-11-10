import asyncio
import re
import xml.etree.ElementTree as ET
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import monotonic
from urllib.parse import urljoin
from html import unescape
import httpx
from animebt.models import Resource, size_bytes
from .web_results import parse_release_table


MAX_SEARCH_PAGES = 12


@dataclass
class QueryAudit:
    collect: bool
    page_budget: int
    slots: object
    requests: list = field(default_factory=list)


query_audit = ContextVar("source_query_audit", default=None)


class SourcePage(list):
    """Records received before adapter-specific category and size limits."""

    def __init__(self, items, raw_count, incomplete=""):
        super().__init__(items)
        self.raw_count = raw_count
        self.incomplete = incomplete


class Source:
    name = ""
    base_url = ""
    coverage = "paged search"
    _cooldown = None

    def __init__(self, client, base_url=None, limit=50):
        self.client = client
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.limit = limit
        self._request_slots = asyncio.Semaphore(2)

    async def request(self, method, path, **kwargs):
        audit = query_audit.get()
        if audit is None:
            return await self._request(method, path, **kwargs)
        async with self._request_slots, audit.slots:
            return await self._request(method, path, **kwargs)

    async def _request(self, method, path, **kwargs):
        cooldown = type(self)._cooldown
        if cooldown and cooldown[0] > monotonic() and cooldown[1] == self.base_url:
            response = cooldown[2]
            raise httpx.HTTPStatusError("来源仍在 Retry-After 冷却期", request=response.request, response=response)
        audit = query_audit.get()
        trace = {"method": method, "path": path, "params": kwargs.get("params"), "json": kwargs.get("json")}
        if audit is not None:
            audit.requests.append(trace)
        try:
            response = await self.client.request(method, self.base_url + path, **kwargs)
            trace["status"] = response.status_code
            if response.status_code == 429:
                value = response.headers.get("Retry-After", "")
                try:
                    delay = int(value) if value.isdecimal() else (
                        parsedate_to_datetime(value) - datetime.now(timezone.utc)
                    ).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    delay = 30
                type(self)._cooldown = (monotonic() + max(1, delay), self.base_url, response)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, TimeoutError) as error:
            trace["error"] = type(error).__name__
            raise
        except asyncio.CancelledError:
            trace["error"] = "CancelledError"
            raise

    @property
    def page_budget(self):
        audit = query_audit.get()
        return audit.page_budget if audit else MAX_SEARCH_PAGES

    async def search_pages(self, keyword):
        yield await self.search(keyword)


class AnimeGarden(Source):
    name = "Anime Garden"
    base_url = "https://api.animes.garden"

    async def search(self, keyword):
        return [item async for page in self.search_pages(keyword) for item in page]

    async def search_pages(self, keyword):
        signatures = set()
        for page in range(1, self.page_budget + 1):
            params = {"search": keyword, "pageSize": self.limit, "page": page}
            data = (await self.request("GET", "/resources", params=params)).json()
            rows = data.get("resources")
            if data.get("status") != "OK" or not isinstance(rows, list):
                raise ValueError("Anime Garden 返回异常数据")
            pagination = data.get("pagination")
            more = isinstance(pagination, dict) and pagination.get("complete") is False
            items = [Resource(title=r["title"], size=size_bytes(r.get("size")), publish_time=r.get("createdAt"),
                              magnet=r.get("magnet"), info_hash=r.get("infoHash"), source=self.name,
                              source_id=str(r["id"]) if r.get("id") is not None else None)
                     for r in rows if isinstance(r, dict) and isinstance(r.get("title"), str) and r["title"].strip()]
            signature = tuple((r.source_id, r.info_hash, r.title) for r in items)
            inconsistent = more and (not items or pagination.get("page", page) != page or signature in signatures)
            if inconsistent:
                yield SourcePage([], len(rows), "分页响应重复或不一致")
                break
            signatures.add(signature)
            incomplete = "达到分页预算" if more and page == self.page_budget else ""
            if rows and (not isinstance(pagination, dict) or type(pagination.get("complete")) is not bool):
                incomplete = incomplete or "响应缺少分页状态"
            if len(items) != len(rows):
                incomplete = incomplete or "有记录缺少有效标题"
            yield SourcePage(items, len(rows), incomplete)
            if not more:
                break


class BangumiMoe(Source):
    name = "萌番组"
    base_url = "https://bangumi.moe"

    async def search(self, keyword):
        return [item async for page in self.search_pages(keyword) for item in page]

    async def search_pages(self, keyword):
        signatures = set()
        for page in range(1, self.page_budget + 1):
            data = (await self.request("POST", "/api/v2/torrent/search", json={"query": keyword, "p": page})).json()
            if data.get("success") is False or not isinstance(data.get("torrents"), list):
                raise ValueError("萌番组返回异常数据")
            rows = data["torrents"]
            items = []
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("title"), str) or not row["title"].strip():
                    continue
                entry_id = row.get("_id")
                torrent = urljoin(self.base_url, f"/download/torrent/{entry_id}") if isinstance(entry_id, str) and re.fullmatch(r"[a-zA-Z0-9]+", entry_id) else None
                items.append(Resource(row["title"], size_bytes(row.get("size")), row.get("publish_time"),
                                      magnet=row.get("magnet"), info_hash=row.get("infoHash"), torrent_url=torrent,
                                      source=self.name, source_id=entry_id))
            page_count = data.get("page_count")
            more = type(page_count) is int and page < page_count
            signature = tuple((row.source_id, row.info_hash, row.title) for row in items)
            if (more and not items) or signature in signatures:
                yield SourcePage([], len(rows), "分页响应重复或不一致")
                break
            signatures.add(signature)
            incomplete = "达到分页预算" if more and page == self.page_budget else ""
            if len(items) != len(rows):
                incomplete = incomplete or "有记录缺少有效标题"
            if type(page_count) is not int and rows:
                incomplete = incomplete or "响应缺少页数"
            yield SourcePage(items, len(rows), incomplete)
            if not more:
                break


class RssSource(Source):
    coverage = "bounded RSS search"
    rss_window = 50
    path = ""
    parameter = ""
    parameters = {}

    def include_item(self, fields):
        return True

    def parse(self, content):
        root = ET.fromstring(content)
        if root.tag != "rss":
            raise ValueError("来源返回的不是 RSS（可能是拦截页面或接口错误）")
        if root.find("channel") is None:
            raise ValueError("RSS 缺少 channel")
        items = []
        # A search feed may already contain older releases beyond its first page of items.
        rows = root.findall("./channel/item")
        malformed = 0
        for element in rows:
            fields = {}
            for child in element.iter():
                name = child.tag.rsplit("}", 1)[-1].lower()
                if child.text:
                    fields.setdefault(name, child.text.strip())
            if not self.include_item(fields):
                continue
            if not fields.get("title"):
                malformed += 1
                continue
            enclosure = element.find("enclosure")
            torrent = enclosure.get("url") if enclosure is not None else None
            length = enclosure.get("length") if enclosure is not None else None
            description = unescape(fields.get("description", ""))
            magnet = next(iter(re.findall(r'magnet:\?[^\s<>"\']+', unescape(ET.tostring(element, encoding="unicode")))), None)
            attributes = {c.get("name", "").lower(): c.get("value") for c in element.iter()
                          if c.tag.rsplit("}", 1)[-1] == "attr"}
            info_hash = fields.get("infohash") or attributes.get("infohash")
            if torrent and torrent.startswith("magnet:"):
                magnet, torrent = torrent, None
                length = None  # Some feeds use a placeholder length of 1 for magnets.
            if not torrent and re.search(r"\.torrent(?:\?|$)", fields.get("link", "")):
                torrent = fields["link"]
            if not info_hash:
                match = re.search(r"(?:show-|hash=)([a-fA-F0-9]{40})", (torrent or "") + " " + fields.get("link", ""))
                info_hash = match[1] if match else None
            if self.name == "Mikan":
                match = re.search(r"/([a-fA-F0-9]{40})(?:\.torrent|$)", torrent or fields.get("link", ""))
                info_hash = info_hash or (match[1] if match else None)
            size = size_bytes(fields.get("size") or attributes.get("size") or length or fields.get("contentlength"))
            if size is None:
                match = re.search(r"(?:Size:\s*|\|\s*)([\d.]+\s*[KMGT]i?B)\b", description, re.I)
                size = size_bytes(match[1]) if match else None
            items.append(Resource(title=fields["title"], size=size,
                                  publish_time=fields.get("pubdate"), torrent_url=urljoin(self.base_url, torrent) if torrent else None,
                                  magnet=magnet, info_hash=info_hash, source=self.name,
                                  source_id=fields.get("guid") or fields.get("link")))
        incomplete = "RSS 窗口可能已满" if len(rows) >= self.rss_window else ""
        return SourcePage(items, len(rows), incomplete or ("有记录缺少有效标题" if malformed else ""))

    async def search(self, keyword):
        response = await self.request("GET", self.path, params={**self.parameters, self.parameter: keyword})
        return self.parse(response.content)


class Mikan(RssSource):
    name = "Mikan"
    base_url = "https://mikanani.me"
    path = "/RSS/Search"
    parameter = "searchstr"
    rss_window = 100
    coverage = "RSS plus public search table in deep mode"

    async def search_pages(self, keyword):
        page = await self.search(keyword)
        yield page
        audit = query_audit.get()
        if audit and audit.collect and audit.page_budget >= MAX_SEARCH_PAGES and page.raw_count >= self.rss_window:
            response = await self.request("GET", "/Home/Search", params={"searchstr": keyword})
            items, _ = parse_release_table(response.text, self, "mikan")
            yield SourcePage(items, len(items), "网页结果达到当前窗口" if len(items) >= 1000 else "")


class AcgRip(RssSource):
    name = "ACG.RIP"
    base_url = "https://acg.rip"
    path = "/.xml"
    parameter = "term"
