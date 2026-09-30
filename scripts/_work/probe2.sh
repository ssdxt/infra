#!/bin/bash
VLLM=/deploy/models/docker_run/vllm
LOG=/glm-4.log

echo "===== A. fix model-path config.json ownership/mode ====="
sudo chown root:root /deploy/models/glm-4-9b-chat/config.json
sudo chmod 640 /deploy/models/glm-4-9b-chat/config.json
sudo ls -la /deploy/models/glm-4-9b-chat/config.json

echo
echo "===== B. recreate from user's compose ====="
cd $VLLM || exit 1
sudo docker-compose -f docker-compose.yml up -d --force-recreate 2>&1 | tail -5

echo
echo "===== C. wait 45s then read log ====="
sleep 45
CNAME=$(sudo docker ps -a --format '{{.Names}}' | grep -E '^glm' | head -1)
echo "container = $CNAME"
sudo docker ps -a --filter "name=$CNAME" --format 'table {{.Names}}\t{{.Status}}'
echo "--- $LOG ---"
sudo docker exec "$CNAME" bash -c "ls -la $LOG 2>&1; echo '--- content ---'; cat $LOG 2>&1" 2>&1 | tail -60

echo
echo "===== D. /deploy layout ====="
ls -la /deploy/
echo "--- app configs ---"
ls -la /deploy/chat_doc_0918/configs/ 2>&1 | head
