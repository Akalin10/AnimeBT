param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    & $Python -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw "Environment creation failed" }
    $buildPython = Join-Path (Get-Location) '.build-venv\Scripts\python.exe'
    & $buildPython -m pip install -r requirements-build.lock
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
    & $buildPython -m PyInstaller --noconfirm --clean AnimeBT.spec
    if ($LASTEXITCODE -ne 0) { throw "Build failed" }
    $app = Join-Path (Get-Location) 'dist\AnimeBT'
    Copy-Item -LiteralPath README.md,CHANGELOG.md,packaging\THIRD_PARTY.md -Destination $app
    & $buildPython tools/collect_notices.py $app
    if ($LASTEXITCODE -ne 0) { throw "License notice collection failed" }
    $releaseVersion = (& $buildPython -c 'from animebt.version import __version__; print(__version__)').Trim()
    $zip = "dist\AnimeBT-$releaseVersion-Windows-x64.zip"
    Compress-Archive -LiteralPath $app -DestinationPath $zip -Force
    $digest = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
    "$digest  $(Split-Path -Leaf $zip)" | Set-Content -LiteralPath "$zip.sha256" -Encoding ascii
} finally { Pop-Location }
