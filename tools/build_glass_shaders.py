"""Bake Qt 6 multi-backend shader packages; qsb is a development tool only."""
import os
from pathlib import Path
import shutil
import subprocess

import PySide6


root = Path(__file__).resolve().parents[1]
qt = Path(PySide6.__file__).parent
candidates = [os.environ.get("ANIMEBT_QSB"), shutil.which("qsb"),
              qt / "qsb.exe", qt / "Qt/libexec/qsb", root / "artifacts/shader-tools/tool/qsb.exe"]
tool = next((Path(value) for value in candidates if value and Path(value).is_file()), None)
if tool is None:
    raise SystemExit("Qt Shader Tools qsb not found. Install the Qt 6 development tool or set ANIMEBT_QSB.")
environment = {**os.environ, "PATH": str(qt) + os.pathsep + os.environ.get("PATH", "")}
for program, stage in [(program, stage) for program in ("glass", "ambient") for stage in ("vert", "frag")] + [("wallpaper", "frag"), ("backdropblur", "frag")]:
    source = root / f"animebt/gui/qml/shaders/{program}.{stage}"
    target = source.with_suffix(source.suffix + ".qsb")
    subprocess.run([str(tool), "--qsbversion", "64", "--qt6", "-o", str(target), str(source)],
                   check=True, env=environment)
    print(f"Baked {target.name}: {target.stat().st_size} bytes")
