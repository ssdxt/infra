#!/bin/bash
cd /deploy/code/chat_doc_0918 || exit 1
F=startup_obd.py
TS=$(date +%Y%m%d-%H%M%S)

echo "########## 1. 修改前：4 处 uvicorn.run ##########"
grep -n "uvicorn.run" $F

echo
echo "########## 2. 备份 ##########"
cp -a $F $F.bak-$TS
echo "  $F.bak-$TS"

echo
echo "########## 3. 去掉 ssl_certfile / ssl_keyfile 参数 ##########"
python3 - <<'EOF'
import re, io
p = "/deploy/code/chat_doc_0918/startup_obd.py"
src = open(p, encoding="utf-8").read()
before = src.count("ssl_certfile=SSL_CERTFILE,ssl_keyfile=SSL_KEYFILE")
# 同时处理可能的空格变体
pat = re.compile(r",\s*ssl_certfile=SSL_CERTFILE,\s*ssl_keyfile=SSL_KEYFILE")
new, n = pat.subn("", src)
open(p, "w", encoding="utf-8").write(new)
print(f"  匹配到 {before} 处（含空格变体共替换 {n} 处）")
EOF

echo
echo "########## 4. 修改后 ##########"
grep -n "uvicorn.run" $F
echo
echo "--- 确认 SSL 变量只作为定义残留（不再被使用）---"
grep -n "SSL_CERTFILE\|SSL_KEYFILE" $F

echo
echo "########## 5. 语法检查 ##########"
/root/anaconda3/envs/recovery/bin/python -m py_compile $F && echo "  语法 OK" || echo "  语法错误！"

echo
echo "########## 6. 重启服务 ##########"
systemctl restart chat_doc_api
sleep 45
systemctl is-active chat_doc_api

echo
echo "########## 7. 端口与协议复核 ##########"
for p in 20400 20401 8261 3333; do
  printf "  port %-6s http=" $p
  curl -s -o /dev/null -w "%{http_code} " -m 8 http://127.0.0.1:$p/docs 2>/dev/null
  printf " https="
  curl -sk -o /dev/null -w "%{http_code}\n" -m 8 https://127.0.0.1:$p/docs 2>/dev/null
done
