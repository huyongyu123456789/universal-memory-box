$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "MemoryBox"
if (-not (Test-Path (Join-Path $InstallDir "memorybox_main.py"))) { $InstallDir = $Source }

$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = "选择一个已经由百度网盘桌面客户端同步的本地文件夹。Memory Box 不会读取百度账号密码或 Cookie；新端点默认使用端到端加密。"
$dialog.ShowNewFolderButton = $true
if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
$Folder = $dialog.SelectedPath

$exe = Join-Path $InstallDir "MemoryBox-CLI.exe"
$py = Join-Path $InstallDir "runtime\python.exe"
$main = Join-Path $InstallDir "memorybox_main.py"

if (Test-Path $exe) {
    $output = & $exe sync-add $Folder --provider baidu-netdisk --name "百度网盘" 2>&1
} elseif (Test-Path $py) {
    $output = & $py $main sync-add $Folder --provider baidu-netdisk --name "百度网盘" 2>&1
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) { throw "Memory Box runtime not found. Please install Memory Box first." }
    $output = & $python.Source $main sync-add $Folder --provider baidu-netdisk --name "百度网盘" 2>&1
}
if ($LASTEXITCODE -ne 0) { throw ($output -join "`n") }
[System.Windows.Forms.MessageBox]::Show("百度网盘同步目录已连接到 Memory Box。`n`n$Folder`n`n请在另一台电脑上选择对应的同一百度网盘同步目录。`n`n随后在两台电脑的“设备同步 → 可信设备”中核对完整指纹并互相信任，才会开始加密互传。", "Memory Box", 'OK', 'Information') | Out-Null
