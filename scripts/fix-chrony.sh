#!/bin/bash
# 修复 chrony：以 10.100.10.14 为内网 NTP 服务器（它是唯一能连上外部时间源的节点）
set -u
SERVER=10.100.10.14
EXT=119.28.183.184
CLIENTS="10.100.10.10 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47"

echo "############################################################"
echo "步骤 1/3：把 $SERVER 配置为内网时间服务器"
echo "############################################################"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@$SERVER '
  F=""
  for f in /etc/chrony/chrony.conf /etc/chrony.conf; do [ -f "$f" ] && { F="$f"; break; }; done
  [ -z "$F" ] && { echo "找不到 chrony 配置文件"; exit 1; }
  cp -a "$F" "$F.bak.$(date +%m%d-%H%M)"
  echo "  配置文件: $F（已备份）"

  # 外部时间源改成 IP（离线环境解析不了外部域名）
  sed -i "s|^\(server\|pool\).*cn\.pool\.ntp\.org.*|server 119.28.183.184 iburst|" "$F"
  grep -q "^server " "$F" || echo "server 119.28.183.184 iburst" >> "$F"

  # 开放集群网段 + 本地备用层级
  grep -q "^allow 10.100.10.0/24" "$F" || echo "allow 10.100.10.0/24" >> "$F"
  grep -q "^local stratum" "$F" || echo "local stratum 8" >> "$F"

  systemctl restart chronyd
  sleep 10
  echo "  --- 关键配置行:"
  grep -E "^(server|pool|allow|local)" "$F" | sed "s/^/      /"
  echo "  --- 服务状态: $(systemctl is-active chronyd)"
  echo "  --- chronyc tracking:"
  chronyc tracking 2>/dev/null | grep -E "Reference ID|Stratum|System time|Last offset|Leap" | sed "s/^/      /"
  echo "  --- chronyc sources:"
  chronyc sources 2>/dev/null | tail -3 | sed "s/^/      /"
  echo "  --- 是否在监听 UDP 123:"
  ss -lunp 2>/dev/null | grep ":123" | sed "s/^/      /" || echo "      ⚠️ 未监听 123"
'
echo ""

echo "############################################################"
echo "步骤 2/3：其余节点改为同步 $SERVER"
echo "############################################################"
for ip in $CLIENTS; do
  echo "--- $ip"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=10 root@$ip "
    F=''
    for f in /etc/chrony/chrony.conf /etc/chrony.conf; do [ -f \"\$f\" ] && { F=\"\$f\"; break; }; done
    [ -z \"\$F\" ] && { echo '    找不到配置文件'; exit 1; }
    cp -a \"\$F\" \"\$F.bak.\$(date +%m%d-%H%M)\"
    sed -i 's|^\(server\|pool\).*cn\.pool\.ntp\.org.*|server $SERVER iburst|' \"\$F\"
    grep -q '^server ' \"\$F\" || echo 'server $SERVER iburst' >> \"\$F\"
    # 清理可能残留的其他外部源（都不可达）
    sed -i '/^pool .*ntp\.org/d' \"\$F\"
    systemctl restart chronyd
    sleep 8
    echo -n '    服务: '; systemctl is-active chronyd
    echo -n '    源: '; chronyc sources 2>/dev/null | tail -2 | tr '\n' ' '; echo
    echo -n '    基准: '; chronyc tracking 2>/dev/null | grep 'Reference ID' | sed 's/.*: //'
  " 2>&1 | sed 's/^/  /'
done
echo ""

echo "############################################################"
echo "步骤 3/3：等待收敛并检查同步状态"
echo "############################################################"
echo "  等 60 秒让 chrony 完成初次同步..."
sleep 60
for ip in $SERVER $CLIENTS; do
  echo -n "  [$ip] "
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip \
    "c=\$(chronyc tracking 2>/dev/null | grep -c 'Leap status.*Normal'); s=\$(chronyc sources 2>/dev/null | grep -c '^\^\*'); ref=\$(chronyc tracking 2>/dev/null | grep 'Reference ID' | sed 's/.*: //'); echo \"已同步源数=\$s 基准=\$ref\"" 2>/dev/null
done
echo ""
echo "  内核同步状态（Prometheus 里的 node_timex_sync_status）:"
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=node_timex_sync_status' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    ok=0; bad=[]
    for r in d["data"]["result"]:
        inst=r["metric"].get("instance","?").split(":")[0]; v=r["value"][1]
        if v=="1": ok+=1
        else: bad.append(inst)
    print("    ✅ 已同步: %d 台" % ok)
    print("    ❌ 未同步: %s" % (", ".join(bad) if bad else "无"))
except Exception as e: print("    查询失败:", e)
'