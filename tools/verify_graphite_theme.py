"""Actual Main.qml visual verification; cached real covers and labelled offline rows.

No API search, desktop capture or user settings are used. Covers are decoded
from the existing Qt disk cache without changing it or requesting the network.
"""
import json,os,re,sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
os.environ['QT_QPA_PLATFORM']='windows';os.environ['QT_QUICK_BACKEND']='';os.environ['QSG_RHI_BACKEND']='d3d11';os.environ['ANIMEBT_MODE_QT_TEST']='1'
from PySide6.QtCore import QObject,QMetaObject,QPointF,QUrl,Qt
from PySide6.QtGui import QImage
from PySide6.QtNetwork import QNetworkDiskCache
from PySide6.QtQml import QJSValue,QQmlComponent
from PySide6.QtTest import QTest
import test_gui_keyword_search as fixtures
fixtures.KeywordWindowTest.setUpClass()
scale=fixtures.KeywordWindowTest.app.primaryScreen().devicePixelRatio()
out=root/('artifacts/graphite-theme' if scale==1 else f'artifacts/graphite-theme-dpi{round(scale*100)}');out.mkdir(parents=True,exist_ok=True)
if '--plain' in sys.argv:
    out=root/('artifacts/plain-theme' if scale==1 else f'artifacts/plain-theme-dpi{round(scale*100)}');out.mkdir(parents=True,exist_ok=True)
if '--frost' in sys.argv:
    out=root/('artifacts/clear-tinted-light' if '--light-frost' in sys.argv else 'artifacts/clear-tinted');out.mkdir(parents=True,exist_ok=True)
if '--stripes' in sys.argv:
    out=root/'artifacts/full-transmission-stripes';out.mkdir(parents=True,exist_ok=True)
cache_dir=Path(os.environ['LOCALAPPDATA'])/'AnimeBT/cache/bangumi-covers'
cache=QNetworkDiskCache();cache.setCacheDirectory(str(cache_dir))
assets=out/'cached-covers';assets.mkdir(exist_ok=True)
subjects=[];ids=set()
for file in cache_dir.rglob('*.d'):
    match=re.search(rb'https://lain\.bgm\.tv/[^\x00\s]+',file.read_bytes()[:1000])
    if not match:continue
    url=match[0].decode('ascii',errors='ignore')
    id_match=re.search(r'/([0-9]+)_',url)
    if not id_match or '/cover/l/' not in url:continue
    subject_id=int(id_match[1])
    if subject_id in ids:continue
    device=cache.data(QUrl(url))
    if device is None:continue
    img=QImage.fromData(device.readAll());device.deleteLater()
    if img.isNull() or img.width()<250 or img.height()<img.width():continue
    ids.add(subject_id);path=assets/f'{subject_id}.png';img.save(str(path))
    subjects.append({'id':subject_id,'title':f'缓存海报 #{subject_id}','original':'本地真实封面 · 排版验收','season':'离线 GUI 检查','cover':QUrl.fromLocalFile(str(path)).toString(),'coverAlternatives':[]})
    if len(subjects)>=18:break
assert len(subjects)>=8,'not enough actual cached covers'
report={'cover_origin':'existing real Bangumi Qt cache; labels are explicitly offline layout fixtures','covers':len(subjects),'warnings':[],'screens':[]}
with TemporaryDirectory() as tmp:
    folder=Path(tmp);(folder/'appearance.ini').write_text('[General]\ndarkMode=true\nanimations=false\nstartupAnimation=false\nposterSizeStep=1\n',encoding='utf8')
    engine,window,catalog,backend,assistant,network=fixtures.KeywordWindowTest().make_window(folder)
    engine.warnings.connect(lambda values:report['warnings'].extend(v.toString() for v in values))
    pool_patch=patch.object(backend._pool,"start");page_jobs=pool_patch.start()
    catalog_pool_patch=patch.object(backend._catalog_pool,"start");catalog_jobs=catalog_pool_patch.start()
    area=fixtures.KeywordWindowTest.app.primaryScreen().availableGeometry()
    window.resize(min(1500,area.width()-40),min(920,area.height()-40));window.requestActivate()
    def find_visual(name):
        pending=[window.contentItem()];matches=[]
        while pending:
            item=pending.pop()
            if item.objectName()==name and item.isVisible():
                center=item.mapToScene(QPointF(item.width()/2,item.height()/2))
                if 15<center.x()<window.width()-15 and 15<center.y()<window.height()-25:
                    matches.append((center.y(),item))
            pending.extend(item.childItems())
        assert matches,"Missing visible item: "+name
        return min(matches,key=lambda pair:pair[0])[1]
    def shot(name):
        QTest.qWait(220)
        if '--plain' in sys.argv:
            manager=window.findChild(QObject,'glassThemeManager')
            assert not manager.property('enabled') and not manager.property('liquidGlass')
            for capture in ('ambientGlassCapture','pageGlassCapture','dialogGlassCapture'):
                assert window.findChild(QObject,capture).property('sourceItem') is None,capture
            pending=[window.contentItem()];shaders=[];fills=[]
            while pending:
                item=pending.pop();pending.extend(item.childItems())
                if item.objectName() in ('liquidGlassShader','ambientGlassShader'):shaders.append(item)
                if item.objectName()=='plainSurface' and item.isVisible():fills.append(item)
            assert not shaders,'optical shader remains instantiated'
            assert fills and all(i.property('color').alphaF()==1 for i in fills)
            report['plain_render_check']={'optical_shaders':len(shaders),'capture_sources':0,'opaque_surfaces':len(fills)}
        window.grabWindow().save(str(out/(name+'.png')));report['screens'].append(name)
    def theme(dark):
        switch=window.findChild(QObject,'darkModeSwitch');switch.setProperty('checked',dark);QMetaObject.invokeMethod(switch,'toggled')
    stripe=None
    if '--stripes' in sys.argv:
        component=QQmlComponent(engine)
        component.setData(b'import QtQuick; Item { anchors.fill: parent; z: 100; property real shift: 0; Repeater { model: Math.ceil(parent.width/40)+2; Rectangle { required property int index; x:index*40-parent.shift; width:40; height:parent.height; color:index%2 ? "white" : "black" } } }',QUrl())
        assert not component.errors(),component.errors()
        stripe=component.create();stripe.setParentItem(window.findChild(QObject,'glassBackdropLayer'))
        optics=window.findChild(QObject,'glassThemeManager');optics.setProperty('blurStrength',0)
    try:
        if '--plain' in sys.argv:
            switch=window.findChild(QObject,'liquidGlassSwitch');switch.setProperty('checked',False);QMetaObject.invokeMethod(switch,'toggled')
        shot('dark-home')
        window.findChild(QObject,'searchField').setProperty('text','缓存封面排版验收')
        catalog._keyword='缓存封面排版验收';catalog._results=subjects;catalog._status='ready';catalog.changed.emit()
        backend._receive_catalog_finished(backend._catalog_generation)
        for subject in subjects:backend.catalogModel.append(subject)
        QTest.qWait(900);shot('dark-posters')
        popup=window.findChild(QObject,'settingsPopup');QMetaObject.invokeMethod(popup,'open');shot('dark-settings');QMetaObject.invokeMethod(popup,'close')
        ai=window.findChild(QObject,'titleSettingsDialog');QMetaObject.invokeMethod(ai,'open');shot('dark-ai');QMetaObject.invokeMethod(ai,'close')
        rows=[{'key':str(i),'title':'[本地界面验收] 中日英混排 / 日本語 / Example Anime S02 - %02d [1080p][HEVC][CHS]'%(i+1),
               'category':'合集资源' if i%3==0 else '独立资源','season_values':[2], 'episode':str(i+1),'resolution':'1080p','fansub':'界面测试组',
               'works':[],'size':'1.2 GB','date':'2026-11-13','sources':'离线 GUI 样本'} for i in range(30)]
        with patch.object(backend._pool,'start'):backend.openSubject(subjects[0],[])
        backend._receive_progress(backend._generation,(rows,{},False));backend._receive_finished(backend._generation,'')
        shot('dark-details')
        thumbnail=find_visual('resourceThumbnail')
        hover_point=thumbnail.mapToScene(QPointF(thumbnail.width()/2,thumbnail.height()/2)).toPoint()
        QTest.mouseMove(window,hover_point);QTest.qWait(720);shot('dark-tooltip')
        QTest.mouseMove(window,QPointF(600,80).toPoint());QTest.qWait(250)
        title=find_visual('resourceTitle');menu_point=title.mapToScene(QPointF(100,title.height()/2)).toPoint()
        QTest.mouseClick(window,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier,menu_point);shot('dark-resource-menu');assert window.findChild(QObject,'resourceMenu').property('visible');QTest.keyClick(window,Qt.Key.Key_Escape)
        backend._sources=[{'name':'离线状态样本 A','status':'样式验收','count':0,'error':'','keywords':''},
                          {'name':'离线状态样本 B','status':'错误态验收','count':0,'error':'仅用于配色检查','keywords':''}]
        backend.changed.emit();resource_page=find_visual('resourcePage');resource_page.setProperty('showSources',True)
        shot('dark-source-status');resource_page.setProperty('showSources',False);backend._sources=[];backend.changed.emit()
        combo=window.findChild(QObject,'分类Filter');point=combo.mapToScene(QPointF(combo.width()/2,combo.height()/2)).toPoint()
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point);shot('dark-dropdown');QTest.keyClick(window,Qt.Key.Key_Escape)
        window.changeSearchMode(QJSValue('list'))
        with patch.object(backend._pool,'start'):
            window.findChild(QObject,'searchField').setProperty('text','离线 GUI 检查');window.submitSearch()
        backend._receive_progress(backend._generation,(rows,{},False));backend._receive_finished(backend._generation,'')
        QTest.qWait(200)
        report['completed_loading_height']=find_visual('resourcePage').property('loadingHeight')
        assert report['completed_loading_height']==0
        shot('dark-list')
        if '--frost' in sys.argv:
            if '--light-frost' in sys.argv:theme(False)
            report['frost_theme']='light' if '--light-frost' in sys.argv else 'dark'
            import statistics
            # This is a live QML pattern in the app's actual material source.
            component=QQmlComponent(engine)
            component.setData(b'import QtQuick; Item { anchors.fill: parent; z:100; Repeater { model: Math.ceil(parent.width/16); Rectangle { required property int index; x:index*16; width:16; height:parent.height; color:index%2 ? "#ed9dcb" : "#315188" } } }',QUrl())
            assert not component.errors(),component.errors()
            frost_pattern=component.create();frost_pattern.setParentItem(window.findChild(QObject,'glassBackdropLayer'))
            QMetaObject.invokeMethod(popup,'open');QTest.qWait(150)
            slider=window.findChild(QObject,'glassFrostSlider');manager=window.findChild(QObject,'glassThemeManager')
            report['frost_levels']=[]
            for level in (0,25,50,75,100):
                handle_width=slider.property('handle').width()
                x=slider.property('leftPadding')+handle_width/2+level/100*(slider.property('availableWidth')-handle_width)
                point=slider.mapToScene(QPointF(x,slider.height()/2)).toPoint()
                QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
                QTest.qWait(150);shot('frost-%03d'%level)
                actual=window.property('glassFrost');assert abs(actual-level)<1,(actual,level)
                img=window.grabWindow();title=find_visual('resourceTitle');yy=round(title.mapToScene(QPointF(0,title.height()/2)).y())
                values=[img.pixelColor(xx,yy).red() for xx in range(round(window.width()*.65),round(window.width()*.73))]
                report['frost_levels'].append({'requested':level,'actual':actual,'blur_radius':manager.property('blurRadius'),'red_stddev':statistics.pstdev(values),'red_mean':statistics.mean(values),'foreground_opacity':title.opacity()})
                assert title.opacity()==1
                import hashlib
                grab=title.grabToImage()
                for attempt in range(50):
                    if not grab.image().isNull():break
                    QTest.qWait(10)
                assert not grab.image().isNull()
                report['frost_levels'][-1]['foreground_hash']=hashlib.sha256(bytes(grab.image().constBits())).hexdigest()
            assert len({v['foreground_hash'] for v in report['frost_levels']})==1,'foreground glyph rendering changed'
            spread=[v['red_stddev'] for v in report['frost_levels']]
            assert all(b<=max(1.0,a) for a,b in zip(spread,spread[1:])),spread
            assert spread[-1]<spread[0]*.25,spread
            point=slider.mapToScene(QPointF(slider.width()*.4,slider.height()/2)).toPoint()
            QTest.mousePress(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            continuous=[]
            for fraction in (.371,.383,.397,.416):
                x=slider.property('leftPadding')+fraction*slider.property('availableWidth')
                QTest.mouseMove(window,slider.mapToScene(QPointF(x,slider.height()/2)).toPoint(),20)
                continuous.append(window.property('glassFrost'))
            QTest.mouseRelease(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            assert len(set(continuous))==4,continuous
            report['continuous_drag_values']=continuous
            QMetaObject.invokeMethod(popup,'close');frost_pattern.setVisible(False)
            window.changeGlassFrost(QJSValue(0))
            theme(True)
        if stripe is not None:
            optics.setProperty('refractionStrength',0);optics.setProperty('edgeStrength',0)
            shot('stripe-zero-refraction');baseline=window.grabWindow()
            title=find_visual('resourceTitle');y=round(title.mapToScene(QPointF(0,title.height()/2)).y())
            xs=range(round(window.width()*.72),round(window.width()*.92))
            values=[baseline.pixelColor(x,y).red() for x in xs]
            assert min(values)<8 and max(values)>247,('central transmission lost',min(values),max(values))
            optics.setProperty('refractionStrength',2);shot('stripe-refracted');warped=window.grabWindow()
            delta=sum(abs(baseline.pixelColor(x,y).red()-warped.pixelColor(x,y).red()) for x in xs)/len(xs)
            assert delta>1,('no center refraction',delta)
            stripe.setProperty('shift',15);shot('stripe-background-moved');moved=window.grabWindow()
            motion=sum(abs(warped.pixelColor(x,y).red()-moved.pixelColor(x,y).red()) for x in xs)/len(xs)
            assert motion>20,('stale capture',motion)
            report['actual_resource_center']={'black':min(values),'white':max(values),'refraction_difference':delta,'background_motion_difference':motion,'sample_y':y}
            report['actual_component_ranges']={}
            for name in ('titleBarGlass','searchGlass','comboGlass','resourceCardGlass'):
                item=find_visual(name);a=item.mapToScene(QPointF(item.width()*.25,item.height()*.5));b=item.mapToScene(QPointF(item.width()*.75,item.height()*.5))
                vals=[moved.pixelColor(x,round(a.y())).red() for x in range(round(a.x()),round(b.x()))]
                report['actual_component_ranges'][name]={'minimum':min(vals),'maximum':max(vals)}
            optics.setProperty('refractionStrength',1);optics.setProperty('edgeStrength',.75)

        field=window.findChild(QObject,'searchField');menu_point=field.mapToScene(QPointF(90,field.height()/2)).toPoint()
        QTest.mouseClick(window,Qt.MouseButton.RightButton,Qt.KeyboardModifier.NoModifier,menu_point);shot('dark-search-menu');QTest.keyClick(window,Qt.Key.Key_Escape)
        theme(False);shot('light-list');QMetaObject.invokeMethod(popup,'open');shot('light-settings');QMetaObject.invokeMethod(popup,'close')
        QMetaObject.invokeMethod(ai,'open');shot('light-ai');QMetaObject.invokeMethod(ai,'close')
        window.resize(740,580);shot('light-compact');theme(True);shot('dark-compact')
        report['resources']=backend.resourceModel.rowCount();report['network_requests']=len(network.replies)
        report['blocked_bt_jobs']=page_jobs.call_count+catalog_jobs.call_count
        assert not report['warnings'],report['warnings']
        assert report['resources']==len(rows)
    finally:
        assistant.shutdown();backend.shutdown();window.close();pool_patch.stop();catalog_pool_patch.stop()
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False,indent=2))
