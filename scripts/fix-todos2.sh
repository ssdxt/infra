#!/bin/bash
export KUBECONFIG=/etc/kubernetes/admin.conf
echo "== A. adapter CPU limit（先查真实容器名）=="
CN=$(kubectl -n monitoring get deploy prometheus-adapter -o jsonpath='{.spec.template.spec.containers[0].name}')
echo "  容器名: $CN"
kubectl -n monitoring set resources deploy/prometheus-adapter --containers=$CN \
  --limits=cpu=1 --requests=cpu=250m 2>&1 | tail -1
kubectl -n monitoring rollout status deploy/prometheus-adapter --timeout=180s 2>&1 | tail -1
sleep 20
echo -n "  限流速率（期望≈0）: "
kubectl -n monitoring exec prometheus-prometheus-stack-kube-prom-prometheus-0 -c prometheus -- \
  wget -qO- 'http://localhost:9090/api/v1/query?query=sum(rate(container_cpu_cfs_throttled_periods_total%7Bpod%3D~%22prometheus-adapter.*%22%7D%5B2m%5D))' 2>/dev/null | head -c 130; echo

echo ""
echo "== B. remoteWrite 固化：快照 CR 当前状态 + 追加到 02 脚本 =="
mkdir -p /data1/ssdxt/monitoring/backup
kubectl -n monitoring get prometheus prometheus-stack-kube-prom-prometheus -o json \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
rw = d["spec"].get("remoteWrite", [])
open("/data1/ssdxt/monitoring/remote-write-desired.json","w").write(json.dumps({"spec":{"remoteWrite":rw}}, ensure_ascii=False, indent=1))
print("  已快照 remoteWrite（含 queueConfig + relabel），数组长度:", len(rw))
for i, x in enumerate(rw):
    qc = x.get("queueConfig")
    print("   [%d] url=%s queueConfig=%s" % (i, x.get("url"), "有" if qc else "无"))
'
if ! grep -q "remote-write-desired.json" /data1/ssdxt/monitoring/02-remote-write.sh 2>/dev/null; then
  cat >> /data1/ssdxt/monitoring/02-remote-write.sh <<'EOF'

# ===== [追加] helm upgrade 后恢复 remoteWrite 完整配置（含 queueConfig）=====
# 来源：kubectl patch 的最终态快照。helm upgrade 会用 values 重建 CR 丢掉手工 patch，
#       因此每次 helm upgrade prometheus-stack 之后必须重跑本脚本。
kubectl -n monitoring patch prometheus prometheus-stack-kube-prom-prometheus --type=merge \
  -p "$(cat /data1/ssdxt/monitoring/remote-write-desired.json)" >/dev/null \
  && echo "remoteWrite 已恢复（含 queueConfig）"
EOF
  echo "  ✅ 已把恢复步骤追加到 02-remote-write.sh"
else
  echo "  ✅ 02 脚本已包含恢复步骤"
fi
echo "  规矩：helm upgrade prometheus-stack 后 → 重跑 bash /data1/ssdxt/monitoring/02-remote-write.sh"