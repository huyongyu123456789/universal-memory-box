# Project Workspaces (v0.16)

A Project Workspace is a durable continuity object above individual memories.

Fields: stable `P000xxx` id, name, summary, current state, next action, status, timestamps, and linked memories with roles such as `context`, `decision`, `evidence`, or `next-step`.

Projects are local-first and migrate in `.mboxpack` transfer format v3. Conflicting remote project IDs are remapped without overwriting local projects, while origin mapping is preserved for idempotent re-import.

## Smart retrieval

The v0.14 ranker is fully local and dependency-free. It combines weighted field evidence (title, summary, tags, content, project name), recency decay, pin/favorite signals, and approximate string similarity. It deliberately does not claim neural embeddings.

## Resume

`project-resume` builds a project header containing status/current state/next action and then appends the highest-ranked linked memories as normal Memory Box Resume Context.

## v0.16 derived continuity

v0.16 adds derived project continuity fields (`auto_summary`, `auto_current_state`, `auto_next_action`). They are refreshed from linked memories and used as fallbacks in Project Resume Context, but never overwrite curated user fields. Smart retrieval now also includes a fully local vector similarity signal; see `SEMANTIC.md`.
