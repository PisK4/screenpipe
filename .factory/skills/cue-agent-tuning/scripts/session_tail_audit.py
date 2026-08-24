#!/usr/bin/env python3
"""Batch-classify how unattended Cue agent sessions ended.

Reads pi session JSONL files for one agent dir under
~/.cue/pi-config/sessions/ and reports, per session, the tail state: whether
the last assistant message completed, hung pending, or the file ends on a tool
result (stream died before any reply). This reproduces the manual forensics
used to separate stream-hang deaths from budget truncations and prose endings.

Usage:
    session_tail_audit.py [agent-dir-name] [--limit N] [--tail-chars C]

    agent-dir-name   e.g. --Users-pis-.cue-pi-intent--  (default: intent)
                     a bare word like "intent" is matched against dir names
    --limit          newest N sessions (default 10)
    --tail-chars     chars of the last assistant text to show (default 120)

Exit codes: 0 ok, 1 usage error, 2 agent dir not found.
"""

import argparse
import json
import sys
from pathlib import Path

SESSIONS_ROOT = Path.home() / ".cue" / "pi-config" / "sessions"


def last_assistant(entries):
    """Return (index, entry) of the last assistant message entry."""
    for i in range(len(entries) - 1, -1, -1):
        d = entries[i]
        msg = d.get("message") or {}
        if d.get("type") == "message" and msg.get("role") == "assistant":
            return i, d
        if d.get("role") == "assistant":
            return i, d
    return None, None


def classify(entries):
    idx, entry = last_assistant(entries)
    if not entry:
        return "NO_ASSISTANT", ""
    msg = entry.get("message") or entry
    stop = entry.get("stopReason") or msg.get("stopReason") or ""
    content = msg.get("content", "")
    if isinstance(content, list):
        content = " ".join(
            c.get("text", "") for c in content if isinstance(c, dict)
        )
    if stop:
        return f"STOP:{stop}", content
    # No stopReason recorded: pending stream death if we are at file end.
    if idx == len(entries) - 1:
        return "PENDING_HANG", content
    return "NO_STOP_REASON", content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", nargs="?", default="intent")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--tail-chars", type=int, default=120)
    args = ap.parse_args()

    dirs = [
        d for d in SESSIONS_ROOT.iterdir()
        if d.is_dir() and args.agent in d.name
    ] if SESSIONS_ROOT.exists() else []
    if not dirs:
        print(f"no agent dir matching {args.agent!r} under {SESSIONS_ROOT}",
              file=sys.stderr)
        return 2

    files = sorted(
        (f for d in dirs for f in d.glob("*.jsonl")),
        key=lambda f: f.stat().st_mtime, reverse=True,
    )[: args.limit]

    print(f"{'mtime':16} {'class':16} chars  session")
    for f in files:
        try:
            entries = [json.loads(l) for l in open(f) if l.strip()]
        except Exception as e:  # noqa: BLE001 - forensic tool, report and go on
            print(f"{f.name[:36]:36} UNREADABLE: {e}")
            continue
        cls, text = classify(entries)
        mtime = f.stat().st_mtime
        import datetime
        ts = datetime.datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
        tail = text[-args.tail_chars:].replace("\n", " ")
        print(f"{ts:16} {cls:16} {len(text):5}  {f.stem[:44]}")
        if tail:
            print(f"{'':16} {'':16} tail │ {tail}")

    # Junk-result scan: flag files whose tool results contain placeholder rows.
    print("\n-- placeholder-junk scan (tool results with '? | ?' rows) --")
    for f in files:
        try:
            raw = open(f).read()
        except Exception:  # noqa: BLE001
            continue
        n = raw.count("? | ? |")
        if n:
            print(f"{f.stem[:44]:44} junk-rows≈{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
