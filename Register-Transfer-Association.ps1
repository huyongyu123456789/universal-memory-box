$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$DesktopCmd = Join-Path $Root "MemoryBox.bat"
$RecoverCmd = Join-Path $Root "MemoryBox-Recover.cmd"

$types = @(
    @{ Ext = ".mboxpack"; Type = "MemoryBox.TransferPackage"; Label = "Memory Box Transfer Package"; Command = $DesktopCmd },
    @{ Ext = ".mboxenc";  Type = "MemoryBox.EncryptedPackage"; Label = "Memory Box End-to-End Encrypted Package"; Command = $DesktopCmd },
    @{ Ext = ".mbxrecovery"; Type = "MemoryBox.RecoveryVault"; Label = "Memory Box Encrypted Recovery Vault"; Command = $RecoverCmd }
)
foreach ($item in $types) {
    $ExtKey = "HKCU:\Software\Classes\$($item.Ext)"
    $TypeKey = "HKCU:\Software\Classes\$($item.Type)"
    $OpenKey = Join-Path $TypeKey "shell\open\command"
    New-Item -Path $ExtKey -Force | Out-Null
    Set-Item -Path $ExtKey -Value $item.Type
    New-Item -Path $TypeKey -Force | Out-Null
    Set-Item -Path $TypeKey -Value $item.Label
    New-Item -Path $OpenKey -Force | Out-Null
    Set-Item -Path $OpenKey -Value ('"' + $item.Command + '" "%1"')
}
Write-Host "Registered .mboxpack/.mboxenc with the desktop shell and .mbxrecovery with the local recovery helper."
