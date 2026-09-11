# Duplicate Review and Merge (v0.16)

Duplicate handling is deliberately review-first. `dedup-find` and `dedup-scan` compare exact normalized content, local vector similarity, token overlap, title similarity and summary similarity. They return candidates only.

```bash
memorybox dedup-find M000007
memorybox dedup-scan --threshold 0.78
memorybox dedup-merge M000007 M000021 --keep-sources
```

An explicit merge creates a new consolidated memory. Project memberships from source memories are carried to the merged memory. The UI keeps source memories by default; CLI users can choose whether to archive them. Merge events are recorded in `dedup_events`.

Project auto-insights are separate from curated fields: derived summaries can be regenerated without erasing a human-authored summary, state or next action.
