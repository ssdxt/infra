#!/bin/bash
C=glm-4-9b-chat
echo "===== time $(date +%T) ====="
sudo docker ps -a --filter name=$C --format '{{.Names}} {{.Status}}'
sudo docker inspect $C --format 'Restarts={{.RestartCount}} Started={{.State.StartedAt}} Status={{.State.Status}}'

echo
echo "===== ps in container ====="
sudo docker exec $C ps -ef 2>&1

echo
echo "===== docker logs tail 20 ====="
sudo docker logs --tail 20 $C 2>&1

echo
echo "===== find ALL recent logs in container (last 10 min) ====="
sudo docker exec $C bash -c 'find / -xdev -name "*.log" -newermt "-10 minutes" 2>/dev/null | head -30'

echo
echo "===== mindservice.log (service) ====="
sudo docker exec $C bash -c 'for p in /usr/local/Ascend/mindie/latest/mindie-service/logs/mindservice.log /usr/local/Ascend/mindie/1.0.0/mindie-service/logs/mindservice.log; do echo "--- $p ---"; tail -40 $p 2>&1; done'

echo
echo "===== python log ====="
sudo docker exec $C bash -c 'f=/usr/local/Ascend/mindie/latest/mindie-llm/logs/pythonlog.log; ls -la $f 2>&1; tail -40 $f 2>&1'

echo
echo "===== ascend plog ====="
sudo docker exec $C bash -c 'ls -la /root/ascend/log/plog 2>&1 | tail -5; ls -la /ascend/log 2>&1 | tail -3'

echo
echo "===== npu-smi ====="
sudo npu-smi info 2>&1 | tail -20
