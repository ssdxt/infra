#!/bin/bash
# 判定第 4 条 drop 是否生效: 连续采样看 max(timestamp) 是否【冻结】
P=http://10.100.10.29:9091
g() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1" | python3 -c "
import sys,json
try:
  r=json.load(sys.stdin)['data']['result']
  print(r[0]['value'][1] if r else '0')
except Exception as e: print('ERR')"; }
h() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1" | python3 -c "
import sys,json,datetime
try:
  r=json.load(sys.stdin)['data']['result']
  if not r: print('0'); raise SystemExit
  v=float(r[0]['value'][1])
  print('%s (=%s)' % (r[0]['value'][1], datetime.datetime.utcfromtimestamp(v).strftime('%H:%M:%S')))
except SystemExit: pass
except Exception as e: print('ERR')"; }

echo "现在(UTC): $(date -u '+%H:%M:%S')  epoch=$(date +%s)"
echo
for i in 1 2 3; do
  echo "--- 第 $i 次采样 ($(date -u '+%H:%M:%S')) ---"
  for m in ALERTS count:up1; do
    printf '  %-12s max(ts) = %s\n' "$m" "$(h "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
  done
  for m in apiserver_request_total node_cpu_seconds_total; do
    printf '  %-26s max(ts) = %s  (对照, 应推进)\n' "$m" "$(h "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"
  done
  [ $i -lt 3 ] && sleep 30
done
echo
echo "解读: ALERTS/count:up1 的时间戳若【不再变化】=> drop 已生效,"
echo "      剩下的报错只是配置重载时 WAL 重放旧样本造成的, 会随重放结束而停止。"
echo
echo "===== 最近 5 分钟错误是否已停 ====="
echo -n "  近 5 分钟 out-of-order 条数 = "
docker logs wxq-prometheus --since 5m 2>&1 | grep -c 'Out of order sample'
echo -n "  近 2 分钟 out-of-order 条数 = "
docker logs wxq-prometheus --since 2m 2>&1 | grep -c 'Out of order sample'
echo
echo "  最近 3 条错误时间:"
docker logs wxq-prometheus --since 10m 2>&1 | grep 'Out of order sample' | tail -3 | grep -o 'time=[^ ]*'
