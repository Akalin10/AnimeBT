"""Independent desktop optics experiment; never imported by AnimeBT.

Qt 6.12 Windows x64 only: ctypes calls Qt's public exported fromNative because
PySide does not bind QNativeInterface::QSGD3D11Texture. The export ABI is pinned;
a production integration needs an SDK-built Qt C++ plugin, not this bridge.
"""
import argparse, ctypes as C, json, os, sys, time
from pathlib import Path
os.environ['QSG_RHI_BACKEND']='d3d11'
os.environ['QSG_RENDER_LOOP']='basic'  # Python SG callbacks must not deadlock on GIL.
os.environ.pop('QT_QUICK_BACKEND',None)
import PySide6, shiboken6
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, QUrl, QRectF, QPoint, Qt, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickItem, QSGSimpleTextureNode, QSGTexture, QSGRendererInterface
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
import logging
log=logging.getLogger(__name__)
class Size(C.Structure): _fields_=[('w',C.c_int),('h',C.c_int)]
class Bridge(QObject):
    changed=Signal()
    def __init__(self, parent=None, native_path=None, measure=False, allow_monitor_rebind=False):
        super().__init__(parent);self.native_path=Path(native_path) if native_path else Path(__file__).parent/"native/desktop_capture.dll";self.measure=measure;self.allow_monitor_rebind=allow_monitor_rebind
        self.failed=False;self.enabled=False;self.ready=False;self.error='Capture disabled';self.item=None
        self.frames=0;self.ages=[];self.intervals=[];self.last=0.;self.pointer=0;self.rect=[0]*6
        self._timer=QTimer(self);self._timer.setInterval(16);self._timer.timeout.connect(self.heartbeat)
        self.started=0.;self.input_delays=[];self._sequence=0;self.gpu=[];self.vram=[];self.slow=0;self.swap_times=[];self.active_time=0.;self.active_since=0.
    @Property(bool, constant=True)
    def supported(self):
        return self.supportReason==""
    @Property(str, constant=True)
    def supportReason(self):
        if sys.platform!="win32":return "仅支持 Windows"
        if sys.getwindowsversion().build<19041:return "需要 Windows 10 2004 或更新系统"
        if qVersion()!="6.12.0" or C.sizeof(C.c_void_p)!=8:return "桌面桥接仅验证 Qt 6.12.0 / Windows x64"
        if os.environ.get("QT_QUICK_BACKEND", "").lower()=="software":return "软件渲染不支持桌面折射"
        if os.environ.get("QSG_RHI_BACKEND", "d3d11").lower()!="d3d11":return "当前图形后端不是 D3D11"
        if os.environ.get("QSG_RENDER_LOOP", "").lower()!="basic":return "桌面桥接需要 basic 渲染循环"
        if not self.native_path.is_file():return "未构建桌面捕获模块"
        return ""
    @Slot(bool)
    def setEnabled(self,enabled):
        self.start() if enabled else self.stop()
    @Slot()
    def shutdown(self):
        self.stop()
        if self.item:self.item.shutdown()
    @Property(str,notify=changed)
    def displayMessage(self):
        if self.ready:return "真实桌面折射已启用"
        if "Display changed" in self.error:return "显示器已切换，已回退；窗口稳定后可重新开启"
        if "Cross-monitor" in self.error:return "窗口跨越显示器边界，暂用应用内玻璃"
        if self.enabled:return "正在启动桌面捕获…"
        if not self.failed:return "使用应用内玻璃"
        reason=self.error.split(" — ")[0]
        if "0x80070005" in reason:reason="捕获权限被拒绝"
        elif "0x887A0005" in reason or "0x887A0006" in reason:reason="图形设备不可用"
        elif "budget" in reason:reason="持续渲染开销超出预算"
        elif "No desktop frames" in reason:reason="未收到桌面帧"
        return "已回退应用内玻璃："+reason
    failedState=Property(bool,lambda s:s.failed,notify=changed)
    def frame_swapped(self):
        now=time.perf_counter()
        previous=getattr(self,"_last_swap",now)
        self._bad_swaps=getattr(self,"_bad_swaps",0)+1 if self.enabled and now-previous>.05 else 0
        self._last_swap=now
        if self._bad_swaps>=20:self.fail("Sustained rendering budget exceeded")
    active=Property(bool,lambda s:s.enabled,notify=changed)
    available=Property(bool,lambda s:s.ready,notify=changed)
    message=Property(str,lambda s:s.error,notify=changed)
    @Slot()
    def start(self):
        if self.enabled:return
        if not self.supported:
            self.fail(self.supportReason);return
        if getattr(self,"deny",False):self.fail("Simulated permission denied (E_ACCESSDENIED)");return
        self.failed=False;self.slow=0
        self.active_since=time.perf_counter()
        self.error='Starting WGC; window excluded from screen capture';self.enabled=True;self.started=time.perf_counter();self._timer.start();self.changed.emit()
    @Slot()
    def stop(self):
        if self.active_since:self.active_time+=time.perf_counter()-self.active_since;self.active_since=0.
        self.failed=False;self.enabled=False;self.ready=False;self.error='Capture disabled — in-app material'
        if self.item:self.item.pause()
        self._timer.stop()
        self.changed.emit()
    @Slot()
    def heartbeat(self):
        now=time.perf_counter()
        if self.measure and self.last:self.intervals.append((now-self.last)*1000)
        self.last=now
        if self.item:self.item.update()
    @Slot()
    def inputProbe(self):
        # Qt delivery-to-next-frame metric only, not physical input-to-photon.
        self.pointer=time.perf_counter()
    def fail(self,message):
        if self.active_since:self.active_time+=time.perf_counter()-self.active_since;self.active_since=0.
        self.failed=True;self.enabled=False;self.ready=False;self.error=message+' — in-app fallback'
        if self.item:self.item.pause()
        self._timer.stop()
        log.warning("Desktop glass fallback: %s",message)
        self.changed.emit()
class DesktopTexture(QQuickItem):
    def __init__(self,parent=None):
        super().__init__(parent);self.setFlag(QQuickItem.Flag.ItemHasContents,True)
        self.windowChanged.connect(self._window_changed)
        self._native_busy=False;self._pending_pause=False;self._pending_release=False
        self._controller=None;self.capture=None;self.texture=None;self.address=0;self.dll=None;self.last_frame=0.;self.seq=0
    def _window_changed(self, window):
        if window:
            window.sceneGraphInvalidated.connect(self._scene_invalidated,Qt.ConnectionType.DirectConnection)
            window.frameSwapped.connect(self._swapped)
    def _swapped(self):
        if self._controller:self._controller.frame_swapped()
    def _scene_invalidated(self):
        # Runs on the tested basic render loop while SG teardown is safe.
        if self._controller and self._controller.enabled:
            self._controller.fail("Scene Graph invalidated; desktop capture stopped")
        self.release()
    controllerChanged=Signal()
    def get_controller(self):
        return self._controller
    def set_controller(self, value):
        if self._controller is value:
            return
        if self._controller:
            self._controller.stop()
        self._controller=value
        if value:
            value.item=self
        self.controllerChanged.emit()
        self.update()
    controller=Property(QObject,get_controller,set_controller,notify=controllerChanged)
    def load(self):
        if sys.getwindowsversion().build<19041:raise RuntimeError('Windows 10 2004 or newer required for capture exclusion')
        if qVersion()!='6.12.0' or C.sizeof(C.c_void_p)!=8:raise RuntimeError('Native bridge requires Qt 6.12.0 Windows x64')
        os.add_dll_directory(str(Path(PySide6.__file__).parent))
        self.dll=C.WinDLL(str(self._controller.native_path))
        self.dll.dg_create.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(C.c_long)];self.dll.dg_create.restype=C.c_void_p
        self.dll.dg_tick.argtypes=[C.c_void_p,C.POINTER(C.c_int),C.POINTER(C.c_ulonglong),C.POINTER(C.c_longlong)];self.dll.dg_tick.restype=C.c_long
        self.dll.dg_monitor.argtypes=[C.c_void_p];self.dll.dg_monitor.restype=C.c_void_p
        self.user32=C.WinDLL("user32");self.user32.MonitorFromWindow.argtypes=[C.c_void_p,C.c_ulong];self.user32.MonitorFromWindow.restype=C.c_void_p
        self.dll.dg_texture.argtypes=[C.c_void_p];self.dll.dg_texture.restype=C.c_void_p
        self.dll.dg_destroy.argtypes=[C.c_void_p]
        self.dll.dg_pause.argtypes=[C.c_void_p]
        self.dll.dg_gpu_ms.argtypes=[C.c_void_p];self.dll.dg_gpu_ms.restype=C.c_double
        self.dll.dg_vram.argtypes=[C.c_void_p];self.dll.dg_vram.restype=C.c_ulonglong
        self.qt=C.WinDLL(str(Path(PySide6.__file__).parent/'Qt6Quick.dll'))
        self.native=getattr(self.qt,'?fromNative@QSGD3D11Texture@QNativeInterface@@SAPEAVQSGTexture@@PEAXPEAVQQuickWindow@@AEBVQSize@@V?$QFlags@W4CreateTextureOption@QQuickWindow@@@@@Z')
        self.native.argtypes=[C.c_void_p,C.c_void_p,C.POINTER(Size),C.c_int];self.native.restype=C.c_void_p
    def _release_now(self,node=None):
        # WinRT Close can pump window messages. Keep the old node/texture alive
        # until it returns; the busy guard prevents nested capture calls.
        if self.capture:
            handle=self.capture;self.capture=None;self.dll.dg_destroy(handle)
        if node:shiboken6.delete(node)
        if self.texture:shiboken6.delete(self.texture);self.texture=None
        self.address=0
    def release(self,node=None):
        if self._native_busy:
            self._pending_release=True
            return
        self._native_busy=True
        try:self._release_now(node)
        finally:self._native_busy=False
    def updatePaintNode(self,node,data):
        if self._native_busy:return node
        self._native_busy=True
        try:return self._paint(node,data)
        finally:
            self._native_busy=False
            if self._pending_pause:
                self._pending_pause=False;QTimer.singleShot(0,self.pause)
            if self._pending_release:
                self._pending_release=False;QTimer.singleShot(0,self.release)
    def _paint(self,node,data):
        bridge=self._controller
        
        try:
            if bridge is None or not bridge.enabled:
                self._release_now(node);return None
            window=self.window();ri=window.rendererInterface()
            if ri.graphicsApi()!=QSGRendererInterface.GraphicsApi.Direct3D11:raise RuntimeError('D3D11 unavailable')
            if not self.dll:self.load()
            if not self.capture:
                dev=ri.getResource(window,QSGRendererInterface.Resource.DeviceResource)
                hr=C.c_long();self.capture=self.dll.dg_create(int(dev),int(window.winId()),C.byref(hr))
                if not self.capture:raise RuntimeError(f'WGC / exclusion denied: 0x{hr.value & 0xffffffff:08X}')
                self.last_frame=time.perf_counter();self.seq=0
            if not bridge.allow_monitor_rebind:
                actual=self.user32.MonitorFromWindow(int(window.winId()),2)
                if actual!=self.dll.dg_monitor(self.capture):
                    raise RuntimeError("Display changed; desktop capture stopped")
            rect=(C.c_int*6)();count=C.c_ulonglong();stamp=C.c_longlong()
            tick_start=time.perf_counter()
            hr=self.dll.dg_tick(self.capture,rect,C.byref(count),C.byref(stamp))
            elapsed=time.perf_counter()-tick_start;bridge.slow=bridge.slow+1 if elapsed>.05 else 0
            if bridge.slow>20:raise RuntimeError("Sustained capture budget exceeded")
            if hr<0:raise RuntimeError(f'Capture/device error: 0x{hr & 0xffffffff:08X}')
            address=self.dll.dg_texture(self.capture)
            if count.value!=self.seq:
                self.seq=count.value;self.last_frame=time.perf_counter();bridge.frames+=1
                if bridge.measure:
                    gpu=self.dll.dg_gpu_ms(self.capture)
                    if gpu>0:bridge.gpu.append(gpu)
                    if self.seq%30==0:bridge.vram.append(self.dll.dg_vram(self.capture))
                    for sample in (bridge.gpu,bridge.vram,bridge.ages):
                        if len(sample)>4096:del sample[:2048]
                # WGC timestamps use QPC's time base, expressed in 100ns.
                age=(time.perf_counter()-stamp.value/1e7)*1000
                if bridge.measure and 0<=age<5000:bridge.ages.append(age)
            if self.seq==0 and time.perf_counter()-self.last_frame>4:raise RuntimeError('No desktop frames for 4 seconds')
            if address:
                if address!=self.address or (self.texture and (self.texture.textureSize().width()!=rect[4] or self.texture.textureSize().height()!=rect[5])):
                    old_texture=self.texture
                    ptr=self.native(address,shiboken6.getCppPointer(window)[0],C.byref(Size(rect[4],rect[5])),0)
                    if not ptr:raise RuntimeError('Qt native texture import failed')
                    self.texture=shiboken6.wrapInstance(ptr,QSGTexture);self.address=address
                    self.texture.setFiltering(QSGTexture.Filtering.Linear)
                    if not node:node=QSGSimpleTextureNode();node.setOwnsTexture(False)
                    node.setTexture(self.texture)
                    if old_texture:shiboken6.delete(old_texture)
                node.setRect(self.boundingRect());node.setSourceRect(QRectF(rect[0],rect[1],rect[2],rect[3]))
                bridge.rect=list(rect)
                if getattr(bridge,"diagnostic",False) and self.seq>10:
                    self.dll.dg_probe.argtypes=[C.c_void_p,C.POINTER(C.c_ubyte)]
                    pixel=(C.c_ubyte*4)();self.dll.dg_probe(self.capture,pixel)
                    print("Native BGRA:",list(pixel),"item",self.width(),self.height(),"texture",self.texture.textureSize(),flush=True);bridge.diagnostic=False
                within=rect[0]>=0 and rect[1]>=0 and rect[0]+rect[2]<=rect[4] and rect[1]+rect[3]<=rect[5]
                if bridge.ready!=within:
                    bridge.ready=within;bridge.error='Live WGC desktop · GPU texture' if within else 'Cross-monitor seam — in-app fallback';bridge.changed.emit()
            if not address and bridge.ready:
                bridge.ready=False;bridge.error="Waiting for desktop frames";bridge.changed.emit()
            if not address and node:
                shiboken6.delete(node);node=None
                if self.texture:shiboken6.delete(self.texture);self.texture=None;self.address=0
            if bridge.pointer:
                bridge.input_delays.append((time.perf_counter()-bridge.pointer)*1000);bridge.pointer=0
        except Exception as ex:
            bridge.fail(str(ex));self._release_now(node);node=None
        return node
    def pause(self):
        if self._native_busy:
            self._pending_pause=True
            return
        self._native_busy=True
        try:
            if self.capture:self.dll.dg_pause(self.capture)
        finally:self._native_busy=False
        self.update()
    @Slot()
    def shutdown(self):self.release()

bridge=Bridge(native_path=HERE/'capture.dll',measure=True,allow_monitor_rebind=True)

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--test-pattern',action='store_true');parser.add_argument('--seconds',type=float,default=0)
    parser.add_argument('--exercise',action='store_true');parser.add_argument('--multi-monitor',action='store_true');parser.add_argument('--simulate-device-loss',action='store_true');parser.add_argument('--deny-capture',action='store_true');parser.add_argument('--proof',action='store_true',help='Save rendered synthetic-pattern proofs only; requires --test-pattern')
    args=parser.parse_args()
    if args.proof and not args.test_pattern:parser.error('--proof requires controlled --test-pattern')
    if (args.exercise or args.multi_monitor) and not args.test_pattern:parser.error('Exercise scenarios require --test-pattern')
    bridge.deny=args.deny_capture
    app=QGuiApplication(sys.argv);app.setApplicationName('AnimeBT Desktop Glass Prototype')
    qmlRegisterType(DesktopTexture,'DesktopGlass',1,0,'DesktopTexture')
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('capture',bridge)
    engine.load(QUrl.fromLocalFile(str(HERE/'Prototype.qml')))
    if not engine.rootObjects():return 2
    window=engine.rootObjects()[0]
    bad_frames=[0]
    def swapped():
        now=time.perf_counter()
        if bridge.swap_times and bridge.enabled:
            bad_frames[0]=bad_frames[0]+1 if now-bridge.swap_times[-1]>.05 else 0
            if bad_frames[0]>=20:bridge.fail('Sustained rendering budget exceeded');bad_frames[0]=0
        bridge.swap_times.append(now)
    window.frameSwapped.connect(swapped);timer=QTimer()
    pattern=None;warnings=[]
    if args.test_pattern:
        bridge.diagnostic=True
        pattern=QQmlApplicationEngine();pattern.load(QUrl.fromLocalFile(str(HERE/'Pattern.qml')))
        back=pattern.rootObjects()[0];back.showFullScreen()
        area=app.primaryScreen().availableGeometry();window.resize(min(920,area.width()-100),min(590,area.height()-100))
        window.setPosition(area.x()+40,area.y()+40);window.raise_()
        # Explicit CLI opt-in: never used in normal launch.
        QTimer.singleShot(700,bridge.start)
    out=HERE/'results';out.mkdir(exist_ok=True)
    (out/"active-pid.txt").write_text(str(os.getpid()),encoding="ascii")
    proofs=[];memory=[];state_history=[]
    bridge.changed.connect(lambda:state_history.append({"time":round(time.perf_counter(),3),"active":bridge.enabled,"ready":bridge.ready,"message":bridge.error}))
    class ProcessMemory(C.Structure):
        _fields_=[("cb",C.c_ulong),("pageFaults",C.c_ulong)]+[(name,C.c_size_t) for name in ("peakWorkingSet","workingSet","quotaPeakPaged","quotaPaged","quotaPeakNonPaged","quotaNonPaged","pagefile","peakPagefile","privateUsage")]
    def memory_sample():
        mem=ProcessMemory();mem.cb=C.sizeof(mem);ps=C.WinDLL("psapi");kernel=C.WinDLL("kernel32");kernel.GetCurrentProcess.restype=C.c_void_p
        ps.GetProcessMemoryInfo.argtypes=[C.c_void_p,C.c_void_p,C.c_ulong]
        if ps.GetProcessMemoryInfo(kernel.GetCurrentProcess(),C.byref(mem),mem.cb):memory.append({"rss":mem.workingSet,"private":mem.privateUsage})
    memtimer=QTimer();memtimer.timeout.connect(memory_sample);memtimer.start(1000)
    def proof(name):
        if args.proof and (bridge.ready or name=="stopped-fallback"):
            window.grabWindow().save(str(out/(name+'.png')));proofs.append(name)
    def stop():
        def stats(values):
            values=sorted(values)
            return {'samples':len(values),'median_ms':round(values[len(values)//2],3),'p95_ms':round(values[min(len(values)-1,int(len(values)*.95))],3),'max_ms':round(values[-1],3)} if values else {}
        report={'qt':qVersion(),'api':str(window.rendererInterface().graphicsApi()),'capture_frames':bridge.frames,'capture_ready':bridge.ready,'message':bridge.error,'client_rect_physical':bridge.rect,'update_timer_intervals':stats(bridge.intervals),'qt_swap_intervals':stats([(b-a)*1000 for a,b in zip(bridge.swap_times,bridge.swap_times[1:])]),'qt_submitted_fps':round((len(bridge.swap_times)-1)/(bridge.swap_times[-1]-bridge.swap_times[0]),2) if len(bridge.swap_times)>1 else 0,'effective_import_fps':round(bridge.frames/(bridge.active_time+(time.perf_counter()-bridge.active_since if bridge.active_since else 0)),2) if bridge.frames else 0,'frame_age_at_import':stats(bridge.ages),'delivery_to_next_update':stats(bridge.input_delays),'input_method':'QTest mouse click -> QML pressed event -> next scene update; not physical input-to-photon','proofs':proofs,'continuous_cpu_image_transfers':0,'synthetic_diagnostic_pixels':1 if args.test_pattern else 0,'gpu_copy_conversion':stats(bridge.gpu),'local_video_memory_bytes':bridge.vram,'process_cpu_seconds':time.process_time(),'gpu_path':'WGC BGRA -> same Qt D3D11 device CopyResource + GPU RGBA conversion -> native QSGTexture -> ShaderEffectSource -> existing GlassSurface','controlled_pattern':args.test_pattern,'states':state_history,'memory':memory,'screens':[{'name':s.name(),'dpr':s.devicePixelRatio(),'width':s.size().width(),'height':s.size().height()} for s in app.screens()]}
        (out/'metrics.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report),flush=True)
        bridge.stop();bridge.item.shutdown();app.quit()
    if args.multi_monitor and args.test_pattern and len(app.screens())>1:
        primary=app.primaryScreen();secondary=next(s for s in app.screens() if s!=primary)
        def seam():window.setPosition(primary.geometry().right()-window.width()//2,primary.geometry().y()+40)
        def secondary_monitor():
            back.setScreen(secondary);back.setGeometry(secondary.geometry());back.showFullScreen()
            area=secondary.availableGeometry();window.resize(min(920,area.width()-100),min(590,area.height()-100))
            window.setScreen(secondary);window.setPosition(area.x()+40,area.y()+40);window.raise_()
        QTimer.singleShot(6000,seam)
        QTimer.singleShot(8000,lambda:state_history.append({'scenario':'monitor_seam','ready':bridge.ready,'message':bridge.error}))
        QTimer.singleShot(9000,secondary_monitor)
        QTimer.singleShot(12000,lambda:proof('secondary-monitor'))
    if args.simulate_device_loss:QTimer.singleShot(4000,lambda:bridge.fail("Simulated device removal (DXGI_ERROR_DEVICE_REMOVED)"))
    def input_click():
        from PySide6.QtTest import QTest
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,QPoint(window.width()-80,window.height()-25))
    if args.seconds:
        QTimer.singleShot(2500,lambda:proof('desktop-light'))
        QTimer.singleShot(3500,lambda:window.setProperty('dark',True))
        QTimer.singleShot(4500,lambda:proof('desktop-dark'))
        for ms in range(1800,int(args.seconds*1000)-500,150):QTimer.singleShot(ms,input_click)
        if args.exercise:
            def move():window.setPosition(window.x()+110,window.y()+55)
            def resize():window.resize(1000,650)
            def static():
                back.setProperty('moving',False);back.setProperty('offset',20)
                window.setProperty('dark',False);window.setProperty('testBend',0);window.setProperty('testBlur',0);window.setProperty('testEdge',0)
            def optical():window.setProperty('testBend',1)
            QTimer.singleShot(5500,move);QTimer.singleShot(6500,resize)
            QTimer.singleShot(7500,lambda:proof('moved-resized'))
            QTimer.singleShot(8000,static);QTimer.singleShot(8500,lambda:proof('static-desktop'))
            QTimer.singleShot(9000,optical);QTimer.singleShot(9500,lambda:proof('refracted-desktop'))
            QTimer.singleShot(10000,bridge.stop);QTimer.singleShot(10500,lambda:proof('stopped-fallback'))
            QTimer.singleShot(11000,bridge.start)
        QTimer.singleShot(int(args.seconds*1000),stop)
    app.aboutToQuit.connect(lambda:bridge.item.shutdown())
    return app.exec()
if __name__=='__main__':raise SystemExit(run())










