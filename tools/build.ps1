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
    $docs = Join-Path $app 'docs'
    New-Item -ItemType Directory -Path $docs -Force | Out-Null
    Copy-Item -LiteralPath docs\guide.md -Destination $docs
    Copy-Item -LiteralPath docs\showcase -Destination $docs -Recurse
    $readmePath = Join-Path $app 'README.md'
    $readme = [System.IO.File]::ReadAllText($readmePath).Replace('animebt/gui/assets/icon.png', '_internal/animebt/gui/assets/icon.png').Replace('packaging/THIRD_PARTY.md', 'THIRD_PARTY.md')
    [System.IO.File]::WriteAllText($readmePath, $readme, [System.Text.UTF8Encoding]::new($false))
    & $buildPython tools/collect_notices.py $app
    if ($LASTEXITCODE -ne 0) { throw "License notice collection failed" }
    $releaseVersion = (& $buildPython -c 'from animebt.version import __version__; print(__version__)').Trim()
    $zip = "dist\AnimeBT-$releaseVersion-Windows-x64.zip"
    Compress-Archive -LiteralPath $app -DestinationPath $zip -Force
    Write-Host "Created $zip"
} finally { Pop-Location }
