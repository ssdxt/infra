#!/bin/bash
# 修正 compose 文件：把已存在的网络/卷标记为 external，避免 compose 试图重建
# 带 dry-run 安全门：只有在确认 compose 不会动网络/卷时才真正执行
set -u
D=/data1/apps/wxq-plant01-monitor
cd $D || exit 1
F=docker-compose.yaml

echo "############ 1. 修文件：网络与卷标记为 external ############"
cp -a $F $F.before-external-$(date +%m%d-%H%M)
python3 - <<'PYEOF'
import re
p = '/data1/apps/wxq-plant01-monitor/docker-compose.yaml'
s = open(p).read()
if 'external: true\n\nnetworks:' not in s and re.search(r'networks:\s*\n\s+monitoring:', s) and 'external: true' not in s.split('networks:')[-1]:
    s = re.sub(r'(networks:\s*\n\s+monitoring:\s*\n)', r'\1    external: true\n', s, count=1)
# 卷：每个 "    name: wxq-monitor_xxx" 后面补 external: true
s = re.sub(r'(^    name: wxq-monitor_[^\n]*\n)', r'\1    external: true\n', s, flags=re.M)
open(p,'w').write(s)
print("已插入 external 标记")
PYEOF
echo "--- networks 段:"
sed -n '/^networks:/,$p' $F | sed 's/^/    /'
echo "--- volumes 段:"
sed -n '/^volumes:/,/^networks:/p' $F | sed 's/^/    /'
echo ""
echo "############ 2. 语法校验 ############"
docker compose config -q && echo "  ✅ 语法 OK"
echo ""
echo "############ 3. 【安全门】dry-run：看 compose 打算做什么 ############"
OUT=$(docker compose --dry-run up -d 2>&1)
echo "$OUT" | sed 's/^/  /'
echo ""
DANGER=$(echo "$OUT" | grep -icE 'network .*(creat|remov|recreat)|volume .*(creat|remov|recreat)|deleting|removing' || true)
echo "  危险动作计数: $DANGER"
echo ""
if [ "$DANGER" != "0" ]; then
  echo "  ⛔ dry-run 显示会动网络/卷 —— 已中止，不执行实际变更"
  exit 1
fi
echo "  ✅ dry-run 干净（不会动网络/卷）"
echo ""

echo "############ 4. 通过安全门：重建 wxq-prometheus 以补回 compose 标签 ############"
echo "  （数据在具名卷 wxq-monitor_prometheus-data，不会丢）"
docker stop wxq-prometheus >/dev/null 2>&1 && echo "  已停止"
docker rm wxq-prometheus >/dev/null 2>&1 && echo "  已删除旧容器"
docker compose up -d prometheus 2>&1 | tail -4 | sed 's/^/    /'
sleep 15
echo ""
echo "############ 5. 验证 ############"
echo "--- compose 全量状态（应 10 个服务都在，prometheus 带标签）"
docker compose ps -a 2>&1 | sed 's/^/  /'
echo ""
echo -n "  prometheus compose 标签: "
docker inspect -f 'proj={{index .Config.Labels "com.docker.compose.project"}} svc={{index .Config.Labels "com.docker.compose.service"}}' wxq-prometheus 2>&1
echo ""
echo "--- Prometheus 健康"
echo -n "    /-/ready              : "; curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://10.100.10.29:9091/-/ready; echo
echo -n "    remote-write 参数     : "; docker inspect -f '{{range .Args}}{{.}} {{end}}' wxq-prometheus 2>/dev/null | grep -q 'enable-remote-write-receiver' && echo "在 ✅" || echo "丢失 ❌"
echo -n "    规则数                : "; curl -s --max-time 10 http://10.100.10.29:9091/api/v1/rules 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); a=r=0
    for g in d["data"]["groups"]:
        for x in g["rules"]:
            a += x["type"]=="alerting"; r += x["type"]=="recording"
    print("alerting=%d recording=%d" % (a,r))
except Exception as e: print("读取失败", e)
'
echo -n "    数据卷挂载            : "; docker inspect -f '{{range .Mounts}}{{if eq .Destination "/prometheus"}}{{.Name}}{{end}}{{end}}' wxq-prometheus 2>/dev/null; echo
echo -n "    与 Grafana 网络互通   : "; docker exec wxq-grafana sh -c 'wget -qO- --timeout=5 http://prometheus:9090/-/ready 2>/dev/null | head -c 20' 2>/dev/null; echo
echo ""
echo "--- 其他 9 个容器未受影响"
for c in wxq-grafana wxq-alertmanager wxq-victoriametrics wxq-prometheusalert wxq-node-exporter wxq-blackbox wxq-otel wxq-process-exporter wxq-pushgateway; do
  printf "    %-24s %s\n" "$c" "$(docker inspect -f '{{.State.Status}}' $c 2>/dev/null)"
done
echo ""
echo "############ 完成 ############"