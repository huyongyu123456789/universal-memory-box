$ErrorActionPreference = "Stop"
$TaskName = "Memory Box Automatic Insurance"
& schtasks.exe /Delete /TN $TaskName /F | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "Task was not present or could not be removed." }
