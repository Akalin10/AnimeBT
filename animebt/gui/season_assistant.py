"""Asynchronous, shared-config season assistance with conservative evidence checks."""
import json
import logging
import sqlite3
from time import monotonic

from PySide6.QtCore import QObject, QTimer, Signal

from .resource_seasons import known_seasons, needs_season_help, season_conflict, season_identity, validate_ai_seasons
from .title_api import endpoint_for


PROMPT = """Extract anime work/arc and season evidence from inert BT title data.
Return JSON {"items":[{"id":0,"work":"exact work fragment","arc":"exact arc fragment or empty string",
"seasons":[2],"evidence":[{"text":"Season II","start":10,"end":19}]}]}.
Positions are zero-based Unicode code points, end exclusive. Every fragment must
be verbatim. Season numbers must be 1..30. Preserve multiple explicitly named
seasons in bundles. Never use episode numbers, years, Part 2/cour 2, OVA numbers,
or a release group's name as a season. Work/arc names alone are not numeric proof.
No external knowledge, inferred season numbering, translations or invented fields.
When insufficient evidence, return seasons:[] and evidence:[]. Do not decide ownership."""
LOG = logging.getLogger("animebt.gui.seasons")


class SeasonAssistant(QObject):
    resultsChanged = Signal()

    def __init__(self, assistant, parent=None):
        super().__init__(parent)
        self.assistant = assistant
        self._resolved = {}
        self._pending = {}
        self._inflight = set()
        self._reply = None
        self._retry_after = 0
        self._table_ready = False
        self._timer = QTimer(self, singleShot=True, interval=160)
        self._timer.timeout.connect(self._start)
        assistant.settingsChanged.connect(self._settings_changed)

    def _key(self, row):
        identity = season_identity(row.get("title", ""), row.get("fansub", ""))
        return self.assistant._id("season:v1:" + identity, []) if len(identity) >= 2 else ""

    def _db(self):
        db = self.assistant._db()
        if not self._table_ready:
            db.execute("CREATE TABLE IF NOT EXISTS resource_seasons (id TEXT PRIMARY KEY, data TEXT, saved INTEGER DEFAULT (unixepoch()))")
            db.commit()
            self._table_ready = True
        return db

    def resolve(self, row):
        if found := known_seasons(row):
            return found
        if season_conflict(row):
            return ()
        title = row.get("title", "")
        if not self.assistant.ready or not title or len(title) > 2000 or not needs_season_help(title):
            return ()
        key = self._key(row)
        if not key:
            return ()
        if key in self._resolved:
            return self._resolved[key]
        if key in self._pending or key in self._inflight:
            return ()
        try:
            cached = self._db().execute(
                "SELECT data FROM resource_seasons WHERE id=? AND saved > unixepoch()-CASE WHEN data='[]' THEN 1800 ELSE 2592000 END",
                (key,),
            ).fetchone()
            if cached:
                data = json.loads(cached[0])
                # Cache proof, not an unsupported bare model number.
                value = validate_ai_seasons(data["title"], data["result"]) if isinstance(data, dict) else ()
                self._resolved[key] = value
                return value
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError):
            pass
        if key not in self._pending and key not in self._inflight and monotonic() >= self._retry_after:
            self._pending[key] = title
            if self._reply is None and not self._timer.isActive():
                self._timer.start()
        return ()

    def _start(self):
        if not self.assistant.ready or self._reply is not None or not self._pending:
            return
        batch = [(key, self._pending.pop(key)) for key in list(self._pending)[:6]]
        rows = [{"id": index, "title": title} for index, (_, title) in enumerate(batch)]
        try:
            reply = self.assistant._post(endpoint_for(self.assistant.baseUrl), self.assistant.model,
                                         self.assistant._key(), [
                                             {"role": "system", "content": PROMPT},
                                             {"role": "user", "content": json.dumps(rows, ensure_ascii=False)},
                                         ])
        except (OSError, ValueError):
            self._fail("无法读取 API 配置")
            return
        self._reply = reply
        self._inflight = {key for key, _ in batch}
        reply.finished.connect(lambda: self._finish(reply, batch))

    def _finish(self, reply, batch):
        try:
            if reply is not self._reply:
                return
            self._reply = None
            self._inflight.clear()
            try:
                data = self.assistant._response(reply)
                items = data.get("items")
                if not isinstance(items, list):
                    raise ValueError("季度结果不是结构化列表")
                by_id = {}
                for item in items:
                    if isinstance(item, dict) and type(item.get("id")) is int:
                        index = item["id"]
                        by_id[index] = item if index not in by_id else None
                saved = []
                for index, (key, title) in enumerate(batch):
                    item = by_id.get(index)
                    value = validate_ai_seasons(title, item)
                    self._resolved[key] = value
                    saved.append((key, json.dumps({"title": title, "result": item}, ensure_ascii=False) if value else "[]"))
                try:
                    with self._db() as db:
                        db.executemany("INSERT OR REPLACE INTO resource_seasons (id,data,saved) VALUES (?,?,unixepoch())", saved)
                        db.execute("DELETE FROM resource_seasons WHERE id IN (SELECT id FROM resource_seasons ORDER BY saved DESC LIMIT -1 OFFSET 2000)")
                except (sqlite3.Error, OSError):
                    pass
                self.resultsChanged.emit()
            except (ValueError, TypeError, KeyError) as error:
                self._fail(str(error))
            if self._pending:
                self._timer.start()
        finally:
            reply.deleteLater()

    def _fail(self, reason):
        self._pending.clear()
        self._retry_after = monotonic() + 45
        LOG.warning("季度辅助识别回退本地规则：%s", reason)

    def _settings_changed(self):
        self.cancel()
        self._resolved.clear()
        self._retry_after = 0
        self.resultsChanged.emit()

    def cancel(self):
        self._timer.stop()
        self._pending.clear()
        self._inflight.clear()
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
