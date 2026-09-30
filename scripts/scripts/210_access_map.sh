#!/bin/bash
echo '== 容器端口映射 =='
docker ps --format '{{.Names}} => {{.Ports}}' | grep -v '^.*=> *$' | sort
echo
echo '== 宿主监听端口 =='
ss -tlnp 2>/dev/null | awk 'NR==1 || /LISTEN/' | grep -vE '127.0.0.1|::1' | head -25
echo
echo '== 健康探测 =='
echo -n 'nginx :80 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:80/ 2>&1
echo -n 'nginx :8378 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:8378/ 2>&1
echo -n 'ai_server :8375 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:8375/ 2>&1
echo -n 'assistant :8366 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:8366/ 2>&1
echo -n 'parser :8010 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:8010/ 2>&1
echo -n 'img_service :18080 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:18080/ 2>&1
echo -n 'embedding :8021/v1/models => '; curl -s --max-time 5 http://localhost:8021/v1/models 2>&1 | head -c 80; echo
echo -n 'rerank :8022/v1/models => '; curl -s --max-time 5 http://localhost:8022/v1/models 2>&1 | head -c 80; echo
echo -n 'portainer :9001 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:9001/ 2>&1
echo -n 'minio :9090 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:9090/ 2>&1
echo -n 'milvus :9091 => '; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://localhost:9091/healthz 2>&1
