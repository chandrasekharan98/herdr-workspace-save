# Regenerate the README stills with: vhs docs/screenshots.tape
# Writes docs/warning.png and docs/picker.png. Same throwaway session and
# isolated XDG_STATE_HOME as docs/demo.tape; docs/screenshots.gif is a byproduct.

Output docs/screenshots.gif
Set Shell zsh
Set FontSize 14
Set Width 1200
Set Height 680
Set Padding 15

Hide
Type "unset HERDR_ENV HERDR_SOCKET_PATH HERDR_PANE_ID HERDR_TAB_ID HERDR_WORKSPACE_ID" Enter
Type "export XDG_STATE_HOME=$PWD/.demo-state REPO=$PWD" Enter
Type "herdr --session wss-shots server stop >/dev/null 2>&1; rm -rf .demo-state ~/.config/herdr/sessions/wss-shots" Enter
Type "mkdir -p .demo-state/herdr && cp -r ~/.local/state/herdr/agent-detection .demo-state/herdr/ 2>/dev/null" Enter
Type "cd ~/personal" Enter
Type "clear" Enter
Show

Type "herdr --session wss-shots" Enter
Sleep 8s

# 1. The warning pane, rendered by the plugin's own report writer.
Type "cd $REPO && python3 docs/warning_shot.py" Enter
Sleep 10s
Screenshot docs/warning.png
Enter
Sleep 3s

# 2. The picker: build a workspace worth saving, save it, then open the picker.
Type "clear && cd ~/personal" Enter
Sleep 1s
Type "python3 -m http.server 8098" Enter
Sleep 3s
Ctrl+B
Type "v"
Sleep 2s
Type "ping -i 1 127.0.0.1" Enter
Sleep 4s
Ctrl+B
Type "S"
Sleep 5s
Ctrl+B
Alt+w
Sleep 12s
Screenshot docs/picker.png
Sleep 1s

Hide
Ctrl+B
Type "d"
Sleep 2s
Type "herdr --session wss-shots server stop >/dev/null 2>&1" Enter
Sleep 2s
