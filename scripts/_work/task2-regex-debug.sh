#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; CP=prometheus-prometheus-stack-kube-prom-prometheus-0

echo "===== [1] 集群侧时钟(校验 plant01 时间戳可信) ====="
date -u '+  control-01 : %H:%M:%S UTC (epoch=%s)'

echo
echo "===== [2] operator 生成的 remote_write 原文(逐字) ====="
kubectl -n $NS exec $CP -c prometheus -- cat /etc/prometheus/config_out/prometheus.env.yaml 2>/dev/null \
  | sed -n '/^remote_write:/,/^[a-z]/p' | cat -A | sed -n '1,40p'

echo
echo "===== [3] 用 promtool 验证 '该配置是否真的会丢弃 _bucket' ====="
# 构造一个最小配置, 用 promtool 的 relabel 调试能力无法直接测 remote_write,
# 改为直接在集群 Prometheus 上做对照: 查被 drop 与未被 drop 的指标
echo "  --- 集群侧 job=apiserver 下 __name__ 以 _bucket 结尾的指标名(前 5 个):"
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/label/__name__/values?match%5B%5D=%7Bjob%3D%22apiserver%22%7D' 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
b=[x for x in d if x.endswith('_bucket')]
print('    共 %d 个 _bucket 指标名, 例如: %s' % (len(b), b[:5]))
print('    repr(第一个) =', repr(b[0]) if b else '无')
"

echo
echo "===== [4] 决定性对照: plant01 上桶样本的\"新鲜度\"(距 now 多少秒) ====="
NOW=$(date +%s)
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=now() - max(timestamp(apiserver_request_duration_seconds_bucket))' \
  | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  桶指标滞后 now = %s 秒' % (r[0]['value'][1] if r else '无数据'))
"
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=now() - max(timestamp(node_cpu_seconds_total))' \
  | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print('  对照(node_cpu)滞后 now = %s 秒' % (r[0]['value'][1] if r else '无数据'))
"

echo
echo "===== [5] 试判定: 桶是否由 WAL 重放补发 ====="
echo "  查 plant01 上桶指标 5 分钟内的样本密度(应已无新样本):"
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=count_over_time(apiserver_request_duration_seconds_bucket[2m])' \
  | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
if r:
    vals=[int(float(x['value'][1])) for x in r]
    print('    有 %d 条序列, 2m 内样本数 min=%d max=%d' % (len(r),min(vals),max(vals)))
else:
    print('    无数据')
"
curl -s --get 'http://10.100.10.29:9091/api/v1/query' \
  --data-urlencode 'query=count_over_time(node_cpu_seconds_total[2m])' \
  | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
if r:
    vals=[int(float(x['value'][1])) for x in r]
    print('    对照 node_cpu: %d 条序列, 2m 样本数 min=%d max=%d' % (len(r),min(vals),max(vals)))
else: print('    无数据')
"
