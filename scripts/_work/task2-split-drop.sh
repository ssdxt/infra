#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus; CP=prometheus-$PROM-0
P=http://10.100.10.29:9091

echo "===== [1] dry-run ====="
kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch4.yaml --dry-run=server >/dev/null 2>&1 \
  && echo "  ✅ 通过" || { echo "  ❌ 失败"; exit 1; }

echo
echo "===== [2] 应用 ====="
kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch4.yaml

echo
echo "===== [3] 等热加载(最多 180s, 以渲染出 7 条规则为准) ====="
for i in $(seq 1 18); do
  N=$(kubectl -n $NS exec $CP -c prometheus -- sh -c \
       'sed -n "/^remote_write:/,/^[a-z_]*:/p" /etc/prometheus/config_out/prometheus.env.yaml | grep -c "action:"' 2>/dev/null)
  echo "  [$((i*10))s] remote_write 内 action 条数 = $N (目标 8: 1 keep + 7 drop)"
  [ "$N" = "8" ] && { echo "  ✅ 已渲染"; break; }
  sleep 10
done

echo
echo "===== [4] 渲染结果 ====="
kubectl -n $NS exec $CP -c prometheus -- sh -c \
  'sed -n "/^remote_write:/,/^[a-z_]*:/p" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1

echo
echo "===== [5] 等待生效后判定: ALERTS/count:up1 时间戳是否冻结 ====="
sleep 90
g() { curl -s --get "$P/api/v1/query" --data-urlencode "query=$1" | python3 -c "
import sys,json,datetime
try:
  r=json.load(sys.stdin)['data']['result']
  if not r: print('无数据'); raise SystemExit
  v=float(r[0]['value'][1])
  print('%s (=%s)' % (r[0]['value'][1], datetime.datetime.utcfromtimestamp(v).strftime('%H:%M:%S')))
except SystemExit: pass
except Exception as e: print('ERR')"; }
echo "  第1次 $(date -u '+%H:%M:%S')"
for m in ALERTS count:up1; do printf '    %-12s max(ts) = %s\n' "$m" "$(g "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"; done
printf '    %-12s max(ts) = %s  (对照)\n' "apiserver_request_total" "$(g 'max(timestamp(apiserver_request_total{prometheus=~"monitoring/.*"}))')"
sleep 45
echo "  第2次 $(date -u '+%H:%M:%S')"
for m in ALERTS count:up1; do printf '    %-12s max(ts) = %s\n' "$m" "$(g "max(timestamp($m{prometheus=~\"monitoring/.*\"}))")"; done
printf '    %-12s max(ts) = %s  (对照)\n' "apiserver_request_total" "$(g 'max(timestamp(apiserver_request_total{prometheus=~"monitoring/.*"}))')"
