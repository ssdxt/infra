#!/bin/bash
echo "===== NTP 时间源可达性测试（chronyd -Q 查询模式，不干扰正在运行的守护进程）====="
for ip in 10.100.10.10 10.100.10.19 10.100.10.33; do
  echo ""
  echo "########## 节点 $ip ##########"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@$ip '
    echo -n "  cn.pool.ntp.org 解析: "; getent hosts cn.pool.ntp.org 2>/dev/null | head -2 | awk "{print \$1}" | tr "\n" " "; echo
    for srv in 119.28.183.184 203.107.6.88 120.25.115.20 10.100.10.14 time.windows.com; do
      echo -n "  测试 $srv: "
      timeout 12 chronyd -Q -t 6 "server $srv iburst" 2>&1 | grep -E "System clock|Reference ID|stratum|No suitable|timed out|failed" | head -2 | tr "\n" " "
      echo ""
    done
    echo -n "  UDP 123 出口测试(119.28.183.184): "
    timeout 5 bash -c "echo > /dev/udp/119.28.183.184/123" 2>/dev/null && echo "可发（不代表能回）" || echo "被阻断"
  ' 2>/dev/null
done
echo ""
echo "===== .14 到底为什么能同步成功 ====="
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=8 root@10.100.10.14 '
  echo "  --- 它的 chrony sources 详情"
  chronyc sources -v 2>/dev/null | tail -4 | sed "s/^/    /"
  echo "  --- 它的 resolv.conf"
  cat /etc/resolv.conf 2>/dev/null | grep -v "^#" | sed "s/^/    /"
  echo "  --- 路由表（看有没有特殊出口）"
  ip route 2>/dev/null | head -5 | sed "s/^/    /"
  echo "  --- chrony 是否在做时钟驯服（STA_PLL）"
  python3 -c "
import ctypes
class timex(ctypes.Structure):
    _fields_=[(\"modes\",ctypes.c_uint),(\"offset\",ctypes.c_long),(\"freq\",ctypes.c_long),
              (\"maxerror\",ctypes.c_long),(\"esterror\",ctypes.c_long),(\"status\",ctypes.c_int),
              (\"constant\",ctypes.c_long),(\"precision\",ctypes.c_long),(\"tolerance\",ctypes.c_long),
              (\"time\",ctypes.c_long*2),(\"tick\",ctypes.c_long),(\"ppsfreq\",ctypes.c_long),
              (\"jitter\",ctypes.c_long),(\"shift\",ctypes.c_int),(\"stabil\",ctypes.c_long),
              (\"jitcnt\",ctypes.c_long),(\"calcnt\",ctypes.c_long),(\"errcnt\",ctypes.c_long),
              (\"stbcnt\",ctypes.c_long),(\"tai\",ctypes.c_int)]
libc=ctypes.CDLL(\"libc.so.6\",use_errno=True)
t=timex(); t.modes=0; libc.adjtimex(ctypes.byref(t))
f=[]
for bit,name in [(0x0001,\"STA_PLL\"),(0x0002,\"STA_PPSFREQ\"),(0x0004,\"STA_PPSTIME\"),(0x0040,\"STA_NANO\"),(0x1000,\"STA_FREQHOLD\"),(0x2000,\"STA_UNSYNC\")]:
    if t.status & bit: f.append(name)
print(\"    status=0x%04x -> %s\" % (t.status, \" \".join(f)))
"
' 2>/dev/null
echo ""
echo "===== 所有节点的 resolv.conf 对比（DNS 差异会导致解析到不同 IP）====="
for ip in 10.100.10.10 10.100.10.19 10.100.10.33 10.100.10.14; do
  echo -n "  [$ip] "; ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=6 root@$ip 'grep -h "^nameserver" /etc/resolv.conf 2>/dev/null | tr "\n" " "' 2>/dev/null; echo
done