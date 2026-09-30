#!/bin/bash
# 安装反向心跳：plant01 每 5 分钟检查集群 Watchdog 是否存活，丢了就发钉钉
set -u
DIR=/data1/apps/wxq-plant01-monitor/scripts
mkdir -p $DIR

# 从 alertmanager.yml 里提取 PrometheusAlert 的钉钉 webhook 地址（复用现有接收器）
HOOK=$(grep -oE 'http://[^"'"'"' ]*prometheusalert[^"'"'"' ]*' /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml | head -1)
[ -z "$HOOK" ] && { echo "❌ 没找到 prometheusalert webhook 地址"; exit 1; }
echo "钉钉通道: $HOOK"

cat > $DIR/watchdog-heartbeat.sh <<EOF
#!/bin/bash
# 反向心跳：Watchdog 应该永远 firing；查不到 = 告警链路挂了 → 发钉钉
AM="http://localhost:9093/api/v2/alerts?active=true"
HOOK="$HOOK"
STATE=/var/log/watchdog-heartbeat.last
COOLDOWN=1800
NOW=\$(date +%s)
cnt=\$(curl -s --max-time 10 "\$AM" 2>/dev/null | grep -c '"Watchdog"')
curl_rc=\$?
if [ \$curl_rc -ne 0 ]; then echo "\$(date '+%F %T') Alertmanager API 不可达"; fi
if [ "\$cnt" -ge 1 ]; then
  rm -f \$STATE; exit 0   # 心跳正常
fi
last=\$(cat \$STATE 2>/dev/null || echo 0)
[ \$((NOW-last)) -lt \$COOLDOWN ] && exit 0   # 30 分钟冷却，防轰炸
echo \$NOW > \$STATE
curl -s --max-time 10 -X POST "\$HOOK" -H 'Content-Type: application/json' -d '{
  "alerts":[{"status":"firing","labels":{
      "alertname":"AlertPipelineHeartbeatLost","severity":"critical","instance":"plant01-watchdog-probe"},
    "annotations":{
      "summary":"⚠️ 告警链路心跳丢失：Watchdog 已停止触发",
      "description":"plant01 反向心跳探针在 Alertmanager 中找不到 Watchdog 活跃告警。可能原因：集群 Prometheus/Alertmanager 故障、通知链路断、网络中断。请检查监控栈！"}}],
  "commonLabels":{"alertname":"AlertPipelineHeartbeatLost"}
}' >/dev/null
echo "\$(date '+%F %T') Watchdog 丢失，已发钉钉告警"
EOF
chmod +x $DIR/watchdog-heartbeat.sh
echo "✅ 检查脚本: $DIR/watchdog-heartbeat.sh"

cat > /etc/cron.d/watchdog-heartbeat <<EOF
# 反向心跳：每 5 分钟确认告警链路的 Watchdog 还活着
*/5 * * * * root $DIR/watchdog-heartbeat.sh >> /var/log/watchdog-heartbeat.log 2>&1
EOF
chmod 644 /etc/cron.d/watchdog-heartbeat
echo "✅ cron: /etc/cron.d/watchdog-heartbeat (*/5 * * * *)"

echo ""
echo "--- 正常路径自测（Watchdog 现在活着，应静默退出）"
bash $DIR/watchdog-heartbeat.sh && echo "  ✅ 正常路径 OK（无输出=心跳正常）"

echo "--- 故障路径演练（TEST=1：用测试标题发一条真实钉钉）"
if [ "${TEST:-0}" = "1" ]; then
  curl -s --max-time 10 -X POST "$HOOK" -H 'Content-Type: application/json' -d '{
    "alerts":[{"status":"firing","labels":{"alertname":"HeartbeatProbeTest","severity":"info","instance":"plant01-watchdog-probe"},
      "annotations":{"summary":"【测试】反向心跳链路验证（可忽略，5 分钟后自动恢复提示）"}}]}' >/dev/null \
    && echo "  ✅ 测试消息已发钉钉（收到 = 通知链路通）"
fi
echo ""
echo "安装完成。日志: /var/log/watchdog-heartbeat.log"