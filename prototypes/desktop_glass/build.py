"""Rebuild the isolated native DLL with installed MinGW; no downloads or installs."""
import os,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
target=root/'capture.dll'
target.parent.mkdir(parents=True,exist_ok=True)
compiler=os.environ.get('ANIMEBT_PROTO_CXX') or shutil.which('g++')
if not compiler:raise SystemExit('MinGW-w64 g++ with WinRT headers required; set ANIMEBT_PROTO_CXX')
subprocess.run([compiler,'-std=c++17','-O2','-shared','-static',str(root/'capture.cpp'),'-o',str(target),'-ld3d11','-ldxgi','-ld3dcompiler','-lruntimeobject','-lole32','-luuid'],check=True)
print(target)
