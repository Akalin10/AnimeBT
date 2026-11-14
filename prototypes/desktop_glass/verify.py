"""Explicit opt-in native acceptance matrix; only controlled pattern is captured."""
import json,os,subprocess,sys
from pathlib import Path
from PySide6.QtGui import QImage
root=Path(__file__).resolve().parent
out=root/'results'
def run(name,args,scale='1'):
    env={**os.environ,'QT_SCALE_FACTOR':scale,'PYTHONUTF8':'1'}
    p=subprocess.run([sys.executable,str(root/'run.py'),*args],env=env,capture_output=True,text=True,timeout=50)
    (out/(name+'.log')).write_text(p.stdout+'\n'+p.stderr,encoding='utf8')
    if p.returncode:raise AssertionError((name,p.returncode,p.stderr))
    data=json.loads((out/'metrics.json').read_text());(out/(name+'.json')).write_text(json.dumps(data,indent=2),encoding='utf8')
    return data
reports={}
reports['default']=run('default',['--seconds','3'])
assert reports['default']['capture_frames']==0 and not reports['default']['capture_ready']
reports['denied']=run('denied',['--test-pattern','--deny-capture','--seconds','4'])
assert reports['denied']['capture_frames']==0 and 'E_ACCESSDENIED' in reports['denied']['message']
reports['device-loss']=run('device-loss',['--test-pattern','--simulate-device-loss','--seconds','6'])
assert reports['device-loss']['capture_frames']>0 and not reports['device-loss']['capture_ready']
assert 'DXGI_ERROR_DEVICE_REMOVED' in reports['device-loss']['message']
reports['dpi150']=run('dpi150',['--test-pattern','--seconds','6'],'1.5')
assert reports['dpi150']['capture_ready'] and reports['dpi150']['capture_frames']>50
reports['multimonitor']=run('multimonitor',['--test-pattern','--multi-monitor','--seconds','14'])
assert reports['multimonitor']['capture_ready'] and reports['multimonitor']['capture_frames']>50
if len(reports['multimonitor']['screens'])>1:
    seam=next(s for s in reports['multimonitor']['states'] if s.get('scenario')=='monitor_seam')
    assert not seam['ready'],seam
# Same stationary real desktop frame; high lights and blur are zero in both.
a=QImage(str(out/'static-desktop.png'));b=QImage(str(out/'refracted-desktop.png'))
assert not a.isNull() and a.size()==b.size()
def delta(rect):
    x0,y0,x1,y1=rect;values=[]
    for y in range(y0,y1,2):
        for x in range(x0,x1,2):
            c=a.pixelColor(x,y);d=b.pixelColor(x,y)
            values.extend(abs(getattr(c,k)()-getattr(d,k)()) for k in ('red','green','blue'))
    return round(sum(values)/len(values),3)
center=delta((300,188,600,220));edge=delta((30,185,65,300))
assert center>.2 and edge>.2,(center,edge)
report={'scenarios':{k:{'frames':v['capture_frames'],'ready':v['capture_ready'],'message':v['message']} for k,v in reports.items()},'center_optical_delta':center,'edge_optical_delta':edge,'units':'mean absolute RGB code-value difference; blur and highlights disabled','permission_test':'simulated denial; no OS policy changed','device_test':'simulated removal; GPU not physically reset'}
(out/'acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report,indent=2))
