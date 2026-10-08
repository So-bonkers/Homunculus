#!/bin/bash
# Start the homunculus web app (if it is not already running) and open it.   launch.sh [--no-open]
# Used by the clickable homunculus.html, the "homunculus" application-menu entry and the homunculus:// link handler.
cd "$(dirname "$0")" || exit 1
URL="http://127.0.0.1:8765/"
up() { curl -s -m 1 -o /dev/null "$URL"; }
# Unsloth Studio's API (Qwen-Image + the judges) on 8888: start it as the user unit 'unsloth-api' if nothing answers there.
STUDIO=$(command -v unsloth || echo "$HOME/.unsloth/studio/unsloth_studio/bin/unsloth")
if ! curl -s -m 1 -o /dev/null http://127.0.0.1:8888/ && [ -x "$STUDIO" ] && ! systemctl --user is-active --quiet unsloth-api; then
  systemd-run --user --unit=unsloth-api --collect "$STUDIO" studio --api-only -H 127.0.0.1 -p 8888 >/dev/null 2>&1
fi
if ! up; then
  systemctl --user start homunculus-web 2>/dev/null
  for _ in $(seq 1 40); do up && break; sleep 0.5; done
fi
if [ "$1" != "--no-open" ] && up; then xdg-open "$URL" >/dev/null 2>&1 & fi
up && exit 0 || { notify-send -a homunculus "homunculus could not start" "Check: systemctl --user status homunculus-web" 2>/dev/null; exit 1; }
