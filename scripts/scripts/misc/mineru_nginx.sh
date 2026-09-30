#!/bin/bash
echo "=== mineru nginx.conf 硬编码IP上下文 ==="
grep -n -B5 -A5 '192.168.8.1' /root/work/mineru/nginx/nginx.conf 2>/dev/null
echo "=== 这个 nginx 属于哪个容器 ==="
grep -rn -E 'mineru.*nginx|nginx.*mineru' /root/work /root/llm /root/apps --include='*.yml' --include='*.yaml' 2>/dev/null | head -10
echo "=== 所有部署目录里 192.168.8.x 的引用 ==="
grep -rn '192.168.8\.' /root/work /root/llm /root/apps /data 2>/dev/null | head -10
