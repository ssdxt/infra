#!/bin/bash
# 判定 _bucket$ drop 是否真的生效: 看"最新样本时间"是否已冻结
P=http://10.100.10.29:9091
run() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1"; }
show() { python3 -c "
import sys,json
try:
  j=json.load(sys.stdin)
  r=j['data']['result']
  if not r: print('  无数据'); raise SystemExit
  print('  %s' % r[0]['value'][1])
except SystemExit: pass
except Exception as e: print('  ERR', e)
"; }

echo "===== 现在 ====="
date -u '+  %H:%M:%S UTC  epoch=%s'
echo
echo "===== [关键] 连续三次采样, 间隔 20 秒, 看桶指标最新时间戳是否在推进 ====="
for i in 1 2 3; do
  printf '  第%d次 (%s):\n' "$i" "$(date -u '+%H:%M:%S')"
  printf '    bucket  max(timestamp) = '; run 'max(timestamp(apiserver_request_duration_seconds_bucket))' | show
  printf '    total   max(timestamp) = '; run 'max(timestamp(apiserver_request_total))' | show
  printf '    nodecpu max(timestamp) = '; run 'max(timestamp(node_cpu_seconds_total))' | show
  [ $i -lt 3 ] && sleep 20
done
echo
echo "  解读: total/nodecpu 每次推进 ~20s = 正常推送中;"
echo "        若 bucket 也同步推进 => drop 未生效;"
echo "        若 bucket 停在某一点不动 => drop 已生效, 残留是历史序列。"
echo
echo "===== 近 30 秒内桶是否还有新样本(30s < 采集间隔 30s, 有则需要恰好命中) ====="
printf '  近 45 秒有值的 bucket 序列数 = '; run 'count(last_over_time(apiserver_request_duration_seconds_bucket[45s]))' | show
printf '  近 45 秒有值的 total  序列数 = '; run 'count(last_over_time(apiserver_request_total[45s]))' | show
echo
echo "===== plant01 上仍存在的 _bucket 指标名(前 12) ====="
run 'count by(__name__)({__name__=~".*_bucket"})' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  共 %d 个 _bucket 指标名' % len(r))
for x in sorted(r, key=lambda z:-float(z['value'][1]))[:12]:
    print('    %-58s %s' % (x['metric']['__name__'], x['value'][1]))
"
