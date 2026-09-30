#!/bin/bash
VLLM=/deploy/models/docker_run/vllm
C=glm-4-9b-chat
LOG=/deploy/logs/mindie/glm-4.log

echo "===== deploy fixed compose ====="
sudo cp /tmp/docker-compose.fixed.yml $VLLM/docker-compose.fixed.yml
sudo chown root:root $VLLM/docker-compose.fixed.yml
sudo mkdir -p /deploy/logs/mindie
sudo chown -R 1000:0 /deploy/logs/mindie

echo "===== recreate ====="
cd $VLLM || exit 1
sudo docker-compose -f docker-compose.fixed.yml up -d --force-recreate 2>&1 | grep -v "obsolete" | tail -5

echo "===== poll up to 6 min ====="
for i in $(seq 1 18); do
  sleep 20
  ST=$(sudo docker ps -a --filter name=$C --format '{{.Status}}')
  LISTEN=$(ss -tln 2>/dev/null | grep -c ':10006')
  SIZE=$(sudo stat -c %s $LOG 2>/dev/null || echo 0)
  echo "[$i] $(date +%T) status='$ST' logsize=$SIZE listen10006=$LISTEN"
  if [ "$LISTEN" -gt 0 ]; then echo "*** PORT 10006 IS LISTENING ***"; break; fi
done

echo
echo "===== last 20 log lines ====="
sudo tail -20 $LOG

echo
echo "===== curl /v1/models ====="
curl -s -m 8 http://127.0.0.1:10006/v1/models | head -c 600
echo
echo "===== docker ps ====="
sudo docker ps -a --filter name=$C --format 'table {{.Names}}\t{{.Status}}'
echo "===== npu-smi ====="
sudo npu-smi info 2>&1 | sed -n '1,20p'
