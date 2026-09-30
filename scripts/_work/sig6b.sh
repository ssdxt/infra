#!/bin/bash
C=bge-m3-npu

echo "########## 1. /tmp/start.log（之前重定向的日志）##########"
sudo docker exec $C bash -c 'cat /tmp/start.log 2>&1 | tail -30'

echo
echo "########## 2. 最新的 run/plog 全文 ##########"
sudo docker exec $C bash -c '
for f in $(ls -t /root/ascend/log/run/plog/*.log 2>/dev/null | head -2); do
  echo "===== $f ====="
  cat "$f"
  echo
done
'

echo
echo "########## 3. 有没有 debug/plog ##########"
sudo docker exec $C bash -c 'ls -laR /root/ascend/log/ 2>&1 | head -30'

echo
echo "########## 4. 容器启动命令和环境 ##########"
sudo docker inspect $C --format 'Cmd={{json .Config.Cmd}}
Entrypoint={{json .Config.Entrypoint}}
User={{.Config.User}}'
sudo docker inspect $C --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -viE "^PATH=|^LD_LIBRARY" | head -20

echo
echo "########## 5. glm-4 容器（新镜像）状态 ##########"
sudo docker inspect glm-4-9b-chat --format 'Image={{.Config.Image}}
Status={{.State.Status}}
Started={{.State.StartedAt}}'
sudo docker logs --tail 15 glm-4-9b-chat 2>&1
