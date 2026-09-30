#!/bin/bash
C=glm-4-9b-chat
echo "===== RestartCount / ExitCode / State ====="
sudo docker inspect $C --format 'Restarts={{.RestartCount}} ExitCode={{.State.ExitCode}} Status={{.State.Status}} FinishedAt={{.State.FinishedAt}} OOM={{.State.OOMKilled}} Error={{.State.Error}}'

echo
echo "===== docker logs FULL (line count + first 40) ====="
sudo docker logs $C 2>&1 | wc -l
sudo docker logs $C 2>&1 | head -40

echo
echo "===== /deploy/logs/mindie/glm-4.log FULL ($(sudo wc -c < /deploy/logs/mindie/glm-4.log) bytes) ====="
echo "--- first 30 lines ---"
sudo head -30 /deploy/logs/mindie/glm-4.log
echo "--- last 25 lines ---"
sudo tail -25 /deploy/logs/mindie/glm-4.log
echo "--- grep err ---"
sudo grep -inE "error|fail|exception|abort|EZ9999|EE9999|retCode|aicore" /deploy/logs/mindie/glm-4.log | head -20

echo
echo "===== in-container service log (via docker cp to /tmp) ====="
sudo rm -rf /tmp/mlogs
sudo docker cp $C:/usr/local/Ascend/mindie/1.0.0/mindie-service/logs /tmp/mlogs 2>&1
sudo ls -la /tmp/mlogs/ 2>&1
sudo tail -50 /tmp/mlogs/mindservice.log 2>&1

echo
echo "===== ascend logs inside container ====="
sudo docker cp $C:/root/ascend /tmp/ascend_log 2>&1 | head -2
sudo find /tmp/ascend_log -name "*.log" 2>/dev/null | head -10
