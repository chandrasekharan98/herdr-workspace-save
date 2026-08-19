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


SHELLS = {"bash", "zsh", "fish", "sh", "dash", "ksh", "nu", "elvish", "xonsh"}


def state_dir():
    state = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if not state:
        sys.exit("HERDR_PLUGIN_STATE_DIR unset — run this through herdr plugin action/pane")
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


def foreground_argv(pane_id):
    """The command a pane is running, or None when it is just sitting at a shell."""
    info = call("pane.process_info", {"pane_id": pane_id})["process_info"]
    for proc in info.get("foreground_processes", []):
        # A pane launched with a command reports it as the shell pid, so match on name only.
        if proc.get("name") in SHELLS:
            continue
        return proc.get("argv") or None
    return None


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
        argv = foreground_argv(pane_id) if pane_id else None
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
    warn = sorted(set(warn))
    notify(f"Saved '{doc['label']}'", "\n".join([path] + warn), alert=bool(warn))
    print(path)
    for line in warn:
        print(line, file=sys.stderr)
    if warn:
        report(f"Saved '{doc['label']}', but {len(warn)} agent session(s) were NOT captured.",
               warn, f"Those panes reopen as fresh agents.\n\nSaved to: {path}")


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


def list_saved():
    print(state_dir())
    for name, label, saved_at, tabs, path in entries():
        print(f"{name}\t{label}\t{saved_at}\t{tabs} tabs\t{path}")


def pick():
    if not shutil.which("fzf"):
        print("fzf not found on PATH. Install it, or run: python3 wss.py list")
        input("Press enter to close…")
        return
    rows = entries()
    if not rows:
        print(f"No saved workspaces yet in {state_dir()}")
        input("Press enter to close…")
        return
    menu = "\n".join(f"{n}\t{l}\t{ts}\t{t} tabs\t{p}" for n, l, ts, t, p in rows)
    fzf = subprocess.run(
        ["fzf", "--delimiter=\t", "--with-nth=1,2,3,4", "--prompt=saved workspace> ",
         "--header=enter reopens · saved to " + state_dir(), "--preview", "cat {5}"],
        input=menu, stdout=subprocess.PIPE, text=True,  # stderr stays on the tty: that is fzf's UI
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


REPORT = "last-report.txt"


def report(headline, lines, footer=""):
    """Stage a message and open a pane for it: Herdr shows plugin output nowhere else."""
    with open(os.path.join(state_dir(), REPORT), "w") as f:
        f.write("\n".join([headline, ""] + [f"  - {line}" for line in lines] + ["", footer]))
    open_pane("report")


def show_report():
    path = os.path.join(state_dir(), REPORT)
    print(open(path).read() if os.path.exists(path) else "Nothing to report.")
    input("\nPress enter to close…")


COMMANDS = {
    "save": lambda: save(sys.argv[2] if len(sys.argv) > 2 else None),
    "save-close": save_and_close,
    "open": lambda: open_pane("picker"),
    "pick": pick,
    "report": show_report,
    "list": list_saved,
    "restore": lambda: restore(sys.argv[2]),
}

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd not in COMMANDS:
        sys.exit(f"usage: wss.py [{'|'.join(COMMANDS)}]")
    COMMANDS[cmd]()
