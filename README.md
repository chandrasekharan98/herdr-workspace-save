# herdr-workspace-save

Save a Herdr workspace — layout, cwds, agent sessions, running commands — and reopen it later
from an fzf picker.

Reopening rebuilds the tabs and splits, then **types** each pane's command into it without
running it. You press enter in the panes you actually want. Reopening a six-agent workspace
therefore costs nothing until you say so.

## Install (local)

```bash
herdr plugin link /path/to/herdr-workspace-save
```

Requires `python3` and `fzf`. MIT licensed.

## Keys

Add to `~/.config/herdr/config.toml`, then `herdr server reload-config`:

```toml
[[keys.command]]
key = "prefix+shift+s"
type = "plugin_action"
command = "workspace-save.save"
description = "save workspace"

[[keys.command]]
key = "prefix+alt+w"
type = "plugin_action"
command = "workspace-save.open"
description = "open saved workspace"
```

## Actions

| Action | What it does |
| --- | --- |
| `workspace-save.save` | Save the focused workspace. Slug comes from its label. |
| `workspace-save.save-close` | Save, then close the workspace. |
| `workspace-save.open` | Open the picker overlay; enter reopens the selection. |

Run any manually with `herdr plugin action invoke <id> --plugin workspace-save`.
`python3 wss.py list` prints the save directory and one line per save.

## What gets captured

Per pane, in this order:

1. **Agent session.** Herdr already tracks a session ref for recognized agents
   (`{source, agent, kind, value}`); it is stored verbatim and armed as a resume command.
2. **Foreground command.** Whatever the pane is running, from `pane.process-info`.
   Panes sitting at a shell prompt record nothing.
3. **cwd**, always.

Not captured: scrollback, env (Herdr's layout export doesn't expose it — `env` is honoured on
restore if you add it by hand), and anything a process holds only in memory.

## Agent support

Resuming an agent needs two things, and the plugin tells you which one is missing.

**1. Herdr must report a session ref for it.** That comes from Herdr's state integration
(`herdr integration status`). Agents Herdr detects but ships no integration for — currently
`gemini`, `agy`, `cline`, `kiro`, `amp`, `maki` — can never be resumed; their panes reopen
fresh. Saving warns per pane:

```
codex: integration not installed — run: herdr integration install codex
pi: integration outdated (v6 < v8) — run: herdr integration install pi
gemini: Herdr ships no state integration, sessions cannot be captured
claude: no session id reported yet, pane will reopen fresh
```

**2. A resume command must be known** for that agent. Defaults match Herdr's own internal
resume table: `--resume` for claude, codex (`codex resume`), grok, droid, devin, hermes,
cursor (`cursor-agent`), qodercli; `--session` for pi, opencode, kimi, kilo;
`--conversation` for agy; `--thread` for mastracode. Reopening warns when it can't resume:

```
copilot: no resume command known, opened fresh — add one to config.json
claude 11c3d682: transcript deleted, opened fresh — raise cleanupPeriodDays
mastracode: saved without a session id, opened fresh
```

Where warnings show up: a Herdr notification with a `request` sound, and — when you reopened
from the picker — the picker pane stays open listing them until you press enter. Herdr does not
surface plugin stderr on screen, so the notification is the only signal for a keybind-invoked
save; `herdr plugin log list --plugin workspace-save` has the full text.

## Resume commands

`{ref}` is substituted with the agent's session id or path:

```json
{ "resume": { "claude": ["claude", "--resume", "{ref}"] } }
```

Put overrides in `$HERDR_PLUGIN_CONFIG_DIR/config.json`
(`herdr plugin config-dir workspace-save`). Defaults cover claude, codex, grok, droid, devin,
hermes, cursor, qodercli, agy, opencode, pi, kimi and kilo. Flags drift — since commands are
armed and not run, a wrong one is visible in the pane before you press enter.

For Claude, a saved session whose transcript no longer exists on disk arms a bare `claude`
instead of a resume that would only error. Claude Code deletes transcripts older than
`cleanupPeriodDays` (default 30) at startup, so raise that in `~/.claude/settings.json` if you
want month-old saved workspaces to still resume.

## Where saves live

`$HERDR_PLUGIN_STATE_DIR/workspaces/<slug>.json`, i.e.
`~/.local/state/herdr/plugins/workspace-save/workspaces/`.

If a saved `cwd` no longer exists (deleted worktree), Herdr silently opens that pane in
`$HOME` — reopening warns which paths were missing, so an armed `--resume` in the wrong
directory doesn't go unnoticed.

The picker header shows that directory, previews the selected file, and saving raises a
notification with the full path. Saving a workspace whose label matches an existing save
overwrites it — no versioning. Rename the workspace first if you want two.

## Format

```json
{
  "version": 1,
  "name": "reviews",
  "label": "reviews",
  "saved_at": "2026-08-05T16:26:29Z",
  "tabs": [
    { "label": "1",
      "root": { "type": "split", "direction": "down", "ratio": 0.5,
        "first":  { "type": "pane", "cwd": "/tmp", "command": ["npm", "run", "dev"] },
        "second": { "type": "pane", "cwd": "/src",
                    "agent": { "source": "herdr:claude", "agent": "claude",
                               "kind": "id", "value": "c1ba9b75-…" } } } }
  ]
}
```

Hand-editable: delete a `command` you don't want re-armed, add `env`, retarget a `cwd`.
On restore the `agent`/`command` keys are stripped out and the rest is passed to Herdr's
`layout.apply` as-is.

## Tests

```bash
python3 test_wss.py
```

Covers the pure parts — key stripping, saved-to-live pane pairing, and command arming
including the stale-transcript and unknown-agent fallbacks.
