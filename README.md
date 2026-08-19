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

Requires `python3` and `fzf`.

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
