#!/bin/bash
# The homunculus web app (launcher, runs, review, 3D viewer); only runs while you use the pipeline, not started at login.
#   ./web.sh start | stop | open [run]
case "$1" in
  start) systemctl --user start homunculus-web && echo "serving http://127.0.0.1:8765/" ;;
  stop)  systemctl --user stop homunculus-web && echo "stopped" ;;
  open)  systemctl --user start homunculus-web; xdg-open "http://127.0.0.1:8765/${2:+#/run/$2}" >/dev/null 2>&1 & ;;
  *)     echo "usage: ./web.sh start | stop | open [run-name]" ;;
esac
