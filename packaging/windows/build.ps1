$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $projectRoot
try {
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    $python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
    $env:PYTHONPATH = Join-Path $projectRoot "src"
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: $LASTEXITCODE" }
    & $python -m PyInstaller --clean --noconfirm packaging\windows\okul-zili.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path -LiteralPath $inno)) {
        $inno = Join-Path $projectRoot ".build-inno\ISCC.exe"
    }
    if (-not (Test-Path -LiteralPath $inno)) {
        throw "Inno Setup 6 bulunamadı."
    }
    & $inno packaging\windows\okul-zili.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}
