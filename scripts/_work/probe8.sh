#!/bin/bash
C=glm-4-9b-chat
echo "===== container command actually in use ====="
sudo docker inspect $C --format 'Cmd={{json .Config.Cmd}} Entrypoint={{json .Config.Entrypoint}} User={{.Config.User}} WorkingDir={{.Config.WorkingDir}}'

echo
echo "===== /glm-4.log inside container ====="
sudo docker exec $C bash -c 'ls -la /glm-4.log; echo "--- content ---"; cat /glm-4.log' 2>&1 | tail -30

echo
echo "===== in-container mindservice.log ====="
sudo docker exec $C bash -c 'tail -25 /usr/local/Ascend/mindie/1.0.0/mindie-service/logs/mindservice.log' 2>&1

echo
echo "===== ps ====="
sudo docker exec $C ps -ef 2>&1
