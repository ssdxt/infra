#!/bin/bash
echo "===== [1] Alertmanager receiver 实际指向 ====="
grep -nE 'receiver:|url:|webhook_configs|matchers|name:' \
  /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml | sed 's/^/  /'
echo
echo "===== [2] 各 receiver 的渠道类型(type=)=\"dd 钉钉 / fs 飞书 / wx 企微\" ====="
grep -oE 'type=(dd|fs|wx)' /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml | sort | uniq -c
echo "  说明: type= 的值决定 PrometheusAlert 往哪个渠道发"
echo
echo "===== [3] 目标 webhook 域名 ====="
grep -oE 'url=https%3A%2F%2F[^&]*' /data1/apps/wxq-plant01-monitor/alertmanager/alertmanager.yml \
  | sed 's/url=//' | python3 -c "
import sys,urllib.parse
for l in sys.stdin:
    print('   ', urllib.parse.unquote(l.strip())[:80])
"
echo
echo "===== [4] PrometheusAlert(8280) 配置里的渠道开关与地址 ====="
grep -nE '^(PA_OPEN|PA_DINGDING|PA_FEISHU|PA_WECHAT|PA_WORKWEIXIN|PA_TITLE)|ddurl|fsurl|wxurl|DingDing|Feishu|WeChat' \
  /data1/apps/wxq-plant01-monitor/prometheusalert/app.conf | head -40 | sed 's/^/  /'
echo
echo "===== [5] PrometheusAlert 容器环境变量 ====="
docker inspect wxq-prometheusalert --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -iE 'PA_|FEISHU|DING|WECHAT|WX' | sed 's/^/  /'
echo
echo "===== [6] PrometheusAlert 服务是否健康 ====="
echo -n "  http://127.0.0.1:8280/ HTTP "
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 http://127.0.0.1:8280/
echo
echo "===== [7] Alertmanager -> PrometheusAlert 连通性(容器内解析) ====="
docker exec wxq-alertmanager wget -qO- --timeout=8 http://prometheus-alert:8080/ 2>&1 | head -c 120; echo
echo
echo "===== [8] PrometheusAlert 最近日志(是否真的发出过告警) ====="
docker logs wxq-prometheusalert --tail 30 2>&1 | tail -20
