"""A bounded HTTP cache for the QML engine's asynchronous image requests."""

from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache, QNetworkRequest
from PySide6.QtQml import QQmlNetworkAccessManagerFactory

from .bangumi import USER_AGENT


class CoverNetworkManager(QNetworkAccessManager):
    def createRequest(self, operation, original_request, outgoing_data=None):
        request = QNetworkRequest(original_request)
        if operation == self.Operation.GetOperation and request.url().host() == "lain.bgm.tv":
            request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                                 QNetworkRequest.CacheLoadControl.PreferCache)
            request.setRawHeader(b"User-Agent", USER_AGENT)
            request.setTransferTimeout(15000)
        return super().createRequest(operation, request, outgoing_data)


class CoverCacheFactory(QQmlNetworkAccessManagerFactory):
    def create(self, parent):
        manager = CoverNetworkManager(parent)
        cache = QNetworkDiskCache(manager)
        base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        if base:
            cache.setCacheDirectory(str(Path(base) / "bangumi-covers"))
            cache.setMaximumCacheSize(80 * 1024 * 1024)
            manager.setCache(cache)
        return manager
