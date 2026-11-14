"""Focused native GUI reading screenshots with offline, explicitly labelled rows."""
import os,sys,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
os.environ.update(QT_QPA_PLATFORM='windows',QT_QUICK_BACKEND='',QSG_RHI_BACKEND='d3d11',ANIMEBT_MODE_QT_TEST='1')
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
from PySide6.QtCore import QObject,QMetaObject,QUrl
from PySide6.QtQml import QJSValue
from PySide6.QtTest import QTest
import test_gui_keyword_search as fixture
fixture.KeywordWindowTest.setUpClass()
out=root/'artifacts/readability-focused';out.mkdir(parents=True,exist_ok=True)
with TemporaryDirectory() as folder:
 folder=Path(folder);(folder/'appearance.ini').write_text('[General]\nliquidGlass=true\nanimations=false\nstartupAnimation=false\ndarkMode=true\n',encoding='utf8')
 engine,w,c,b,a,n=fixture.KeywordWindowTest().make_window(folder)
 try:
  w.resize(1480,940);w.changeSearchMode(QJSValue('list'))
  field=w.findChild(QObject,'searchField');field.setProperty('text','进击的巨人')
  with patch.object(b._pool,'start'):w.submitSearch()
  titles=['[GUI 验收样本] [7³ACG] 剧场版 进击的巨人 完结篇 THE LAST ATTACK / Shingeki no Kyojin Movie [1080p x265 OPUS 2.0]',
          '[GUI 验收样本] [VCB-Studio] 进击的巨人 / Shingeki no Kyojin / 進撃の巨人 10-bit 1080p HEVC BDRip [S1-4 + OADs Fin]',
          '[GUI 验收样本] [字幕组] 中文・日本語・English & 特殊字符 [WEB-DL][繁日双语]']
  rows=[{'key':str(i),'title':titles[i%3],'category':'独立资源','episode':'01','resolution':'1080p','fansub':'GUI fixture',
         'works':[],'size':'1 GB','date':'2026-11-14','sources':'离线显示验收样本'} for i in range(16)]
  b._receive_progress(b._generation,(rows,{},False));b._receive_finished(b._generation,'')
  wallpaper=Path('E:/新建文件夹/719179.png');assert wallpaper.exists()
  w.selectWallpaper(QJSValue(QUrl.fromLocalFile(str(wallpaper)).toString()));QTest.qWait(400)
  popup=w.findChild(QObject,'settingsPopup');QMetaObject.invokeMethod(popup,'open');QTest.qWait(120)
  report={'samples':[],'resource_data':'offline GUI fixture, not live search'}
  for dark in (True,False):
   switch=w.findChild(QObject,'darkModeSwitch');switch.setProperty('checked',dark);QMetaObject.invokeMethod(switch,'toggled')
   for frost in (0,32,100):
    w.changeGlassFrost(QJSValue(frost));QTest.qWait(200)
    view=w.findChild(QObject,'resourceList');view.setProperty('contentY',0);QTest.qWait(120)
    name=('dark' if dark else 'light')+f'-{frost}.png';assert w.grabWindow().save(str(out/name))
    report['samples'].append(name)
  report['bangumi_requests']=len(n.replies)
  pending=[w.contentItem()]
  while pending:
   item=pending.pop()
   if item.objectName()=='resourceTitle' and item.isVisible():
    f=item.property('font');print('Actual title font:',f.family(),f.weight(),f.pixelSize());break
   pending.extend(item.childItems())
 finally:a.shutdown();b.shutdown();w.close();engine.deleteLater();QTest.qWait(30)
(out/'report.json').write_text(json.dumps(report),encoding='utf8');print(report)
