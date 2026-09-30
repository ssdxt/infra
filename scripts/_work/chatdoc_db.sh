#!/bin/bash
echo "########## 1 找到应用代码目录 ##########"
APIDIR=""
for p in $(ps -ef | grep -E "startup_obd.py|https_server.py" | grep -v grep | awk '{print $2}'); do
  d=$(readlink -f /proc/$p/cwd 2>/dev/null)
  echo "  pid=$p cwd=$d"
  [ -n "$d" ] && APIDIR="$d"
done
echo "  APIDIR=$APIDIR"

echo
echo "########## 2 启动脚本内容 ##########"
for f in api_start.sh web_start.sh speech_service_start.sh; do
  echo "===== /deploy/cc/bash/$f ====="
  cat /deploy/cc/bash/$f 2>&1
  echo
done

echo
echo "########## 3 systemd 单元内容 ##########"
for u in chat_doc_api chat_doc_web chat_doc_speech; do
  echo "===== /etc/systemd/system/$u.service ====="
  cat /etc/systemd/system/$u.service 2>&1
  echo
done

echo
echo "########## 4 chat_doc_speech 为什么循环 ##########"
journalctl -u chat_doc_speech --no-pager -n 60 2>&1 | tail -60

echo
echo "########## 5 chat_doc_api 最近日志（找数据库报错）##########"
journalctl -u chat_doc_api --no-pager -n 120 2>&1 | grep -iE "error|exception|refused|timeout|mysql|ocean|2881|1045|2003|traceback" | tail -40
echo "--- 尾部 30 行 ---"
journalctl -u chat_doc_api --no-pager -n 30 2>&1 | tail -30

echo
echo "########## 6 OceanBase 连通性 ##########"
echo -n "  宿主 -> 127.0.0.1:2881 : "; timeout 5 bash -c 'cat < /dev/null > /dev/tcp/127.0.0.1/2881' 2>/dev/null && echo "通" || echo "不通"
echo -n "  宿主 -> 192.168.21.111:2881 : "; timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.21.111/2881' 2>/dev/null && echo "通" || echo "不通"
echo "  --- 容器内监听 ---"
docker exec oceanbase-ce sh -c 'ss -lntp 2>/dev/null || netstat -lntp 2>/dev/null' 2>&1 | head -20
echo "  --- 容器内进程 ---"
docker exec oceanbase-ce sh -c 'ps -ef | head -12' 2>&1
echo "  --- 容器内 2881 自测 ---"
docker exec oceanbase-ce sh -c 'timeout 4 bash -c "cat < /dev/null > /dev/tcp/127.0.0.1/2881" && echo 容器内2881通 || echo 容器内2881不通' 2>&1

echo
echo "########## 7 obclient 各种连法 ##########"
echo "--- -h127.0.0.1 ---"; docker exec oceanbase-ce obclient -h127.0.0.1 -P2881 -uroot@test -p12345 -e "select 1" 2>&1 | head -5
echo "--- -h192.168.21.111 ---"; docker exec oceanbase-ce obclient -h192.168.21.111 -P2881 -uroot@test -p12345 -e "select 1" 2>&1 | head -5
echo "--- 宿主用 recovery 环境的 python ---"
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='192.168.21.111',port=2881,user='root@test',password='12345',connect_timeout=8);cur=c.cursor();cur.execute('show databases');print('OK ->',[r[0] for r in cur.fetchall()])" 2>&1 | tail -5
echo "--- 直接连 chat_doc 库并列表 ---"
/root/anaconda3/envs/recovery/bin/python -c "import pymysql;c=pymysql.connect(host='192.168.21.111',port=2881,user='root@test',password='12345',database='chat_doc',connect_timeout=8);cur=c.cursor();cur.execute('show tables');rows=cur.fetchall();print('chat_doc 表数量 =',len(rows));[print('   ',r[0]) for r in rows[:20]]" 2>&1 | tail -25

echo
echo "########## 8 应用里数据库配置指向哪 ##########"
if [ -n "$APIDIR" ]; then
  echo "  在 $APIDIR 里搜 2881 / oceanbase / chat_doc"
  grep -rn "2881\|oceanbase\|OCEANBASE\|chat_doc" "$APIDIR" --include=*.py --include=*.env --include=*.json --include=*.yaml --include=*.yml 2>/dev/null | head -25
fi

echo
echo "########## 9 GLM-4 现在通不通（10006 在监听）##########"
curl -s -m 8 -o /tmp/m.json -w "  /v1/models HTTP %{http_code}\n" http://127.0.0.1:10006/v1/models
head -c 400 /tmp/m.json 2>/dev/null; echo
echo "  --- 实测一次对话 ---"
curl -s -m 60 -X POST http://127.0.0.1:10006/v1/chat/completions -H 'Content-Type: application/json' -d '{"model":"glm-4","messages":[{"role":"user","content":"你好"}],"max_tokens":16}' -w '\n  HTTP %{http_code}\n' 2>&1 | head -c 800
