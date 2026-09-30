#!/bin/bash
P=http://127.0.0.1:9091
C=wxq-prometheus
echo "===== [1] 宿主机与容器内 各自看到的 rules 目录 ====="
echo "  --- 宿主机 /data1/apps/wxq-plant01-monitor/prometheus/rules/"
ls -la /data1/apps/wxq-plant01-monitor/prometheus/rules/
echo
echo "  --- 容器内 /etc/prometheus/rules/"
docker exec $C ls -la /etc/prometheus/rules/
echo
echo "  --- 容器内 glob 展开测试(关键!) ---"
echo "    *.yml   :"; docker exec $C sh -c 'ls -1 /etc/prometheus/rules/*.yml' | sed 's/^/      /'
echo "    *.y*ml  :"; docker exec $C sh -c 'ls -1 /etc/prometheus/rules/*.y*ml' | sed 's/^/      /'
echo "    *.yaml  :"; docker exec $C sh -c 'ls -1 /etc/prometheus/rules/*.yaml' | sed 's/^/      /'
echo
echo "===== [2] 容器内实际的 prometheus.yml ====="
docker exec $C sh -c 'sed -n "25,40p" /etc/prometheus/prometheus.yml'
echo
echo "===== [3] 容器内实际看到的文件内容头(确认不是空/坏) ====="
docker exec $C sh -c 'ls -la /etc/prometheus/rules/cluster-wxq-rules.yaml 2>&1; head -3 /etc/prometheus/rules/cluster-wxq-rules.yaml 2>&1'
echo
echo "===== [4] reload 之后的日志(看 rules 加载情况) ====="
docker logs $C --since 10m 2>&1 | grep -iE 'rule|config|error' | tail -25
echo
echo "===== [5] 再显式 reload 一次并立刻看日志 ====="
echo -n "  reload HTTP: "; curl -s -o /dev/null -w '%{http_code}\n' -X POST "$P/-/reload"
sleep 6
docker logs $C --since 1m 2>&1 | tail -20
echo
echo "===== [6] 再看规则总数 ====="
curl -s "$P/api/v1/rules" | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']['groups']
print('  groups =',len(d),' rules =',sum(len(g['rules']) for g in d))
"
