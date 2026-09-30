#!/bin/bash
C=glm-4-9b-chat
VLLM=/deploy/models/docker_run/vllm

echo "===== 0. stop restart loop ====="
cd $VLLM && sudo docker-compose -f docker-compose.fixed.yml stop 2>&1 | tail -3
sudo docker ps -a --filter name=$C --format 'table {{.Names}}\t{{.Status}}\t{{.ExitCode}}'

echo
echo "===== 1. docker logs (last 120) ====="
sudo docker logs --tail 120 $C 2>&1

echo
echo "===== 2. grep ERROR/Traceback in docker logs ====="
sudo docker logs $C 2>&1 | grep -inE "error|traceback|exception|failed|aborted|EZ|EE[0-9]" | tail -40

echo
echo "===== 3. copy out mindservice.log + ls logs ====="
sudo docker cp $C:/usr/local/Ascend/mindie/1.0.0/mindie-service/logs /tmp/mindie_logs 2>&1
ls -la /tmp/mindie_logs/ 2>&1
echo "--- mindservice.log tail ---"
sudo tail -60 /tmp/mindie_logs/mindservice.log 2>&1

echo
echo "===== 4. ascend plog ====="
sudo docker cp $C:/root/ascend/log /tmp/ascend_log 2>&1 | head -2
find /tmp/ascend_log -name "*.log" 2>/dev/null | tail -5
for f in $(find /tmp/ascend_log -name "*.log" 2>/dev/null | tail -3); do
  echo "--- $f ---"
  tail -40 "$f"
done

echo
echo "===== 5. full host log size ====="
sudo ls -la /deploy/logs/mindie/
