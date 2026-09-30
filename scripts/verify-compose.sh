#!/bin/bash
cd /data1/apps/wxq-plant01-monitor
F=docker-compose.reconstructed.yaml
echo "=== 关键参数是否保留 ==="
grep -q 'enable-remote-write-receiver' $F && echo "  ✅ remote-write 接收参数已保留" || echo "  ❌ 丢了 remote-write 参数！"
grep -q 'enable-lifecycle' $F && echo "  ✅ lifecycle 参数在"
echo ""
echo "=== prometheus 段 ==="
sed -n '/^  prometheus:/,/^  [a-z]/p' $F | head -22
echo ""
echo "=== 端口映射总览（关键：看有没有冲突）==="
grep -A3 'ports:' $F | grep -E '^\s+- "' | sort | uniq -c | sort -rn
echo ""
echo "=== 与错误文件的关键差异对比 ==="
echo "  错误文件(你复制的):  name=device-monitoring，容器 dm-*，镜像 quay.io/*"
echo -n "  重建文件(实际事实):  "
grep -m1 '^name:' $F
grep -m2 'image:' $F | sed 's/^/                        /'
echo ""
echo "=== 卷定义（确认指向现有卷，不会新建空卷丢数据）==="
sed -n '/^volumes:/,$p' $F
echo ""
echo "=== 各服务端口（对比错误文件会冲突的地方）==="
python3 - <<'PYEOF'
import re
txt = open('/data1/apps/wxq-plant01-monitor/docker-compose.reconstructed.yaml').read()
cur = None
for line in txt.split('\n'):
    m = re.match(r'^  ([a-z0-9-]+):$', line)
    if m: cur = m.group(1)
    m2 = re.match(r'^\s+- "(\d+):(\d+)', line)
    if m2: print("  %-22s %s -> %s" % (cur, m2.group(1), m2.group(2)))
PYEOF