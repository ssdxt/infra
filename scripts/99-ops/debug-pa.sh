#!/bin/bash
HOOK=$(grep -oE 'http://localhost:8280[^"'"'"']*' /data1/apps/wxq-plant01-monitor/scripts/watchdog-heartbeat.sh | head -1)
echo "测试 POST 到: $HOOK"
echo "--- 响应（HTTP码 + 内容）"
curl -s --max-time 10 -w '\nHTTP=%{http_code}\n' -X POST "$HOOK" -H 'Content-Type: application/json' -d '{
  "alerts":[{"status":"firing","labels":{"alertname":"HeartbeatProbeTest","severity":"info","instance":"plant01-watchdog-probe"},
    "annotations":{"summary":"【测试】反向心跳链路验证，可忽略"}}],
  "commonLabels":{"alertname":"HeartbeatProbeTest"}
}'
echo ""
echo "--- PrometheusAlert 容器最近日志"
docker logs wxq-prometheusalert --since 2m 2>&1 | tail -5
echo ""
echo "--- 对照：alertmanager.yml 里 default 接收器的完整 url 定义"
grep -A6 "name: 'default'" /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml | head -8