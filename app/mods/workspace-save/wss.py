#!/usr/bin/env python3
"""Save a Herdr workspace — layout, cwds, agent sessions, running commands — and reopen it later."""

import glob
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time

FORMAT_VERSION = 1
HERDR = os.environ.get("HERDR_BIN_PATH", "herdr")

# Mirrors Herdr's own resume table (src/app/agent_resume.rs); re-check it when Herdr updates.
# {ref} is the agent's own session id or session path, as reported to Herdr.
# Wrong flag for your agent? Override in config.json — armed commands are shown before you run them.
DEFAULT_RESUME = {
    "claude": ["claude", "--resume", "{ref}"],
    "codex": ["codex", "resume", "{ref}"],
    "grok": ["grok", "--resume", "{ref}"],
    "droid": ["droid", "--resume", "{ref}"],
    "devin": ["devin", "--resume", "{ref}"],
    "hermes": ["hermes", "--resume", "{ref}"],
    "cursor": ["cursor-agent", "--resume", "{ref}"],
    "qodercli": ["qodercli", "--resume", "{ref}"],
    "agy": ["agy", "--conversation", "{ref}"],
    "opencode": ["opencode", "--session", "{ref}"],
    "pi": ["pi", "--session", "{ref}"],
    "kimi": ["kimi", "--session", "{ref}"],
    "kilo": ["kilo", "--session", "{ref}"],
    "mastracode": ["mastracode", "--thread", "{ref}"],
}

REPORT = "last-report.txt"
SHELLS = {"bash", "zsh", "fish", "sh", "dash", "ksh", "nu", "elvish", "xonsh"}


def state_dir():
    # The Herdr app has no plugin env; it shares the TUI plugin's folder so both see every save.
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR") or os.path.expanduser(
        "~/.local/state/herdr/plugins/workspace-save")
    d = os.path.join(state, "workspaces")
    os.makedirs(d, exist_ok=True)
    return d


def resume_table():
    config = os.path.join(os.environ.get("HERDR_PLUGIN_CONFIG_DIR", ""), "config.json")
    table = dict(DEFAULT_RESUME)
    if os.path.exists(config):
        with open(config) as f:
            table.update(json.load(f).get("resume", {}))
    return table


def call(method, params):
    sock_path = os.environ.get("HERDR_SOCKET_PATH")
    if not sock_path:
        sys.exit("HERDR_SOCKET_PATH unset — not running inside Herdr")
    s = socket.socket(socket.AF_UNIX)
    s.connect(sock_path)
    s.sendall((json.dumps({"id": "wss", "method": method, "params": params}) + "\n").encode())
    buf = b""
    while b"\n" not in buf:
        chunk = s.recv(65536)
        if not chunk:
            sys.exit(f"herdr closed the socket during {method}")
        buf += chunk
    s.close()
    reply = json.loads(buf.split(b"\n", 1)[0].decode())
    if "error" in reply:
        sys.exit(f"{method} failed: {reply['error']}")
    return reply["result"]


def notify(title, body, alert=False):
    cmd = [HERDR, "notification", "show", title, "--body", body]
    if alert:
        cmd += ["--sound", "request"]
    subprocess.run(cmd, stdout=subprocess.DEVNULL)


def slugify(label):
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or "workspace"


# ---------------------------------------------------------------- capture


def integration_status():
    """agent -> Herdr integration state. Only agents with an installed one report a session ref."""
    try:
        out = subprocess.run([HERDR, "integration", "status"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True).stdout
    except OSError:
        return {}
    status = {}
    for line in out.splitlines():
        name, sep, rest = line.partition(":")
        if sep:
            status[name.strip()] = rest.split("(/")[0].strip()  # drop the integration file path
    return status


def why_no_session(agent, status, where):
    at = f"{agent} in {where}"
    if agent not in status:
        return f"{at}: Herdr ships no state integration for {agent}, its session cannot be captured"
    if status[agent].startswith("not installed"):
        return f"{at}: integration not installed — run: herdr integration install {agent}"
    if status[agent].startswith("outdated"):
        return f"{at}: integration {status[agent]} — run: herdr integration install {agent}"
    return f"{at}: no session id reported yet"


def foreground_argv(pane_id, warn, where):
    """The command a pane is running, or None when it is just sitting at a shell."""
    info = call("pane.process_info", {"pane_id": pane_id})["process_info"]
    # A pane launched with a command reports it as the shell pid, so match on name only.
    procs = [p for p in info.get("foreground_processes", []) if p.get("name") not in SHELLS]
    if not procs:
        return None
    if len(procs) > 1:
        rest = " | ".join(p.get("name", "?") for p in procs[1:])
        warn.append(f"{where}: pipeline captured as its first stage only, dropping: {rest}")
    return procs[0].get("argv") or None


def capture_node(node, agents, warn, status, where):
    if node["type"] == "split":
        return {
            "type": "split",
            "direction": node["direction"],
            "ratio": node["ratio"],
            "first": capture_node(node["first"], agents, warn, status, where),
            "second": capture_node(node["second"], agents, warn, status, where),
        }

    pane = {"type": "pane"}
    for key in ("cwd", "label", "env"):
        if node.get(key):
            pane[key] = node[key]

    pane_id = node.get("pane_id")
    live = agents.get(pane_id, {})
    session = live.get("agent_session")
    if session:
        pane["agent"] = session
    else:
        if live.get("agent"):
            warn.append(why_no_session(live["agent"], status, node.get("label") or where or pane_id))
        argv = foreground_argv(pane_id, warn, node.get("label") or where or pane_id) if pane_id else None
        if argv:
            pane["command"] = argv
    return pane


def save(name=None):
    ws_id = os.environ.get("HERDR_WORKSPACE_ID")
    if not ws_id:
        sys.exit("HERDR_WORKSPACE_ID unset — invoke from a workspace")
    label = call("workspace.get", {"workspace_id": ws_id})["workspace"].get("label") or ws_id
    agents = {a["pane_id"]: a for a in call("session.snapshot", {})["snapshot"]["agents"]}

    tabs, warn, status = [], [], integration_status()
    for tab in call("tab.list", {"workspace_id": ws_id})["tabs"]:
        root = call("layout.export", {"tab_id": tab["tab_id"]})["layout"]["root"]
        tabs.append({"label": tab.get("label"),
                     "root": capture_node(root, agents, warn, status, tab.get("label"))})

    path = write_save(label, tabs, name)
    warn = sorted(set(warn))
    notify(f"Saved '{doc['label']}'", "\n".join([path] + warn), alert=bool(warn))
    print(path)
    for line in warn:
        print(line, file=sys.stderr)
    if warn:
        report(f"Saved '{doc['label']}', but {len(warn)} agent session(s) were NOT captured.",
               warn, f"Those panes reopen as fresh agents.\n\nSaved to: {path}")


def write_save(label, tabs, name=None):
    doc = {
        "version": FORMAT_VERSION,
        "name": name or slugify(label),
        "label": label,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tabs": tabs,
    }
    path = os.path.join(state_dir(), doc["name"] + ".json")
    with open(path, "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return path


def save_and_close():
    save()
    call("workspace.close", {"workspace_id": os.environ["HERDR_WORKSPACE_ID"]})


# ---------------------------------------------------------------- restore


def claude_transcript_exists(ref):
    return bool(glob.glob(os.path.expanduser(f"~/.claude/projects/*/{ref}.jsonl")))


def armed_command(pane, table, warn=None):
    """Text to type into a restored pane, or None. Never executed — the user presses enter."""
    def note(msg):
        if warn is not None:
            warn.append(msg)

    if pane.get("command"):
        return shlex.join(pane["command"])

    session = pane.get("agent")
    if not session:
        return None
    agent = session.get("agent")
    ref = session.get("value")
    template = table.get(agent)
    if not ref:
        note(f"{agent}: saved without a session id, opened fresh")
        return agent
    if not template:
        note(f"{agent}: no resume command known, opened fresh — add one to config.json")
        return agent
    if agent == "claude" and session.get("kind") == "id" and not claude_transcript_exists(ref):
        # transcript aged out of cleanupPeriodDays; resume would just error
        note(f"claude {ref[:8]}: transcript deleted, opened fresh — raise cleanupPeriodDays")
        return "claude"
    return shlex.join([part.replace("{ref}", ref) for part in template])


def layout_only(node):
    """Herdr's layout tree: our agent/command keys stripped out."""
    if node["type"] == "split":
        return {**node, "first": layout_only(node["first"]), "second": layout_only(node["second"])}
    return {k: v for k, v in node.items() if k in ("type", "cwd", "env", "label")}


def missing_cwds(node, out):
    """Saved directories that are gone. Herdr substitutes $HOME, so restores go quietly wrong."""
    if node["type"] == "split":
        missing_cwds(node["first"], out)
        missing_cwds(node["second"], out)
    elif node.get("cwd") and not os.path.isdir(node["cwd"]):
        out.append(node["cwd"])
    return out


def pair_panes(saved, applied, out):
    """Walk both trees in lockstep to learn which live pane got which saved pane."""
    if saved["type"] == "split":
        pair_panes(saved["first"], applied["first"], out)
        pair_panes(saved["second"], applied["second"], out)
    else:
        out.append((saved, applied["pane_id"]))
    return out


def load(name):
    path = os.path.join(state_dir(), name + ".json")
    if not os.path.exists(path):
        sys.exit(f"no saved workspace named '{name}' at {path}")
    with open(path) as f:
        doc = json.load(f)
    if doc.get("version") != FORMAT_VERSION:
        sys.exit(f"{path} is format version {doc.get('version')}, expected {FORMAT_VERSION}")
    return doc


def restore(name):
    doc = load(name)
    table = resume_table()
    created = call("workspace.create", {"label": doc["label"], "focus": True})
    ws_id = created["workspace"]["workspace_id"]
    # The new workspace ships with one empty tab; reuse it for the first saved tab.
    spare_tab = created["tab"]["tab_id"]

    armed, gone, warn = 0, [], []
    for tab in doc["tabs"]:
        missing_cwds(tab["root"], gone)
        params = {"root": layout_only(tab["root"]), "focus": True}
        if spare_tab:
            params["tab_id"] = spare_tab  # herdr rejects tab_id and workspace_id together
            spare_tab = None
        else:
            params["workspace_id"] = ws_id
        if tab.get("label"):
            params["tab_label"] = tab["label"]
        applied = call("layout.apply", params)["layout"]

        for saved_pane, pane_id in pair_panes(tab["root"], applied["root"], []):
            text = armed_command(saved_pane, table, warn)
            if text:
                call("pane.send_text", {"pane_id": pane_id, "text": text})
                armed += 1

    call("workspace.focus", {"workspace_id": ws_id})
    body = [f"{armed} pane(s) armed — press enter in each to run"]
    if gone:
        body.append(f"{len(gone)} cwd(s) gone, opened in $HOME: " + ", ".join(sorted(set(gone))))
    body += sorted(set(warn))
    warn = sorted(set(warn)) + [f"cwd gone, opened in $HOME: {c}" for c in sorted(set(gone))]
    notify(f"Reopened '{doc['label']}'", "\n".join(body), alert=bool(warn))
    print(ws_id)
    for line in warn:
        print(line, file=sys.stderr)
    return warn


# ---------------------------------------------------------------- picker


def entries():
    out = []
    for path in sorted(glob.glob(os.path.join(state_dir(), "*.json"))):
        try:
            with open(path) as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        out.append((os.path.basename(path)[:-5], doc.get("label", "?"),
                    doc.get("saved_at", "?"), len(doc.get("tabs", [])), path))
    return out


TRASH_DAYS = 7


def trash_dir():
    d = os.path.join(state_dir(), "trash")
    os.makedirs(d, exist_ok=True)
    return d


def delete(name):
    """Soft delete: move to trash/ and stamp the time, so undelete restores the newest first."""
    src = os.path.join(state_dir(), name + ".json")
    if os.path.exists(src):
        dst = os.path.join(trash_dir(), name + ".json")
        os.replace(src, dst)
        os.utime(dst)


def undelete():
    trashed = sorted(glob.glob(os.path.join(trash_dir(), "*.json")), key=os.path.getmtime)
    for path in reversed(trashed):
        dst = os.path.join(state_dir(), os.path.basename(path))
        if not os.path.exists(dst):  # re-saved since the delete: the newer save wins
            os.replace(path, dst)
            return


def purge_trash():
    cutoff = time.time() - TRASH_DAYS * 86400
    for path in glob.glob(os.path.join(trash_dir(), "*.json")):
        if os.path.getmtime(path) < cutoff:
            os.remove(path)


def menu():
    return "\n".join(f"{n}\t{l}\t{ts}\t{t} tabs\t{p}" for n, l, ts, t, p in entries())


def list_saved():
    print(state_dir())
    for name, label, saved_at, tabs, path in entries():
        print(f"{name}\t{label}\t{saved_at}\t{tabs} tabs\t{path}")


def pick():
    if not shutil.which("fzf"):
        print("fzf not found on PATH. Install it, or run: python3 wss.py list")
        input("Press enter to close…")
        return
    purge_trash()
    rows = menu()
    if not rows:
        print(f"No saved workspaces yet in {state_dir()}")
        input("Press enter to close…")
        return
    # Delete is undoable instead of confirmed: one keypress, the row vanishes, ctrl-z brings it back.
    # ctrl-x, not ctrl-d: shell habit sends ctrl-d to quit.
    wss = f"{shlex.quote(sys.executable)} {shlex.quote(os.path.abspath(__file__))}"
    header = f"enter reopens · ctrl-x deletes · ctrl-z undoes · saved to {state_dir()}"
    fzf = subprocess.run(
        ["fzf", "--delimiter=\t", "--with-nth=1,2,3,4", "--prompt=saved workspace> ",
         "--header=" + header, "--preview", "cat {5}",
         "--bind", f"ctrl-x:transform-header(echo deleted {{1}} · ctrl-z undoes · kept {TRASH_DAYS} days in trash/)"
                   f"+execute-silent({wss} delete {{1}})+reload({wss} menu)",
         "--bind", f"ctrl-z:execute-silent({wss} undelete)+reload({wss} menu)+change-header({header})"],
        input=rows, stdout=subprocess.PIPE, text=True,  # stderr stays on the tty: that is fzf's UI
    )
    if fzf.returncode != 0 or not fzf.stdout.strip():
        return
    warn = restore(fzf.stdout.split("\t")[0])
    if warn:
        print("\nReopened with warnings:\n  " + "\n  ".join(warn))
        input("\nPress enter to close…")


def open_pane(entrypoint):
    subprocess.run([HERDR, "plugin", "pane", "open",
                    "--plugin", os.environ.get("HERDR_PLUGIN_ID", "workspace-save"),
                    "--entrypoint", entrypoint, "--placement", "overlay"],
                   stdout=subprocess.DEVNULL)


def report(headline, lines, footer=""):
    """Stage a message and open a pane for it: Herdr shows plugin output nowhere else."""
    with open(os.path.join(state_dir(), REPORT), "w") as f:
        f.write("\n".join([headline, ""] + [f"  - {line}" for line in lines] + ["", footer]))
    open_pane("report")


def show_report():
    path = os.path.join(state_dir(), REPORT)
    print(open(path).read() if os.path.exists(path) else "Nothing to report.")
    input("\nPress enter to close…")


# ---------------------------------------------------------------- Herdr app (herdr-app + herdr-core)
# The app keeps each tab's splits in herdr-core's "herdr-app" document and each terminal's
# foreground program in `hc get`. Saves use the same tree and file as the TUI, so either restores.

# Written by the opt-in Claude Code SessionStart hook (README: Agent sessions). One JSON object
# per line: {"terminal", "agent", "session_id", "cwd", "at"}; the last line for a terminal wins.
SESSIONS = os.path.expanduser("~/.local/state/herdr/terminal-sessions.jsonl")
APP_AGENTS = {"claude-code": "claude"}  # hc's agent names -> the resume table's


def run_json(argv, stdin=None):
    r = subprocess.run(argv, input=stdin, capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        sys.exit(f"{' '.join(argv[:3])}: {(r.stderr or r.stdout).strip()}")
    if isinstance(data, dict) and "error" in data:
        sys.exit(f"{' '.join(argv[:3])}: {data['error']}")
    return data


def app_do(command, args):
    return run_json(["herdr-app", "do", command, json.dumps({k: v for k, v in args.items() if v is not None})])


def layout_doc():
    req = {"jsonrpc": "2.0", "id": 1, "method": "doc.get", "params": {"name": "herdr-app"}}
    return run_json(["hc", "connect"], json.dumps(req) + "\n")["result"]["value"] or {"spaces": []}


def claude_session(pid, terminal):
    """Claude Code's own ~/.claude/sessions/<pid>.json first; the hook's map when that is missing."""
    try:
        with open(os.path.expanduser(f"~/.claude/sessions/{pid}.json")) as f:
            return json.load(f)["sessionId"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    found = None
    try:
        with open(SESSIONS) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("terminal") == terminal:
                    found = rec.get("session_id")
    except OSError:
        pass
    return found


def capture_terminal(address, warn, where):
    t = run_json(["hc", "get", address, "--json"])
    fg = t.get("foreground") or {}
    pane = {"type": "pane"}
    if fg.get("cwd") or t.get("cwd"):
        pane["cwd"] = fg.get("cwd") or t["cwd"]
    if t.get("name"):
        pane["label"] = t["name"]
    reported = (t.get("status") or {}).get("app")
    agent = "claude" if fg.get("name") == "claude" else APP_AGENTS.get(reported, reported)
    if agent == "claude":
        session = claude_session(fg.get("pid"), address)
        if session:
            pane["agent"] = {"source": "herdr-app", "agent": "claude", "kind": "id", "value": session}
            return pane
        warn.append(f"claude in {where}: no session id found, it will reopen fresh")
    elif agent:
        warn.append(f"{agent} in {where}: the Herdr app can't capture {agent} sessions, saved its command only")
    if fg.get("argv") and fg.get("name") not in SHELLS:
        pane["command"] = fg["argv"]
    return pane


def capture_tree(node, warn, where, leaf=capture_terminal):
    """App row/column tree -> the TUI's binary split tree (row = right, column = down)."""
    if node["type"] == "block":
        content = node.get("content") or {}
        if content.get("terminal"):
            return leaf(content["terminal"], warn, where)
        warn.append(f"{where}: {content.get('mod') or 'non-terminal'} pane not saved")
        return None
    kids = [((c.get("size") or {}).get("weight", 1.0), capture_tree(c, warn, where, leaf))
            for c in node.get("children", [])]
    kids = [(w, k) for w, k in kids if k]
    direction = "right" if node["type"] == "row" else "down"

    def fold(ks):
        if len(ks) == 1:
            return ks[0][1]
        return {"type": "split", "direction": direction,
                "ratio": round(ks[0][0] / sum(w for w, _ in ks), 4),
                "first": ks[0][1], "second": fold(ks[1:])}
    return fold(kids) if kids else None


def app_save(space_id):
    if "/" in space_id:
        sys.exit("spaces on other machines can't be saved yet")
    space = next((s for s in layout_doc()["spaces"] if s["id"] == space_id), None)
    if not space:
        sys.exit(f"no space {space_id} on this machine")
    shown = next((s for s in run_json(["herdr-app", "ls"])["spaces"] if s["id"] == space_id), {})
    label = space.get("name") or shown.get("name") or space_id
    tabs, warn = [], []
    for i, tab in enumerate(space.get("tabs", []), 1):
        root = capture_tree(tab["root"], warn, f"{label} / {tab.get('name') or i}")
        if root:
            tabs.append({"label": tab.get("name") or None, "root": root})
    if not tabs:
        sys.exit(f"'{label}' has no terminals to save")
    print(json.dumps({"path": write_save(label, tabs), "label": label, "warnings": sorted(set(warn))}))


def first_leaf(node):
    return first_leaf(node["first"]) if node["type"] == "split" else node


def launch_args(pane, table, warn):
    """Folder and argv to start a restored pane with. The app runs argv; it can't type it unsent."""
    text = armed_command(pane, table, warn)
    cwd = pane.get("cwd")
    return {"folder": cwd if cwd and os.path.isdir(cwd) else None,
            "argv": shlex.split(text) if text else None}


def pane_of(terminal):
    for space in run_json(["herdr-app", "ls"])["spaces"]:
        for tab in space["tabs"]:
            for t in tab["terminals"]:
                if t["terminal"] == terminal:
                    return t["pane"]
    sys.exit(f"terminal {terminal} has no pane")


def build(node, pane, table, warn):
    """`pane` already runs node's first leaf; split it for every second branch."""
    if node["type"] != "split":
        return
    app_do("pane.focus", {"pane": pane})  # terminal.open splits the focused pane; pane.split has no folder
    made = app_do("terminal.open", {"place": node["direction"],
                                    **launch_args(first_leaf(node["second"]), table, warn)})
    build(node["first"], pane, table, warn)
    build(node["second"], made.get("pane") or pane_of(made["terminal"]), table, warn)


def app_restore(name):
    doc, table = load(name), resume_table()
    warn, gone, space = [], [], None
    for tab in doc["tabs"]:
        missing_cwds(tab["root"], gone)
        args = launch_args(first_leaf(tab["root"]), table, warn)
        if space is None:
            made = app_do("space.new", {"name": doc["label"], "tab": tab.get("label"), **args})
            space = made["space"]
        else:
            made = app_do("tab.new", {"space": space, "name": tab.get("label"), **args})
        build(tab["root"], made.get("pane") or pane_of(made["terminal"]), table, warn)
    if space:
        app_do("space.select", {"id": space})
    warn = sorted(set(warn)) + [f"folder gone, opened in home: {c}" for c in sorted(set(gone))]
    print(json.dumps({"space": space, "label": doc["label"], "warnings": warn}))


def transcript_tail(ref, n=4, width=400):
    """Last n text messages of a Claude Code transcript. Read from disk only: no tokens spent."""
    paths = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{ref}.jsonl"))
    if not paths:
        return []
    out = []
    with open(paths[0]) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") not in ("user", "assistant") or rec.get("isMeta"):
                continue
            content = (rec.get("message") or {}).get("content")
            if isinstance(content, list):  # tool calls and results carry no "text" part
                content = "\n".join(p.get("text", "") for p in content if p.get("type") == "text")
            text = (content or "").strip()
            if text and not text.startswith("<"):  # <command-name>, <system-reminder>, ...
                out.append({"role": rec["type"], "text": text[:width]})
    return out[-n:]


def preview(name):
    """What reopening a save would start, pane by pane, with the Claude conversation's last words."""
    doc, table = load(name), resume_table()

    def leaves(node):
        return leaves(node["first"]) + leaves(node["second"]) if node["type"] == "split" else [node]

    tabs = []
    for i, tab in enumerate(doc["tabs"], 1):
        panes = []
        for pane in leaves(tab["root"]):
            agent = pane.get("agent") or {}
            panes.append({
                "cwd": pane.get("cwd"),
                "run": armed_command(pane, table),
                "transcript": transcript_tail(agent["value"])
                if agent.get("agent") == "claude" and agent.get("kind") == "id" and agent.get("value") else [],
            })
        tabs.append({"label": tab.get("label") or str(i), "panes": panes})
    print(json.dumps({"label": doc["label"], "saved_at": doc.get("saved_at"), "tabs": tabs}))


def app_list():
    purge_trash()
    print(json.dumps([{"name": n, "label": l, "saved_at": ts, "tabs": t, "path": p}
                      for n, l, ts, t, p in entries()]))


COMMANDS = {
    "app-save": lambda: app_save(sys.argv[2]),
    "app-restore": lambda: app_restore(sys.argv[2]),
    "app-list": app_list,
    "app-preview": lambda: preview(sys.argv[2]),
    "save": lambda: save(sys.argv[2] if len(sys.argv) > 2 else None),
    "save-close": save_and_close,
    "open": lambda: open_pane("picker"),
    "pick": pick,
    "report": show_report,
    "list": list_saved,
    "menu": lambda: print(menu()),
    "delete": lambda: delete(sys.argv[2]),
    "undelete": undelete,
    "restore": lambda: restore(sys.argv[2]),
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in COMMANDS:
        sys.exit(f"usage: wss.py [{'|'.join(COMMANDS)}]")
    COMMANDS[cmd]()
