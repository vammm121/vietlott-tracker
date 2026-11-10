# setup_schedule.ps1 - dang ky Task Scheduler cho vietlott tracker (Mega + Power)
# Dung: .\setup_schedule.ps1              (chi kiem tra)
#       .\setup_schedule.ps1 -Register    (dang ky that)
param([switch]$Register)

$dir   = $PSScriptRoot
$py    = (Get-Command python).Source
$name  = "VietlottTracker-Auto"
$argMegaA  = "`"$dir\vietlott_tracker.py`" auto"
$argMegaD  = "`"$dir\vietlott_tracker.py`" dashboard"
$argPowerA = "`"$dir\vietlott_power655.py`" auto"
$argPowerD = "`"$dir\vietlott_power655.py`" dashboard"

Write-Host "Thu muc : $dir"
Write-Host "Python  : $py"
Write-Host "Lenh    : $py $argMegaA"
Write-Host "          $py $argPowerA"
Write-Host ""

$actionMegaA  = New-ScheduledTaskAction -Execute $py -Argument $argMegaA -WorkingDirectory $dir
$actionMegaD  = New-ScheduledTaskAction -Execute $py -Argument $argMegaD -WorkingDirectory $dir
$actionPowerA = New-ScheduledTaskAction -Execute $py -Argument $argPowerA -WorkingDirectory $dir
$actionPowerD = New-ScheduledTaskAction -Execute $py -Argument $argPowerD -WorkingDirectory $dir
# Mega 6/45 quay Thu 4, Thu 6, Chu nhat 18:05 (gio VN)
$triggerMega  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday,Friday,Sunday -At 18:10
# Power 6/55 quay Thu 3, Thu 5, Thu 7 18:05 (gio VN)
$triggerPower = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday,Thursday,Saturday -At 18:10
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited

if (-not $Register) {
  Write-Host "[dry-run] Se dang ky task '$name':"
  Write-Host "  Mega  18:10 Thu 4 / Thu 6 / Chu nhat"
  Write-Host "  Power 18:10 Thu 3 / Thu 5 / Thu 7"
  Write-Host "Chay lai voi -Register de ap dung."
  exit 0
}

Register-ScheduledTask -TaskName $name -Action $actionMegaA,$actionMegaD,$actionPowerA,$actionPowerD `
  -Trigger $triggerMega,$triggerPower -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Da dang ky '$name'."
Get-ScheduledTask -TaskName $name | Select-Object TaskName,State | Format-Table -AutoSize

# Go bo:
#   Unregister-ScheduledTask -TaskName "VietlottTracker-Auto" -Confirm:$false