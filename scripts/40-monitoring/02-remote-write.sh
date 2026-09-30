#!/bin/bash
# 把本集群 Prometheus 数据推送到 plant01（10.100.10.29:9091）
# 前置: plant01 Prometheus 需带 --web.enable-remote-write-receiver 参数重启
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
PLANT01=10.100.10.29:9091

echo "=== [1/2] 检查 plant01 接收端是否就绪 ==="
if curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$PLANT01/api/v1/status/runtimeinfo" | grep -q 200; then
  echo "  plant01 Prometheus 可达"
else
  echo "  !! plant01 Prometheus 不可达，检查地址/网络"
fi
echo "  提示: 若推送报 404，需要在 plant01 上加启动参数 --web.enable-remote-write-receiver 并重启容器"

echo ""
echo "=== [2/2] 给本集群 Prometheus 加 remoteWrite ==="
cat > /tmp/remote-write-patch.yaml <<YAML
spec:
  remoteWrite:
  - url: http://$PLANT01/api/v1/write
    remoteTimeout: 60s
    writeRelabelConfigs:
    - action: keep
      regex: (kubelet|node-exporter|kube-state-metrics|apiserver|etcd|kube-scheduler|kube-controller-manager|coredns|prometheus)
      sourceLabels: [job]
YAML
kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus \
  --type merge --patch-file /tmp/remote-write-patch.yaml

echo "  已写入。验证（1~2 分钟后）:"
echo "    在 plant01 Grafana 查询 up{cluster=\"wxq\"} 或看 job 列表"
echo "    本集群检查: kubectl -n monitoring logs prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus | grep -i remotewrite"

# ===== [追加] helm upgrade 后恢复 remoteWrite 完整配置（含 queueConfig）=====
# 来源：kubectl patch 的最终态快照。helm upgrade 会用 values 重建 CR 丢掉手工 patch，
#       因此每次 helm upgrade prometheus-stack 之后必须重跑本脚本。
kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus --type=merge \
  -p "$(cat /data1/ssdxt/monitoring/remote-write-desired.json)" >/dev/null \
  && echo "remoteWrite 已恢复（含 queueConfig）"
