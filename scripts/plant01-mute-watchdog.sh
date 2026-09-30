#!/bin/bash
# plant01 Alertmanager：Watchdog/InfoInhibitor 静音（null 接收器），不再推钉钉
set -u
cd /data1/apps/wxq-plant01-monitor || exit 1
F=alertmanager/alertmanager.yml
cp -a $F $F.bak.$(date +%m%d-%H%M)
echo "备份: $F.bak.$(date +%m%d-%H%M)"
echo ""
echo "--- 当前 route/receivers 结构（前 20 行关键行）"
grep -nE "^(route:|receivers:|  routes:|  receiver:|- name:|  - name:)" $F | head -20
echo ""

python3 - <<'PY'
p = "/data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml"
s = open(p).read()
if "InfoInhibitor" in s:
    print("静音路由已存在，无需修改"); raise SystemExit
lines = s.split("\n")
out, ins_route, ins_recv = [], False, False
for ln in lines:
    out.append(ln)
    if not ins_route and ln.strip() == "routes:" and ln.startswith("  "):
        ind = ln[: len(ln) - len(ln.lstrip())] + "  "
        out += [ind + "- match_re:",
                ind + "    alertname: \"Watchdog|InfoInhibitor\"",
                ind + "  receiver: 'null'"]
        ins_route = True
if ins_route:
    for ln in out:
        if ln.startswith("receivers:"):
            idx = out.index(ln) + 1
            out.insert(idx, "- name: 'null'")
            ins_recv = True
            break
if not (ins_route and ins_recv):
    print("结构不符合预期（未找到 routes:/receivers:），不做修改"); raise SystemExit(1)
open(p, "w").write("\n".join(out2 if False else out))
print("✅ 已插入静音路由（match_re Watchdog|InfoInhibitor → receiver null）与空接收器")
PY
RC=$?
[ $RC -ne 0 ] && { echo "中止，不重启服务"; exit 1; }
echo ""
echo "--- amtool 语法校验"
docker exec wxq-alertmanager /bin/amtool check-config /etc/alertmanager/alertmanager.yml 2>&1 | tail -3
CHECK=${PIPESTATUS[0]}
if ! docker exec wxq-alertmanager /bin/amtool check-config /etc/alertmanager/alertmanager.yml >/dev/null 2>&1; then
  echo "❌ 校验失败，恢复备份"
  B=$(ls -t alertmanager/alertmanager.yml.bak.* | head -1)
  cp -a "$B" $F
  docker compose restart alertmanager >/dev/null 2>&1
  exit 1
fi
echo "  ✅ 校验通过"
echo ""
echo "--- 重启 alertmanager"
docker compose restart alertmanager >/dev/null 2>&1
sleep 10
echo -n "  服务: "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://localhost:9093/-/ready; echo ""
echo -n "  启动日志错误: "; docker logs wxq-alertmanager --since 1m 2>&1 | grep -ciE '"level":"error"' || echo 0
echo ""
echo "--- 当前路由树里的静音项确认（API 回读配置）"
curl -s http://localhost:9093/api/v2/status 2>/dev/null | grep -o 'InfoInhibitor' | head -1 && echo "  ✅ 静音路由已生效" || echo "  ⚠️ 未见（检查配置）"