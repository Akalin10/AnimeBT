import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

class WallpaperBrightnessTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows native wall rendering")
    def test_bounds_live_drag_foreground_shadow_and_restart(self):
        if os.environ.get("ANIMEBT_BRIGHTNESS_TEST") != "1":
            result=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(Path(__file__).parent),"-p",Path(__file__).name],
                env={**os.environ,"ANIMEBT_BRIGHTNESS_TEST":"1","ANIMEBT_MODE_QT_TEST":"1","PYTHONUTF8":"1","QT_QPA_PLATFORM":"windows","QT_QUICK_BACKEND":"","QSG_RHI_BACKEND":"d3d11","QT_SCALE_FACTOR":"1"},
                capture_output=True,text=True,encoding="utf8",timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return
        import hashlib
        from PySide6.QtCore import QObject,QUrl,QMetaObject,QPointF,Qt
        from PySide6.QtGui import QImage,QPainter,QColor
        from PySide6.QtQml import QJSValue
        from PySide6.QtTest import QTest
        import test_gui_keyword_search as fixtures
        fixtures.KeywordWindowTest.setUpClass()
        out=Path(__file__).resolve().parents[1]/"artifacts/wallpaper-brightness";out.mkdir(parents=True,exist_ok=True)
        report={"samples":[],"warnings":[]}
        def wait_for(predicate):
            for _ in range(400):
                if predicate():return
                QTest.qWait(10)
            self.assertTrue(predicate())
        def find(window,name):
            pending=[window.contentItem()]
            while pending:
                item=pending.pop()
                if item.objectName()==name and item.isVisible():return item
                pending.extend(item.childItems())
            self.fail(name)
        def toggle(window,name,value):
            obj=window.findChild(QObject,name);obj.setProperty('checked',value);QMetaObject.invokeMethod(obj,'toggled');QTest.qWait(60)
        def glyph_hash(title):
            grab=title.grabToImage();wait_for(lambda:not grab.image().isNull())
            return hashlib.sha256(bytes(grab.image().constBits())).hexdigest()
        with TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'appearance.ini').write_text('[General]\ndarkMode=true\nanimations=false\nstartupAnimation=false\n',encoding='utf8')
            files={}
            for kind,base in [('white','#ffffff'),('black','#000000'),('complex','#ca89a6')]:
                image=QImage(1600,900,QImage.Format.Format_RGB32);image.fill(QColor(base))
                if kind=='complex':
                    painter=QPainter(image)
                    for i in range(36):
                        painter.fillRect(i*47,0,22,900,QColor('#e4b3cf' if i%2 else '#304d75'))
                        painter.setPen(QColor('#f7e9f2'));painter.drawEllipse(i*43,50+(i%5)*120,200,180)
                    painter.end()
                path=folder/(kind+'.png');self.assertTrue(image.save(str(path)));files[kind]=path
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            engine.warnings.connect(lambda warnings:report['warnings'].extend(v.toString() for v in warnings))
            window.resize(1100,740)
            wall=window.findChild(QObject,'wallpaperBackground')
            try:
                self.assertEqual(window.property('wallpaperBrightness'),100)
                window.changeSearchMode(QJSValue('list'));field=window.findChild(QObject,'searchField');field.setProperty('text','文字阅读 日本語 English')
                with patch.object(backend._pool,'start'):window.submitSearch()
                rows=[{'key':'brightness','title':'[测试字幕组] 中文 / 日本語 / Example S02E01 [1080p]','category':'独立资源','episode':'01','resolution':'1080p','fansub':'fixture','works':[],'size':'1 GB','date':'','sources':'offline'}]
                backend._receive_progress(backend._generation,(rows,{},False));backend._receive_finished(backend._generation,'')
                for kind,path in files.items():
                    window.selectWallpaper(QJSValue(QUrl.fromLocalFile(str(path)).toString()));wait_for(lambda:wall.property('active'))
                    QTest.qWait(100)
                    for dark in (False,True):
                        toggle(window,'darkModeSwitch',dark)
                        hashes=[];background=[]
                        for level in (100,0):
                            window.setWallpaperBrightness(QJSValue(level));QTest.qWait(90)
                            title=find(window,'resourceTitle');self.assertTrue(title.property('wallpaperShadowActive'))
                            self.assertEqual(title.opacity(),1)
                            self.assertIsNone(window.findChild(QObject,'fieldTextShadow'))
                            button=window.findChild(QObject,'searchButton').property('contentItem')
                            self.assertTrue(button.property('wallpaperShadowActive'))
                            hashes.append(glyph_hash(title))
                            frame=window.grabWindow();frame.save(str(out/(kind+('-dark' if dark else '-light')+f'-{level}.png')))
                            color=frame.pixelColor(550,690);background.append([color.red(),color.green(),color.blue()])
                            self.assertAlmostEqual(wall.property('shadeOpacity'),.6*(1-level/100))
                            report['samples'].append({'background':kind,'dark':dark,'brightness':level,'pixel':background[-1],'foreground_hash':hashes[-1]})
                        self.assertEqual(len(set(hashes)),1)
                        if kind=='white':
                            self.assertEqual(background[0],[255,255,255])
                            self.assertTrue(all(abs(v-102)<=1 for v in background[1]),background)
                        elif kind=='black':self.assertEqual(background,[[0,0,0],[0,0,0]])
                        else:
                            for a,b in zip(background[0],background[1]):self.assertAlmostEqual(b,a*.4,delta=1.5)
                popup=window.findChild(QObject,'settingsPopup');QMetaObject.invokeMethod(popup,'open');QTest.qWait(60)
                slider=window.findChild(QObject,'wallpaperBrightnessSlider');node=slider.parentItem()
                while node and 'QQuickFlickable' not in node.metaObject().className():node=node.parentItem()
                if node:node.setProperty('contentY',max(0,node.property('contentHeight')-node.height()))
                QTest.qWait(70)
                handle=slider.property('handle');samples=[]
                p=slider.mapToScene(QPointF(slider.property('leftPadding')+handle.width()/2,slider.height()/2)).toPoint()
                QTest.mousePress(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,p)
                for fraction in (.25,.5,.75,1):
                    x=slider.property('leftPadding')+handle.width()/2+fraction*(slider.property('availableWidth')-handle.width())
                    p=slider.mapToScene(QPointF(x,slider.height()/2)).toPoint();QTest.mouseMove(window,p,20)
                    samples.append(window.property('wallpaperBrightness'))
                QTest.mouseRelease(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,p)
                self.assertEqual(len(set(samples)),4);self.assertTrue(all(a<b for a,b in zip(samples,samples[1:])),samples)
                report['drag_samples']=samples
                window.grabWindow().save(str(out/'settings.png'));QMetaObject.invokeMethod(popup,'close')
                window.setWallpaperBrightness(QJSValue(150));self.assertEqual(window.property('wallpaperBrightness'),100)
                window.setWallpaperBrightness(QJSValue(-5.0));self.assertEqual(window.property('wallpaperBrightness'),0)
                window.setWallpaperBrightness(QJSValue(37.5))
                self.assertEqual(network.replies,[])
                window.setWallpaperEnabled(QJSValue(False));QTest.qWait(70)
                self.assertFalse(find(window,'resourceTitle').property('wallpaperShadowActive'))
                window.setWallpaperEnabled(QJSValue(True));wait_for(lambda:wall.property('active'))
                toggle(window,'liquidGlassSwitch',False)
                self.assertFalse(find(window,'resourceTitle').property('wallpaperShadowActive'))
                toggle(window,'liquidGlassSwitch',True);wait_for(lambda:wall.property('active'))
                self.assertFalse(report['warnings'],report['warnings'])
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
            self.assertIn('wallpaperBrightness=37.5',(folder/'appearance.ini').read_text(encoding='utf8'))
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            try:
                wait_for(lambda:window.findChild(QObject,'wallpaperBackground').property('active'))
                self.assertEqual(window.property('wallpaperBrightness'),37.5)
                report['restart_restored']=True
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
