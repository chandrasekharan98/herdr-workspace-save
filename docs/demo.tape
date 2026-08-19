# Regenerate with: vhs docs/demo.tape   (https://github.com/charmbracelet/vhs)
# Runs against a throwaway Herdr session so it never touches your real workspaces.

Output docs/demo.gif
Set FontSize 16
Set Width 1400
Set Height 800
Set Padding 20
Set Framerate 24

Hide
Type "herdr --session wss-demo" Enter
Sleep 4s
Show

# A workspace worth saving: an agent on the left, a dev server on the right.
Type "claude" Enter
Sleep 6s
Ctrl+B
Type "%"
Sleep 1s
Type "npm run dev" Enter
Sleep 3s

# prefix+shift+S — save it.
Ctrl+B
Type "S"
Sleep 3s

# prefix+alt+W — reopen it from the picker.
Ctrl+B
Alt+w
Sleep 2s
Type "demo"
Sleep 2s
Enter
Sleep 4s

# Restored panes are armed, not run: the resume command waits for enter.
Sleep 3s
