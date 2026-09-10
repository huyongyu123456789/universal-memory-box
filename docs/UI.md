# Memory Box v0.12 UI

v0.12 introduces a desktop-control-center shell built directly on top of the existing local Memory Box HTTP API. It is an Apple-inspired design language, not a copy of any Apple product.

## Design principles

- calm, low-noise hierarchy with generous whitespace;
- translucent sidebar/top toolbar where the platform supports backdrop blur;
- rounded surfaces, thin separators and restrained shadows;
- one primary accent color and semantic health colors;
- system-native typography first, with CJK sans-serif fallbacks;
- responsive desktop/tablet/mobile layout;
- Light / Dark / Auto appearance stored locally in the browser profile;
- no external web fonts, analytics or remote UI assets.

## Primary screens

- **Home**: disaster-recovery health, quick actions, recent memories, E2EE/sync/insurance summary.
- **Memories**: global search, category filter, pinned/favorite state, open and Resume Context actions.
- **Save**: one-step memory capture with category/tags and local attachments.
- **Agent**: local MCP Agent detection and connection.
- **Sync**: device fingerprint, trusted devices, Baidu Netdisk/OneDrive/NAS folders, encrypted LAN transfer.
- **Insurance**: GREEN/YELLOW/RED readiness state, automatic encrypted insurance and local recovery-code drill.
- **Recovery**: create/restore `.mbxrecovery` without exposing the recovery code to MCP.
- **Transfer**: export/import `.mboxpack` complete-session capsules.
- **Settings**: Light / Dark / Auto UI appearance.

## Responsive behavior

Desktop uses a persistent 228 px sidebar. Narrow desktops collapse it to icon navigation. Mobile converts the first five navigation destinations into a fixed bottom bar and keeps the global search toolbar visible.

## Security boundary

The redesign does not widen the network surface. The normal application still defaults to `127.0.0.1`, and human-only recovery secrets remain outside MCP/Agent APIs.

## v0.13 desktop wrapper

The same control-center UI now runs inside a native Windows pywebview/WebView2 window. Desktop-only toggles appear in Settings when `window.pywebview` is available; browser mode remains fully usable.
