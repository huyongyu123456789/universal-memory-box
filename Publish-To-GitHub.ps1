param(
  [string]$Repository = "https://github.com/huyongyu123456789/-memory-box.git",
  [string]$Tag = "v0.14.0"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Memory Box v0.14.0 - GitHub Publisher" -ForegroundColor Red
Write-Host "Repository: $Repository"
Write-Host "Release tag: $Tag"
Write-Host ""

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Git for Windows is not installed." -ForegroundColor Yellow
  Write-Host "Install Git for Windows from https://git-scm.com/download/win and run this file again."
  Read-Host "Press Enter to close"
  exit 2
}

$gitDir = Join-Path $PSScriptRoot ".git"
if (-not (Test-Path $gitDir)) {
  git init -b main
}

git config user.name 2>$null | Out-Null
if ($LASTEXITCODE -ne 0 -or -not (git config user.name)) {
  git config user.name "Memory Box Publisher"
}
if (-not (git config user.email)) {
  git config user.email "memory-box@users.noreply.github.com"
}

$originExists = git remote 2>$null | Select-String '^origin$'
if ($originExists) {
  git remote set-url origin $Repository
} else {
  git remote add origin $Repository
}

git add -A
$hasHead = $true
try { git rev-parse --verify HEAD *> $null } catch { $hasHead = $false }
$changes = git status --porcelain
if ($changes -or -not $hasHead) {
  git commit -m "Release Memory Box v0.14.0: Windows, macOS and HarmonyOS"
}

git branch -M main
Write-Host ""
Write-Host "Pushing main... Git may open a browser for GitHub sign-in." -ForegroundColor Cyan
git push -u origin main

# Create/update local release tag, but never force-overwrite a remote tag.
$remoteTag = git ls-remote --tags origin "refs/tags/$Tag"
if ($remoteTag) {
  Write-Host "Remote tag $Tag already exists; leaving it unchanged." -ForegroundColor Yellow
} else {
  git tag -f -a $Tag -m "Memory Box $Tag"
  Write-Host "Pushing release tag $Tag..." -ForegroundColor Cyan
  git push origin "refs/tags/$Tag"
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "Expected GitHub Actions:" -ForegroundColor Green
Write-Host "  - CI: Linux / Windows / macOS tests"
Write-Host "  - Validate HarmonyOS project"
Write-Host "  - Build Windows desktop app -> MemoryBox.exe + MemoryBox-CLI.exe"
Write-Host "  - Build macOS apps -> arm64 + x86_64 .app/.dmg"
Write-Host ""
Write-Host "Actions page: https://github.com/huyongyu123456789/-memory-box/actions"
Read-Host "Press Enter to close"
