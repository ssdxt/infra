#!/bin/bash
# 停止 oceanbase（及依赖容器）。顺序无硬性要求，保持与 ob-start.sh 相反的确定性。
set -u
for c in polardb oceanbase-ce; do
    if docker ps --format '{{.Names}}' | grep -qx "$c"; then
        echo "[$(date '+%F %T')] stopping $c ..."
        docker stop -t 120 "$c"
    fi
done
echo "stopped."
