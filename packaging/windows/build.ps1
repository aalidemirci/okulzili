$ErrorActionPreference = "Stop"
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Push-Location $projectRoot
try {
    # Derleme yorumlayıcısı Python 3.12 olmak ZORUNDADIR: Tcl/Tk DLL'leri,
    # tzdata ve customtkinter bu yorumlayıcıdan toplanır. PATH'teki rastgele
    # "python" kullanılmaz (D12). Sıra: .venv (yalnız 3.12 + bağımlılıklar
    # kuruluysa) -> "py -3.12" -> anlaşılır hata.
    $requiredModules = "PyInstaller, customtkinter, tzdata, miniaudio, PIL, six"
    $probeVersion = "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    $probeModules = "import $requiredModules"

    function Test-BuildPython([string] $candidate) {
        if (-not $candidate -or -not (Test-Path -LiteralPath $candidate)) { return $false }
        $version = Start-Process -FilePath $candidate -ArgumentList "-c", "`"$probeVersion`"" -Wait -PassThru -WindowStyle Hidden
        if ($version.ExitCode -ne 0) { return $false }
        $modules = Start-Process -FilePath $candidate -ArgumentList "-c", "`"$probeModules`"" -Wait -PassThru -WindowStyle Hidden
        return ($modules.ExitCode -eq 0)
    }

    $python = $null
    $venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
    if (Test-BuildPython $venvPython) {
        $python = $venvPython
    } else {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if ($launcher) {
            $stdout = Join-Path $env:TEMP "okul-zili-py312.txt"
            $probe = Start-Process -FilePath $launcher.Source -ArgumentList "-3.12", "-c", "`"import sys; print(sys.executable)`"" -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout
            if ($probe.ExitCode -eq 0) {
                $candidate = (Get-Content -LiteralPath $stdout -TotalCount 1).Trim()
                if (Test-BuildPython $candidate) { $python = $candidate }
            }
            Remove-Item -LiteralPath $stdout -ErrorAction SilentlyContinue
        }
    }
    if (-not $python) {
        throw ("Derleme için Python 3.12 ve şu modüller gerekir: $requiredModules. " +
               "Kurulum: py -3.12 -m pip install pyinstaller `"customtkinter==5.2.2`" `"tzdata>=2024.1`" " +
               "`"miniaudio>=1.71,<2`" `"Pillow>=10,<13`" `"six>=1.16,<2`"")
    }
    Write-Host "Derleme yorumlayıcısı: $python"

    $env:PYTHONPATH = Join-Path $projectRoot "src"
    & $python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Tests failed: $LASTEXITCODE" }
    # EXE sürüm bilgisi tek kaynaktan (okul_zili.__version__) üretilir.
    & $python packaging\windows\make_version_info.py
    if ($LASTEXITCODE -ne 0) { throw "Version info failed: $LASTEXITCODE" }
    & $python -m PyInstaller --clean --noconfirm packaging\windows\okul-zili.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    # Paket içinde saat dilimi verisi olmalı; yoksa ön kontrol temiz makinede
    # "Saat dilimi verisi bulunamadı" kritik uyarısı verir (D11).
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "dist\OkulZili-Windows-x64\_internal\tzdata"))) {
        throw "Paket içinde tzdata yok; derleme Python'ında 'tzdata' kurulu olmalıdır."
    }
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
