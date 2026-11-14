import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class GlassSettingsTest(unittest.TestCase):
    def test_chrome_insets_live_slider_theme_persistence_and_readability(self):
        if os.environ.get("ANIMEBT_GLASS_SETTINGS_QT") != "1":
            result = subprocess.run([
                sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent), "-p", Path(__file__).name,
            ], env={**os.environ, "ANIMEBT_GLASS_SETTINGS_QT": "1", "ANIMEBT_MODE_QT_TEST": "1",
                    "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=35)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from PySide6.QtCore import QObject, QMetaObject, QPointF, Qt
        from PySide6.QtQml import QJSValue
        from PySide6.QtQuick import QQuickItem
        from PySide6.QtTest import QTest
        import test_gui_keyword_search as fixtures
        fixtures.KeywordWindowTest.setUpClass()
        factory = fixtures.KeywordWindowTest()
        def visual_items(item):
            yield item
            for child in item.childItems():
                yield from visual_items(child)
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            engine, window, catalog, backend, assistant, network = factory.make_window(folder)
            warnings = []
            engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
            try:
                QTest.qWait(100)
                bar = window.findChild(QQuickItem, "windowTitleBar")
                buttons = [window.findChild(QQuickItem, name) for name in (
                    "settingsButton", "minimizeButton", "maximizeButton", "closeButton")]
                for width in (1100, 680):
                    window.resize(width, 740)
                    QTest.qWait(30)
                    bar_point = bar.mapToScene(QPointF())
                    for button in buttons:
                        point = button.mapToScene(QPointF())
                        self.assertEqual((button.width(), button.height()), (36, 36))
                        self.assertGreaterEqual(point.y() - bar_point.y(), 6)
                        self.assertLessEqual(point.y() + button.height(), bar_point.y() + bar.height() - 6)
                    last = buttons[-1].mapToScene(QPointF())
                    self.assertLessEqual(last.x() + buttons[-1].width(), bar_point.x() + bar.width() - 6)
                    for first, second in zip(buttons, buttons[1:]):
                        self.assertLess(first.mapToScene(QPointF()).x() + first.width(), second.mapToScene(QPointF()).x())
                self.assertFalse(buttons[0].property("floating"))
                window.resize(1100, 740)
                backend._active = True
                backend._update_rows([{"key": "material", "title": "材质同步测试样本 S02E01", "category": "独立资源",
                                       "episode": "01", "resolution": "1080p", "fansub": "测试组", "works": [],
                                       "size": "1 GB", "date": "", "sources": "离线界面测试"}])
                backend.changed.emit()
                QTest.qWait(350)
                popup = window.findChild(QObject, "settingsPopup")
                QMetaObject.invokeMethod(popup, "open")
                QTest.qWait(180)
                slider = window.findChild(QQuickItem, "glassFrostSlider")
                manager = window.findChild(QObject, "glassThemeManager")
                self.assertAlmostEqual(window.property("glassFrost"), 0)
                self.assertAlmostEqual(manager.property("level"), 0)
                self.assertAlmostEqual(slider.property("value"), 0)
                expected = []
                for fraction in (.18, .83):
                    local_x = slider.property("leftPadding") + fraction * slider.property("availableWidth")
                    point = slider.mapToScene(QPointF(local_x, slider.height() / 2)).toPoint()
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                    QTest.qWait(20)
                    amount = window.property("glassFrost")
                    self.assertAlmostEqual(amount, fraction * 100, delta=7)
                    self.assertAlmostEqual(manager.property("level"), amount / 100)
                    expected.append(amount)
                    self.assertEqual(window.opacity(), 1)
                    self.assertEqual(buttons[0].opacity(), 1)
                    items = list(visual_items(window.contentItem()))
                    shaders = [item for item in items if item.objectName() == "liquidGlassShader"]
                    if manager.property("enabled"):
                        self.assertGreaterEqual(len(shaders), 4)
                        for shader in shaders:
                            self.assertAlmostEqual(shader.property("tintAmount"), manager.property("tintAmount"))
                    card = next(item for item in items if item.objectName() == "resourceCardGlass")
                    plate = card.findChild(QObject, "glassReadingPlate")
                    self.assertIsNone(plate)
                    self.assertEqual(manager.property("tintAmount"), 0)
                    self.assertEqual(backend.facets["total"], 1)
                    from animebt.gui.title_format import contrast
                    title = next(item for item in items if item.objectName() == "resourceTitle")
                    self.assertEqual(title.property("opacity"), 1)
                self.assertGreater(expected[1] - expected[0], 50)
                slider.forceActiveFocus()
                before_key = window.property("glassFrost")
                QTest.keyClick(window, Qt.Key.Key_Right)
                self.assertGreater(window.property("glassFrost"), before_key)
                QTest.keyClick(window, Qt.Key.Key_Left)
                self.assertAlmostEqual(window.property("glassFrost"), before_key)
                # Real dragging updates the material before the mouse is released.
                start = slider.mapToScene(QPointF(slider.width() * .8, slider.height() / 2)).toPoint()
                QTest.mousePress(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
                samples = []
                for fraction in (.7, .6, .5, .4):
                    point = slider.mapToScene(QPointF(slider.width() * fraction, slider.height() / 2)).toPoint()
                    QTest.mouseMove(window, point, 12)
                    samples.append(window.property("glassFrost"))
                QTest.mouseRelease(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                self.assertGreater(samples[0], samples[-1])
                light = window.property("glassFrost")
                theme = window.findChild(QObject, "darkModeSwitch")
                theme.setProperty("checked", True)
                QMetaObject.invokeMethod(theme, "toggled")
                self.assertAlmostEqual(window.property("glassFrost"), 0)
                window.changeGlassFrost(QJSValue(35))
                self.assertAlmostEqual(slider.property("value"), 35)
                self.assertAlmostEqual(manager.property("level"), .35)
                window.changeGlassFrost(QJSValue(200))
                self.assertEqual(window.property("glassFrost"), 100)
                window.changeGlassFrost(QJSValue(-1.0))
                self.assertEqual(window.property("glassFrost"), 0)
                window.changeGlassFrost(QJSValue(42))
                # Closing during the debounce interval must flush the final value.
                window.close()
                saved = (folder / "appearance.ini").read_text(encoding="utf-8")
                self.assertIn("glassFrostLight=", saved)
                self.assertIn("glassFrostDark=42", saved)
                self.assertFalse(warnings, warnings)
                self.assertEqual(network.replies, [])
            finally:
                assistant.shutdown()
                backend.shutdown()
                window.close()
                engine.deleteLater()
                QTest.qWait(10)
            engine, window, catalog, backend, assistant, network = factory.make_window(folder)
            try:
                QTest.qWait(40)
                self.assertAlmostEqual(window.property("glassFrost"), 42)
                theme = window.findChild(QObject, "darkModeSwitch")
                theme.setProperty("checked", False)
                QMetaObject.invokeMethod(theme, "toggled")
                self.assertAlmostEqual(window.property("glassFrost"), light)
            finally:
                assistant.shutdown()
                backend.shutdown()
                window.close()
                engine.deleteLater()
                QTest.qWait(10)
