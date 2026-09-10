-- Memory Box SQLite schema v8
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memories(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT UNIQUE,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'general',
  source_agent TEXT NOT NULL DEFAULT 'unknown',
  source_type TEXT NOT NULL DEFAULT 'conversation',
  source_uri TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  pinned INTEGER NOT NULL DEFAULT 0,
  favorite INTEGER NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tags(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS memory_tags(
  memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY(memory_id_fk, tag_id)
);
CREATE TABLE IF NOT EXISTS memory_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  version_no INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(memory_id_fk, version_no)
);
CREATE TABLE IF NOT EXISTS attachments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sha256 TEXT NOT NULL UNIQUE,
  original_name TEXT NOT NULL,
  mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  size_bytes INTEGER NOT NULL,
  stored_relpath TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_attachments(
  memory_id_fk INTEGER NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  attachment_id INTEGER NOT NULL REFERENCES attachments(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'attachment',
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  PRIMARY KEY(memory_id_fk, attachment_id)
);
CREATE TABLE IF NOT EXISTS agent_connections(
  agent_key TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  detected INTEGER NOT NULL DEFAULT 0,
  connected INTEGER NOT NULL DEFAULT 0,
  connection_mode TEXT NOT NULL DEFAULT '',
  config_path TEXT NOT NULL DEFAULT '',
  last_checked_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  memory_id TEXT,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transfer_origins(
  source_device_id TEXT NOT NULL,
  origin_memory_id TEXT NOT NULL,
  local_memory_id TEXT NOT NULL,
  transfer_id TEXT NOT NULL DEFAULT '',
  imported_at TEXT NOT NULL,
  PRIMARY KEY(source_device_id, origin_memory_id)
);
CREATE TABLE IF NOT EXISTS sync_endpoints(
  endpoint_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  root_path TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  auto_import INTEGER NOT NULL DEFAULT 1,
  encryption_mode TEXT NOT NULL DEFAULT 'e2ee',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sync_receipts(
  endpoint_id TEXT NOT NULL,
  transfer_id TEXT NOT NULL,
  source_device_id TEXT NOT NULL,
  package_sha256 TEXT NOT NULL,
  status TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '',
  processed_at TEXT NOT NULL,
  PRIMARY KEY(endpoint_id, transfer_id, source_device_id)
);
CREATE TABLE IF NOT EXISTS trusted_devices(
  endpoint_id TEXT NOT NULL,
  device_id TEXT NOT NULL,
  device_name TEXT NOT NULL DEFAULT '',
  public_key TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  trusted_at TEXT NOT NULL,
  revoked_at TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(endpoint_id, device_id)
);
CREATE TABLE IF NOT EXISTS recovery_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  fingerprint TEXT NOT NULL DEFAULT '',
  recovery_file_sha256 TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insurance_settings(
  profile_id TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL DEFAULT 0,
  endpoint_id TEXT NOT NULL DEFAULT '',
  interval_hours INTEGER NOT NULL DEFAULT 24,
  retention INTEGER NOT NULL DEFAULT 7,
  deep_verify INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS insurance_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  endpoint_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  backup_path TEXT NOT NULL DEFAULT '',
  backup_sha256 TEXT NOT NULL DEFAULT '',
  transfer_id TEXT NOT NULL DEFAULT '',
  memory_count INTEGER NOT NULL DEFAULT 0,
  attachment_count INTEGER NOT NULL DEFAULT 0,
  detail TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);
