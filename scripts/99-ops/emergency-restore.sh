#!/bin/bash
echo "############ 紧急恢复 wxq-prometheus ############"
echo "--- 用之前生成的回滚命令（与重建前完全一致，含 remote-write 参数）"
bash /data1/ssdxt/plant01-compose-backup/prometheus-rollback-dockerrun.sh 2>&1 | tail -3
echo ""
echo "--- 等待启动"
sleep 15
echo "--- 容器状态"
docker inspect -f '  状态={{.State.Status}}  镜像={{.Config.Image}}' wxq-prometheus 2>&1
docker inspect -f '  参数={{.Args}}' wxq-prometheus 2>/dev/null | tr ' ' '\n' | grep -E 'remote-write|lifecycle|external-url' | sed 's/^/    /'
echo ""
echo "--- 健康检查"
echo -n "  /-/ready : "; curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://10.100.10.29:9091/-/ready; echo
echo -n "  /api/v1/status/runtimeinfo : HTTP "; curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://10.100.10.29:9091/api/v1/status/runtimeinfo; echo
echo -n "  remote_write 是否在推 : "; curl -s --max-time 10 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_samples_total' 2>/dev/null | head -c 200; echo
echo ""
echo "--- 告警规则是否加载（应有 194 alert / 85 record）"
curl -s --max-time 10 http://10.100.10.29:9091/api/v1/rules 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    a=r=0
    for g in d["data"]["groups"]:
        for x in g["rules"]:
            if x["type"]=="alerting": a+=1
            else: r+=1
    print("    alerting=%d recording=%d" % (a,r))
except Exception as e: print("    读取失败:", e)
'
echo ""
echo "--- 网络标签（诊断 compose 为何想重建网络）"
docker network inspect wxq-monitor -f '  名称={{.Name}}
  标签={{.Labels}}
  已连容器数={{len .Containers}}' 2>&1