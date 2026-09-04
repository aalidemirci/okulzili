$ErrorActionPreference = "Stop"
$taskName = "Okul Zili"
$executable = Join-Path $PSScriptRoot "OkulZili.exe"
$action = New-ScheduledTaskAction -Execute $executable
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 1)
# Etki alanı hesaplarında yalnız kullanıcı adı yetmez; kurucu bu betiği
# runasoriginaluser ile günlük hesabın bağlamında çalıştırır (D13).
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
