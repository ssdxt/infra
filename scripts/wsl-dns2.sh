#!/bin/bash
echo "== WSL 代理环境变量"
env | grep -i proxy || echo "无代理变量"
echo "== 加 hosts 条目后重测"
echo "10.100.10.29 harbor.wuxing.local" >> /etc/hosts
grep harbor /etc/hosts
curl -sk -o /dev/null -w 'domain-after-hosts=%{http_code}\n' --max-time 8 https://harbor.wuxing.local
echo "== verbose 看卡在哪"
curl -skv -o /dev/null --max-time 8 https://harbor.wuxing.local 2>&1 | grep -E 'Trying|Connected|SSL|HTTP|error|refused' | head -8