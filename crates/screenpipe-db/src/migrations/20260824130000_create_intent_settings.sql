-- Intent runtime configuration. Shared SQLite KV so BOTH the engine process
-- (draft cap/TTL enforcement on /intent-cards/drafts) and the app process
-- (heartbeat cadence, card TTL, material window) read one definition.
-- Values are clamped at load; missing keys fall back to compile-time defaults.
CREATE TABLE IF NOT EXISTS intent_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
