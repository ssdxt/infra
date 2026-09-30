#!/bin/bash
cd /deploy/code/chat_doc_0918 || exit 1
F=server/knowledge_base/kb_doc_api.py
TS=$(date +%Y%m%d-%H%M%S)

echo "########## 修复1: examples 的 dict -> list（kb_doc_api.py）##########"
echo "--- 修改前 ---"
grep -n "examples={\"page_start\"" $F

cp -a $F $F.bak-$TS
echo "  备份: $F.bak-$TS"

python3 - <<'EOF'
p = "/deploy/code/chat_doc_0918/server/knowledge_base/kb_doc_api.py"
src = open(p, encoding="utf-8").read()
old = 'examples={"page_start":0,"page_end":100,"catalogue_re":[],"image_save":True,"generate_question": False}'
new = 'examples=[{"page_start":0,"page_end":100,"catalogue_re":[],"image_save":True,"generate_question": False}]'
if old in src:
    src = src.replace(old, new)
    open(p, "w", encoding="utf-8").write(src)
    print("  已替换 dict -> list")
else:
    print("  !! 未找到目标字符串，请人工确认")
EOF

echo "--- 修改后 ---"
grep -n "examples=\[{\"page_start\"" $F
echo "--- 校验：所有 examples= 都是 list ---"
grep -oE 'examples=\[[^]]*\]|examples=\{[^}]*\}' $F | sed 's/^/  /' | head -20

echo
echo "--- 语法检查 ---"
/root/anaconda3/envs/recovery/bin/python -m py_compile $F && echo "  语法 OK" || echo "  语法错误"

echo
echo "########## 修复2: 重启 web 服务（清掉卡死的连接）##########"
systemctl restart chat_doc_web
sleep 8
systemctl is-active chat_doc_web

echo
echo "########## 重启 chat_doc_api（让 openapi 修复生效）##########"
systemctl restart chat_doc_api
sleep 45
systemctl is-active chat_doc_api

echo
echo "########## 验证 ##########"
echo "--- 8261 /openapi.json ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -m 15 http://127.0.0.1:8261/openapi.json
echo "--- 8261 /docs ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -m 10 http://127.0.0.1:8261/docs
echo "--- 20400 /v1/models ---"
curl -s -o /dev/null -w "  HTTP %{http_code}\n" -m 10 http://127.0.0.1:20400/v1/models
echo "--- 3333 web (https，这次用对吗) ---"
curl -sk -o /dev/null -w "  HTTP %{http_code}\n" -m 10 https://127.0.0.1:3333/

echo
echo "########## 三服务状态 ##########"
for s in chat_doc_api chat_doc_web chat_doc_speech; do
  printf "  %-20s %s\n" "$s" "$(systemctl is-active $s)"
done
