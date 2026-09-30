#!/usr/bin/env bash
if [[ -f /deploy/cc/model_main.pid ]]; then
  while read pid; do
    if kill -0 "$pid" &>/dev/null; then
      echo "Killing $pid"
      kill -9 "$pid"
    fi
  done < /deploy/cc/model_main.pid
  rm -f /deploy/cc/model_main.pid
else
  echo "PID file not found, fallback to port-based kill"
  for port in 9885 8105 8106; do
    pid=$(lsof -i:$port -t)
    [[ -n "$pid" ]] && kill -9 $pid
  done
fi
