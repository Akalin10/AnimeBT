# Build with: python -m PyInstaller --noconfirm --clean AnimeBT.spec
from PyInstaller.utils.hooks import collect_data_files
from pathlib import PureWindowsPath

analysis = Analysis(
    ['packaging/entrypoint.py'],
    pathex=[SPECPATH],
    datas=collect_data_files('opencc') + [
        ('animebt/gui/qml/*.qml', 'animebt/gui/qml'),
        ('animebt/gui/qml/shaders/*.qsb', 'animebt/gui/qml/shaders'),
        ('animebt/gui/assets/icon.png', 'animebt/gui/assets'),
    ],
    excludes=['pytest', 'pytest_asyncio', 'setuptools', 'pip'],
    noarchive=False,
)
# Qt links to the unversioned Windows ICU exports. Do not shadow the system
# DLLs with unrelated ICU builds that happen to be on the developer's PATH.
def use_bundled_binary(entry):
    name = PureWindowsPath(entry[0]).name.lower()
    windows_libraries = {'icu.dll', 'icuin.dll', 'icuuc.dll', 'icudt.dll', 'ucrtbase.dll'}
    return (name not in windows_libraries
            and not name.startswith(('api-ms-win-', 'ext-ms-win-', 'icudt'))
            and name not in {'libssl-3-x64.dll', 'libcrypto-3-x64.dll'})


analysis.binaries = [entry for entry in analysis.binaries if use_bundled_binary(entry)]
archive = PYZ(analysis.pure)
exe = EXE(
    archive, analysis.scripts, [],
    exclude_binaries=True,
    name='AnimeBT', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    version='packaging/version_info.txt', icon='packaging/assets/icon.ico',
)
app = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='AnimeBT')
