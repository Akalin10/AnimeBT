import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

class PlainDarkPaletteTest(unittest.TestCase):
    def test_protected_palettes_and_graphite_contrast(self):
        if os.environ.get("ANIMEBT_PALETTE_TEST") != "1":
            result=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(Path(__file__).parent),"-p",Path(__file__).name],
                env={**os.environ,"ANIMEBT_PALETTE_TEST":"1","QT_QPA_PLATFORM":"offscreen","QT_QUICK_BACKEND":"software","PYTHONUTF8":"1"},
                capture_output=True,text=True,encoding="utf8",timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return
        from PySide6.QtGui import QGuiApplication,QColor
        from PySide6.QtQml import QQmlEngine,QQmlComponent
        from PySide6.QtCore import QUrl
        from animebt.gui.title_format import contrast
        app=QGuiApplication.instance() or QGuiApplication([])
        engine=QQmlEngine();root=Path(__file__).resolve().parents[1]
        component=QQmlComponent(engine,QUrl.fromLocalFile(str(root/"animebt/gui/qml/GlassTheme.qml")))
        self.assertFalse(component.errors(),component.errors())
        obj=component.create()
        baseline=json.loads((root/"tests/fixtures/protected_theme_palette.json").read_text(encoding="utf8"))
        for glass,dark,key in [(False,False,"plain-light"),(True,False,"glass-light"),(True,True,"glass-dark")]:
            obj.setProperty("liquidGlass",glass);obj.setProperty("dark",dark)
            self.assertFalse(obj.property("plainDark"))
            for name,expected in baseline[key].items():
                actual=obj.property(name)
                if isinstance(actual,QColor):actual=actual.name(QColor.NameFormat.HexArgb)
                self.assertEqual(actual,expected,(key,name))
        obj.setProperty("liquidGlass",False);obj.setProperty("dark",True)
        self.assertTrue(obj.property("plainDark"))
        for name in ("backgroundTop","backgroundMiddle","backgroundBottom","panel","panelSoft","panelFaint","controlBase","field","popup","line","frame"):
            color=obj.property(name)
            self.assertEqual(color.alpha(),255,name)
            self.assertLessEqual(max(color.red(),color.green(),color.blue())-min(color.red(),color.green(),color.blue()),9,name)
        for ink,paper in [("ink","panel"),("muted","panel"),("accentText","controlSelected"),("accentInk","accent")]:
            self.assertGreaterEqual(contrast(obj.property(ink).name(),obj.property(paper).name()),4.5,(ink,paper))
        obj.deleteLater();engine.deleteLater()
