import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class WindowLayoutTest(unittest.TestCase):
    def test_fixed_chrome_popup_geometry_and_rounded_cover_pixels(self):
        if os.environ.get("ANIMEBT_LAYOUT_QT_TEST") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                "-p", Path(__file__).name,
            ], env={**os.environ, "ANIMEBT_LAYOUT_QT_TEST": "1", "ANIMEBT_MODE_QT_TEST": "1",
                    "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=40)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        import test_gui_keyword_search as fixtures
        from PySide6.QtCore import QObject, QPointF, QMetaObject, QUrl
        from PySide6.QtGui import QImage, QColor
        from PySide6.QtQml import QQmlApplicationEngine, QJSValue
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        fixtures.KeywordWindowTest.setUpClass()
        app = fixtures.KeywordWindowTest.app
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            engine, window, catalog, backend, assistant, network = fixtures.KeywordWindowTest().make_window(folder)
            warnings = []
            engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
            try:
                controls = [window.findChild(QQuickItem, name) for name in (
                    "windowTitleBar", "homeButton", "minimizeButton", "maximizeButton", "closeButton")]
                coordinates = [item.mapToScene(QPointF()).y() for item in controls]
                # Load a real QML grid with fixture subjects; no service requests.
                field = window.findChild(QObject, "searchField")
                field.setProperty("text", "layout fixture")
                catalog._status = "ready"
                catalog.changed.emit()
                for number in range(40):
                    backend._catalog_model.append({"id": number + 1, "title": "布局样本", "original": "Layout fixture", "season": "", "cover": ""})
                QTest.qWait(200)
                grid = window.findChild(QObject, "catalogPage")
                self.assertGreater(grid.property("contentHeight"), grid.property("height"))
                for position in (100, 400, 900, 0):
                    grid.setProperty("contentY", position)
                    QTest.qWait(20)
                    self.assertEqual([item.mapToScene(QPointF()).y() for item in controls], coordinates)
                bar = controls[0]
                self.assertGreaterEqual(grid.property("y"), bar.y() + bar.height() + 10)

                popup = window.findChild(QObject, "titleSettingsDialog")
                theme_switch = window.findChild(QObject, "darkModeSwitch")
                for dark in (False, True):
                    theme_switch.setProperty("checked", dark)
                    QMetaObject.invokeMethod(theme_switch, "toggled")
                    for width, height in ((1100, 740), (680, 520)):
                        window.resize(width, height)
                        QMetaObject.invokeMethod(popup, "open")
                        assistant._report("用于验证自动换行与弹窗高度的错误提示。" * 12, True)
                        QTest.qWait(100)
                        background = window.findChild(QQuickItem, "aiSettingsBackground")
                        self.assertEqual(background.width(), popup.property("width"))
                        self.assertEqual(background.height(), popup.property("height"))
                        self.assertEqual((background.x(), background.y()), (0, 0))
                        capture = window.findChild(QObject, "dialogGlassCapture")
                        if capture.property("sourceItem") is not None:
                            self.assertEqual(capture.property("sourceItem"), background)
                            origin = background.mapToScene(QPointF())
                            rect = capture.property("sourceRect")
                            self.assertAlmostEqual(rect.x(), -origin.x())
                            self.assertAlmostEqual(rect.y(), -origin.y())
                        self.assertLessEqual(popup.property("height"), window.height() - 32)
                        QMetaObject.invokeMethod(popup, "close")
                self.assertFalse(warnings, warnings)
            finally:
                assistant.shutdown()
                backend.shutdown()
                window.close()
                engine.deleteLater()
                QTest.qWait(10)

            # A saturated fixture proves corner alpha, not just a rounded border.
            picture = QImage(80, 120, QImage.Format.Format_RGB32)
            picture.fill(QColor("#ff0000"))
            picture.save(str(folder / "cover.png"))
            engine = QQmlApplicationEngine()
            qml_dir = Path(__file__).resolve().parents[1] / "animebt/gui/qml"
            source = QUrl.fromLocalFile(str(folder / "cover.png")).toString()
            engine.loadData((f'import QtQuick\nWindow {{width:180; height:220; visible:true; color:"#00ff00"; '
                             f'RoundedCover {{x:30;y:30;width:80;height:120;radius:12;source:"{source}";sourceSize.width:80}} }}').encode(),
                            QUrl.fromLocalFile(str(qml_dir / "LayoutPixelTest.qml")))
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            try:
                QTest.qWait(250)
                pixels = window.grabWindow()
                ratio = pixels.width() / window.width()
                corner = pixels.pixelColor(round(31 * ratio), round(31 * ratio))
                center = pixels.pixelColor(round(70 * ratio), round(90 * ratio))
                self.assertGreater(corner.green(), 240)
                self.assertLess(corner.red(), 15)
                self.assertGreater(center.red(), 240)
                self.assertLess(center.green(), 15)
                print("Graphics API:", window.rendererInterface().graphicsApi(), "DPR:", ratio,
                      "rounded corner:", corner.name(), "center:", center.name())
            finally:
                window.close()
                engine.deleteLater()
                QTest.qWait(10)
