#!/usr/bin/env bash
# Saves every Herdr app space just before the machine suspends or hibernates, so a resume that
# fails and cold-boots loses nothing since the last sleep. A logind delay lock holds the sleep
# back until the save is written (at most InhibitDelayMaxSec), before user processes freeze.
# On login it also reopens the spaces that came back as bare shells, once the window is up.
set -u
shopt -s lastpipe
wss="$(dirname "$(readlink -f "$0")")/wss.py"

lock() {
    systemd-inhibit --what=sleep --mode=delay --who="herdr workspace-save" \
        --why="saving Herdr workspaces" sleep infinity &
    lock_pid=$!
}
unlock() { pkill -P "$lock_pid" 2>/dev/null; kill "$lock_pid" 2>/dev/null; }
trap unlock EXIT

# Once per login: when the app window first answers, reopen spaces that came back as bare shells.
( until herdr-app ls >/dev/null 2>&1; do sleep 5; done
  python3 "$wss" app-restore-stale >/dev/null ) &

lock
gdbus monitor --system --dest org.freedesktop.login1 --object-path /org/freedesktop/login1 |
while read -r line; do
    case "$line" in
        *"PrepareForSleep (true"*) python3 "$wss" app-save-all >/dev/null; unlock ;;
        *"PrepareForSleep (false"*) lock ;;
    esac
done
