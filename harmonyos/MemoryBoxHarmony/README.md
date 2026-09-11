# Memory Box for HarmonyOS NEXT — v0.16.0

This is the native ArkTS/ArkUI **Stage model** foundation for Memory Box on HarmonyOS NEXT. It uses a local HarmonyOS RDB (SQLite-backed relationalStore) rather than embedding the Python desktop runtime.

## What is implemented in v0.16

- Native HarmonyOS Stage-model project structure.
- ArkTS/ArkUI home screen using the red cavalry app icon.
- Local `relationalStore` database initialization and recent-memory list.
- Phone/tablet/2-in-1 device targets.
- Internet permission reserved for trusted-device E2EE sync transport.

## Not yet claimed as complete

Full `.mboxpack`/`.mboxenc` import, X25519/AES-GCM interoperability, background sync, and AppGallery-signed release packaging still require DevEco Studio/HarmonyOS SDK validation. The source is intentionally separated from the Python desktop shell so it can evolve as a real HarmonyOS app rather than a web wrapper.

## Build

Open `harmonyos/MemoryBoxHarmony` in a current DevEco Studio, configure an AppGallery Connect signing profile, then build the entry HAP/APP. Release publishing requires Huawei developer signing credentials.
