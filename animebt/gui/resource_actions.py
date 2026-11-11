"""Qt clipboard and asynchronous torrent actions for a selected resource."""

import asyncio
from pathlib import Path
import re
from threading import Event
from urllib.parse import parse_qs, urlsplit

import httpx
from PySide6.QtCore import QObject, Property, QRunnable, QStandardPaths, QThreadPool, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication

from animebt.core.torrent import resolve_magnet, save_torrent
from animebt.models import Resource, normalize_hash
from animebt.version import __version__


def valid_magnet(value, expected_hash=None):
    if not value or any(character.isspace() for character in value):
        return False
    try:
        url = urlsplit(value)
    except ValueError:
        return False
    if url.scheme != "magnet" or url.netloc or url.path:
        return False
    topics = [topic.lower() for topic in parse_qs(url.query).get("xt", [])]
    hashes = {digest for topic in topics if topic.startswith("urn:btih:")
              if (digest := normalize_hash(topic[9:]))}
    if expected_hash and hashes and hashes != {expected_hash}:
        return False
    return bool(hashes) or any(re.fullmatch(r"urn:btmh:1220[0-9a-f]{64}", topic) for topic in topics)


def torrent_resource(row):
    try:
        url = urlsplit(row.get("torrent_url") or "")
    except ValueError as error:
        raise ValueError("种子链接无效") from error
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("种子链接无效")
    # Avoid returning an existing but invalid Magnet from resolve_magnet.
    resource = Resource(row["title"], torrent_url=url.geturl(), info_hash=row.get("info_hash"))
    resource.magnet = None
    return resource


async def fetch_action(row, target=None):
    resource = torrent_resource(row)
    expected = resource.info_hash
    async with asyncio.timeout(15):
        async with httpx.AsyncClient(timeout=15, follow_redirects=True,
                                     headers={"User-Agent": f"AnimeBT/{__version__}"}) as client:
            if target is not None:
                return str(await save_torrent(resource, target, client))
            magnet = await resolve_magnet(resource, client)
            if not valid_magnet(magnet, expected):
                raise ValueError("种子 infohash 与搜索结果不一致")
            return magnet


def failure_reason(error):
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "请求种子文件超时，请重试"
    if isinstance(error, httpx.HTTPStatusError):
        return f"来源返回 HTTP {error.response.status_code}"
    if isinstance(error, httpx.RequestError):
        return "无法连接种子来源，请检查网络"
    if isinstance(error, FileExistsError):
        return "文件已存在，请选择其他文件名"
    if isinstance(error, PermissionError):
        return "没有权限写入所选目录"
    if isinstance(error, OSError):
        return "无法写入所选文件"
    if isinstance(error, ValueError):
        reason = str(error)
        return reason if re.search(r"[\u4e00-\u9fff]", reason) else "种子文件无效或不完整"
    return "资源操作未能完成，请重试"


class TorrentJob(QRunnable):
    def __init__(self, row, target, generation, finished):
        super().__init__()
        self.row = row
        self.target = target
        self.generation = generation
        self.finished = finished
        self.cancelled = Event()

    async def fetch(self):
        task = asyncio.create_task(fetch_action(self.row, self.target))
        while not task.done() and not self.cancelled.is_set():
            await asyncio.wait({task}, timeout=0.1)
        if self.cancelled.is_set():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return ""
        return await task

    def run(self):
        if self.cancelled.is_set():
            return
        value, error = "", ""
        try:
            value = asyncio.run(self.fetch())
        except Exception as exc:
            error = failure_reason(exc)
        if not self.cancelled.is_set():
            self.finished.emit(self.generation, value, error)


class ResourceActions(QObject):
    changed = Signal()
    feedback = Signal(str, bool)
    magnetCopied = Signal(str)
    _finished = Signal(int, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._job = None
        self._generation = 0
        self._finished.connect(self._receive, Qt.ConnectionType.QueuedConnection)
        self._resolved = {}

    @Property(bool, notify=changed)
    def busy(self):
        return self._job is not None

    @Property(str, notify=changed)
    def pendingKey(self):
        return self._job.row["key"] if self._job else ""

    @Slot("QVariantMap")
    def copyMagnet(self, row):
        if self.busy:
            return
        magnet = row.get("magnet")
        expected = row.get("info_hash")
        if valid_magnet(magnet, expected):
            self._copy_magnet(row, magnet)
        elif cached := self._resolved.get((row.get("torrent_url"), expected)):
            self._copy_magnet(row, cached)
        elif row.get("torrent_url"):
            self._start(row)
        else:
            reason = "Magnet 格式无效" if magnet else "该资源没有 Magnet 或种子链接"
            self.feedback.emit("复制磁链失败：" + reason, False)

    @Slot("QVariantMap")
    def copyTitle(self, row):
        if not self.busy and row.get("title"):
            self._copy(row["title"], "✓ 标题已复制", "复制标题失败")

    @Slot("QVariantMap", result=QUrl)
    def suggestedTorrent(self, row):
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        name = f"AnimeBT-{row['key'][:12]}.torrent"
        return QUrl.fromLocalFile(str((Path(folder) if folder else Path.home()) / name))

    @Slot("QVariantMap", QUrl)
    def saveTorrent(self, row, destination):
        if self.busy:
            return
        if not row.get("torrent_url"):
            self.feedback.emit("保存种子失败：该资源没有种子链接", False)
        elif destination.isLocalFile() and destination.toLocalFile():
            self._start(row, destination.toLocalFile())

    def _start(self, row, target=None):
        self._generation += 1
        self._job = TorrentJob(row, target, self._generation, self._finished)
        self.changed.emit()
        self._pool.start(self._job)

    def _copy(self, text, success, failure):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(text)
        if clipboard.text() == text:
            self.feedback.emit(success, True)
            return True
        else:
            self.feedback.emit(failure + "：无法写入 Windows 剪贴板，请重试", False)
            return False

    def _copy_magnet(self, row, magnet):
        if self._copy(magnet, "✓ 磁链已复制", "复制磁链失败"):
            self.magnetCopied.emit(row.get("key", ""))

    @Slot(int, str, str)
    def _receive(self, generation, value, error):
        if generation != self._generation or self._job is None:
            return
        job, self._job = self._job, None
        self.changed.emit()
        if error:
            operation = "保存种子失败" if job.target is not None else "复制磁链失败"
            self.feedback.emit(operation + "：" + error, False)
        elif job.target is not None:
            self.feedback.emit("✓ 种子已保存 · " + Path(value).name, True)
        elif value:
            self._resolved[(job.row["torrent_url"], job.row.get("info_hash"))] = value
            self._copy_magnet(job.row, value)

    def cancelCopy(self):
        if self._job is not None and self._job.target is None:
            self._cancel()

    def _cancel(self):
        self._generation += 1
        if self._job is not None:
            self._job.cancelled.set()
            self._job = None
            self.changed.emit()

    def shutdown(self):
        self._cancel()
        self._pool.waitForDone()
