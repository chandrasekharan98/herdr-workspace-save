# Herdr Workspace Save

[![Release](https://img.shields.io/github/v/release/chandrasekharan98/herdr-workspace-save)](https://github.com/chandrasekharan98/herdr-workspace-save/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
![Herdr app 0.1.15+](https://img.shields.io/badge/herdr--app-0.1.15%2B-6e56cf)
![herdr TUI](https://img.shields.io/badge/herdr-TUI-555)

Close the Herdr workspaces you're not using, and get them back as they were: tabs, splits,
folders, running commands and Claude Code conversations.

![Saving a workspace, closing it, browsing saved workspaces with their previews, and reopening it with Claude Code resumed](app/demo.gif)

> [!TIP]
> Using the herdr TUI? See [herdr TUI](#herdr-tui). Both builds read the same saves.

## Install

Paste into an agent running in the Herdr app:

```text
Read ~/.config/herdr-app/AGENTS.md, then add this mod: github.com/chandrasekharan98/herdr-workspace-save/tree/main/app
```

<details>
<summary>By hand</summary>

Copy `app/mods/workspace-save/` and `app/mods/workspace-save-now/` to
`~/.config/herdr-app/mods/` (keep the folder names), and merge `app/keys.json` into
`~/.config/herdr-app/keys.json`.

</details>

**Requires:** `python3`, and herdr-core's `hc` on PATH.

The mods run `python3` and `hc`, write saves to `~/.local/state/herdr/plugins/workspace-save/`
and read `~/.claude/sessions/`.

## Quick start

1. Press `ctrl-b shift-s` in a space to save it.
2. Close the space whenever you like.
3. Press `ctrl-b alt-w` to see your saves. Select one to preview its tabs and screens.
4. Press Enter, or click it, to reopen it. Claude Code picks up the same conversation.

| Key | Does |
| --- | --- |
| `ctrl-b shift-s` | Save the current space |
| `ctrl-b alt-w` | Open saved workspaces |
| `ctrl+s` / `ctrl+shift+s` | In the dialog: save, or save and close |
| `ctrl+x` / `ctrl+z` | In the dialog: delete, undo |

Everything works with the mouse too: click a save to reopen it, ✕ to delete it, or use the
**Save this space** and **Save and close** buttons.

![The Saved workspaces dialog: saves on the left, the selected one's tab drawn with its panes' screens on the right](app/preview.png)

### Save automatically before sleep (Linux)

If a hibernate resume fails, the machine cold-boots and every agent is gone. To save every
space just before suspend or hibernate, enable the bundled user service (no root needed):

```bash
systemctl --user enable --now ~/.config/herdr-app/mods/workspace-save/herdr-presleep-save.service
```

It holds a logind delay lock and saves while sleep waits. Spaces that are only bare shells
are skipped, and a pane that fell back to a shell keeps the session it was saved with, so a
save after a failed resume never wipes the agents you still need to reopen.

Want save and open in the spaces right-click menu? Ask your agent to "add the
workspace-save space menu items to my layout" ([how](app/RECIPE.md#optional-drawer-and-space-menu)).

## Update and uninstall

- **Update:** an installed copy doesn't update itself. Watch [Releases](https://github.com/chandrasekharan98/herdr-workspace-save/releases), then ask your Herdr agent to add the mod again from the same link (or copy the folders again).
- **Uninstall:** delete the two `workspace-save*` folders in `~/.config/herdr-app/mods/` and
  their keys in `keys.json`. Your saves stay in `~/.local/state/herdr/plugins/workspace-save/`.

## Limitations

- In the app, commands run as soon as you reopen; the TUI types them and waits for Enter.
- In the app, only Claude Code conversations resume. Other agents reopen fresh, with a warning.
- Split sizes, mod panes (Files, Changes) and spaces on other machines aren't restored in the app yet.
- Not saved anywhere: scrollback, environment variables, a command that already exited.
- Claude Code deletes conversations after `cleanupPeriodDays` (default 30). Older saves open a
  fresh `claude`.

## herdr TUI

![Saving a workspace, reopening it from the picker with every command armed, then pressing enter to resume the Claude session](docs/demo.gif)

```bash
herdr plugin install chandrasekharan98/herdr-workspace-save
```

**Requires:** `python3` and `fzf`. Bind keys in `~/.config/herdr/config.toml`, then run
`herdr server reload-config`:

```toml
[[keys.command]]
key = "prefix+shift+s"
type = "plugin_action"
command = "workspace-save.save"        # or workspace-save.save-close
description = "save workspace"

[[keys.command]]
key = "prefix+alt+w"
type = "plugin_action"
command = "workspace-save.open"
description = "open saved workspace"
```

Reopening rebuilds the tabs and splits and types each pane's command without running it, so
you press Enter only where you want. Agents with a resume flag (claude, codex, opencode and
more) resume their session. In the picker, `ctrl-x` deletes and `ctrl-z` undoes.

Uninstall with `herdr plugin uninstall workspace-save`.

## Details

<details>
<summary>How agent sessions are found</summary>

**TUI:** Herdr's state integration reports each agent's session. Saving warns when an
integration is missing (`herdr integration install <agent>`) or Herdr has none for that agent.

**App:** for Claude Code the mod reads `~/.claude/sessions/<pid>.json`, which Claude Code
writes for each running session. That file isn't a documented interface, so there's an
optional fallback, a `SessionStart` hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [{ "type": "command", "command": "sh ~/.config/herdr-app/mods/workspace-save/claude-session-start.sh" }] }
    ]
  }
}
```

It appends one line per session to `~/.local/state/herdr/terminal-sessions.jsonl` and does
nothing outside a Herdr terminal.

**Resume commands** match Herdr's: `--resume` for claude, codex, grok, droid, devin, hermes,
cursor, qodercli; `--session` for pi, opencode, kimi, kilo; `--conversation` for agy;
`--thread` for mastracode. Override them in `$HERDR_PLUGIN_CONFIG_DIR/config.json`:

```json
{ "resume": { "claude": ["claude", "--resume", "{ref}"] } }
```

</details>

<details>
<summary>Save files</summary>

One JSON file per workspace in `~/.local/state/herdr/plugins/workspace-save/workspaces/`.
Saving again overwrites it. Deletes go to `trash/` for 7 days. The files are hand-editable:
drop a `command`, retarget a `cwd`, add `env`.

```json
{
  "version": 1,
  "name": "reviews",
  "label": "reviews",
  "saved_at": "2026-08-05T16:26:29Z",
  "tabs": [
    {
      "label": "1",
      "root": {
        "type": "split",
        "direction": "down",
        "ratio": 0.5,
        "first": { "type": "pane", "cwd": "/tmp", "command": ["npm", "run", "dev"] },
        "second": {
          "type": "pane",
          "cwd": "/src",
          "agent": { "source": "herdr:claude", "agent": "claude", "kind": "id", "value": "c1ba9b75-…" }
        }
      }
    }
  ]
}
```

In the app, each pane also stores its screen text for the preview, so anything on screen
ends up in the file.

</details>

<details>
<summary>Development</summary>

`wss.py` is the shared core. The TUI plugin runs it from the repo root (a symlink); the app
mods run `app/mods/workspace-save/wss.py` through `exec`. [`app/RECIPE.md`](app/RECIPE.md)
describes how the app half is built.

```bash
python3 test_wss.py
herdr-app check app/mods/workspace-save
herdr-app check app/mods/workspace-save-now
```

</details>

## Pairs well with

[Herdr Easy Annotate](https://github.com/chandrasekharan98/herdr-ez-annotate).

## License

MIT
