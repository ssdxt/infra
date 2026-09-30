#!/bin/bash
cd /deploy/code/chat_doc_0918 2>/dev/null || exit 1

echo "########## 1. SSL_CERTFILE / SSL_KEYFILE 的定义 ##########"
grep -rn "SSL_CERTFILE\|SSL_KEYFILE" --include="*.py" . 2>/dev/null | head -15

echo
echo "########## 2. configs 里的 SSL 配置项 ##########"
grep -rn "SSL_CERTFILE\|SSL_KEYFILE\|ssl" configs/*.py 2>/dev/null | head -15

echo
echo "########## 3. 证书文件是否存在 ##########"
for f in $(grep -rhoE '"[^"]*\.(pem|crt|key)"' configs/*.py startup_obd.py 2>/dev/null | tr -d '"' | sort -u); do
  [ -e "$f" ] && echo "  存在: $f" || echo "  缺失: $f"
done

echo
echo "########## 4. controller 是否真的在跑 ##########"
echo "--- POST https /refresh_all_workers ---"
curl -sk -m 8 -X POST https://127.0.0.1:20401/refresh_all_workers | head -c 100
echo
echo "--- POST https /list_models ---"
curl -sk -m 8 -X POST https://127.0.0.1:20401/list_models | head -c 400
echo
echo "--- GET https /workers ---"
curl -sk -m 8 -X POST https://127.0.0.1:20401/worker_get_status 2>/dev/null | head -c 300
echo
echo "--- 对比 http ---"
curl -s -m 8 -X POST http://127.0.0.1:20401/list_models 2>&1 | head -c 200
echo

echo
echo "########## 5. 代码里所有用 http:// 拼内部地址的地方 ##########"
grep -rn 'f"http://{host}\|"http://" *+\|http://{.*port' --include="*.py" server/ configs/ 2>/dev/null | head -10

echo
echo "########## 6. 这些错误影响哪些接口 ##########"
echo "--- fastchat openai_api_server 里所有 fetch_remote 调用点 ---"
grep -n "fetch_remote" /root/anaconda3/envs/recovery/lib/python3.8/site-packages/fastchat/serve/openai_api_server.py 2>/dev/null | head -10

echo
echo "########## 7. 服务实际业务接口测试 ##########"
for ep in /v1/models /v1/chat/completions; do
  printf "  %-26s " "$ep"
  curl -sk -o /dev/null -w "HTTP %{http_code}\n" -m 10 https://127.0.0.1:20400$ep
done
