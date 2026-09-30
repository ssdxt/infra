#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; CP=prometheus-prometheus-stack-kube-prom-prometheus-0
P=http://10.100.10.29:9091

echo "########## 一、集群侧: 这些指标在 remote_write 前是否存在 ##########"
kubectl -n $NS exec $CP -c prometheus -- wget -qO- 'http://localhost:9090/api/v1/label/__name__/values' 2>/dev/null | python3 -c "
import sys,json
d=set(json.load(sys.stdin)['data'])
tests={
 'kubernetes_feature_enabled':'rule3 目标',
 'apiserver_request_duration_seconds_bucket':'rule2 目标',
 'apiserver_request_total':'对照',
 'etcd_request_duration_seconds_bucket':'rule2 目标',
 'node_cpu_seconds_total':'对照',
}
print('  指标名在【集群 Prometheus】中是否存在:')
for k,v in tests.items():
    print('    %-52s %-9s (%s)' % (k, '存在' if k in d else '不存在', v))
print()
print('  集群侧 job=apiserver 下 _bucket 名称数: ', len([x for x in d if x.endswith('_bucket')]))
"

echo
echo "########## 二、plant01 侧: 同样的指标名是否存在 ##########"
for m in kubernetes_feature_enabled apiserver_request_duration_seconds_bucket apiserver_request_total etcd_request_duration_seconds_bucket node_cpu_seconds_total; do
  n=$(curl -s --get "$P/api/v1/query" --data-urlencode "query=count($m)" | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')")
  printf '  %-52s %s\n' "$m" "$n"
done

echo
echo "########## 三、判定 ##########"
echo "  · kubernetes_feature_enabled 在集群存在 / 在 plant01 为 0  => rule3 生效"
echo "  · apiserver_*_bucket 两侧都存在且 plant01 有新样本       => rule2 未生效"
echo
echo "########## 四、渲染配置的精确字节(control-01 本地) ##########"
kubectl -n $NS exec $CP -c prometheus -- sh -c 'awk "/^remote_write:/,/^[a-z_]+\$/" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1 | head -30
echo
echo "  --- 用 cat -A 看不可见字符 ---"
kubectl -n $NS exec $CP -c prometheus -- sh -c 'awk "/^remote_write:/,/^[a-z_]+\$/" /etc/prometheus/config_out/prometheus.env.yaml' 2>&1 | cat -A | head -30
