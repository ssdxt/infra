#!/bin/bash
# 01-install-argocd.sh — 离线安装 ArgoCD non-HA (v3.5.3)，镜像已进 Harbor
# 幂等：重复执行不破坏现有状态（apply 为服务端幂等）
set -euo pipefail

DIR=/data1/ssdxt/gitops
NS=argocd
HARBOR_AUTH='admin:<HARBOR_PASSWORD>'

mkdir -p "$DIR"
cd "$DIR"

# ---------- 1. 确保镜像在 Harbor（跳过已存在的 tag） ----------
mirror_if_missing() {
  local dest_repo="$1" dest_tag="$2" src="$3"
  local name="${dest_repo##*/}"
  local code
  code=$(curl -sk --noproxy '*' -o /dev/null -w '%{http_code}' \
    "https://10.100.10.29/api/v2.0/projects/argocd/repositories/${dest_repo#argocd/}/artifacts/${dest_tag}" \
    -u "$HARBOR_AUTH")
  if [ "$code" = "200" ]; then
    echo "SKIP $name:$dest_tag (already in Harbor)"
  else
    echo "MIRROR $name:$dest_tag"
    skopeo copy --override-arch amd64 --retry-times 3 \
      --dest-tls-verify=false --dest-creds "$HARBOR_AUTH" \
      "docker://$src" "docker://10.100.10.29/argocd/${name}:${dest_tag}"
  fi
}
# 镜像搬运清单（需 WSL/外网代理环境执行；本脚本在集群节点上仅做存在性检查）
mirror_if_missing argocd/argocd v3.5.3 quay.io/argoproj/argocd:v3.5.3 || true
mirror_if_missing argocd/redis 8.2.3-alpine public.ecr.aws/docker/library/redis:8.2.3-alpine || true
mirror_if_missing argocd/dex v2.45.1 ghcr.io/dexidp/dex:v2.45.1 || true

# ---------- 2. 安装 ----------
kubectl create namespace "$NS" --dry-run=client -o yaml | kubectl apply -f -
# 大 CRD（applicationsets）注解超 256KB，客户端 apply 会报
# "metadata.annotations: Too long" —— 必须用 server-side apply
kubectl apply --server-side --force-conflicts -n "$NS" -f "$DIR/argocd-install-harbor.yaml"

# ---------- 3. 暴露：argocd-server 改 NodePort 30443 ----------
kubectl -n "$NS" patch svc argocd-server --type merge \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"https","port":443,"targetPort":8080,"nodePort":30443},{"name":"http","port":80,"targetPort":8080,"nodePort":30080}]}}' \
  -o name

# ---------- 4. 等待就绪 ----------
kubectl -n "$NS" wait --for=condition=available --timeout=600s deployment --all

# ---------- 5. 输出初始密码 ----------
echo "ADMIN_PASSWORD=$(kubectl -n "$NS" get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d)"
