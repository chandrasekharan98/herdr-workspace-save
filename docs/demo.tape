# Regenerate with: vhs docs/demo.tape   (needs vhs, ttyd, ffmpeg)
# Runs in a throwaway `herdr --session wss-demo` under its own XDG_STATE_HOME,
# so recording never sees or touches real saved workspaces.
# MesloLGS NF carries the Nerd Font glyphs the status line uses.

Output docs/demo.gif
Set Shell zsh
Set FontFamily "MesloLGS NF"
Set FontSize 14
Set Width 1200
Set Height 680
Set Padding 15
Set Framerate 15
Set PlaybackSpeed 1.5

Hide
# Herdr refuses to nest, so drop any inherited session env before launching.
Type "unset HERDR_ENV HERDR_SOCKET_PATH HERDR_PANE_ID HERDR_TAB_ID HERDR_WORKSPACE_ID" Enter
# A Claude launched from inside Claude keeps its parent's session and writes no
# transcript, so the demo agent would have no id to capture. Start clean.
Type "for v in ${(k)parameters[(I)CLAUDE*]} CLAUDECODE AI_AGENT; do unset $v; done" Enter
Type "export XDG_STATE_HOME=$PWD/.demo-state" Enter
Type "herdr --session wss-demo server stop >/dev/null 2>&1; rm -rf .demo-state ~/.config/herdr/sessions/wss-demo" Enter
Type "pkill -f 'http.server 8099' 2>/dev/null; sleep 1" Enter
Type "mkdir -p .demo-state/herdr && cp -r ~/.local/state/herdr/agent-detection .demo-state/herdr/ 2>/dev/null" Enter
# zsh-autosuggestions would paint history behind every armed command
Type "export ZSH_AUTOSUGGEST_BUFFER_MAX_SIZE=0" Enter
Type "cd ~/personal" Enter
Type "clear" Enter
Show

Type "herdr --session wss-demo" Enter
Sleep 2s

# An agent on the left. Herdr's integration reports its session id to the plugin.
Type "claude" Enter
Sleep 4s
Type "in one sentence, what is a terminal multiplexer?" Enter
Sleep 9s

# A server on the right, so the save has a running command to capture too.
Ctrl+B
Type "v"
Sleep 2s
Type "python3 -m http.server 8099" Enter
Sleep 2s

# prefix+shift+S saves the layout, cwds, agent sessions and running commands.
Ctrl+B
Type "S"
Sleep 3s

# prefix+alt+W reopens it from the picker: pick a save, preview it, press enter.
Ctrl+B
Alt+w
Sleep 4s
Enter

# Restored panes are armed, not run — `claude --resume <id>` waits for enter.
Sleep 4s

Hide
Sleep 2s
Ctrl+B
Type "d"
Sleep 3s
Type "herdr --session wss-demo server stop >/dev/null 2>&1" Enter
Sleep 2s
