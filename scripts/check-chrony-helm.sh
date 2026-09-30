#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "===== 1. kube-prometheus-stack 的 helm release 信息 ====="
helm list -n monitoring 2>/dev/null | sed 's/^/  /'
REL=$(helm list -n monitoring -o json 2>/dev/null | python3 -c '
import sys,json
for r in json.load(sys.stdin):
    if "prometheus" in r["name"]: print(r["name"], r["chart"], r["namespace"])
' 2>/dev/null)
echo "  release/chart/ns: $REL"
echo ""
echo "--- 找 values 文件"
ls -la /data1/ssdxt/values/ 2>/dev/null | sed 's/^/  /'
find /data1/ssdxt -maxdepth 3 -iname '*prometheus*' -name '*.yaml' 2>/dev/null | sed 's/^/  /'
echo ""
echo "--- 当前 values 里有没有 kubeProxy 相关配置"
helm get values $(helm list -n monitoring -o json 2>/dev/null | python3 -c 'import sys,json;print([r["name"] for r in json.load(sys.stdin) if "prometheus" in r["name"]][0])') -n monitoring 2>/dev/null | grep -iE 'kubeProxy|kubeEtcd|kubeScheduler' -A3 | sed 's/^/  /' || echo "  （无 kubeProxy 配置，用的是 chart 默认 = enabled）"
echo ""
echo "===== 2. chrony 实际状态（三台 control + 抽一台 worker）====="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33; do
  echo "--- [$ip]"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip '
    echo -n "    chronyd 服务: "; systemctl is-active chronyd 2>/dev/null || systemctl is-active chrony 2>/dev/null || echo "未安装/未运行"
    echo "    chronyc tracking:"
    chronyc tracking 2>/dev/null | grep -E "Reference ID|Stratum|System time|Last offset|Leap status|Frequency" | sed "s/^/      /" || echo "      chronyc 不可用"
    echo "    chronyc sources:"
    chronyc sources 2>/dev/null | head -6 | sed "s/^/      /" || echo "      无输出"
    echo -n "    /etc/chrony 里的 server 配置: "
    grep -hE "^(server|pool|peer)" /etc/chrony/chrony.conf /etc/chrony.conf 2>/dev/null | tr "\n" " " || echo "（无）"
    echo ""
    echo -n "    内核同步状态 node_timex_sync_status: "
    cat /proc/sys/kernel/... 2>/dev/null
    python3 -c "
import subprocess
try:
    out=subprocess.run([\"chronyc\",\"tracking\"],capture_output=True,text=True).stdout
    for l in out.splitlines():
        if \"Leap status\" in l: print(l.split(\":\")[-1].strip())
except Exception as e: print(\"未知\")
"
  ' 2>/dev/null
done
echo ""
echo "===== 3. Prometheus 里各节点的 node_timex_sync_status ====="
PP=$(kubectl -n monitoring get pods --no-headers 2>/dev/null | grep 'prometheus-stack-kube-prom-prometheus-0' | awk '{print $1}')
kubectl -n monitoring exec $PP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/query?query=node_timex_sync_status' 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    for r in d["data"]["result"]:
        inst=r["metric"].get("instance","?"); v=r["value"][1]
        print("  %-24s node_timex_sync_status = %s  %s" % (inst, v, "✅同步" if v=="1" else "❌未同步"))
except Exception as e: print("  查询失败:", e)
'
echo ""
echo "===== 4. 节点上 Chrony 与内核判断的差异（关键诊断）====="
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@10.100.10.10 '
  echo "  --- chronyc tracking 完整输出"
  chronyc tracking 2>&1 | sed "s/^/    /"
  echo "  --- chronyc sources -v（看 Reach 列，0 = 完全不可达）"
  chronyc sources -v 2>&1 | tail -8 | sed "s/^/    /"
  echo "  --- 系统时间偏差"
  timedatectl 2>/dev/null | sed "s/^/    /"
  echo "  --- 内核 timex 状态（0x2000 = STA_UNSYNC 未同步）"
  python3 -c "
import ctypes
class timex(ctypes.Structure):
    _fields_=[(\"modes\",ctypes.c_uint),(\"offset\",ctypes.c_long),(\"freq\",ctypes.c_long),
              (\"maxerror\",ctypes.c_long),(\"esterror\",ctypes.c_long),(\"status\",ctypes.c_int),
              (\"constant\",ctypes.c_long),(\"precision\",ctypes.c_long),(\"tolerance\",ctypes.c_long),
              (\"time\",ctypes.c_long*2),(\"tick\",ctypes.c_long),(\"ppsfreq\",ctypes.c_long),
              (\"jitter\",ctypes.c_long),(\"shift\",ctypes.c_int),(\"stabil\",ctypes.c_long),
              (\"jitcnt\",ctypes.c_long),(\"calcnt\",ctypes.c_long),(\"errcnt\",ctypes.c_long),
              (\"stbcnt\",ctypes.c_long)]
libc=ctypes.CDLL(\"libc.so.6\",use_errno=True)
t=timex(); t.modes=0
libc.adjtimex(ctypes.byref(t))
st=t.status
flags=[]
if st & 0x0001: flags.append(\"STA_PLL\")
if st & 0x0002: flags.append(\"STA_PPSFREQ\")
if st & 0x0040: flags.append(\"STA_NANO\")
if st & 0x2000: flags.append(\"STA_UNSYNC(未同步)\")
if st & 0x1000: flags.append(\"STA_FREQHOLD\")
print(\"    status=0x%04x %s\" % (st, \" \".join(flags)))
"
' 2>/dev/null