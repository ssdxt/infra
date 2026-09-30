#!/bin/bash
set -u
cd /data1/apps/wxq-plant01-monitor || exit 1
F=alertmanager/alertmanager.yml
python3 - <<'PY'
import re
p = "/data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml"
s = open(p).read()
if "InfoInhibitor" in s:
    print("已存在，跳过"); raise SystemExit
lines = s.split("\n")

# 1) 在 routes: 之后插入静音子路由（沿用该文件的缩进风格）
out, done_r = [], False
for ln in lines:
    out.append(ln)
    if not done_r and re.match(r"^\s+routes:\s*$", ln):
        ind = ln[: len(ln) - len(ln.lstrip())] + "  "
        out += [ind + "- match_re:",
                ind + "      alertname: \"Watchdog|InfoInhibitor\"",
                ind + "  receiver: 'null'"]
        done_r = True

# 2) 在 receivers: 后插入空接收器（缩进与现有 - name: 行对齐）
done_n = False
out2 = []
for ln in out:
    out2.append(ln)
    if not done_n and ln.rstrip() == "receivers:":
        m = re.search(r"^\s+- name:", "\n".join(lines), re.M)
        ind = m.group(0)[: len(m.group(0)) - len(m.group(0).lstrip())] if m else "  "
        out2.append(ind + "- name: 'null'")
        done_n = True

if not (done_r and done_n):
    print("结构不符合预期"); raise SystemExit(1)
open(p, "w").write("\n".join(out2))
print("✅ 已写入静音路由 + 空接收器")
PY

echo "--- 插入后的相关片段"
grep -nE "routes:|match_re|alertname|name: 'null'|name: 'default'" $F | head -10 | sed 's/^/  /'
echo ""
echo "--- amtool 校验（完整输出）"
if docker exec wxq-alertmanager /bin/amtool check-config /etc/alertmanager/alertmanager.yml 2>&1; then
  echo "  ✅ 校验通过，重启 alertmanager"
  docker compose restart alertmanager >/dev/null 2>&1
  sleep 10
  echo -n "  服务就绪: "; curl -s -o /dev/null -w '%{http_code}' --max-time 8 http://localhost:9093/-/ready; echo ""
  echo -n "  启动错误日志: "; docker logs wxq-alertmanager --since 1m 2>&1 | grep -ciE '"level":"error"' || echo 0
  echo "  ✅ 完成（Watchdog/InfoInhibitor 不再推钉钉）"
else
  echo "  ❌ 仍失败，恢复备份"
  B=$(ls -t $F.bak.* | head -1); cp -a "$B" $F; docker compose restart alertmanager >/dev/null 2>&1
  docker exec wxq-alertmanager /bin/amtool check-config /etc/alertmanager/alertmanager.yml 2>&1 | tail -2
  exit 1
fi