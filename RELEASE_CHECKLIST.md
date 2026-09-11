# Memory Box v0.16.0 Release Checklist

- [x] Python, Browser Bridge, Kimi and WorkBuddy metadata synchronized to 0.16.0.
- [x] Red cavalry icon present as PNG / Windows ICO / macOS ICNS / HarmonyOS media asset.
- [x] FastEmbed BGE model manager is explicit-download and local-only at retrieval time.
- [x] Windows build workflow stages neural model cache and creates a double-click desktop release folder.
- [x] macOS workflow creates `MemoryBox.app` + DMG and supports optional Developer ID notarization.
- [x] HarmonyOS NEXT ArkTS/ArkUI Stage project added with local RDB foundation.
- [x] 92/92 source regression tests pass under ResourceWarning strict mode.
- [ ] Windows native artifact must still be built on `windows-latest` and smoke-tested.
- [ ] macOS signed/notarized artifact requires publisher Apple Developer credentials and macOS runner validation.
- [ ] HarmonyOS HAP/APP requires DevEco Studio/HarmonyOS SDK build and publisher signing; full E2EE parity is not claimed yet.
