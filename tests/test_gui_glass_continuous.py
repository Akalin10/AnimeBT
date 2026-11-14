import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class ContinuousGlassTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Native RHI GUI test requires Windows")
    def test_menu_contrast_layers_and_continuous_material(self):
        if os.environ.get("ANIMEBT_CONTINUOUS_QT") != "1":
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                                     "-p", Path(__file__).name], capture_output=True, text=True, encoding="utf-8", timeout=35,
                env={**os.environ, "ANIMEBT_CONTINUOUS_QT":"1", "ANIMEBT_MODE_QT_TEST":"1",
                     "QT_QPA_PLATFORM":"windows", "QT_QUICK_BACKEND":"", "QSG_RHI_BACKEND":"d3d11", "PYTHONUTF8":"1"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from PySide6.QtCore import QObject, QMetaObject, QPointF, Qt
        from PySide6.QtQml import QJSValue
        from PySide6.QtTest import QTest
        from animebt.gui.title_format import contrast
        import test_gui_keyword_search as fixtures
        fixtures.KeywordWindowTest.setUpClass()
        def visual_items(item):
            yield item
            for child in item.childItems():
                yield from visual_items(child)
        output = Path(__file__).resolve().parents[1] / "artifacts/glass-continuous"
        output.mkdir(parents=True, exist_ok=True)
        report = []
        with TemporaryDirectory() as tmp:
            engine, window, catalog, backend, assistant, network = fixtures.KeywordWindowTest().make_window(Path(tmp))
            warnings = []
            engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
            try:
                window.changeSearchMode(QJSValue("list"))
                window.findChild(QObject, "searchField").setProperty("text", "界面验证样本")
                with patch.object(backend._pool, "start"):
                    window.submitSearch()
                rows = [{"key":str(i), "title":"背景文字干扰样本 BACKGROUND TEXT [S02E01][1080p]", "category":"独立资源" if i%2 else "合集资源",
                         "episode":"01", "resolution":"1080p", "fansub":"测试组", "works":[], "size":"1 GB", "date":"", "sources":"离线界面测试"} for i in range(60)]
                backend._receive_progress(backend._generation, (rows, {}, False))
                backend._receive_finished(backend._generation, "")
                QTest.qWait(350)
                for dark in (False, True):
                    switch = window.findChild(QObject, "darkModeSwitch")
                    switch.setProperty("checked", dark)
                    QMetaObject.invokeMethod(switch, "toggled")
                    QTest.qWait(160)
                    combo = window.findChild(QObject, "分类Filter")
                    point = combo.mapToScene(QPointF(combo.width()/2, combo.height()/2)).toPoint()
                    QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point)
                    QTest.qWait(200)
                    popup = combo.findChild(QObject, "glassOptions")
                    self.assertTrue(popup.property("visible"))
                    image = window.grabWindow()
                    ratio = image.width()/window.width()
                    items = [item for item in visual_items(window.contentItem()) if "GlassMenuItem" in item.metaObject().className()
                             and item.property("visible") and item.width()>0]
                    self.assertGreaterEqual(len(items), 3)
                    values = []
                    borders = 0
                    for item in items:
                        foreground = item.property("contentItem").property("color")
                        point = item.mapToScene(QPointF(item.width()-38, item.height()/2))
                        background = image.pixelColor(round(point.x()*ratio), round(point.y()*ratio))
                        values.append(contrast(foreground.name(), background.name()))
                        body = item.property("background")
                        if body.property("outline").alphaF()>0:
                            borders += 1
                    self.assertGreaterEqual(min(values), 4.5)
                    self.assertLessEqual(borders, 1)
                    theme = "dark" if dark else "light"
                    image.save(str(output/f"dropdown-{theme}.png"))
                    report.append({"theme":theme,"minimum_sampled_text_contrast":min(values),"items":len(items),"focus_borders":borders})
                    QMetaObject.invokeMethod(popup, "close")
                    QTest.qWait(100)
                self.assertFalse(warnings, warnings)
                self.assertEqual(len(network.replies), 0)
                (output/"menu-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2),encoding="utf-8")
                print(json.dumps(report, ensure_ascii=False))
            finally:
                assistant.shutdown()
                backend.shutdown()
                window.close()
                engine.deleteLater()
                QTest.qWait(10)
