#!/bin/bash
# wxq-longhorn-auth-proxy: Longhorn UI Basic Auth 反向代理 (nginx)
# 幂等：可重复执行；不改任何 longhorn 自身组件
set -euo pipefail
NS=longhorn-system
K=/usr/local/bin/kubectl
command -v kubectl >/dev/null && K=$(command -v kubectl)
export KUBECONFIG=/etc/kubernetes/admin.conf
TS=$(date +%Y%m%d-%H%M)
BK=/data1/ssdxt/storage/backup
mkdir -p "$BK"

# 1) 密码（已存在则复用，保证幂等）
CRED=/data1/ssdxt/storage/longhorn-ui-credentials.txt
if [ -s "$CRED" ]; then
  PW=$(sed -n 's/^password: //p' "$CRED" | head -1)
else
  PW=$(openssl rand -base64 15 | tr -dc 'A-Za-z0-9' | head -c 16)
fi
[ -n "$PW" ] || { echo "FATAL: password empty"; exit 1; }
HASH=$(openssl passwd -apr1 "$PW")

# 2) Secret（key: .htpasswd）
$K -n $NS create secret generic wxq-longhorn-basic-auth \
  --from-literal=.htpasswd="admin:$HASH" \
  --dry-run=client -o yaml | $K apply -f -

# 3) ConfigMap（nginx 配置：8080 监听 + Basic Auth + WebSocket）
cat > /tmp/wxq-lhap-nginx.conf <<'NGINX'
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
server {
    listen 8080;
    server_name _;

    location = /healthz { auth_basic off; access_log off; return 200 "ok"; }

    auth_basic "Longhorn UI";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://longhorn-frontend.longhorn-system.svc.cluster.local:80;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        client_max_body_size 0;
    }
}
NGINX
$K -n $NS create configmap wxq-longhorn-nginx \
  --from-file=default.conf=/tmp/wxq-lhap-nginx.conf \
  --dry-run=client -o yaml | $K apply -f -

# 4) Deployment + Service
$K -n $NS apply -f - <<'DEPLOY' || exit 1
apiVersion: apps/v1
kind: Deployment
metadata:
  name: wxq-longhorn-auth-proxy
  namespace: longhorn-system
  labels: {app: wxq-longhorn-auth-proxy}
spec:
  replicas: 2
  selector:
    matchLabels: {app: wxq-longhorn-auth-proxy}
  template:
    metadata:
      labels: {app: wxq-longhorn-auth-proxy}
    spec:
      containers:
      - name: nginx
        image: harbor.wuxing.local/library/nginx:1.27-alpine
        ports: [{containerPort: 8080}]
        resources:
          requests: {cpu: 50m, memory: 64Mi}
          limits: {cpu: 200m, memory: 128Mi}
        volumeMounts:
        - {name: htpasswd, mountPath: /etc/nginx/.htpasswd, subPath: .htpasswd, readOnly: true}
        - {name: conf, mountPath: /etc/nginx/conf.d/default.conf, subPath: default.conf, readOnly: true}
        readinessProbe:
          httpGet: {path: /healthz, port: 8080}
          initialDelaySeconds: 3
          periodSeconds: 10
      volumes:
      - name: htpasswd
        secret: {secretName: wxq-longhorn-basic-auth, items: [{key: .htpasswd, path: .htpasswd}]}
      - name: conf
        configMap: {name: wxq-longhorn-nginx, items: [{key: default.conf, path: default.conf}]}
---
apiVersion: v1
kind: Service
metadata:
  name: wxq-longhorn-auth-proxy
  namespace: longhorn-system
  labels: {app: wxq-longhorn-auth-proxy}
spec:
  selector: {app: wxq-longhorn-auth-proxy}
  ports: [{port: 80, targetPort: 8080}]
DEPLOY

echo "== waiting for proxy rollout =="
$K -n $NS rollout status deploy/wxq-longhorn-auth-proxy --timeout=180s

# 5) 备份并切换 HTTPRoute 后端（只动 rule[1] 的 backendRefs）
$K -n gateway get httproute longhorn-route -o yaml > "$BK/longhorn-route-$TS.yaml"
CUR=$($K -n gateway get httproute longhorn-route -o jsonpath='{.spec.rules[1].backendRefs[0].name}')
echo "current backend: $CUR"
if [ "$CUR" != "wxq-longhorn-auth-proxy" ]; then
  $K -n gateway patch httproute longhorn-route --type=json -p \
    '[{"op":"replace","path":"/spec/rules/1/backendRefs/0/name","value":"wxq-longhorn-auth-proxy"}]'
fi

# 6) 凭据文件（600）
umask 077
cat > "$CRED" <<EOF
# Longhorn UI Basic Auth 凭据（经 nginx 反代 wxq-longhorn-auth-proxy）
# 生成时间: $(date '+%F %T')
url: https://longhorn.wuxing.local:32298
username: admin
password: $PW
# 重置方法见 kk-full/40-存储/longhorn-ui-auth.md
EOF
chmod 600 "$CRED"

echo "== DONE =="
echo "password: $PW"
