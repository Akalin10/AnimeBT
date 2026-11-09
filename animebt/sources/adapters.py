import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from html import unescape
from animebt.models import Resource, size_bytes


MAX_SEARCH_PAGES = 12


class Source:
    name = ""
    base_url = ""

    def __init__(self, client, base_url=None, limit=50):
        self.client = client
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.limit = limit

    async def request(self, method, path, **kwargs):
        response = await self.client.request(method, self.base_url + path, **kwargs)
        response.raise_for_status()
        return response

    async def search_pages(self, keyword):
        yield await self.search(keyword)


class AnimeGarden(Source):
    name = "Anime Garden"
    base_url = "https://api.animes.garden"

    async def search(self, keyword):
        return [item async for page in self.search_pages(keyword) for item in page]

    async def search_pages(self, keyword):
        for page in range(1, MAX_SEARCH_PAGES + 1):
            params = {"search": keyword, "pageSize": self.limit, "page": page}
            data = (await self.request("GET", "/resources", params=params)).json()
            rows = data.get("resources")
            if data.get("status") != "OK" or not isinstance(rows, list):
                raise ValueError("Anime Garden 返回异常数据")
            yield [Resource(title=r["title"], size=size_bytes(r.get("size")), publish_time=r.get("createdAt"),
                            magnet=r.get("magnet"), source=self.name) for r in rows[:self.limit]]
            pagination = data.get("pagination")
            if not rows or not isinstance(pagination, dict) or pagination.get("complete") is not False:
                break
            if pagination.get("page", page) != page:
                break


class BangumiMoe(Source):
    name = "萌番组"
    base_url = "https://bangumi.moe"

    async def search(self, keyword):
        data = (await self.request("POST", "/api/v2/torrent/search", json={"query": keyword, "p": 1})).json()
        if data.get("success") is False or not isinstance(data.get("torrents"), list):
            raise ValueError("萌番组返回异常数据")
        return [Resource(title=r["title"], size=size_bytes(r.get("size")), publish_time=r.get("publish_time"),
                         magnet=r.get("magnet"), info_hash=r.get("infoHash"),
                         torrent_url=urljoin(self.base_url, f'/download/torrent/{r["_id"]}'), source=self.name)
                for r in data["torrents"][:self.limit]]


class RssSource(Source):
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
        for element in root.findall("./channel/item")[:self.limit * MAX_SEARCH_PAGES]:
            fields = {}
            for child in element.iter():
                name = child.tag.rsplit("}", 1)[-1].lower()
                if child.text:
                    fields.setdefault(name, child.text.strip())
            if not self.include_item(fields):
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
                info_hash = match[1] if match else None
            size = size_bytes(fields.get("size") or attributes.get("size") or length or fields.get("contentlength"))
            if size is None:
                match = re.search(r"(?:Size:\s*|\|\s*)([\d.]+\s*[KMGT]i?B)\b", description, re.I)
                size = size_bytes(match[1]) if match else None
            items.append(Resource(title=fields.get("title", "未命名"), size=size,
                                  publish_time=fields.get("pubdate"), torrent_url=urljoin(self.base_url, torrent) if torrent else None,
                                  magnet=magnet, info_hash=info_hash, source=self.name))
        return items

    async def search(self, keyword):
        response = await self.request("GET", self.path, params={**self.parameters, self.parameter: keyword})
        return self.parse(response.content)


class Mikan(RssSource):
    name = "Mikan"
    base_url = "https://mikanani.me"
    path = "/RSS/Search"
    parameter = "searchstr"


class AcgRip(RssSource):
    name = "ACG.RIP"
    base_url = "https://acg.rip"
    path = "/.xml"
    parameter = "term"
