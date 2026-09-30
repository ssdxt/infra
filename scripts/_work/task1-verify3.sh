#!/bin/bash
echo "===== [1] 容器内到底有哪些网络工具 ====="
for t in getent nslookup wget curl nc ping busybox; do
  printf '  %-8s %s\n' "$t" "$(docker exec wxq-prometheus sh -c "command -v $t" 2>/dev/null || echo '(无)')"
done
echo "  --- busybox applets:"
docker exec wxq-prometheus busybox --list 2>/dev/null | grep -E '^(nslookup|wget|nc|ping|getent)$' | tr '\n' ' '; echo
echo
echo "===== [2] 真实 DNS 解析(用 busybox nslookup) ====="
for h in victoria-metrics alertmanager prometheus-alert; do
  echo "  --- $h"
  docker exec wxq-prometheus nslookup "$h" 2>&1 | sed 's/^/      /'
done
echo
echo "===== [3] 决定性证据: remote write 成功/失败计数 ====="
for m in prometheus_remote_storage_succeeded_samples_total prometheus_remote_storage_failed_samples_total prometheus_remote_storage_samples_total prometheus_remote_storage_samples_pending prometheus_remote_storage_samples_dropped_total prometheus_remote_storage_shards; do
  printf '  %-52s ' "$m"
  curl -s "http://10.100.10.29:9091/api/v1/query?query=$m" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(', '.join(x['value'][1] for x in r) if r else '(无数据)')
except Exception as e: print('ERR',e)"
done
echo
echo "===== [4] 等 10 秒再采样, 确认 succeeded 在增长 / failed 为 0 ====="
A=$(curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_succeeded_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'NA')")
FA=$(curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_failed_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else '0')")
sleep 10
B=$(curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_succeeded_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else 'NA')")
FB=$(curl -s 'http://10.100.10.29:9091/api/v1/query?query=prometheus_remote_storage_failed_samples_total' | python3 -c "import sys,json;r=json.load(sys.stdin)['data']['result'];print(r[0]['value'][1] if r else '0')")
echo "  succeeded: $A -> $B   (差值 $(( ${B%.*} - ${A%.*} )))"
echo "  failed:    $FA -> $FB"
echo
echo "===== [5] VM 侧是否真的收到 plant01 的数据(在 VM 上查 prometheus_remote_storage_samples_total) ====="
curl -s 'http://10.100.10.29:8428/api/v1/query?query=prometheus_remote_storage_samples_total' | head -c 500; echo
echo
echo "===== [6] Alertmanager 可达性(用 /-/healthy 从宿主机+容器) ====="
echo -n "  宿主机 -> alertmanager:9093 : HTTP "; curl -s -o /dev/null -w '%{http_code}\n' --max-time 5 http://10.100.10.29:9093/-/healthy
echo "  Alertmanager 已收到的告警数(通过 host 端口):"
curl -s --max-time 5 'http://10.100.10.29:9093/api/v2/alerts' | python3 -c "import sys,json;d=json.load(sys.stdin);print('   ',len(d),'条');[print('     -',a['labels'].get('alertname'),a['labels'].get('instance_name')) for a in d[:8]]" 2>&1
