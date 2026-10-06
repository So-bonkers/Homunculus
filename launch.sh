#!/bin/bash
# Start the homunculus web app (if it is not already running) and open it.   launch.sh [--no-open]
# Used by the clickable homunculus.html, the "homunculus" application-menu entry and the homunculus:// link handler.
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:8765/"
up() { curl -s -m 1 -o /dev/null "$URL"; }
if ! up; then
  systemctl --user start homunculus-web 2>/dev/null
  for _ in $(seq 1 40); do up && break; sleep 0.5; done
fi
if [ "$1" != "--no-open" ] && up; then xdg-open "$URL" >/dev/null 2>&1 & fi
up && exit 0 || { notify-send -a homunculus "homunculus could not start" "Check: systemctl --user status homunculus-web" 2>/dev/null; exit 1; }
