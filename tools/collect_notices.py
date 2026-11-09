"""Collect the bundled libraries' notices beside the Windows executable."""

from importlib.metadata import distribution
from pathlib import Path
from shutil import copy2
import sys


ROOT = Path(__file__).resolve().parents[1]


def copy_notices(destination):
    target = destination / "licenses"
    target.mkdir(exist_ok=True)
    for source in (ROOT / "packaging" / "licenses").glob("*.txt"):
        copy2(source, target)
    for line in (ROOT / "requirements-build.lock").read_text(encoding="utf-8").splitlines():
        name, separator, _ = line.partition("==")
        if not separator:
            continue
        package = distribution(name)
        for entry in package.files or ():
            parts = entry.parts
            if any(part == ".." for part in parts) or not parts[0].endswith(".dist-info"):
                continue
            if "licenses" not in parts and not entry.name.lower().startswith(("license", "copying", "notice")):
                continue
            source = Path(package.locate_file(entry))
            if source.is_file():
                output = target.joinpath(name, *parts[1:])
                output.parent.mkdir(parents=True, exist_ok=True)
                copy2(source, output)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        copy2(python_license, target / "Python-LICENSE.txt")


if __name__ == "__main__":
    copy_notices(Path(sys.argv[1]))
