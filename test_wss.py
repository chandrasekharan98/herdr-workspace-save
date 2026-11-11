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

CURRENT = {"claude": "current (v7)"}
assert "no state integration" in wss.why_no_session("gemini", CURRENT, "t1")
assert "integration install codex" in wss.why_no_session("codex", {"codex": "not installed"}, "t1")
assert "integration install pi" in wss.why_no_session("pi", {"pi": "outdated (v6 < v8)"}, "t1")
assert wss.why_no_session("claude", CURRENT, "sideshow") == "claude in sideshow: no session id reported yet"

CWDS = {"type": "split", "direction": "down", "ratio": 0.5,
        "first": {"type": "pane", "cwd": "/"},
        "second": {"type": "pane", "cwd": "/no/such/dir"}}
assert wss.missing_cwds(CWDS, []) == ["/no/such/dir"]

import json, os, tempfile, time
os.environ["HERDR_PLUGIN_STATE_DIR"] = tempfile.mkdtemp()
for name in ("a", "b"):
    open(os.path.join(wss.state_dir(), name + ".json"), "w").write("{}")
wss.delete("a"); time.sleep(0.01); wss.delete("b")
assert wss.menu() == "", wss.menu()
wss.undelete()  # newest delete first
assert wss.menu().startswith("b\t"), wss.menu()
os.utime(os.path.join(wss.trash_dir(), "a.json"), (0, 0))
wss.purge_trash()
wss.undelete()
assert [e[0] for e in wss.entries()] == ["b"], wss.entries()

# Herdr app: a row of three (weights 1:1:2) whose last cell is a column; mod panes are dropped.
APP_TAB = {"type": "row", "children": [
    {"type": "block", "size": {"weight": 1.0}, "content": {"terminal": "t1"}},
    {"type": "block", "size": {"weight": 1.0}, "content": {"terminal": "t2"}},
    {"type": "column", "size": {"weight": 2.0}, "children": [
        {"type": "block", "content": {"terminal": "t3"}},
        {"type": "block", "content": {"mod": "files"}}]}]}
warn = []
tree = wss.capture_tree(APP_TAB, warn, "s / 1", leaf=lambda t, w, where: {"type": "pane", "cwd": "/" + t})
assert tree == {"type": "split", "direction": "right", "ratio": 0.25, "first": {"type": "pane", "cwd": "/t1"},
                "second": {"type": "split", "direction": "right", "ratio": 0.3333,
                           "first": {"type": "pane", "cwd": "/t2"}, "second": {"type": "pane", "cwd": "/t3"}}}, tree
assert warn == ["s / 1: files pane not saved"], warn

# Restore drives herdr-app: one terminal.open per split, beside the pane that holds its first branch.
calls = []
def fake_do(command, args):
    calls.append((command, args))
    return {"space": "sp1", "tab": "tb1", "terminal": f"t{len(calls)}", "pane": f"p{len(calls)}"}
wss.app_do = fake_do
wss.build(SAVED, "p0", table, [])
assert [(c, a.get("pane"), a.get("place"), a.get("folder")) for c, a in calls] == [
    ("pane.focus", "p0", None, None), ("terminal.open", None, "down", None)], calls
assert calls[1][1]["argv"] == ["claude"], calls  # stale transcript -> fresh claude
assert wss.launch_args({"type": "pane", "cwd": "/", "command": ["npm", "run", "dev"]}, table, []) == \
    {"folder": "/", "argv": ["npm", "run", "dev"]}

# Preview: the transcript tail keeps text messages only (no tool results, meta or <tags>).
home = tempfile.mkdtemp()
os.makedirs(os.path.join(home, ".claude/projects/x"))
with open(os.path.join(home, ".claude/projects/x/s1.jsonl"), "w") as f:
    for rec in [
        {"type": "user", "message": {"content": "<command-name>/clear</command-name>"}},
        {"type": "user", "isMeta": True, "message": {"content": "meta"}},
        {"type": "user", "message": {"content": "fix the bug"}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read"}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "..."}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Fixed."}]}},
    ]:
        f.write(json.dumps(rec) + "\n")
os.environ["HOME"] = home
assert wss.transcript_tail("s1") == [{"role": "user", "text": "fix the bug"},
                                     {"role": "assistant", "text": "Fixed."}], wss.transcript_tail("s1")
assert wss.transcript_tail("nope") == []

# Preview keeps each tab's split tree, with the screen captured at save time on its panes.
import io, contextlib
wss.write_save("pv", [{"label": "1", "root": {"type": "split", "direction": "right", "ratio": 0.5,
    "first": {"type": "pane", "cwd": "/", "command": ["btop"], "screen": {"text": "CPU", "cols": 80, "rows": 24}},
    "second": {"type": "pane", "cwd": "/"}}}])
out = io.StringIO()
with contextlib.redirect_stdout(out):
    wss.preview("pv")
root = json.loads(out.getvalue())["tabs"][0]["root"]
assert root["direction"] == "right" and root["first"]["run"] == "btop", root
assert root["first"]["screen"]["text"] == "CPU" and root["second"]["screen"] is None, root
assert "screen" not in wss.layout_only(root["first"])

print("ok")
