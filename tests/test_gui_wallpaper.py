import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class WallpaperTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows Qt Quick background integration")
    def test_import_render_fit_persistence_fallback_and_frost(self):
        if os.environ.get("ANIMEBT_WALLPAPER_TEST") != "1":
            result=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(Path(__file__).parent),"-p",Path(__file__).name],
                env={**os.environ,"ANIMEBT_WALLPAPER_TEST":"1","ANIMEBT_MODE_QT_TEST":"1","PYTHONUTF8":"1","QT_QPA_PLATFORM":"windows","QT_QUICK_BACKEND":"","QSG_RHI_BACKEND":"d3d11","QT_SCALE_FACTOR":"1"},
                capture_output=True,text=True,encoding="utf8",timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            return
        import hashlib,statistics
        from PySide6.QtCore import QObject,QMetaObject,QUrl,QPointF,Qt
        from PySide6.QtGui import QImage,QPainter,QColor,QImageWriter
        from PySide6.QtQml import QJSValue
        from PySide6.QtTest import QTest
        import test_gui_keyword_search as fixtures
        fixtures.KeywordWindowTest.setUpClass()
        out=Path(__file__).resolve().parents[1]/"artifacts/wallpaper";out.mkdir(parents=True,exist_ok=True)
        report={"kind":"actual Main.qml; generated file fixtures, no network search","formats":[],"frost":[],"warnings":[]}
        def wait_for(predicate):
            for _ in range(300):
                if predicate():return
                QTest.qWait(10)
            self.assertTrue(predicate(),"timed out waiting for asynchronous wallpaper")
        def visual(window,name):
            pending=[window.contentItem()]
            while pending:
                item=pending.pop()
                if item.objectName()==name and item.isVisible():return item
                pending.extend(item.childItems())
            self.fail("missing visual "+name)
        def toggle(window,name,value):
            switch=window.findChild(QObject,name);switch.setProperty("checked",value);self.assertTrue(QMetaObject.invokeMethod(switch,"toggled"));QTest.qWait(90)
        with TemporaryDirectory() as tmp:
            folder=Path(tmp)
            (folder/"appearance.ini").write_text("[General]\ndarkMode=true\nanimations=false\nstartupAnimation=false\n",encoding="utf8")
            picture=QImage(3200,1800,QImage.Format.Format_RGB32)
            painter=QPainter(picture)
            for x in range(0,3200,24):painter.fillRect(x,0,24,1800,QColor("#ed9dcb" if (x//24)%2 else "#315188"))
            painter.end()
            files=[]
            for fmt in ("PNG","JPG","WEBP"):
                self.assertIn(fmt.lower().encode(),[bytes(f).lower() for f in QImageWriter.supportedImageFormats()])
                path=folder/("背景 test."+fmt);self.assertTrue(picture.save(str(path),fmt));files.append(path)
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            engine.warnings.connect(lambda values:report['warnings'].extend(v.toString() for v in values))
            window.resize(1100,740)
            wall=window.findChild(QObject,"wallpaperBackground");picker=window.findChild(QObject,"wallpaperPicker")
            self.assertIsNotNone(picker)
            try:
                for path in files:
                    # Invoke the same accepted callback as a successful local picker.
                    picker.setProperty("selectedFile",QUrl.fromLocalFile(str(path)))
                    self.assertTrue(QMetaObject.invokeMethod(picker,"accepted"))
                    wait_for(lambda:wall.property("active"))
                    QTest.qWait(70)
                    self.assertEqual(window.property("wallpaperSource"),QUrl.fromLocalFile(str(path)))
                    report['formats'].append(path.suffix)
                size=wall.property("decodedSize");budget=wall.property("decodeEdge")
                self.assertLessEqual(max(size.width(),size.height()),budget)
                self.assertLessEqual(budget,4096)
                self.assertAlmostEqual(size.width()/size.height(),3200/1800,places=3)
                report['decode_size']=[size.width(),size.height()]
                report['decode_budget']=budget
                if budget < 3200:self.assertLess(max(size.width(),size.height()),3200)
                window.setWallpaperFit(QJSValue(0));QTest.qWait(100)
                fill=window.grabWindow();fill.save(str(out/'fill.png'))
                window.setWallpaperFit(QJSValue(1));QTest.qWait(100)
                fit=window.grabWindow();fit.save(str(out/'fit.png'))
                self.assertNotEqual(fill.pixelColor(550,710),fit.pixelColor(550,710))
                for w,h in ((740,580),(1300,820),(1100,740)):
                    window.resize(w,h);QTest.qWait(80)
                    self.assertTrue(wall.property("active"));self.assertEqual(wall.property("decodedSize"),size)
                window.setWallpaperFit(QJSValue(0))
                window.changeSearchMode(QJSValue("list"));window.findChild(QObject,"searchField").setProperty("text","wallpaper render fixture")
                with patch.object(backend._pool,"start"):window.submitSearch()
                rows=[{"key":"wallpaper","title":"[GUI fixture] S02E01 [1080p]","category":"独立资源","episode":"01","resolution":"1080p","fansub":"fixture","works":[],"size":"1 GB","date":"","sources":"offline"}]
                backend._receive_progress(backend._generation,(rows,{},False));backend._receive_finished(backend._generation,"")
                QTest.qWait(150)
                for dark in (True,False):
                    toggle(window,"darkModeSwitch",dark)
                    hashes=[];values=[]
                    for value in (0,25,50,75,100):
                        window.changeGlassFrost(QJSValue(value));QTest.qWait(90)
                        frame=window.grabWindow();frame.save(str(out/(('dark' if dark else 'light')+f'-frost-{value:03}.png')))
                        title=visual(window,'resourceTitle');y=round(title.mapToScene(QPointF(0,title.height()/2)).y())
                        red=[frame.pixelColor(x,y).red() for x in range(715,803)]
                        variance=statistics.pstdev(red);values.append(variance)
                        grab=title.grabToImage();wait_for(lambda:not grab.image().isNull())
                        hashes.append(hashlib.sha256(bytes(grab.image().constBits())).hexdigest())
                        report['frost'].append({'dark':dark,'value':value,'red_stddev':variance,'foreground_hash':hashes[-1]})
                    self.assertEqual(len(set(hashes)),1)
                    self.assertLess(values[-1],values[0]*.3)
                popup=window.findChild(QObject,'settingsPopup');QMetaObject.invokeMethod(popup,'open');QTest.qWait(120)
                scroll=visual(window,'wallpaperPreview')
                # Settings use a ScrollView; scroll its content to the wallpaper block.
                node=scroll.parentItem()
                while node and 'QQuickFlickable' not in node.metaObject().className():node=node.parentItem()
                if node:node.setProperty('contentY',max(0,node.property('contentHeight')-node.height()))
                QTest.qWait(100);window.grabWindow().save(str(out/'settings.png'));QMetaObject.invokeMethod(popup,'close')
                window.setWallpaperEnabled(QJSValue(False));wait_for(lambda:not wall.property('active'))
                self.assertEqual(window.property('wallpaperSource'),QUrl.fromLocalFile(str(files[-1])))
                self.assertIn('wallpaperEnabled=false',(folder/'appearance.ini').read_text(encoding='utf8'))
                window.grabWindow().save(str(out/'restored-default.png'))
                window.setWallpaperEnabled(QJSValue(True));wait_for(lambda:wall.property('active'))
                for dark in (True,False):
                    toggle(window,'darkModeSwitch',dark);toggle(window,'liquidGlassSwitch',False)
                    self.assertFalse(wall.property('active'))
                    for name in ('horizontalBackdropBlurShader','verticalBackdropBlurShader','wallpaperShader'):
                        self.assertIsNone(window.findChild(QObject,name))
                    for name in ('horizontalBlurCapture','verticalBlurCapture'):
                        self.assertIsNone(window.findChild(QObject,name).property('sourceItem'))
                    self.assertEqual(window.findChild(QObject,'wallpaperImageSource').property('source'),QUrl(''))
                    self.assertTrue(window.property('wallpaperEnabled'))
                    self.assertIsNone(window.findChild(QObject,'ambientGlassCapture').property('sourceItem'))
                    toggle(window,'liquidGlassSwitch',True);wait_for(lambda:wall.property('active'))
                self.assertFalse(window.selectWallpaper(QJSValue('https://example.invalid/photo.png')))
                window.setWallpaperFit(QJSValue(1));window.saveWallpaper()
                self.assertEqual(network.replies,[])
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            try:
                wall=window.findChild(QObject,'wallpaperBackground');wait_for(lambda:wall.property('active'))
                self.assertTrue(window.property('wallpaperEnabled'));self.assertEqual(window.property('wallpaperFit'),'fit')
                missing=QUrl.fromLocalFile(str(folder/'missing.png')).toString()
                self.assertTrue(window.selectWallpaper(QJSValue(missing)))
                wait_for(lambda:bool(window.property('wallpaperError')))
                self.assertFalse(wall.property('active'))
                self.assertIsNotNone(window.findChild(QObject,'ambientGlassShader'))
                report['missing_file_fallback']=True;report['restart_restored']=True;report['ordinary_theme_suppresses_wallpaper']=True
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
            engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
            try:
                wait_for(lambda:bool(window.property('wallpaperError')))
                self.assertFalse(window.findChild(QObject,'wallpaperBackground').property('active'))
                self.assertIsNotNone(window.findChild(QObject,'ambientGlassShader'))
                report['invalid_file_on_restart_fallback']=True
            finally:
                assistant.shutdown();backend.shutdown();window.close();engine.deleteLater();QTest.qWait(20)
        self.assertFalse(report['warnings'],report['warnings'])
        (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(report,ensure_ascii=False))
