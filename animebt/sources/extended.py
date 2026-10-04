"""Additional independent RSS adapters."""
from urllib.parse import quote
from .adapters import RssSource


class DMHY(RssSource):
    name = "DMHY"
    base_url = "https://share.dmhy.org"
    path = "/topics/rss/rss.xml"
    parameter = "keyword"


class ACGNX(RssSource):
    name = "ACGNX"
    base_url = "https://share.acgnx.se"
    path = "/rss.xml"
    parameter = "keyword"


class KeywordPathRSS(RssSource):
    async def search(self, keyword):
        response = await self.request("GET", "/rss-" + quote(keyword, safe="") + ".xml")
        return self.parse(response.content)


class KissSub(KeywordPathRSS):
    name = "KissSub"
    base_url = "https://kisssub.org"


class Comicat(KeywordPathRSS):
    name = "Comicat"
    base_url = "https://comicat.org"

