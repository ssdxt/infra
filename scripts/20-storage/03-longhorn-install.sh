#!/bin/bash
# 安装 Longhorn（用节点 /data1 做分布式存储，2 副本）
# 前提: 镜像已用 images/mirror.sh 搬完、节点已装 open-iscsi
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt
H=harbor.wuxing.local
CHART=$R/charts/longhorn-1.7.2.tgz
NS=longhorn-system

echo "=== [1/4] 节点前置：open-iscsi（Longhorn 用 iSCSI 提供块设备）==="
for ip in 10.100.10.10 10.100.10.14 10.100.10.19 10.100.10.33 10.100.10.34 10.100.10.39 10.100.10.41 10.100.10.44 10.100.10.45 10.100.10.46 10.100.10.47; do
  ssh -o BatchMode=yes root@$ip 'dpkg -l | grep -q "^ii  open-iscsi" || { apt-get update -qq; apt-get install -y -qq open-iscsi; }; systemctl enable --now iscsid >/dev/null 2>&1; echo ok' >/dev/null 2>&1 &
done
wait
echo "  完成"

echo "=== [2/4] 自动改写镜像为 Harbor ==="
python3 $R/tools/fix-chart-images.py $CHART longhorn $H /tmp/longhorn-values.yaml

echo "=== [3/4] 写自定义参数 ==="
cat > /tmp/longhorn-custom.yaml <<YAML
defaultSettings:
  defaultReplicaCount: 2
  defaultDataPath: /data1/longhorn
  # 100Mbps 网络下降低重建压力
  concurrentReplicaRebuildPerNodeLimit: 1
persistence:
  defaultClass: true
  defaultClassReplicaCount: 2
YAML

echo "=== [4/4] helm 安装 ==="
helm upgrade --install longhorn $CHART -n $NS --create-namespace \
  -f /tmp/longhorn-values.yaml -f /tmp/longhorn-custom.yaml --timeout 15m 2>&1 | tail -5

echo ""
echo "=== 验证（等 2~3 分钟）==="
echo "  kubectl -n longhorn-system get pods"
echo "  kubectl get sc              # 应出现 longhorn (default)"
echo "  kubectl -n longhorn-system get svc longhorn-frontend   # UI"
echo ""
echo "=== Longhorn UI 访问（用 Gateway 或端口转发）==="
echo "  kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80"
