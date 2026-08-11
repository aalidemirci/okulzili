$ErrorActionPreference = "SilentlyContinue"
$target = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "OkulZili.exe"))
$deadline = (Get-Date).AddSeconds(5)

do {
    $matching = @(
        Get-Process -Name "OkulZili" -ErrorAction SilentlyContinue |
            Where-Object {
                try {
                    [System.IO.Path]::GetFullPath($_.Path).Equals(
                        $target,
                        [System.StringComparison]::OrdinalIgnoreCase
                    )
                } catch {
                    $false
                }
            }
    )
    if ($matching.Count -eq 0) {
        exit 0
    }
    foreach ($process in $matching) {
        [void]$process.CloseMainWindow()
    }
    Start-Sleep -Milliseconds 250
} while ((Get-Date) -lt $deadline)

foreach ($process in $matching) {
    if (-not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
}
exit 0
