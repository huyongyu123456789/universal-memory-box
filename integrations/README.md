# Agent integrations

Memory Box uses MCP as the primary local bridge and ships platform-specific wrappers where useful.

- `workbuddy/`: WorkBuddy MCP + Skill connector bundle.
- `kimi-plugin/`: Kimi Code plugin manifest + Skill + MCP declaration.
- `browser-extension/`: Chrome/Edge bridge for web chat products that cannot directly reach a local MCP server. It saves only user-selected text to `127.0.0.1:8765`.
- `generic/SKILL.md`: fallback behavior for any Skill-capable agent.

The desktop app can auto-detect and configure supported local clients including Kimi Code, Cursor, Gemini CLI, Claude Code, Codex CLI, Tencent CodeBuddy, and Qoder. WorkBuddy/TRAE/cloud or browser-only products may still require the platform's own import/approval step.
