import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class VisualModeTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Native Qt render lifecycle test")
    def test_four_combinations_live_switch_render_release_and_restart(self):
        if os.environ.get("ANIMEBT_VISUAL_MODE_TEST") != "1":
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(Path(__file__).parent),
                                     "-p", Path(__file__).name], capture_output=True, text=True, encoding="utf8", timeout=40,
                env={**os.environ, "ANIMEBT_VISUAL_MODE_TEST":"1", "ANIMEBT_MODE_QT_TEST":"1", "PYTHONUTF8":"1",
                     "QT_QPA_PLATFORM":"windows", "QT_QUICK_BACKEND":"", "QSG_RHI_BACKEND":"d3d11"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return
        from PySide6.QtCore import QObject, QMetaObject
        from PySide6.QtQml import QJSValue
        from PySide6.QtTest import QTest
        import test_gui_keyword_search as fixtures
        fixtures.KeywordWindowTest.setUpClass()
        def items(item):
            yield item
            for child in item.childItems():
                yield from items(child)
        def toggle(window, name, value):
            switch=window.findChild(QObject,name)
            switch.setProperty("checked",value)
            self.assertTrue(QMetaObject.invokeMethod(switch,"toggled"))
            QTest.qWait(120)
        report=[]
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(v.toString() for v in values))
            try:
                window.changeSearchMode(QJSValue("list"))
                window.findChild(QObject,"searchField").setProperty("text","visual mode fixture")
                with patch.object(backend._pool,"start"):window.submitSearch()
                rows=[{"key":"stable","title":"[GUI fixture] Example S02E01 [1080p]","category":"独立资源",
                       "episode":"01","resolution":"1080p","fansub":"fixture","works":[],"size":"1 GB","date":"","sources":"offline"}]
                backend._receive_progress(backend._generation,(rows,{},False));backend._receive_finished(backend._generation,"")
                popup=window.findChild(QObject,"settingsPopup")
                self.assertTrue(QMetaObject.invokeMethod(popup,"open"))
                manager=window.findChild(QObject,"glassThemeManager")
                for glass in (False,True,False):
                    toggle(window,"liquidGlassSwitch",glass)
                    for dark in (False,True):
                        toggle(window,"darkModeSwitch",dark)
                        self.assertEqual(manager.property("enabled"),glass)
                        self.assertEqual(manager.property("liquidGlass"),glass)
                        self.assertEqual(window.findChild(QObject,"glassFrostSlider").isEnabled(),glass)
                        self.assertIsNone(window.findChild(QObject,"glassTransparencySlider"))
                        self.assertEqual(manager.property("tintAmount"),0)
                        self.assertIsNone(window.findChild(QObject,"pageGlassCapture").property("sourceItem"))
                        visual=list(items(window.contentItem()))
                        shaders=[i for i in visual if i.objectName() in ("liquidGlassShader","ambientGlassShader")]
                        captures=[window.findChild(QObject,n).property("sourceItem") for n in ("ambientGlassCapture","pageGlassCapture","dialogGlassCapture")]
                        if glass:
                            self.assertTrue(shaders)
                            self.assertIsNotNone(captures[0])
                        else:
                            self.assertFalse(shaders)
                            self.assertTrue(all(c is None for c in captures))
                            fills=[i for i in visual if i.objectName()=="plainSurface" and i.isVisible()]
                            self.assertTrue(fills)
                            self.assertTrue(all(i.property("color").alphaF()==1 for i in fills))
                        self.assertEqual(backend.resourceModel.rowCount(),1)
                        self.assertEqual(window.findChild(QObject,"searchField").property("text"),"visual mode fixture")
                        self.assertEqual(network.replies,[])
                        report.append({"glass":glass,"dark":dark,"shaders":len(shaders)})
                self.assertFalse(warnings,warnings)
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
            self.assertIn("liquidGlass=false",(folder/"appearance.ini").read_text(encoding="utf8"))
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            try:
                QTest.qWait(120)
                self.assertFalse(window.findChild(QObject,"liquidGlassSwitch").property("checked"))
                self.assertFalse(window.findChild(QObject,"glassThemeManager").property("enabled"))
                self.assertTrue(window.findChild(QObject,"darkModeSwitch").property("checked"))
                self.assertFalse([i for i in items(window.contentItem()) if i.objectName() in ("liquidGlassShader","ambientGlassShader")])
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
        print(json.dumps(report))
