"""Parse the public release rows exposed by the supported search pages."""

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from animebt.models import Resource, size_bytes


class ReleaseTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.links = []
        self.tables = []
        self.row = self.cell = self.link = None

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "table":
            self.tables.append(attributes)
        elif tag == "tr":
            self.row = ([], [], [])
        elif tag == "td" and self.row is not None:
            self.cell = (attributes, [])
            self.row[0].append(self.cell)
        elif tag == "a":
            self.link = (attributes, [])
            self.links.append(self.link)
            if self.row is not None:
                self.row[1].append(self.link)
        elif tag == "input" and self.row is not None:
            self.row[2].append(attributes)

    def handle_data(self, value):
        if self.cell is not None:
            self.cell[1].append(value)
        if self.link is not None:
            self.link[1].append(value)

    def handle_endtag(self, tag):
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = self.cell = None
        elif tag == "td":
            self.cell = None
        elif tag == "a":
            self.link = None


def parse_release_table(html, source, layout, page=1):
    table = ReleaseTable()
    table.feed(html)
    title_prefix, size_column, date_column = {
        "dmhy": ("/topics/view/", 4, 0),
        "mikan": ("/Home/Episode/", 2, 3),
        "nyaa": ("/view/", 3, 4),
    }[layout]
    resources = []
    for cells, links, inputs in table.rows:
        title_link = next(((attrs, label) for attrs, label in links
                           if (attrs.get("href") or "").startswith(title_prefix)
                           and "comments" not in (attrs.get("href") or "").split("#")[-1]), None)
        if title_link is None or len(cells) <= max(size_column, date_column):
            continue
        attrs, label = title_link
        title = (attrs.get("title") or "".join(label)).strip()
        if not title:
            continue
        hrefs = [a.get("href") or "" for a, _ in links]
        magnet = next((href for href in hrefs if href.startswith("magnet:?")), None)
        if not magnet:
            magnet = next((a["data-magnet"] for a in inputs if (a.get("data-magnet") or "").startswith("magnet:?")), None)
        torrent = next((href for href in hrefs if urlsplit(href).path.lower().endswith(".torrent")
                        and urlsplit(urljoin(source.base_url, href)).scheme in {"http", "https"}), None)
        date_attrs, date_text = cells[date_column]
        aired = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{2}:\d{2})?", "".join(date_text))
        published = aired[0].replace("/", "-") if aired else None
        if (timestamp := date_attrs.get("data-timestamp", "")).isdigit() and len(timestamp) <= 10:
            published = datetime.fromtimestamp(int(timestamp), timezone.utc).isoformat()
        resources.append(Resource(title, size_bytes("".join(cells[size_column][1])), published,
                                  magnet=magnet, torrent_url=urljoin(source.base_url, torrent) if torrent else None,
                                  source=source.name, source_id=urlsplit(attrs["href"]).path))
    if layout == "dmhy":
        recognized = any(attrs.get("id") == "topic_list" for attrs in table.tables)
        more = any(urlsplit(attrs.get("href") or "").path == f"/topics/list/page/{page + 1}"
                   for attrs, _ in table.links)
    elif layout == "nyaa":
        recognized = any("torrent-list" in (attrs.get("class") or "") for attrs in table.tables)
        recognized = recognized or bool(re.search(r"No results found", html, re.IGNORECASE))
        more = any(str(page + 1) in parse_qs(urlsplit(attrs.get("href") or "").query).get("p", ())
                   for attrs, _ in table.links)
    else:
        recognized = bool(resources or "search-results" in html or "没有找到" in html)
        more = False
    if not recognized:
        raise ValueError(f"{source.name} 返回的不是已验证的搜索页面")
    return resources, more
