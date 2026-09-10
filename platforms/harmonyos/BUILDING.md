# HarmonyOS Build Notes

1. Install DevEco Studio 6.1 or newer and API 26.0.0 SDK.
2. Open `platforms/harmonyos` as a project.
3. Let DevEco Studio refresh/synchronize Hvigor toolchain metadata if it proposes a compatible update.
4. Configure a debug or release signing profile.
5. Build with **Build > Build Hap(s)/APP(s)** or `hvigorw --mode project -p product=default -p buildMode=release assembleApp`.
6. Install the signed HAP/APP. Tapping the red cavalry icon starts `EntryAbility` directly.
