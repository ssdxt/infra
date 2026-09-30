#!/bin/bash
set -u
D=/data1/apps/wxq-plant01-monitor
cd $D || exit 1

echo "############ 1. 【最高优先】立刻恢复 wxq-prometheus ############"
if docker inspect wxq-prometheus >/dev/null 2>&1; then
  echo "  已存在，跳过"
else
  bash /data1/ssdxt/plant01-compose-backup/prometheus-rollback-dockerrun.sh 2>&1 | tail -2
fi
sleep 15
echo -n "  容器状态: "; docker inspect -f '{{.State.Status}}' wxq-prometheus 2>&1
echo -n "  /-/ready : "; curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://10.100.10.29:9091/-/ready; echo
echo -n "  remote-write 参数: "; docker inspect -f '{{range .Args}}{{.}} {{end}}' wxq-prometheus 2>/dev/null | grep -q 'enable-remote-write-receiver' && echo "在 ✅" || echo "丢失 ❌"
echo -n "  规则数: "; curl -s --max-time 10 http://10.100.10.29:9091/api/v1/rules 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); a=r=0
    for g in d["data"]["groups"]:
        for x in g["rules"]:
            a += x["type"]=="alerting"; r += x["type"]=="recording"
    print("alerting=%d recording=%d" % (a,r))
except Exception as e: print("读取失败")
'
echo ""
echo "############ 2. 恢复被弄坏的 compose 文件 ############"
LATEST_BAK=$(ls -t $D/docker-compose.yaml.before-external-* 2>/dev/null | head -1)
if [ -n "$LATEST_BAK" ]; then
  cp -a $D/docker-compose.yaml $D/docker-compose.yaml.broken-$(date +%m%d-%H%M)
  cp -a "$LATEST_BAK" $D/docker-compose.yaml
  echo "  已用 $LATEST_BAK 恢复"
else
  echo "  ⚠️ 没找到 before-external 备份"
fi
echo -n "  语法校验: "; docker compose config -q 2>&1 && echo "✅ OK" || echo "❌ 仍坏"
echo -n "  服务数: "; docker compose config --services 2>/dev/null | wc -l
echo ""
echo "############ 3. 【停止对运行容器的进一步操作】 ############"
echo "  Prometheus 保持手工创建状态（功能正常，只是没有 compose 标签）"
echo "  不再尝试用 compose 重建它 —— 收益（标签）不值得风险（服务中断）"
echo ""
echo "############ 4. 最终状态核对 ############"
echo "--- 10 个监控容器"
for c in wxq-prometheus wxq-grafana wxq-alertmanager wxq-victoriametrics wxq-prometheusalert wxq-node-exporter wxq-blackbox wxq-otel wxq-process-exporter wxq-pushgateway; do
  printf "  %-24s %-10s %s\n" "$c" "$(docker inspect -f '{{.State.Status}}' $c 2>/dev/null)" "$(docker inspect -f '{{.Config.Image}}' $c 2>/dev/null)"
done
echo ""
echo "--- 关键服务连通性"
echo -n "  Prometheus  : "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:9091/-/ready; echo
echo -n "  Alertmanager: "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:9093/-/ready; echo
echo -n "  Grafana     : "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:3001/api/health; echo
echo -n "  VictoriaMetrics: "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:8428/health; echo
echo -n "  PrometheusAlert: "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://10.100.10.29:8280/; echo
echo ""
echo "--- remote_write 是否仍在接收集群数据"
curl -s --max-time 10 'http://10.100.10.29:9091/api/v1/query?query=count(up)' 2>/dev/null | head -c 200; echo
echo ""
echo "############ 5. 备份/回滚材料 ############"
ls -la /data1/ssdxt/plant01-compose-backup/ | sed 's/^/  /'
ls -la $D/docker-compose* 2>/dev/null | sed 's/^/  /'