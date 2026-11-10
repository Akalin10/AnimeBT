# Build with: python -m PyInstaller --noconfirm --clean AnimeBT.spec
from PyInstaller.utils.hooks import collect_data_files
from pathlib import Path, PureWindowsPath
import sys

from pefile import PE


# Resolve OpenSSL from the Python runtime that built _ssl, rather than PATH.
runtime = Path(sys.base_prefix)
runtime_dirs = (runtime / 'DLLs', runtime)
ssl_extension = next(folder / '_ssl.pyd' for folder in runtime_dirs if (folder / '_ssl.pyd').is_file())
ssl_pe = PE(str(ssl_extension), fast_load=True)
ssl_pe.parse_data_directories([1])
openssl = {entry.dll.decode().lower() for entry in ssl_pe.DIRECTORY_ENTRY_IMPORT
           if entry.dll.lower().startswith((b'libssl-', b'libcrypto-'))}
if len(openssl) != 2:
    raise ValueError('Unable to determine the Python runtime OpenSSL dependencies')
openssl_binaries = [
    (name, str(next(folder / name for folder in runtime_dirs if (folder / name).is_file())), 'BINARY')
    for name in sorted(openssl)
]
runtime_ca_policy = runtime / 'Lib' / 'codex-rejected-cas.pem'
runtime_data = [(str(runtime_ca_policy), '.')] if runtime_ca_policy.is_file() else []

analysis = Analysis(
    ['packaging/entrypoint.py'],
    pathex=[SPECPATH],
    datas=collect_data_files('opencc') + runtime_data + [
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
            and not name.startswith(('libssl-', 'libcrypto-')))


analysis.binaries = [entry for entry in analysis.binaries if use_bundled_binary(entry)] + openssl_binaries
archive = PYZ(analysis.pure)
exe = EXE(
    archive, analysis.scripts, [],
    exclude_binaries=True,
    name='AnimeBT', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False,
    version='packaging/version_info.txt', icon='packaging/assets/icon.ico',
)
app = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name='AnimeBT')
