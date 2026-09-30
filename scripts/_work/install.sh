#!/bin/bash
VLLM=/deploy/models/docker_run/vllm
C=glm-4-9b-chat

echo "===== 停掉测试容器 ====="
sudo docker rm -f $C 2>&1 | tail -1

echo "===== 安装修正版 compose ====="
sudo cp /tmp/docker-compose.fixed.yml $VLLM/docker-compose.fixed.yml
sudo chown root:root $VLLM/docker-compose.fixed.yml
sudo mkdir -p /deploy/logs/mindie/ascend
sudo chown -R 1000:0 /deploy/logs/mindie

echo "===== 语法校验 ====="
sudo docker-compose -f $VLLM/docker-compose.fixed.yml config >/dev/null 2>&1 && echo "YAML OK"

echo "===== 目录内容 ====="
sudo ls -la $VLLM/

echo "===== 清理临时文件 ====="
sudo rm -f /tmp/dc-test.yml /tmp/probe*.sh /tmp/run*.sh /tmp/deploy_test.sh /tmp/docker-compose.fixed.yml
sudo rm -rf /tmp/mlogs /tmp/mlogs2 /tmp/mllm /tmp/ascend_log /tmp/mindie_logs

echo "===== 最终状态 ====="
sudo docker ps -a --format 'table {{.Names}}\t{{.Status}}'
