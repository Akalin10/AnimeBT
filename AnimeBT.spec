# Build with: python -m PyInstaller --noconfirm --clean AnimeBT.spec
from PyInstaller.utils.hooks import collect_all

textual_data, textual_binaries, textual_imports = collect_all('textual')
analysis = Analysis(
    ['packaging/entrypoint.py'],
    pathex=[SPECPATH],
    binaries=textual_binaries,
    datas=textual_data,
    hiddenimports=textual_imports,
    hookspath=[],
    excludes=['pytest', 'pytest_asyncio', 'bs4', 'feedparser', 'setuptools', 'pip'],
    noarchive=False,
)
archive = PYZ(analysis.pure)
exe = EXE(
    archive, analysis.scripts, analysis.binaries, analysis.datas,
    name='AnimeBT', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=True,
    version='packaging/version_info.txt', icon='packaging/assets/icon.ico',
)
