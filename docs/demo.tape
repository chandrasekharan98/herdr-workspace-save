# Regenerate with: vhs docs/demo.tape   (needs vhs, ttyd, ffmpeg)
# Runs in a throwaway `herdr --session wss-demo` under its own XDG_STATE_HOME,
# so recording never sees or touches real saved workspaces.

Output docs/demo.gif
Set Shell zsh
Set FontSize 14
Set Width 1200
Set Height 680
Set Padding 15
Set Framerate 15
Set PlaybackSpeed 1.5

Hide
# Herdr refuses to nest, so drop any inherited session env before launching.
Type "unset HERDR_ENV HERDR_SOCKET_PATH HERDR_PANE_ID HERDR_TAB_ID HERDR_WORKSPACE_ID" Enter
Type "export XDG_STATE_HOME=$PWD/.demo-state" Enter
Type "herdr --session wss-demo server stop >/dev/null 2>&1; rm -rf .demo-state ~/.config/herdr/sessions/wss-demo" Enter
Type "mkdir -p .demo-state/herdr && cp -r ~/.local/state/herdr/agent-detection .demo-state/herdr/ 2>/dev/null" Enter
Type "cd ~/personal" Enter
Type "clear" Enter
Show

Type "herdr --session wss-demo" Enter
Sleep 8s

# A workspace worth keeping: a server on the left, a long-running job on the right.
Type "python3 -m http.server 8099" Enter
Sleep 3s
Ctrl+B
Type "v"
Sleep 2s
Type "ping -i 1 127.0.0.1" Enter
Sleep 4s

# prefix+shift+S saves the layout, cwds, agent sessions and running commands.
Ctrl+B
Type "S"
Sleep 5s

# prefix+alt+W reopens it from the picker: pick a save, preview it, press enter.
Ctrl+B
Alt+w
Sleep 12s
Enter
Sleep 8s

# Restored panes are armed, not run — nothing happens until you press enter.
Sleep 4s

Hide
Ctrl+B
Type "d"
Sleep 2s
Type "herdr --session wss-demo server stop >/dev/null 2>&1" Enter
Sleep 2s
