#!/usr/bin/env python3
"""Self-check for the pure parts: run `python3 test_wss.py`."""

import wss

SAVED = {
    "type": "split", "direction": "down", "ratio": 0.5,
    "first": {"type": "pane", "cwd": "/tmp", "command": ["npm", "run", "dev"]},
    "second": {"type": "pane", "cwd": "/src", "label": "agent",
               "agent": {"agent": "claude", "kind": "id", "value": "dead-beef"}},
}
APPLIED = {
    "type": "split", "direction": "down", "ratio": 0.5,
    "first": {"type": "pane", "pane_id": "w1:p1"},
    "second": {"type": "pane", "pane_id": "w1:p2"},
}

stripped = wss.layout_only(SAVED)
assert "command" not in stripped["first"], stripped
assert "agent" not in stripped["second"], stripped
assert stripped["second"]["label"] == "agent", stripped

pairs = wss.pair_panes(SAVED, APPLIED, [])
assert [p[1] for p in pairs] == ["w1:p1", "w1:p2"], pairs

table = wss.DEFAULT_RESUME
assert wss.armed_command(SAVED["first"], table) == "npm run dev"
# Unknown session id: no transcript on disk, so resume is dropped rather than armed to fail.
assert wss.armed_command(SAVED["second"], table) == "claude"
assert wss.armed_command({"type": "pane", "cwd": "/tmp"}, table) is None
assert wss.armed_command(
    {"type": "pane", "agent": {"agent": "agy", "kind": "id", "value": "abc"}}, table
) == "agy --conversation abc"
warn = []
assert wss.armed_command(
    {"type": "pane", "agent": {"agent": "nosuchagent", "kind": "id", "value": "abc"}}, table, warn
) == "nosuchagent"
assert "no resume command known" in warn[0], warn

warn = []
assert wss.armed_command(SAVED["second"], table, warn) == "claude"
assert "transcript deleted" in warn[0], warn

assert "no state integration" in wss.why_no_session("gemini", {"claude": "current (v7)"})
assert "integration install codex" in wss.why_no_session("codex", {"codex": "not installed (/p)"})
assert "integration install pi" in wss.why_no_session("pi", {"pi": "outdated (v6 < v8)"})
assert "no session id reported yet" in wss.why_no_session("claude", {"claude": "current (v7)"})

CWDS = {"type": "split", "direction": "down", "ratio": 0.5,
        "first": {"type": "pane", "cwd": "/"},
        "second": {"type": "pane", "cwd": "/no/such/dir"}}
assert wss.missing_cwds(CWDS, []) == ["/no/such/dir"]

print("ok")
