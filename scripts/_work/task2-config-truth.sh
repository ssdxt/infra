#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; CP=prometheus-prometheus-stack-kube-prom-prometheus-0

echo "===== [1] 从 ConfigMap/Secret 直读 operator 渲染的 remote_write(不经过 exec) ====="
CM=$(kubectl -n $NS get prometheus $CP -o jsonpath='{.spec.remoteWrite}' >/dev/null 2>&1; echo ok)
kubectl -n $NS get secret prometheus-$CP -o jsonpath='{.data.prometheus\.yaml\.gz}' 2>/dev/null | base64 -d 2>/dev/null | gunzip 2>/dev/null | sed -n '/^remote_write:/,/^[a-z_]/p' > /tmp/rw_rendered.txt
if [ -s /tmp/rw_rendered.txt ]; then
  echo "  --- 渲染结果(逐字, cat -A 显示行尾) ---"
  cat -A /tmp/rw_rendered.txt | head -40
else
  echo "  (该路径取不到, 改用 config_out)"
  kubectl -n $NS exec $CP -c prometheus -- sh -c 'grep -A14 "^remote_write:" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1 | head -30
fi

echo
echo "===== [2] 实际生效的 config_out 中 drop 规则的精确字节 ====="
kubectl -n $NS exec $CP -c prometheus -- sh -c "awk '/^remote_write:/,/^[a-z_]+:/' /etc/prometheus/config_out/prometheus.env.yaml | grep -n -A3 'action: drop'" 2>&1

echo
echo "===== [3] 直接看 plant01 是否完全收不到 kubernetes_feature_enabled(验证 drop 能力) ====="
for m in kubernetes_feature_enabled apiserver_request_duration_seconds_bucket; do
  n=$(curl -s --get 'http://10.100.10.29:9091/api/v1/query' --data-urlencode "query=count($m)" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')")
  printf '  count(%-46s) = %s\n' "$m" "$n"
done

echo
echo "===== [4] plant01 上 _bucket 指标名完整清单(用于精确 drop) ====="
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=count by(__name__)({__name__=~".*_bucket"})' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
rows=sorted(((x['metric']['__name__'], int(float(x['value'][1]))) for x in r), key=lambda z:-z[1])
print('  共 %d 个 _bucket 指标名, 合计 %d 序列' % (len(rows), sum(c for _,c in rows)))
print('  Top15:')
for n,c in rows[:15]: print('    %-60s %d' % (n,c))
print()
print('  全部名字(逗号分隔, 供拼 alternation 用):')
print('  ' + '|'.join(n for n,_ in rows))
"
