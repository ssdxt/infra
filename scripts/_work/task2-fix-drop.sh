#!/bin/bash
# 修正 drop 规则: 若 .*_bucket 仍不生效, 自动回退到"显式指标名 alternation"
export KUBECONFIG=/etc/kubernetes/admin.conf
NS=monitoring; PROM=prometheus-stack-kube-prom-prometheus; CP=prometheus-$PROM-0
P=http://10.100.10.29:9091

apply() {
  kubectl -n $NS patch prometheus $PROM --type merge --patch-file "$1" >/dev/null 2>&1
  return $?
}
bcount() { curl -s --get "$P/api/v1/query" --data-urlencode 'query=count({__name__=~".*_bucket",job="apiserver"})' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else '0')"; }

echo "===== 变更前 apiserver 侧 bucket 序列数(plant01) ====="
echo "  count = $(bcount)"
echo
echo "===== 应用变体 A: regex='.*_bucket' ====="
apply /tmp/remote-write-patch2.yaml && echo "  patch 已应用" || { echo "  patch 失败"; exit 1; }
echo "  等待 config-reloader 热加载 + 数据生效(60s)..."
sleep 60
echo "  部署后 apiserver bucket 序列数 = $(bcount)"
echo
echo "  --- 再等 60s 复测(排除 WAL 重放残留) ---"
sleep 60
B2=$(bcount)
echo "  复测 = $B2"
echo
# 判定: 若 bucket 仍 > 1000 且最新样本时间在推进 => 变体 A 也失败
LAG=$(curl -s --get "$P/api/v1/query" --data-urlencode 'query=now() - max(timestamp({__name__=~".*_bucket",job="apiserver"}))' | python3 -c "
import sys,json
r=json.load(sys.stdin)['data']['result']
print(r[0]['value'][1] if r else 'NA')")
echo "  bucket 最新样本滞后 now = $LAG 秒  (小于 90 => 仍在推送, 变体A 失败)"
echo
if [ "$LAG" != "NA" ] && python3 -c "import sys; sys.exit(0 if float('$LAG') < 90 else 1)"; then
  echo "===== 变体 A 失败, 回退到变体 B: 显式指标名 alternation ====="
  # 从 plant01 取实际存在的 bucket 指标名, 拼成 alternation(只取 apiserver/kubelet 等大头的)
  NAMES=$(curl -s --get "$P/api/v1/label/__name__/values" --data-urlencode 'match[]={__name__=~".*_bucket",job="apiserver"}' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
print('|'.join(d))")
  echo "  指标名个数: $(echo "$NAMES" | tr '|' '\n' | wc -l)"
  {
    echo "spec:"
    echo "  remoteWrite:"
    echo "  - url: http://10.100.10.29:9091/api/v1/write"
    echo "    remoteTimeout: 60s"
    echo "    writeRelabelConfigs:"
    echo "    - action: keep"
    echo "      regex: (kubelet|node-exporter|kube-state-metrics|apiserver|etcd|kube-scheduler|kube-controller-manager|coredns|prometheus-stack-kube-prom-prometheus|prometheus-stack-kube-prom-alertmanager|prometheus-stack-kube-prom-operator)"
    echo "      sourceLabels: [job]"
    echo "    - action: drop"
    echo "      regex: '($NAMES)'"
    echo "      sourceLabels: [__name__]"
    echo "    - action: drop"
    echo "      regex: 'kubernetes_feature_enabled'"
    echo "      sourceLabels: [__name__]"
  } > /tmp/remote-write-patch3.yaml
  echo "  --- patch3 预览(前 20 行) ---"
  head -20 /tmp/remote-write-patch3.yaml
  apply /tmp/remote-write-patch3.yaml && echo "  变体 B 已应用" || echo "  变体 B 应用失败"
  sleep 90
  echo "  变体 B 后 apiserver bucket 序列数 = $(bcount)"
else
  echo "===== 变体 A 成功: bucket 已停止推送 ====="
fi
echo
echo "===== 最终 remote_write 配置 ====="
kubectl -n $NS get prometheus $PROM -o jsonpath='{.spec.remoteWrite}' | python3 -m json.tool
