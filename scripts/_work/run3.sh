#!/bin/bash
set -u
VLLM=/deploy/models/docker_run/vllm
M=/deploy/models/glm-4-9b-chat
C=glm-4-9b-chat
LOG=/deploy/logs/mindie/glm-4.log
IMG=swr.cn-south-1.myhuaweicloud.com/ascendhub/mindie:1.0.0-300I-Duo-py311-openeuler24.03-lts

echo "===== 1. build a TLS-off config next to it (originals untouched) ====="
sudo sed -e 's/"interCommTLSEnabled" : true/"interCommTLSEnabled" : false/' \
         -e 's/"interNodeTLSEnabled" : true/"interNodeTLSEnabled" : false/' \
         $M/conf/config.json | sudo tee $VLLM/config.fixed.json >/dev/null
sudo grep -nE 'TLSEnabled' $VLLM/config.fixed.json

echo
echo "===== 2. test compose (temp, /tmp) ====="
sudo tee /tmp/dc-test.yml >/dev/null <<YAML
version: '3.7'
services:
  glm-4-9b-chat:
    container_name: glm-4-9b-chat
    image: $IMG
    restart: "no"
    network_mode: host
    privileged: true
    tty: true
    stdin_open: true
    runtime: runc
    user: "1000:0"
    group_add:
      - "1001"
    environment:
      - TZ=Asia/Shanghai
      - ASCEND_PROCESS_LOG_PATH=/deploy/logs/mindie/ascend
      - ASCEND_GLOBAL_LOG_LEVEL=1
      - ASCEND_SLOG_PRINT_TO_STDOUT=1
      - MINDIE_LLM_PYTHON_LOG_LEVEL=DEBUG
    working_dir: /usr/local/Ascend/mindie/latest/mindie-service
    volumes:
      - /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro
      - /usr/local/sbin:/usr/local/sbin:ro
      - $M:$M:rw
      - /dev/davinci0:/dev/davinci0
      - /dev/davinci1:/dev/davinci1
      - /dev/davinci_manager:/dev/davinci_manager
      - /dev/hisi_hdc:/dev/hisi_hdc
      - /dev/devmm_svm:/dev/devmm_svm
      - $VLLM/config.fixed.json:/usr/local/Ascend/mindie/latest/mindie-service/conf/config.json:ro
      - /deploy/logs/mindie:/deploy/logs/mindie:rw
    shm_size: 50g
    command: >
      bash -c ": > $LOG;
               cd /usr/local/Ascend/mindie/latest/mindie-service &&
               ./bin/mindieservice_daemon 2>&1 | tee -a $LOG"
YAML

sudo chown 1000:0 $VLLM/config.fixed.json
sudo chmod 640   $VLLM/config.fixed.json
sudo mkdir -p /deploy/logs/mindie/ascend
sudo chown -R 1000:0 /deploy/logs/mindie

cd $VLLM || exit 1
sudo docker-compose -f /tmp/dc-test.yml down --remove-orphans 2>&1 | tail -1
sudo docker rm -f $C 2>&1 | tail -1
sudo docker-compose -f /tmp/dc-test.yml up -d 2>&1 | grep -viE 'obsolete|orphan' | tail -4

echo
echo "===== 3. poll 4 min ====="
for i in $(seq 1 16); do
  sleep 15
  ST=$(sudo docker ps -a --filter "name=^${C}$" --format '{{.Status}}')
  LISTEN=$(ss -tln 2>/dev/null | grep -c ':10006')
  echo "[$((i*15))s] '$ST' listen=$LISTEN :: $(sudo tail -1 $LOG 2>/dev/null | cut -c1-100)"
  if [ "$LISTEN" -gt 0 ]; then echo "*** LISTENING ***"; break; fi
  if echo "$ST" | grep -qiE 'Exited|Restarting'; then echo "*** STOPPED ***"; break; fi
done

echo
echo "===== 4. non-config log lines ====="
sudo grep -v "model_config {" $LOG | tail -25

echo
echo "===== 5. ascend plog ====="
sudo find /deploy/logs/mindie/ascend -name "*.log" 2>/dev/null | head
for f in $(sudo find /deploy/logs/mindie/ascend -name "*.log" 2>/dev/null | head -2); do
  echo "--- $f ---"; sudo grep -iE "error|fail|exception|aicore" "$f" | tail -20
done

echo
echo "===== 6. curl ====="
curl -s -m 8 http://127.0.0.1:10006/v1/models | head -c 400
echo
sudo docker ps -a --filter "name=^${C}$" --format 'table {{.Names}}\t{{.Status}}'
