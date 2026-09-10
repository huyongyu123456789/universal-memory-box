$ErrorActionPreference = "Stop"
$InstallDir = Join-Path $env:LOCALAPPDATA "MemoryBox"
$Runner = Join-Path $InstallDir "MemoryBox-Auto-Insurance.cmd"
$TaskName = "Memory Box Automatic Insurance"
if (-not (Test-Path $Runner)) { throw "Memory Box automatic-insurance runner not found: $Runner" }
Write-Host "Memory Box must already have an E2EE insurance endpoint configured in the app."
Write-Host "This task wakes once per hour; Memory Box itself decides whether the configured backup interval is due."
$taskCmd = '"' + $Runner + '"'
& schtasks.exe /Create /TN $TaskName /TR $taskCmd /SC HOURLY /MO 1 /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Unable to create Windows scheduled task." }
Write-Host "Enabled: $TaskName"
