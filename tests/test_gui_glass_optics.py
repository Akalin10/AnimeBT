import json
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class GlassOpticsTest(unittest.TestCase):
    def test_vertex_and_fragment_have_matching_uniform_layouts(self):
        shaders = Path(__file__).resolve().parents[1] / "animebt/gui/qml/shaders"
        def layout(stage):
            source = (shaders / f"glass.{stage}").read_text(encoding="utf-8")
            block = re.search(r"uniform GlassUniforms\s*\{([^}]+)\}", source)[1]
            return re.findall(r"(\w+)\s+(\w+)\s*;", block)
        self.assertEqual(layout("vert"), layout("frag"))
        for stage in ("vert", "frag"):
            self.assertGreater((shaders / f"glass.{stage}.qsb").stat().st_size, 1000)

    @unittest.skipUnless(sys.platform == "win32", "Native Direct3D optical verification requires Windows")
    def test_native_refraction_moves_features_and_has_no_shader_warnings(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as tmp:
            result = subprocess.run([
                sys.executable, str(root / "tools/verify_glass.py"), "--output", tmp, "--seconds", "0.6",
            ], env={**os.environ, "QT_QPA_PLATFORM": "windows", "QT_QUICK_BACKEND": "",
                    "QSG_RHI_BACKEND": "d3d11", "QT_SCALE_FACTOR": "1", "PYTHONUTF8": "1"},
                capture_output=True, text=True, encoding="utf-8", timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((Path(tmp) / "measurements.json").read_text(encoding="utf-8"))
            self.assertIn("Direct3D11", report["api"])
            self.assertFalse(report["warnings"])
            for probe in report["geometry"].values():
                self.assertGreater(probe["reading_plate_change"], .25)
                self.assertGreater(probe["center_refraction_change"], .2)
                self.assertGreaterEqual(abs(probe["best_local_shift_dip"]), 1)
                self.assertLess(probe["shifted_error"], probe["zero_shift_error"] * .85)
