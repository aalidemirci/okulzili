param(
    [string]$InstallDir = "$env:ProgramFiles\Okul Zili"
)

$ErrorActionPreference = "Stop"
$failures = [System.Collections.Generic.List[string]]::new()
$executable = Join-Path $InstallDir "OkulZili.exe"

if (-not (Test-Path -LiteralPath $executable)) {
    $failures.Add("Uygulama bulunamadı: $executable")
} else {
    foreach ($relativePath in @(
        "_internal\_tkinter.pyd",
        "_internal\tcl86t.dll",
        "_internal\tk86t.dll",
        "_internal\_tcl_data\init.tcl",
        "_internal\_tk_data\tk.tcl"
    )) {
        $requiredPath = Join-Path $InstallDir $relativePath
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            $failures.Add("Tk arayüz bileşeni eksik: $relativePath")
        }
    }
    foreach ($argument in @("--paket-kontrol", "--tepsi-kontrol", "--ilk-kurulum-kontrol", "--baslangic-kontrol", "--arayuz-kontrol", "--ses-cihazi-kontrol")) {
        $process = Start-Process -FilePath $executable -ArgumentList $argument -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(10000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            continue
        }
        if ($process.ExitCode -ne 0) {
            $failures.Add("$argument kontrolü başarısız: $($process.ExitCode)")
        }
    }
}

try {
    $task = Get-ScheduledTask -TaskName "Okul Zili"
    if (-not ($task.Triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskLogonTrigger" })) {
        $failures.Add("Görev Zamanlayıcı oturum açma tetikleyicisi yok.")
    }
    if ($task.Settings.DisallowStartIfOnBatteries) {
        $failures.Add("Görev yalnızca AC güçte başlayacak biçimde ayarlanmış.")
    }
    if ($task.Settings.StopIfGoingOnBatteries) {
        $failures.Add("Görev bataryaya geçince duracak biçimde ayarlanmış.")
    }
    if ($task.Settings.RestartCount -lt 5) {
        $failures.Add("Görev beklenmeyen kapanma sonrasında yeterli sayıda yeniden başlatılmayacak.")
    }
} catch {
    $failures.Add("Görev Zamanlayıcı görevi okunamadı: $($_.Exception.Message)")
}

if ($failures.Count -gt 0) {
    $failures | ForEach-Object { Write-Output "BAŞARISIZ: $_" }
    exit 1
}

Write-Output "BAŞARILI: Windows kurulum, otomatik başlatma, başlangıç penceresi, tepsi, arayüz ve ses cihazı kontrolleri geçti."
exit 0
