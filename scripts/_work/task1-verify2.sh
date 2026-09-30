#!/bin/bash
echo "===== [A] 容器内 resolv.conf ====="
docker exec wxq-prometheus cat /etc/resolv.conf
echo
echo "===== [B] 用真实解析器验证服务别名(DNS) ====="
for h in victoria-metrics alertmanager prometheus-alert grafana otel-collector blackbox-exporter process-exporter; do
  ip=$(docker exec wxq-prometheus getent hosts "$h" 2>/dev/null | awk '{print $1}' | head -1)
  [ -z "$ip" ] && ip=$(docker exec wxq-prometheus nslookup "$h" 2>/dev/null | awk '/^Address: /{print $2; exit}')
  printf '  %-20s -> %s\n' "$h" "${ip:-<未解析>}"
done
echo
echo "===== [C] 用真实解析器验证端口可达性(TCP) ====="
for hp in victoria-metrics:8428 alertmanager:9093 prometheus-alert:8080; do
  h=${hp%%:*}; p=${hp##*:}
  if docker exec wxq-prometheus getent hosts "$h" >/dev/null 2>&1; then
    printf '  %-28s DNS=OK ' "$hp"
  else
    printf '  %-28s DNS=FAIL ' "$hp"
  fi
  # busybox nc 可用则测端口
  if docker exec wxq-prometheus sh -c "nc -z -w 3 $h $p" 2>/dev/null; then echo "TCP=OK"; else echo "TCP=(nc不可用或不通)"; fi
done
echo
echo "===== [D] 决定性证据: 本地 remote_write 到 VM 是否真的在送 ====="
curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_samples_total' | python3 -m json.tool
echo "--- 5 秒后再看一次, 数值应增长:"
sleep 5
curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];[print(' ',x['metric'].get('url'),x['value'][1]) for x in r]"
echo
echo "--- 失败计数(应为 0 或不增长):"
curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_failed_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];[print(' ',x['metric'].get('url'),x['value'][1]) for x in r]" 2>&1
echo
echo "===== [E] 到 VM 送数是否让 VM 时序增长 ====="
curl -s 'http://10.100.10.29:8428/api/v1/query?query=count(count by(__name__)({__name__=~\".+\"}))' 2>&1 | head -c 300; echo
echo
echo "===== [F] Alertmanager 侧: 是否收到 plant01 prometheus 的告警 ====="
docker exec wxq-prometheus wget -qO- --timeout=5 http://alertmanager:9093/api/v2/status 2>&1 | head -c 200; echo
echo
echo "===== [G] 重建后容器 labels(compose 标签是否丢失) ====="
docker inspect wxq-prometheus --format '{{json .Config.Labels}}' | python3 -c "import sys,json;d=json.load(sys.stdin);print(' compose相关标签:', [k for k in d if 'compose' in k] or '(已丢失 — 因 compose 文件缺失, 用 docker run 重建)')"
echo "--- 数据卷/网络归属仍正确?"
docker inspect wxq-prometheus --format '{{range .Mounts}}{{.Type}} {{.Name}} -> {{.Destination}}{{"\n"}}{{end}}'
echo
echo "===== [H] 接收端安全性确认(仅新增 /api/v1/write, 未开放其他) ====="
for p in /api/v1/admin/tsdb/delete_series /api/v1/status/config; do
  printf '  %-40s HTTP %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://10.100.10.29:9091$p)"
done
