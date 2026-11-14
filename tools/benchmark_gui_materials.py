"""Offline 1000-row GUI material/scroll stress test (fixture resources, no API)."""
import json
import argparse
import math
import os
from pathlib import Path
import statistics
import sys
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument("--transparency-stress", action="store_true", help="Drag global material strength while scrolling, with settings open")
parser.add_argument("--wallpaper", action="store_true", help="Measure actual local wallpaper capture and shared Gaussian blur")
options = parser.parse_args()

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / "tests")]
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_QUICK_BACKEND", "")
os.environ.setdefault("QSG_RHI_BACKEND", "d3d11")
os.environ["ANIMEBT_MODE_QT_TEST"] = "1"

from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl
from PySide6.QtQml import QQmlComponent, QJSValue
from PySide6.QtTest import QTest
import test_gui_keyword_search as fixtures

fixtures.KeywordWindowTest.setUpClass()
out = root / ("artifacts/wallpaper" if options.wallpaper else "artifacts/glass-transparency" if options.transparency_stress else "artifacts/glass-optics")
out.mkdir(parents=True, exist_ok=True)
report = {"kind": "offline fixture resources; FrameAnimation UI intervals, not GPU timestamps", "runs": {}}
with TemporaryDirectory() as tmp:
    engine, window, catalog, backend, assistant, network = fixtures.KeywordWindowTest().make_window(Path(tmp))
    if options.wallpaper:
        from PySide6.QtGui import QImage, QPainter, QColor
        photo=QImage(3200,1800,QImage.Format.Format_RGB32)
        painter=QPainter(photo)
        for x in range(0,3200,24):painter.fillRect(x,0,24,1800,QColor("#ed9dcb" if (x//24)%2 else "#315188"))
        painter.end();photo_path=Path(tmp)/"performance-wallpaper.png";assert photo.save(str(photo_path))
        assert window.selectWallpaper(QJSValue(QUrl.fromLocalFile(str(photo_path)).toString()))
        wall=window.findChild(QObject,"wallpaperBackground")
        for attempt in range(500):
            if wall.property("active"):break
            QTest.qWait(10)
        assert wall.property("active"),window.property("wallpaperError")
        report["wallpaper_decoded_size"]=[wall.property("decodedSize").width(),wall.property("decodedSize").height()]
    window.resize(1100, 740)
    window.requestActivate()
    warnings = []
    engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
    component = QQmlComponent(engine)
    component.setData(b'import QtQuick; Item {id:meterRoot; property bool measuring:false; property var intervals:[]; FrameAnimation {running:meterRoot.measuring; onTriggered: if(frameTime>0) meterRoot.intervals.push(frameTime*1000)}}', QUrl())
    meter = component.create()
    meter.setParentItem(window.contentItem())
    rows = [{"key": str(index), "title": f"[benchmark] Example Anime S02E{index % 60 + 1:02} [1080p][HEVC][CHS]",
             "category": "独立资源", "episode": str(index % 60 + 1), "resolution": "1080p", "fansub": "benchmark",
             "works": [], "size": "1 GB", "date": "", "sources": "离线性能测试样本"} for index in range(1000)]
    try:
        for mode in ("list", "poster"):
            window.changeSearchMode(QJSValue(mode))
            with patch.object(backend._pool, "start"):
                if mode == "list":
                    window.findChild(QObject, "searchField").setProperty("text", "benchmark")
                    window.submitSearch()
                else:
                    backend.openSubject({"id": 1, "title": "离线性能测试样本", "original": "Example Anime", "cover": ""}, [])
            backend._receive_progress(backend._generation, (rows, {}, False))
            backend._receive_finished(backend._generation, "")
            for dark in (False, True):
                switch = window.findChild(QObject, "darkModeSwitch")
                switch.setProperty("checked", dark)
                QMetaObject.invokeMethod(switch, "toggled")
                for optical in ((True,) if options.transparency_stress else (False, True)):
                    window.findChild(QObject, "glassThemeManager").setProperty("enabled", optical)
                    if options.transparency_stress:
                        QMetaObject.invokeMethod(window.findChild(QObject, "settingsPopup"), "open")
                    listing = window.findChild(QObject, "resourceList")
                    timer = QTimer(interval=16)
                    tick = [0]
                    def scroll():
                        tick[0] += 1
                        listing.setProperty("contentY", (tick[0] * 28) % 3000)
                        if options.transparency_stress:
                            window.changeGlassFrost(QJSValue(50 + 40 * math.sin(tick[0] * .09)))
                    timer.timeout.connect(scroll)
                    timer.start()
                    QTest.qWait(400)
                    meter.setProperty("intervals", [])
                    meter.setProperty("measuring", True)
                    start = monotonic()
                    QTest.qWait(2500)
                    elapsed = monotonic() - start
                    meter.setProperty("measuring", False)
                    timer.stop()
                    values = meter.property("intervals")
                    if hasattr(values, "toVariant"):
                        values = values.toVariant()
                    values = sorted(values)
                    report["runs"][f"{mode}-{'dark' if dark else 'light'}-{'optical' if optical else 'flat'}"] = {
                        "rows": backend.resourceModel.rowCount(), "ui_frames_per_second": round(len(values) / elapsed, 1),
                        "median_ms": round(statistics.median(values), 2), "p95_ms": round(values[int((len(values) - 1) * .95)], 2),
                        "max_ms": round(max(values), 2), "scroll_updates": tick[0],
                    }
                    window.grabWindow().save(str(out / f"app-{mode}-{'dark' if dark else 'light'}-{'optical' if optical else 'flat'}.png"))
                    if options.transparency_stress:
                        window.saveGlassFrost()
                        QMetaObject.invokeMethod(window.findChild(QObject, "settingsPopup"), "close")
        report["api"] = str(window.rendererInterface().graphicsApi())
        report["warnings"] = warnings
        report["bangumi_requests"] = len(network.replies)
        report["transparency_stress"] = options.transparency_stress
        (out / "application-benchmark.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if warnings:
            raise AssertionError(warnings)
    finally:
        assistant.shutdown()
        backend.shutdown()
        window.close()
