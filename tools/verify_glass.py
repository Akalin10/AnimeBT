"""Local RHI image/geometry and presentation timing verification. No service calls."""
import argparse
import json
import os
from pathlib import Path
import statistics
import sys
from time import monotonic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="artifacts/glass-optics")
    parser.add_argument("--seconds", type=float, default=2.5)
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    os.environ.setdefault("QSG_RHI_BACKEND", "d3d11")
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QSGRendererInterface
    from PySide6.QtTest import QTest
    from animebt.gui.typography import apply_system_typography
    app = QGuiApplication([])
    typography = apply_system_typography(app)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda values: warnings.extend(value.toString() for value in values))
    engine.load(QUrl.fromLocalFile(str(root / "tests/fixtures/GlassOptics.qml")))
    if not engine.rootObjects():
        raise RuntimeError("Optical test scene failed to load")
    window = engine.rootObjects()[0]
    window.requestActivate()
    QTest.qWait(200)
    if window.rendererInterface().graphicsApi() == QSGRendererInterface.GraphicsApi.Software:
        raise RuntimeError("Optical verification requires RHI; software has no refraction")
    output = Path(options.output)
    output.mkdir(parents=True, exist_ok=True)
    report = {"api": str(window.rendererInterface().graphicsApi()), "scale": window.devicePixelRatio(),
              "timing_method": "Qt Quick FrameAnimation wall-frame intervals, not GPU timestamps; excludes image readback",
              "geometry": {}, "timings": {}, "screenshots": []}
    images = {}
    for dark in (False, True):
        theme = "dark" if dark else "light"
        window.setProperty("dark", dark)
        for mode in ("static", "refracted"):
            enabled = mode == "refracted"
            window.setProperty("shift", 0)
            window.setProperty("bend", int(enabled))
            window.setProperty("lightPower", int(enabled))
            window.setProperty("tintLevel", 0.3)
            window.setProperty("blurPower", 1)
            QTest.qWait(150)
            filename = f"{theme}-{mode}.png"
            image = window.grabWindow()
            image.save(str(output / filename))
            images[(theme, mode)] = image
            report["screenshots"].append(filename)
            stamps = []
            def frame():
                stamps.append(monotonic())
            window.frameSwapped.connect(frame)
            window.setProperty("frameIntervals", [])
            window.setProperty("moving", True)
            start = monotonic()
            QTest.qWait(round(options.seconds * 1000))
            elapsed = monotonic() - start
            window.setProperty("moving", False)
            window.frameSwapped.disconnect(frame)
            values = window.property("frameIntervals")
            if hasattr(values, "toVariant"):
                values = values.toVariant()
            intervals = sorted(values)
            report["timings"][f"{theme}-{mode}"] = {
                "frames": len(intervals), "swap_events": len(stamps), "seconds": round(elapsed, 3),
                "ui_frames_per_second": round(len(intervals) / elapsed, 1),
                "median_interval_ms": round(statistics.median(intervals), 2) if intervals else None,
                "p95_interval_ms": round(intervals[int((len(intervals) - 1) * .95)], 2) if intervals else None,
            }
        window.setProperty("moving", False)
        window.setProperty("shift", 0)
        window.setProperty("lightPower", 0)
        window.setProperty("blurPower", 0)
        window.setProperty("tintLevel", 0)
        probes = []
        for bend in (0, 1):
            window.setProperty("bend", bend)
            QTest.qWait(120)
            probes.append(window.grabWindow())
        ratio = probes[0].width() / window.width()
        def gray(image, x, y):
            c = image.pixelColor(round(x * ratio), round(y * ratio))
            return c.red() * .2126 + c.green() * .7152 + c.blue() * .0722
        errors = {}
        for shift in range(-16, 17):
            errors[shift] = sum(abs(gray(probes[1], x, y) - gray(probes[0], x + shift, y))
                                for x in range(45, 60) for y in range(140, 150)) / 150
        best = min(errors, key=errors.get)
        report["geometry"][theme] = {"best_local_shift_dip": best, "zero_shift_error": round(errors[0], 3),
                                     "shifted_error": round(errors[best], 3)}
        # With highlights, blur and tint unchanged, this requires feature movement.
        if abs(best) < 1 or errors[best] >= errors[0] * .85:
            raise AssertionError(f"No verified geometric refraction: {report['geometry'][theme]}")
        def difference(first, second, rect):
            x0, y0, x1, y1 = rect
            return statistics.mean(abs(gray(first, x, y) - gray(second, x, y))
                                   for x in range(x0, x1, 3) for y in range(y0, y1, 3))
        center_refraction = difference(probes[0], probes[1], (190, 125, 350, 170))
        if center_refraction < .2:
            raise AssertionError("No central refraction")
        window.setProperty("shift", 8)
        QTest.qWait(100)
        shifted = window.grabWindow()
        dynamic = difference(probes[1], shifted, (42, 110, 62, 180))
        reading = difference(probes[1], shifted, (80, 380, 130, 470))
        card = difference(probes[1], shifted, (560, 365, 605, 410))
        menu = difference(probes[1], shifted, (750, 476, 780, 510))
        if card < .25 or menu < .25:
            raise AssertionError(f"Card transmission/menu frosting failed: {card}, {menu}")
        if dynamic < 1 or reading < .25:
            raise AssertionError(f"Dynamic texture/reading protection failed: {dynamic}, {reading}")
        window.setProperty("shift", 0)
        window.setProperty("tintLevel", .5)
        window.setProperty("blurPower", 0)
        QTest.qWait(100)
        blur_baseline = window.grabWindow()
        window.setProperty("blurPower", 5)
        QTest.qWait(100)
        blurred = window.grabWindow()
        blur_difference = difference(blur_baseline, blurred, (70, 120, 400, 180))
        if blur_difference < .2:
            raise AssertionError("Blur parameter did not affect texture sampling")
        report["geometry"][theme].update(dynamic_edge_change=round(dynamic, 3),
                                         center_refraction_change=round(center_refraction, 3),
                                         card_center_change=round(card, 3), menu_center_change=round(menu, 3),
                                         reading_plate_change=round(reading, 3),
                                         blur_change=round(blur_difference, 3))
        tint_images = []
        for level, name in ((0, "clear"), (1, "tinted")):
            window.setProperty("bend", 1)
            window.setProperty("lightPower", 1)
            window.setProperty("blurPower", 1)
            window.setProperty("tintLevel", level)
            QTest.qWait(120)
            image = window.grabWindow()
            image.save(str(output / f"{theme}-{name}.png"))
            tint_images.append(image)
        tint_difference = difference(*tint_images, (70, 120, 400, 180))
        if tint_difference < 1:
            raise AssertionError("Clear/Tinted parameter had no visible effect")
        report["geometry"][theme]["tint_change"] = round(tint_difference, 3)
    report["warnings"] = warnings
    (output / "measurements.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    window.close()
    if warnings:
        raise AssertionError(warnings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
