#!/bin/bash
C=glm-4-9b-chat
LOG=/deploy/logs/mindie/glm-4.log

echo "########## 1. 容器状态 ##########"
sudo docker ps -a --filter "name=^${C}$" --format '{{.Names}} {{.Status}}'

echo
echo "########## 2. 日志里的报错/python 异常 ##########"
sudo grep -nE "Traceback|Error|ERROR|error|Exception|raise |RuntimeError|Assertion|FATAL|not found|No such" $LOG \
  | grep -vE "log_error|ERROR\] \[logging|aclrtGetDevice: can not" | tail -40

echo
echo "########## 3. 日志末尾 40 行(去 config 噪音) ##########"
sudo grep -v "model_config {" $LOG | tail -40

echo
echo "########## 4. 容器内日志文件 ##########"
sudo rm -rf /tmp/mlogs2
sudo docker cp $C:/usr/local/Ascend/mindie/1.0.0/mindie-service/logs /tmp/mlogs2 2>&1 | head -2
sudo ls -la /tmp/mlogs2/ 2>&1
echo "--- mindservice.log ---"
sudo tail -40 /tmp/mlogs2/mindservice.log 2>&1

echo
echo "########## 5. 容器内 mindie-llm 的日志 ##########"
sudo docker cp $C:/usr/local/Ascend/mindie/1.0.0/mindie-llm/logs /tmp/mllm 2>&1 | head -2
sudo ls -la /tmp/mllm/ 2>&1
for f in $(sudo find /tmp/mllm -name "*.log" 2>/dev/null | head -3); do
  echo "--- $f ---"; sudo tail -30 "$f"
done

echo
echo "########## 6. /deploy/logs/mindie 目录 ##########"
sudo find /deploy/logs/mindie -type f -o -type d | head -20
