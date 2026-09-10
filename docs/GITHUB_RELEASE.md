# GitHub release / Actions

## One-click Windows publishing

From the extracted Memory Box v0.14.0 source folder, double-click:

`Publish-To-GitHub.cmd`

The helper targets `https://github.com/huyongyu123456789/-memory-box.git`, pushes `main`, then publishes tag `v0.14.0` if that remote tag does not already exist.

Expected automation:

- `CI` runs on every push and tests Linux, Windows and macOS.
- `Validate HarmonyOS project` runs when HarmonyOS project/icon paths change on `main`.
- `Build Windows desktop app` runs on the `v0.14.0` tag and produces `MemoryBox.exe` and `MemoryBox-CLI.exe` inside a Windows ZIP artifact.
- `Build macOS apps` runs on the tag and produces arm64 and x86_64 app ZIP/DMG artifacts.

The publishing helper never stores a GitHub password or token. Git for Windows/Git Credential Manager handles browser sign-in when required.

## Important signing notes

The Windows build is unsigned unless a code-signing certificate is later configured. macOS CI currently uses an ad-hoc signature for bundle integrity; frictionless distribution to arbitrary Macs requires a Developer ID certificate and Apple notarization. HarmonyOS release-device installation requires a valid DevEco/Huawei signing profile.
