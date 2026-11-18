#!/usr/bin/env bash
# A logind delay lock holds sleep and shutdown back until every space is saved (at most
# InhibitDelayMaxSec), before user processes freeze or are killed. The save reads herdr-core,
# so it works with the window closed.
set -u
shopt -s lastpipe
wss="$(dirname "$(readlink -f "$0")")/wss.py"

lock() {
    systemd-inhibit --what=sleep:shutdown --mode=delay --who="herdr workspace-save" \
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
        *"PrepareForSleep (true"* | *"PrepareForShutdown (true"*)
            python3 "$wss" app-save-all >/dev/null; unlock ;;
        # Woke up, or the shutdown was cancelled: hold the next one back too.
        *"PrepareForSleep (false"* | *"PrepareForShutdown (false"*) lock ;;
    esac
done
