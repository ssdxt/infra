#!/bin/bash
# 任务2: 给集群 Prometheus 加 remoteWrite —— 先 dry-run 校验, 再实打
export KUBECONFIG=/etc/kubernetes/admin.conf
set -u
PROM=prometheus-stack-kube-prom-prometheus
NS=monitoring

echo "===== [0] 变更前: 备份 CRD 现状 ====="
mkdir -p /data1/ssdxt/monitoring/backup
STAMP=$(date +%Y%m%d-%H%M%S)
kubectl -n $NS get prometheus $PROM -o yaml > /data1/ssdxt/monitoring/backup/prometheus-crd-$STAMP.yaml
echo "  已备份: /data1/ssdxt/monitoring/backup/prometheus-crd-$STAMP.yaml"
echo "  remoteWrite 现状: '$(kubectl -n $NS get prometheus $PROM -o jsonpath='{.spec.remoteWrite}')' (空=未配置)"
echo

echo "===== [1] 服务端 dry-run 校验 patch ====="
if kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch.yaml --dry-run=server -o jsonpath='{.spec.remoteWrite}' 2>&1; then
  echo
  echo "  ✅ dry-run 通过(CRD 接受该配置)"
else
  echo
  echo "  ❌ dry-run 失败 —— 不执行变更"
  exit 1
fi
echo

echo "===== [2] 正式应用 patch ====="
kubectl -n $NS patch prometheus $PROM --type merge --patch-file /tmp/remote-write-patch.yaml
echo
echo "--- 应用后 spec.remoteWrite:"
kubectl -n $NS get prometheus $PROM -o yaml | sed -n '/remoteWrite:/,/^[a-z]/p'
echo
echo "===== [3] 等待 operator 重建 Prometheus Pod(最多 300s) ====="
for i in $(seq 1 60); do
  READY=$(kubectl -n $NS get pod prometheus-$PROM-0 -o jsonpath='{.status.containerStatuses[*].ready}' 2>/dev/null)
  PHASE=$(kubectl -n $NS get pod prometheus-$PROM-0 -o jsonpath='{.status.phase}' 2>/dev/null)
  AGE=$(kubectl -n $NS get pod prometheus-$PROM-0 -o jsonpath='{.metadata.creationTimestamp}' 2>/dev/null)
  echo "  [$((i*5))s] phase=$PHASE ready=[$READY] created=$AGE"
  case "$READY" in
    "true true") echo "  ✅ Pod 就绪"; break ;;
  esac
  sleep 5
done
echo
echo "===== [4] 生成的 remote_write 配置(operator 渲染结果) ====="
for i in $(seq 1 24); do
  C=$(kubectl -n $NS exec prometheus-$PROM-0 -c prometheus -- cat /etc/prometheus/config_out/prometheus.env.yaml 2>/dev/null)
  if echo "$C" | grep -q 'remote_write'; then
    echo "$C" | sed -n '/^remote_write:/,/^[a-z_]*:/p' | head -60
    break
  fi
  echo "  [$((i*5))s] 等待 config_out 生成 remote_write..."
  sleep 5
done
