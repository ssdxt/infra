#!/bin/bash
# 给 wxq-prometheus 补回 compose 标签（让它出现在 docker compose ps 里）
# 严格安全门：① 配置文件必须校验通过 ② dry-run 不得涉及网络/卷变更
set -u
D=/data1/apps/wxq-plant01-monitor
cd $D || exit 1
F=$D/docker-compose.yaml
TS=$(date +%m%d-%H%M)
BK=/data1/ssdxt/plant01-compose-backup
mkdir -p $BK

fail() { echo ""; echo "⛔ 已中止：$1"; echo "   运行容器未做任何改动（prometheus 仍在运行）"; exit 1; }

echo "############ 0. 前置：确认 prometheus 在跑 + 回滚脚本可用 ############"
docker inspect -f '  当前 prometheus: {{.State.Status}} / {{.Config.Image}}' wxq-prometheus 2>/dev/null || fail "prometheus 不在运行，需先恢复"
[ -f $BK/prometheus-rollback-dockerrun.sh ] || fail "回滚脚本不存在：$BK/prometheus-rollback-dockerrun.sh"
chmod +x $BK/prometheus-rollback-dockerrun.sh 2>/dev/null
# 自检回滚脚本可执行（不实际运行）
bash -n $BK/prometheus-rollback-dockerrun.sh || fail "回滚脚本语法有问题"
grep -q 'docker run' $BK/prometheus-rollback-dockerrun.sh || fail "回滚脚本内容异常"
echo "  回滚脚本就绪 ✅（bash -n 语法校验通过，含 docker run 命令）"
echo ""

echo "############ 1. 精确修改网络/卷为 external（并立即校验）############"
cp -a $F $BK/docker-compose.before-external2-$TS.yaml
python3 - <<'PYEOF'
p = '/data1/apps/wxq-plant01-monitor/docker-compose.yaml'
s = open(p).read()
orig = s

# 网络：在 "  monitoring:" 之后插入 external: true（只动最后一节的 networks）
idx = s.rfind('\nnetworks:')
if idx == -1:
    raise SystemExit("找不到 networks 段")
head, tail = s[:idx], s[idx:]
if 'external: true' not in tail:
    tail = tail.replace('\nnetworks:\n  monitoring:\n', '\nnetworks:\n  monitoring:\n    external: true\n', 1)

# 卷：每个 "    name: wxq-monitor_xxx" 后补 external: true
import re
tail = re.sub(r'(^    name: wxq-monitor_[^\n]*\n)(?!    external: true)', r'\1    external: true\n', tail, flags=re.M)

s = head + tail
open(p, 'w').write(s)
print("修改完成" if s != orig else "无需修改")
PYEOF
echo "--- 修改后的 networks 段:"
sed -n '/^networks:/,$p' $F | sed 's/^/    /'
echo "--- 修改后的 volumes 段（前 12 行）:"
sed -n '/^volumes:/,/^networks:/p' $F | head -14 | sed 's/^/    /'
echo ""

echo "############ 2. 【安全门 1】配置文件校验 ############"
if docker compose config -q 2>/tmp/cfgerr; then
  echo "  ✅ 校验通过"
else
  echo "  ❌ 校验失败："; cat /tmp/cfgerr | sed 's/^/     /'
  cp -a $BK/docker-compose.before-external2-$TS.yaml $F
  fail "配置文件不合法，已还原"
fi
echo -n "  服务数: "; docker compose config --services 2>/dev/null | wc -l
echo ""

echo "############ 3. 【安全门 2】dry-run 检查危险动作 ############"
DRY=$(docker compose --dry-run up -d prometheus 2>&1)
DRYRC=$?
echo "$DRY" | sed 's/^/    /'
if [ $DRYRC -ne 0 ]; then
  cp -a $BK/docker-compose.before-external2-$TS.yaml $F
  fail "dry-run 执行失败（退出码 $DRYRC），可能不支持该参数，已还原"
fi
DANGER=$(echo "$DRY" | grep -icE '(network|volume).*(creat|remov|recreat|delet)' || true)
if [ "$DANGER" != "0" ]; then
  cp -a $BK/docker-compose.before-external2-$TS.yaml $F
  fail "dry-run 显示会变更网络或卷（$DANGER 处），已还原"
fi
echo "  ✅ dry-run 干净：只涉及 prometheus 容器本身"
echo ""

echo "############ 4. 两道门都通过 → 重建 prometheus 补回标签 ############"
echo "  （数据在具名卷 wxq-monitor_prometheus-data，未动）"
docker stop wxq-prometheus >/dev/null 2>&1 && echo "  已停止旧容器"
docker rm wxq-prometheus >/dev/null 2>&1 && echo "  已删除旧容器"
if docker compose up -d prometheus 2>&1 | tail -4 | sed 's/^/    /'; then
  :
fi
sleep 15
if ! docker inspect wxq-prometheus >/dev/null 2>&1; then
  echo "  ❌ 容器未创建，执行回滚！"
  bash $BK/prometheus-rollback-dockerrun.sh 2>&1 | tail -2
  sleep 12
fi
echo ""

echo "############ 5. 验证 ############"
echo "--- docker compose ps -a（应看到 10 个，含 prometheus）"
docker compose ps -a 2>&1 | sed 's/^/  /'
echo ""
echo "--- prometheus 的 compose 标签"
docker inspect -f '    proj={{index .Config.Labels "com.docker.compose.project"}}  svc={{index .Config.Labels "com.docker.compose.service"}}  cfg={{index .Config.Labels "com.docker.compose.project.config_files"}}' wxq-prometheus 2>&1
echo ""
echo -n "    /-/ready            : "; curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://10.100.10.29:9091/-/ready; echo
echo -n "    remote-write 参数   : "; docker inspect -f '{{range .Args}}{{.}} {{end}}' wxq-prometheus 2>/dev/null | grep -q 'enable-remote-write-receiver' && echo "在 ✅" || echo "丢失 ❌"
echo -n "    数据卷              : "; docker inspect -f '{{range .Mounts}}{{if eq .Destination "/prometheus"}}{{.Name}}{{end}}{{end}}' wxq-prometheus 2>/dev/null; echo
echo -n "    规则数              : "; curl -s --max-time 10 http://10.100.10.29:9091/api/v1/rules 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); a=r=0
    for g in d["data"]["groups"]:
        for x in g["rules"]:
            a += x["type"]=="alerting"; r += x["type"]=="recording"
    print("alerting=%d recording=%d" % (a,r))
except Exception: print("读取失败")
'
echo -n "    remote_write 接收中 : "; curl -s --max-time 10 'http://10.100.10.29:9091/api/v1/query?query=count(up)' 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print("count(up)=",d["data"]["result"][0]["value"][1])' 2>/dev/null
echo ""
echo "--- 其他 9 个容器状态"
for c in wxq-grafana wxq-alertmanager wxq-victoriametrics wxq-prometheusalert wxq-node-exporter wxq-blackbox wxq-otel wxq-process-exporter wxq-pushgateway; do
  printf "    %-24s %s\n" "$c" "$(docker inspect -f '{{.State.Status}}' $c 2>/dev/null)"
done
echo ""
echo "############ 完成 ############"