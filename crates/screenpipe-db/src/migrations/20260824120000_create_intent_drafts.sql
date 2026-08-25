-- Intent drafts: non-terminal generation exits (save_intent_draft). A draft
-- is an unripe signal the heartbeat model archives across ticks; lifecycle
-- active -> submitted | discarded | expired. TTL and cap are enforced by
-- DatabaseManager + the POST route, not by constraints.
CREATE TABLE intent_drafts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  gist TEXT NOT NULL,
  evidence_so_far TEXT NOT NULL,
  ripe_when TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active','submitted','discarded','expired')),
  renew_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL DEFAULT (unixepoch()),
  updated_at INTEGER NOT NULL DEFAULT (unixepoch())
);
CREATE INDEX idx_intent_drafts_active ON intent_drafts(status, created_at);
