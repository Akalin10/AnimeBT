"""Native Windows GUI spinner regression; offline backend, isolated settings."""
import os,sys,json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
os.environ.update(QT_QPA_PLATFORM='windows',QSG_RHI_BACKEND='d3d11',ANIMEBT_MODE_QT_TEST='1')
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
from PySide6.QtCore import QObject
from PySide6.QtQml import QJSValue
from PySide6.QtTest import QTest
import test_gui_keyword_search as fixture
fixture.KeywordWindowTest.setUpClass()
out=root/'artifacts/spinner-fallback';out.mkdir(parents=True,exist_ok=True)
with TemporaryDirectory() as folder:
 folder=Path(folder);(folder/'appearance.ini').write_text('[General]\nliquidGlass=false\nanimations=true\nstartupAnimation=false\ndarkMode=true\n',encoding='utf8')
 engine,w,c,b,a,n=fixture.KeywordWindowTest().make_window(folder)
 try:
  w.setProperty('startupMotionAllowed',True);w.changeSearchMode(QJSValue('list'))
  field=w.findChild(QObject,'searchField');field.setProperty('text','进击的巨人')
  with patch.object(b._pool,'start'):w.submitSearch()
  QTest.qWait(400)
  box=w.findChild(QObject,'resourceLoadingBox');spinner=box.findChild(QObject,'searchLoadingSpinner')
  assert box.isVisible() and box.property('animate')
  samples=[]
  for _ in range(4):samples.append(spinner.property('rotation'));QTest.qWait(140)
  assert len(set(round(x) for x in samples))>1,samples
  w.grabWindow().save(str(out/'plain-dark-loading.png'))
  page=w.findChild(QObject,'resourcePage');page.setProperty('loadingMotionAllowed',False);QTest.qWait(100)
  first=spinner.property('rotation');QTest.qWait(150);assert abs(first-spinner.property('rotation'))<.1
  b.cancelSearch();QTest.qWait(350);assert not box.isVisible()
  report={'plain_dark_rotations':samples,'reduced_motion_stops':True,'cancel_hides':True,'bangumi_requests':len(n.replies)}
 finally:
  a.shutdown();b.shutdown();w.close();engine.deleteLater();QTest.qWait(30)
(out/'report.json').write_text(json.dumps(report),encoding='utf8');print(report)
