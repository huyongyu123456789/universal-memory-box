$ErrorActionPreference = "Stop"
$Source = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "MemoryBox"
$RuntimeDir = Join-Path $InstallDir "runtime"
$PythonVersion = "3.12.10"
$PythonZipUrls = @(
  "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip",
  "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embeddable-amd64.zip"
)
$TempZip = Join-Path $env:TEMP "memorybox-python-$PythonVersion.zip"

Write-Host "Installing Memory Box to $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Copy application files, excluding runtime/data/build artifacts.
$items = @("memorybox", "integrations", "docs", "assets", "memorybox_main.py", "memorybox_desktop.py", "MemoryBox.bat", "MemoryBox-MCP.cmd", "MemoryBox-Import.cmd", "MemoryBox-Recover.cmd", "Register-Transfer-Association.cmd", "Register-Transfer-Association.ps1", "Install-Browser-Bridge.cmd", "Install-Neural-Model.cmd", "Add-Baidu-Netdisk-Sync.cmd", "Add-Baidu-Netdisk-Sync.ps1", "MemoryBox-Auto-Insurance.cmd", "Enable-Auto-Insurance.cmd", "Enable-Auto-Insurance.ps1", "Disable-Auto-Insurance.cmd", "Disable-Auto-Insurance.ps1", "LICENSE", "README.md", "README.zh-CN.md")
foreach ($item in $items) {
    $src = Join-Path $Source $item
    if (Test-Path $src) { Copy-Item $src -Destination $InstallDir -Recurse -Force }
}

if (-not (Test-Path (Join-Path $RuntimeDir "python.exe"))) {
    Write-Host "Downloading private Python runtime (first install only)..."
    New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
    $downloaded = $false
    foreach ($uri in $PythonZipUrls) {
        try {
            Invoke-WebRequest -Uri $uri -OutFile $TempZip -UseBasicParsing
            $downloaded = $true
            break
        } catch {
            Write-Warning "Runtime download failed from $uri; trying fallback..."
        }
    }
    if (-not $downloaded) { throw "Unable to download the private Python runtime." }
    Expand-Archive -Path $TempZip -DestinationPath $RuntimeDir -Force
    Remove-Item $TempZip -Force -ErrorAction SilentlyContinue
}

# Ensure local package directory is visible to embedded Python.
$pth = Get-ChildItem $RuntimeDir -Filter "python*._pth" | Select-Object -First 1
if ($pth) {
    $lines = Get-Content $pth.FullName
    if ($lines -notcontains "..") { Add-Content $pth.FullName ".." }
    # Embedded Python disables site by default; enable it for the cryptography wheel.
    $updated = (Get-Content $pth.FullName) -replace '^#import site$','import site'
    Set-Content -Path $pth.FullName -Value $updated -Encoding ASCII
}

# v0.13 desktop runtime: cryptography + pywebview + tray support live only inside Memory Box's private Python.
$Py = Join-Path $RuntimeDir "python.exe"
try {
    & $Py -c "import cryptography, webview, pystray, PIL, fastembed; assert int(cryptography.__version__.split('.')[0]) >= 46" 2>$null
    $DesktopReady = ($LASTEXITCODE -eq 0)
} catch { $DesktopReady = $false }
if (-not $DesktopReady) {
    Write-Host "Installing Memory Box desktop + encryption runtime (first install only)..."
    $GetPip = Join-Path $env:TEMP "memorybox-get-pip.py"
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPip -UseBasicParsing
    & $Py $GetPip --disable-pip-version-check
    Remove-Item $GetPip -Force -ErrorAction SilentlyContinue
    & $Py -m pip install --disable-pip-version-check "cryptography>=46,<47" "pywebview>=6.1,<7" "pystray>=0.19.5,<0.20" "Pillow>=10,<13" "fastembed>=0.7.4,<0.9"
    if ($LASTEXITCODE -ne 0) { throw "Unable to install Memory Box desktop runtime." }
}

# Create Start Menu shortcut.
$Programs = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$ShortcutPath = Join-Path $Programs "Memory Box.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $InstallDir "MemoryBox.bat"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Local AI Agent Memory Box"
$Shortcut.Save()

# Create Browser Bridge setup shortcut.
$BridgeShortcutPath = Join-Path $Programs "Memory Box - Browser Bridge Setup.lnk"
$BridgeShortcut = $WshShell.CreateShortcut($BridgeShortcutPath)
$BridgeShortcut.TargetPath = Join-Path $InstallDir "Install-Browser-Bridge.cmd"
$BridgeShortcut.WorkingDirectory = $InstallDir
$BridgeShortcut.Description = "Install the Memory Box Chrome/Edge Browser Bridge"
$BridgeShortcut.Save()

# Create Baidu Netdisk sync-folder setup shortcut.
$BaiduShortcutPath = Join-Path $Programs "Memory Box - 百度网盘同步设置.lnk"
$BaiduShortcut = $WshShell.CreateShortcut($BaiduShortcutPath)
$BaiduShortcut.TargetPath = Join-Path $InstallDir "Add-Baidu-Netdisk-Sync.cmd"
$BaiduShortcut.WorkingDirectory = $InstallDir
$BaiduShortcut.Description = "Connect a Baidu Netdisk synchronized folder to Memory Box"
$BaiduShortcut.Save()

# Optional background insurance scheduler. It is not enabled silently; the user opts in.
$InsuranceShortcutPath = Join-Path $Programs "Memory Box - 启用自动保险.lnk"
$InsuranceShortcut = $WshShell.CreateShortcut($InsuranceShortcutPath)
$InsuranceShortcut.TargetPath = Join-Path $InstallDir "Enable-Auto-Insurance.cmd"
$InsuranceShortcut.WorkingDirectory = $InstallDir
$InsuranceShortcut.Description = "Enable hourly Memory Box insurance checks; the configured interval controls actual backup frequency"
$InsuranceShortcut.Save()

# Associate portable Memory Box transfer packages with the safe importer.
$ExtKey = "HKCU:\Software\Classes\.mboxpack"
$TypeKey = "HKCU:\Software\Classes\MemoryBox.TransferPackage"
$OpenKey = Join-Path $TypeKey "shell\open\command"
New-Item -Path $ExtKey -Force | Out-Null
Set-Item -Path $ExtKey -Value "MemoryBox.TransferPackage"
New-Item -Path $TypeKey -Force | Out-Null
Set-Item -Path $TypeKey -Value "Memory Box Transfer Package"
New-Item -Path $OpenKey -Force | Out-Null
$DesktopCmd = Join-Path $InstallDir "MemoryBox.bat"
Set-Item -Path $OpenKey -Value ('"' + $DesktopCmd + '" "%1"')

# Associate end-to-end encrypted Memory Box packages too.
$EncExtKey = "HKCU:\Software\Classes\.mboxenc"
$EncTypeKey = "HKCU:\Software\Classes\MemoryBox.EncryptedPackage"
$EncOpenKey = Join-Path $EncTypeKey "shell\open\command"
New-Item -Path $EncExtKey -Force | Out-Null
Set-Item -Path $EncExtKey -Value "MemoryBox.EncryptedPackage"
New-Item -Path $EncTypeKey -Force | Out-Null
Set-Item -Path $EncTypeKey -Value "Memory Box End-to-End Encrypted Package"
New-Item -Path $EncOpenKey -Force | Out-Null
Set-Item -Path $EncOpenKey -Value ('"' + $DesktopCmd + '" "%1"')

# Associate encrypted disaster-recovery vaults. The local recovery helper prompts
# for the recovery code with hidden input; the code is never placed in an AI chat.
$RecExtKey = "HKCU:\Software\Classes\.mbxrecovery"
$RecTypeKey = "HKCU:\Software\Classes\MemoryBox.RecoveryVault"
$RecOpenKey = Join-Path $RecTypeKey "shell\open\command"
New-Item -Path $RecExtKey -Force | Out-Null
Set-Item -Path $RecExtKey -Value "MemoryBox.RecoveryVault"
New-Item -Path $RecTypeKey -Force | Out-Null
Set-Item -Path $RecTypeKey -Value "Memory Box Encrypted Recovery Vault"
New-Item -Path $RecOpenKey -Force | Out-Null
$RecoverCmd = Join-Path $InstallDir "MemoryBox-Recover.cmd"
Set-Item -Path $RecOpenKey -Value ('"' + $RecoverCmd + '" "%1"')

Write-Host "Initializing local SQLite database and E2EE identity..."
& (Join-Path $RuntimeDir "python.exe") (Join-Path $InstallDir "memorybox_main.py") list --limit 1 | Out-Null
& (Join-Path $RuntimeDir "python.exe") (Join-Path $InstallDir "memorybox_main.py") identity | Out-Null

# v0.16 neural retrieval: first install tries to fetch the pinned ~90 MB BGE ONNX model.
# Failure is non-fatal; Memory Box keeps the dependency-free hashing fallback.
if ($env:MEMORYBOX_SKIP_NEURAL_MODEL -ne "1") {
    try {
        $Status = & $Py (Join-Path $InstallDir "memorybox_main.py") model-status | ConvertFrom-Json
        if (-not $Status.ready) {
            Write-Host "Installing local BGE semantic model (~90 MB, one-time download)..."
            & $Py (Join-Path $InstallDir "memorybox_main.py") model-install
            if ($LASTEXITCODE -ne 0) { Write-Warning "Neural model installation failed; Memory Box will use the local hashing fallback." }
        }
    } catch {
        Write-Warning "Neural model setup skipped: $($_.Exception.Message)"
    }
}

Write-Host "Memory Box installed successfully. Opening..."
Start-Process (Join-Path $InstallDir "MemoryBox.bat")
