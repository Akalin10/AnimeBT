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
    Copy-Item -LiteralPath README.md,CHANGELOG.md -Destination dist
    $digest = (Get-FileHash -LiteralPath dist\AnimeBT.exe -Algorithm SHA256).Hash
    "$digest  AnimeBT.exe" | Set-Content -LiteralPath dist\SHA256SUMS.txt -Encoding ascii
    $releaseVersion = (& $buildPython -c 'from animebt.version import __version__; print(__version__)').Trim()
    Compress-Archive -LiteralPath dist\AnimeBT.exe,dist\README.md,dist\CHANGELOG.md,dist\SHA256SUMS.txt -DestinationPath "dist\AnimeBT-$releaseVersion-Windows-x64.zip" -Force
} finally { Pop-Location }
