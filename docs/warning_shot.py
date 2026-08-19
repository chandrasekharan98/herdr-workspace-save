#!/usr/bin/env python3
"""Render the warning pane for docs/warning.png using the plugin's own report writer.

Run from a pane inside the demo Herdr session (see docs/screenshots.tape).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault(
    "HERDR_PLUGIN_STATE_DIR",
    os.path.join(os.environ["XDG_STATE_HOME"], "herdr", "plugins", "workspace-save"),
)

import wss  # noqa: E402  (path must be set first)

wss.report(
    "Saved 'api-refactor', but 2 agent session(s) were NOT captured.",
    ["claude in sideshow: no session id reported yet",
     "codex in worker: integration not installed — run: herdr integration install codex"],
    "Those panes reopen as fresh agents.",
)
