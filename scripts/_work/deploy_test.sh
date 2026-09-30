#!/bin/bash
set -u
VLLM=/deploy/models/docker_run/vllm
M=/deploy/models/glm-4-9b-chat
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "===== 1. one-time permission prep ====="
sudo mkdir -p /deploy/logs/mindie
sudo chown -R 1000:0 /deploy/logs/mindie
sudo chown 1000:0 $M/conf/config.json
sudo chmod 640   $M/conf/config.json
sudo chown 1000:0 $M/config.json
sudo chmod 640   $M/config.json
ls -ln $M/config.json $M/conf/config.json
ls -ldn /deploy/logs/mindie

echo
echo "===== 2. drop in fixed compose ====="
sudo cp /tmp/docker-compose.fixed.yml $VLLM/docker-compose.fixed.yml
sudo chown root:root $VLLM/docker-compose.fixed.yml
ls -la $VLLM/
sudo docker-compose -f $VLLM/docker-compose.fixed.yml config >/dev/null && echo "YAML OK"

echo
echo "===== 3. clean leftover test container ====="
sudo docker rm -f glm4 2>&1 | head -2

echo
echo "===== 4. up -d ====="
cd $VLLM || exit 1
sudo docker-compose -f docker-compose.fixed.yml up -d 2>&1 | tail -8

echo
echo "===== 5. wait 60s ====="
sleep 60
sudo docker ps -a --filter name=glm-4-9b-chat --format 'table {{.Names}}\t{{.Status}}'

echo
echo "===== 6. host log file ====="
sudo tail -80 /deploy/logs/mindie/glm-4.log 2>&1

echo
echo "===== 7. port 10006 ====="
ss -tlnp 2>/dev/null | grep 10006 || echo "NOT LISTENING"

echo
echo "===== 8. curl /v1/models ====="
curl -s -m 5 http://127.0.0.1:10006/v1/models 2>&1 | head -c 800
echo
