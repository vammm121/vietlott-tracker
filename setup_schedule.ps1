# setup_schedule.ps1 - dang ky Task Scheduler cho vietlott_tracker
# Dung: .\setup_schedule.ps1              (chi kiem tra)
#       .\setup_schedule.ps1 -Register    (dang ky that)
param([switch]$Register)

$dir   = $PSScriptRoot
$py    = (Get-Command python).Source
$name  = "VietlottTracker-Auto"
$argA  = "`"$dir\vietlott_tracker.py`" auto"
$argD  = "`"$dir\vietlott_tracker.py`" dashboard"

Write-Host "Thu muc : $dir"
Write-Host "Python  : $py"
Write-Host "Lenh    : $py $argA"
Write-Host ""

$actionA = New-ScheduledTaskAction -Execute $py -Argument $argA -WorkingDirectory $dir
$actionD = New-ScheduledTaskAction -Execute $py -Argument $argD -WorkingDirectory $dir
# Mega 6/45 quay Thu 4, Thu 6, Chu nhat luc 18:05 (gio VN)
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday,Friday,Sunday -At 18:10
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

if (-not $Register) {
  Write-Host "[dry-run] Se dang ky task '$name' chay 18:10 Thu 4 / Thu 6 / Chu nhat."
  Write-Host "Chay lai voi -Register de ap dung."
  exit 0
}

Register-ScheduledTask -TaskName $name -Action $actionA,$actionD -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Da dang ky '$name'."
Get-ScheduledTask -TaskName $name | Select-Object TaskName,State | Format-Table -AutoSize

# Go bo:
#   Unregister-ScheduledTask -TaskName "VietlottTracker-Auto" -Confirm:$false