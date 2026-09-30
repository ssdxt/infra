#!/bin/bash
echo "########## 1 systemd 里 chat_doc 相关单元 ##########"
systemctl list-unit-files 2>/dev/null | grep -i chat_doc || echo "  没有 chat_doc 的 unit file"
echo "--- 运行中的 ---"
systemctl list-units --all 2>/dev/null | grep -i chat_doc || echo "  没有 chat_doc 的 unit"

echo
echo "########## 2 三个服务逐个看状态 ##########"
for u in chat_doc_api chat_doc_web chat_doc_speech; do
  echo "===== $u ====="
  systemctl status "$u" --no-pager -l 2>&1 | head -18
  echo
done

echo "########## 3 所有容器 ##########"
docker ps -a --format '  {{.Names}} | {{.Status}} | {{.Ports}}' 2>&1

echo
echo "########## 4 相关进程 ##########"
ps -ef 2>/dev/null | grep -iE "chat_doc|uvicorn|startup_obd|speech|fschat|fastapi" | grep -v grep | head -25 || echo "  无"

echo
echo "########## 5 端口监听 ##########"
ss -lntp 2>/dev/null | grep -E ':(8261|20400|20401|3333|7870|2881|2882|8105|8106|10006|1026)' || echo "  以上端口都没有监听"

echo
echo "########## 6 OceanBase 容器状态 ##########"
docker ps -a --filter name=oceanbase --format '  {{.Names}} | {{.Status}} | {{.Ports}}' 2>&1
echo "--- 容器日志尾部 ---"
docker logs --tail 15 oceanbase-ce 2>&1 | tail -15

echo
echo "########## 7 数据库连通性（宿主 -> 2881）##########"
echo -n "  TCP 192.168.21.111:2881 : "
timeout 4 bash -c 'cat < /dev/null > /dev/tcp/192.168.21.111/2881' 2>/dev/null && echo "端口开放" || echo "连不上"
echo -n "  TCP 127.0.0.1:2881      : "
timeout 4 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/2881' 2>/dev/null && echo "端口开放" || echo "连不上"

echo
echo "########## 8 尝试登录 OceanBase ##########"
echo "--- 容器内 obclient ---"
docker exec oceanbase-ce sh -c 'which obclient mysql 2>/dev/null' 2>&1
docker exec oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -15
echo "--- 容器内 mysql ---"
docker exec oceanbase-ce mysql -h127.0.0.1 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -15
echo "--- 宿主 mysql 客户端 ---"
which mysql obclient 2>&1
mysql -h192.168.21.111 -P2881 -uroot@test -p12345 -e "show databases;" 2>&1 | head -15

echo
echo "########## 9 应用配置里数据库指向哪里 ##########"
ls -la /deploy/cc/ 2>&1
echo "--- 找配置文件 ---"
find /deploy/cc -maxdepth 3 -name "*.py" -o -maxdepth 3 -name "*.env" -o -maxdepth 3 -name "*.json" 2>/dev/null | head -20
echo "--- 搜 2881 / oceanbase / chat_doc ---"
grep -rn "2881\|oceanbase\|OCEANBASE\|chat_doc" /deploy/cc --include=*.py --include=*.env --include=*.json --include=*.sh --include=*.yaml --include=*.yml -l 2>/dev/null | head -20

echo
echo "########## 10 启动脚本 ##########"
ls -la /deploy/cc/bash/ 2>&1
echo "--- service 目录 ---"
ls -la /deploy/cc/service/ 2>&1
