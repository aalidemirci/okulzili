$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $projectRoot
try {
    # .venv yalnizca PyInstaller iceriyorsa kullanilir; aksi halde derleme
    # bagimliliklarinin kurulu oldugu sistem Python'ina dusulur.
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $python = "python"
    if (Test-Path -LiteralPath $venvPython) {
        $probe = Start-Process -FilePath $venvPython -ArgumentList "-m", "PyInstaller", "--version" -Wait -PassThru -WindowStyle Hidden
        if ($probe.ExitCode -eq 0) { $python = $venvPython }
    }
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: $LASTEXITCODE" }
    & $python -m PyInstaller --clean --noconfirm packaging\windows\okul-zili.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $innoCandidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        (Join-Path $projectRoot ".build-inno\ISCC.exe")
    )
    $inno = $innoCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $inno) {
        throw "Inno Setup 6 bulunamadı."
    }
    & $inno packaging\windows\okul-zili.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
