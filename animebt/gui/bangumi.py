"""Asynchronous Bangumi subject search for the GUI."""

from collections import OrderedDict
import json
import logging
import os
import re
from datetime import date
from time import monotonic
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Property, QUrl, Signal, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from animebt.core.matching import _normalize
from animebt.version import __version__


PRIMARY_LIMIT = 20
SUPPLEMENT_LIMIT = 8
SUPPLEMENT_QUERIES = 3
CACHE_SIZE = 32
CACHE_SECONDS = 300
SEARCH_URL = f"https://api.bgm.tv/v0/search/subjects?limit={PRIMARY_LIMIT}"
RELATIONS_URL = "https://api.bgm.tv/v0/subjects/{}/subjects"
VERIFIED_RELATIONS = {"前传", "续集", "主线故事", "番外篇", "衍生", "总集篇", "不同演绎", "不同世界观"}
USER_AGENT = f"AnimeBT/{__version__} (Windows GUI)".encode("ascii")
SEASON_MARKER = re.compile(
    r"第\s*([零〇一二三四五六七八九十\d]+)\s*[季期]"
    r"|(?<![a-z0-9])(?:season\s*(\d+)\b|(\d+)(?:st|nd|rd|th)\s+season\b|s(\d+)(?=e\d|[^a-z0-9]|$))",
    re.IGNORECASE,
)


def subject_summary(row):
    subject_id = row.get("id")
    original = (row.get("name") or "").strip()
    chinese = (row.get("name_cn") or "").strip()
    if not isinstance(subject_id, int) or subject_id <= 0 or not (original or chinese):
        return None

    aliases = []
    alias_languages = {}
    for item in row.get("infobox") or []:
        key = item.get("key")
        if key not in {"别名", "英文名", "罗马字", "罗马音", "羅馬字"}:
            continue
        values = item.get("value")
        for value in values if isinstance(values, list) else [values]:
            name = value.get("v") if isinstance(value, dict) else value
            if isinstance(name, str) and name.strip():
                aliases.append(name)
                if key != "别名":
                    alias_languages[name] = "latin" if key == "英文名" else "romaji"
    season = ""
    match = SEASON_MARKER.search(chinese) or SEASON_MARKER.search(original)
    if match:
        season = f"第{next(group for group in match.groups() if group)}季"
    try:
        aired = date.fromisoformat(row.get("date") or "")
    except (ValueError, TypeError):
        pass
    else:
        quarter_month = (aired.month - 1) // 3 * 3 + 1
        airtime = f"{aired.year} 年 {quarter_month} 月番"
        season = f"{season} · {airtime}" if season else airtime

    images = row.get("images") or {}
    covers = []
    for size in ("large", "medium", "common", "small"):
        candidate = images.get(size) or ""
        url = urlsplit(candidate)
        if (url.scheme == "https" and url.netloc == "lain.bgm.tv"
                and "/pic/cover/" in url.path and candidate not in covers):
            covers.append(candidate)
    return {
        "id": subject_id,
        "title": chinese or original,
        "original": original if original != chinese else "",
        "season": season,
        "cover": covers[0] if covers else "",
        "coverAlternatives": covers[1:],
        "aliases": aliases,
        "aliasLanguages": alias_languages,
        "date": row.get("date") or "",
        "episodes": row.get("eps") or 0,
        "platform": row.get("platform") or "",
    }


def name_key(name):
    return " ".join(_normalize(name).split())


def matches_name(subject, key):
    return any(name_key(name) == key
               for name in (subject["title"], subject["original"], *subject["aliases"]) if name)


def alternate_queries(subject, original):
    latin_aliases = [
        name for name in subject["aliases"]
        if len(re.findall(r"[a-zA-Z]", name)) >= 4 and not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", name)
    ]
    seen = {name_key(original)}
    queries = []
    for name in (subject["original"], subject["title"], *latin_aliases):
        key = name_key(name)
        if key in seen or not 2 <= len(key) <= 120:
            continue
        queries.append(name.strip())
        seen.add(key)
        if len(queries) == SUPPLEMENT_QUERIES:
            break
    return queries


def read_subjects(data):
    rows = data["data"]
    if not isinstance(rows, list):
        raise ValueError("Invalid Bangumi results")
    subjects = {}
    for row in rows[:PRIMARY_LIMIT]:
        if not isinstance(row, dict) or row.get("type", 2) != 2 or row.get("nsfw") is True:
            continue
        if subject := subject_summary(row):
            subjects.setdefault(subject["id"], subject)
    if rows and not subjects:
        raise ValueError("No valid Bangumi subjects")
    return list(subjects.values())


class BangumiSearch(QObject):
    changed = Signal()
    selectionChanged = Signal()

    def __init__(self, parent=None, *, manager=None):
        super().__init__(parent)
        self._network = manager if manager is not None else QNetworkAccessManager(self)
        self._pending = set()
        self._cache = OrderedDict()
        self._primary = []
        self._primary_total = 0
        self._alternates = []
        self._related_ids = set()
        self._expansion_failed = False
        self._results = []
        self._status = "idle"
        self._error = ""
        self._keyword = ""
        self._total = 0
        self._selected = {}
        self._token = os.environ.get("ANIMEBT_BANGUMI_TOKEN", "").strip()

    @Property("QVariantList", notify=changed)
    def results(self):
        return self._results

    @Property("QVariantList", notify=changed)
    def candidates(self):
        return self._primary if self._status == "loading" else self._results

    @Property(str, notify=changed)
    def status(self):
        return self._status

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Property(str, notify=changed)
    def keyword(self):
        return self._keyword

    @Property(int, notify=changed)
    def total(self):
        return self._total

    @Property(int, notify=changed)
    def primaryCount(self):
        return len(self._primary)

    @Property("QVariantMap", notify=selectionChanged)
    def selected(self):
        return self._selected

    @Slot(str)
    def search(self, keyword):
        keyword = keyword.strip()
        if not keyword or (self._pending and keyword == self._keyword):
            return

        self._abort_pending()
        self._keyword = keyword
        self._results = []
        self._primary = []
        self._primary_total = 0
        self._alternates = []
        self._related_ids = set()
        self._expansion_failed = False
        self._total = 0
        self._error = ""
        self._status = "loading"
        self._selected = {}
        self.selectionChanged.emit()
        cached = self._cache.pop(keyword, None)
        if cached and monotonic() - cached[0] < CACHE_SECONDS:
            self._cache[keyword] = cached
            _, rows, primary_count, self._primary_total = cached
            self._primary = rows[:primary_count]
            self._publish(rows)
            return
        self._post_search(keyword, self._finish_primary, 15000)
        self.changed.emit()

    @Slot()
    def cancel(self):
        if not self._pending:
            return
        self._abort_pending()
        if self._primary:
            self._publish(self._primary)
        else:
            self._status = "cancelled"
            self.changed.emit()

    @Slot()
    def reset(self):
        self._abort_pending()
        self._results = []
        self._primary = []
        self._alternates = []
        self._selected = {}
        self._keyword = ""
        self._total = self._primary_total = 0
        self._status, self._error = "idle", ""
        self.selectionChanged.emit()
        self.changed.emit()

    def _abort_pending(self):
        pending, self._pending = self._pending, set()
        for reply in pending:
            reply.abort()

    def _request(self, url, timeout):
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"Accept", b"application/json")
        request.setRawHeader(b"User-Agent", USER_AGENT)
        request.setTransferTimeout(timeout)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        return request

    def _post_search(self, keyword, handler, timeout, *, offset=0):
        url = f"{SEARCH_URL}&offset={offset}" if offset else SEARCH_URL
        request = self._request(url, timeout)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        if re.fullmatch(r"[A-Za-z0-9._~+/-]+=*", self._token):
            request.setRawHeader(b"Authorization", b"Bearer " + self._token.encode("ascii"))
        body = {"keyword": keyword, "sort": "match", "filter": {"type": [2], "nsfw": False}}
        self._track(self._network.post(request, json.dumps(body, ensure_ascii=False).encode("utf-8")), handler)

    def _track(self, reply, handler):
        self._pending.add(reply)
        reply.finished.connect(lambda: self._finish(reply, handler))

    def _finish(self, reply, handler):
        try:
            if reply in self._pending:
                self._pending.remove(reply)
                handler(reply)
        finally:
            reply.deleteLater()

    @staticmethod
    def _reply_error(reply):
        code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if code in (401, 403):
            return f"Bangumi 拒绝访问（HTTP {code}）。如配置了 Token，请检查它是否有效。"
        if code == 429:
            return "Bangumi 搜索过于频繁（HTTP 429），请稍后重试。"
        if code is not None and not 200 <= code < 300:
            return f"Bangumi 返回 HTTP {code}，请稍后重试。"
        if reply.error() in (QNetworkReply.NetworkError.TimeoutError,
                             QNetworkReply.NetworkError.OperationCanceledError):
            return "连接 Bangumi 超时，请重试。"
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return "无法连接 Bangumi，请检查网络后重试。"
        return ""

    def _finish_primary(self, reply):
        error = self._reply_error(reply)
        if not error:
            try:
                data = json.loads(bytes(reply.readAll()))
                self._primary = read_subjects(data)
            except (ValueError, KeyError, TypeError, AttributeError):
                error = "Bangumi 返回了无法读取的搜索结果，请稍后重试。"
        if error:
            self._fallback_error = error
            logging.getLogger(__name__).warning("Bangumi unavailable, trying AniList: %s", error)
            self._post_anilist(1)
            return

        total = data.get("total")
        self._primary_total = max(total, len(self._primary)) if isinstance(total, int) else len(self._primary)
        if self._primary_total > PRIMARY_LIMIT and len(data["data"]) >= PRIMARY_LIMIT:
            self._post_search(self._keyword, self._finish_next_page, 4000, offset=PRIMARY_LIMIT)
        key = name_key(self._keyword)
        anchors = [row for row in self._primary if matches_name(row, key)]
        if len(anchors) == 1 and (queries := alternate_queries(anchors[0], self._keyword)):
            self._alternates = [[] for _ in queries]
            for index, query in enumerate(queries):
                self._post_search(query, lambda reply, index=index: self._finish_supplement(reply, index), 4000)
            request = self._request(RELATIONS_URL.format(anchors[0]["id"]), 4000)
            self._track(self._network.get(request), self._finish_supplement)
        if self._pending:
            self.changed.emit()
        else:
            self._complete()

    def _post_anilist(self, page):
        from .anilist import URL, QUERY
        request = self._request(URL, 12000)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        body = {"query": QUERY, "variables": {"search": self._keyword, "page": page}}
        self._track(self._network.post(request, json.dumps(body).encode("utf-8")),
                    lambda reply: self._finish_anilist(reply, page))

    def _finish_anilist(self, reply, page):
        from .anilist import read_page
        try:
            code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError or code is not None and not 200 <= code < 300:
                raise ValueError(f"HTTP {code}" if code else reply.errorString())
            rows, more = read_page(json.loads(bytes(reply.readAll())))
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            logging.getLogger(__name__).warning("AniList fallback failed: %s", error)
            if self._primary:
                self._publish(self._primary)
            else:
                self._status, self._error = "error", self._fallback_error + " 备用作品服务也暂不可用。"
                self.changed.emit()
            return
        seen = {row["id"] for row in self._primary}
        self._primary.extend(row for row in rows if row["id"] not in seen)
        self._primary_total = len(self._primary)
        if more and rows and page < 2:
            self._post_anilist(page + 1)
            self.changed.emit()
        else:
            self._complete()

    def _finish_next_page(self, reply):
        try:
            if self._reply_error(reply):
                self._expansion_failed = True
            else:
                rows = read_subjects(json.loads(bytes(reply.readAll())))
                seen = {row["id"] for row in self._primary}
                self._primary.extend(row for row in rows if row["id"] not in seen)
        except (ValueError, KeyError, TypeError, AttributeError):
            self._expansion_failed = True
        if self._pending:
            self.changed.emit()
        else:
            self._complete()

    @staticmethod
    def _read_relations(rows):
        if not isinstance(rows, list):
            raise ValueError("Invalid Bangumi relations")
        return {row["id"] for row in rows if isinstance(row, dict) and row.get("type") == 2
                and type(row.get("id")) is int and row.get("relation") in VERIFIED_RELATIONS}

    def _finish_supplement(self, reply, index=None):
        try:
            if self._reply_error(reply):
                self._expansion_failed = True
            else:
                data = json.loads(bytes(reply.readAll()))
                if index is None:
                    self._related_ids = self._read_relations(data)
                else:
                    self._alternates[index] = read_subjects(data)
        except (ValueError, KeyError, TypeError, AttributeError):
            self._expansion_failed = True
        if not self._pending:
            self._complete()

    def _complete(self):
        results = {row["id"]: row for row in self._primary}
        key = name_key(self._keyword)
        limit = len(results) + SUPPLEMENT_LIMIT
        for batch in self._alternates:
            for row in batch:
                if len(results) >= limit:
                    break
                if row["id"] in self._related_ids or matches_name(row, key):
                    results.setdefault(row["id"], row)
        rows = list(results.values())
        if not self._expansion_failed:
            self._cache[self._keyword] = (monotonic(), rows, len(self._primary), self._primary_total)
            if len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        self._publish(rows)

    def _publish(self, results):
        self._results = results
        self._total = max(self._primary_total, len(results))
        self._status = "ready" if results else "empty"
        self.changed.emit()

    @Slot(int)
    def select(self, subject_id):
        selected = next((row for row in self.candidates if row["id"] == subject_id), None)
        if selected is not None:
            self._selected = selected
            self.selectionChanged.emit()
