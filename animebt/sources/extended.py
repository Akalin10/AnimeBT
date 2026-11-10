"""Additional independent RSS adapters."""
from urllib.parse import quote
from .adapters import MAX_SEARCH_PAGES, RssSource, SourcePage, query_audit
from .web_results import parse_release_table


class DMHY(RssSource):
    name = "DMHY"
    base_url = "https://share.dmhy.org"
    path = "/topics/rss/rss.xml"
    parameter = "keyword"
    rss_window = 500
    coverage = "RSS plus public result pages in deep mode"

    async def search_pages(self, keyword):
        feed = await self.search(keyword)
        yield feed
        audit = query_audit.get()
        if not (audit and audit.collect and audit.page_budget >= MAX_SEARCH_PAGES
                and feed.raw_count >= self.rss_window):
            return
        seen = set()
        for page in range(1, self.page_budget + 1):
            path = "/topics/list" if page == 1 else f"/topics/list/page/{page}"
            response = await self.request("GET", path, params={"keyword": keyword})
            items, more = parse_release_table(response.text, self, "dmhy", page)
            signature = tuple(row.source_id for row in items)
            if signature in seen:
                yield SourcePage([], len(items), "网页分页响应重复")
                return
            seen.add(signature)
            yield SourcePage(items, len(items), "达到网页分页预算" if more and page == self.page_budget else "")
            if not more:
                return


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

