#!/bin/bash
VLLM=/deploy/models/docker_run/vllm
C=glm-4-9b-chat

cd $VLLM || exit 1
echo "===== stop loop, keep container ====="
sudo docker-compose -f docker-compose.fixed.yml stop 2>&1 | grep -v obsolete | tail -2
sudo docker inspect $C --format 'ExitCode={{.State.ExitCode}} OOM={{.State.OOMKilled}} Restarts={{.RestartCount}} Error={{.State.Error}}'

echo
echo "===== locate ALL mindservice/python/plog files in container ====="
sudo docker exec $C bash -c '
echo "--- find mindservice.log ---"
find / -xdev -name "mindservice*.log" 2>/dev/null
echo "--- find pythonlog ---"
find / -xdev -name "pythonlog*" 2>/dev/null
echo "--- ascend logs ---"
find / -xdev -path "*ascend*" -name "*.log" 2>/dev/null | head -20
echo "--- logs dir perms ---"
ls -land /usr/local/Ascend/mindie/1.0.0/mindie-service/logs
ls -lan /usr/local/Ascend/mindie/1.0.0/mindie-service/logs/
echo "--- HOME ---"; echo "HOME=$HOME"
'

echo
echo "===== mindservice.log content ====="
sudo docker exec $C bash -c 'cat /usr/local/Ascend/mindie/1.0.0/mindie-service/logs/mindservice.log 2>&1 | tail -60'

echo
echo "===== mindie_audit.log ====="
sudo docker exec $C bash -c 'cat /usr/local/Ascend/mindie/1.0.0/mindie-service/logs/mindie_audit.log 2>&1 | tail -20'

echo
echo "===== docker logs FULL ====="
sudo docker logs $C 2>&1 | tail -60

echo
echo "===== full host tee log, non-config lines ====="
sudo grep -v "model_config {" /deploy/logs/mindie/glm-4.log | tail -40

echo
echo "===== host dmesg NPU errors ====="
sudo dmesg -T 2>/dev/null | grep -iE "davinci|ascend|npu|svm|hdc" | tail -20
