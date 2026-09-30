#!/bin/bash
C=glm-4-9b-chat
echo "===== now: $(date '+%F %T') ====="
sudo docker ps -a --filter name=$C --format 'table {{.Names}}\t{{.Status}}'
sudo docker inspect $C --format 'ID={{.Id}} Restarts={{.RestartCount}} Started={{.State.StartedAt}} Status={{.State.Status}}'

echo
echo "===== ps inside container ====="
sudo docker exec $C ps -ef 2>&1

echo
echo "===== host log tail (size $(sudo stat -c %s /deploy/logs/mindie/glm-4.log)) ====="
sudo tail -6 /deploy/logs/mindie/glm-4.log

echo
echo "===== ports ====="
ss -tlnp 2>/dev/null | grep -E '10006|1026|1027' || echo "no mindie port"

echo
echo "===== npu-smi (host) ====="
sudo npu-smi info 2>&1 | head -25
