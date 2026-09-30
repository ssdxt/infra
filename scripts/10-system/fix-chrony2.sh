#!/bin/bash
# chrony 修复 v2：用 Python 精确改写配置（避免 sed 转义问题）
set -u
SERVER=10.100.10.14
EXT_IP=5.79.108.34          # .14 实测连上的外部源 IP
CLIENTS="10.100.10.10 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"

# 生成客户端修复脚本
cat > /tmp/fix_chrony_client.py <<'PYEOF'
#!/usr/bin/env python3
import shutil, datetime, sys, subprocess, os
SERVER = "10.100.10.14"
CONF = "/etc/chrony/chrony.conf"
if not os.path.exists(CONF):
    print("  ❌ 找不到 %s" % CONF); sys.exit(1)
ts = datetime.datetime.now().strftime("%m%d-%H%M%S")
shutil.copy2(CONF, "%s.bak2.%s" % (CONF, ts))
lines = open(CONF).read().splitlines()
out, done = [], False
removed = []
for ln in lines:
    s = ln.strip()
    if s.startswith("server ") or s.startswith("pool "):
        removed.append(s)
        if not done:
            out.append("server %s iburst" % SERVER); done = True
        continue
    out.append(ln)
if not done:
    out.insert(0, "server %s iburst" % SERVER)
open(CONF, "w").write("\n".join(out) + "\n")
print("  备份: %s.bak2.%s" % (CONF, ts))
print("  移除的源: %s" % (removed if removed else "无"))
print("  写入: server %s iburst" % SERVER)
# 清理可疑 drift（1000000 ppm 那种坏值）
drift = "/var/lib/chrony/chrony.drift"
if os.path.exists(drift):
    txt = open(drift).read()
    if "1000000" in txt:
        os.remove(drift); print("  ⚠️ 删除损坏的 drift 文件（含 1000000 ppm）: %s" % drift)
subprocess.run(["systemctl", "restart", "chronyd"])
PYEOF

# 生成服务器修复脚本
cat > /tmp/fix_chrony_server.py <<'PYEOF'
#!/usr/bin/env python3
import shutil, datetime, os, subprocess
EXT_IP = "5.79.108.34"
CONF = "/etc/chrony/chrony.conf"
ts = datetime.datetime.now().strftime("%m%d-%H%M%S")
shutil.copy2(CONF, "%s.bak2.%s" % (CONF, ts))
lines = open(CONF).read().splitlines()
out, has_ip, has_pool = [], False, False
for ln in lines:
    s = ln.strip()
    if s.startswith("server ") or s.startswith("pool "):
        if "5.79.108.34" in s: has_ip = True
        if "cn.pool.ntp.org" in s: has_pool = True
        out.append(ln); continue
    out.append(ln)
add = []
if not has_ip:   add.append("server %s iburst" % EXT_IP)
if not has_pool: add.append("server cn.pool.ntp.org iburst")
if add:
    out = add + out
if not any(l.strip().startswith("allow 10.100.10.0/24") for l in out):
    out.append("allow 10.100.10.0/24")
if not any(l.strip().startswith("local stratum") for l in out):
    out.append("local stratum 10")
open(CONF, "w").write("\n".join(out) + "\n")
print("  备份: %s.bak2.%s" % (CONF, ts))
print("  新增: %s" % (add if add else "无（已存在）"))
subprocess.run(["systemctl", "restart", "chronyd"])
PYEOF

push() { ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@$1 "cat > $2" < $3; }

echo "############################################################"
echo "步骤 1：修复服务器 $SERVER"
echo "############################################################"
push $SERVER /tmp/fix_srv.py /tmp/fix_chrony_server.py
ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$SERVER 'python3 /tmp/fix_srv.py; sleep 12;
  echo "  --- 配置行:"; grep -nE "^\s*(server|pool|allow|local)" /etc/chrony/chrony.conf | sed "s/^/      /"
  echo "  --- 服务: $(systemctl is-active chronyd)"
  echo "  --- 同步状态:"; chronyc tracking | grep -E "Reference ID|Stratum|System time|Leap" | sed "s/^/      /"
  echo "  --- 源:"; chronyc sources | tail -3 | sed "s/^/      /"
  echo "  --- 监听123:"; ss -lunp 2>/dev/null | grep -c ":123" | sed "s/^/      /"'
echo ""

echo "############################################################"
echo "步骤 2：修复 10 个客户端（改为同步 $SERVER）"
echo "############################################################"
for ip in $CLIENTS; do
  echo "--- $ip"
  push $ip /tmp/fix_cli.py /tmp/fix_chrony_client.py
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'python3 /tmp/fix_cli.py; sleep 10;
    echo -n "      服务: "; systemctl is-active chronyd
    echo -n "      源: "; chronyc sources 2>/dev/null | tail -1
    echo -n "      基准: "; chronyc tracking 2>/dev/null | grep "Reference ID" | sed "s/.*: //"
    echo -n "      配置: "; grep -E "^\s*(server|pool)" /etc/chrony/chrony.conf | tr "\n" " "; echo' 2>&1
done
echo ""

echo "############################################################"
echo "步骤 3：等 90 秒收敛后总检查"
echo "############################################################"
sleep 90
for ip in $SERVER $CLIENTS; do
  printf "  [%-14s] " $ip
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip \
    'sel=$(chronyc sources 2>/dev/null | grep -c "^\^\*"); ref=$(chronyc tracking 2>/dev/null | grep "Reference ID" | sed "s/.*: //"); leap=$(chronyc tracking 2>/dev/null | grep -c "Leap status.*Normal"); printf "已选源=%s  基准=%s  Leap正常=%s\n" "$sel" "$ref" "$leap"' 2>/dev/null
done
echo ""
echo "  ===== Prometheus 里的 node_timex_sync_status ====="
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=node_timex_sync_status' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin); ok=[];bad=[]
    for r in d["data"]["result"]:
        i=r["metric"].get("instance","?").split(":")[0]
        (ok if r["value"][1]=="1" else bad).append(i)
    print("    ✅ 已同步 %d 台: %s" % (len(ok), ", ".join(sorted(ok))))
    print("    ❌ 未同步 %d 台: %s" % (len(bad), ", ".join(sorted(bad)) if bad else "无"))
except Exception as e: print("    查询失败:", e)
'