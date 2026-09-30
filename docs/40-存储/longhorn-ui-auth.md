# Longhorn UI Basic Auth（nginx 反代方案）

> 日期：2026-09-30　|　状态：✅ 已落地并验证　|　影响面：仅入口层，不改 Longhorn 自身组件

## 1. 为什么需要做（背景）

Longhorn UI 默认**没有任何认证**——官方设计假定 UI 只通过 port-forward / 内网受信环境访问
（上游讨论见 longhorn#2417，官方推荐方案就是"在前面放一个带认证的反向代理"）。
本集群通过 Gateway（`https://longhorn.wuxing.local:32298`）直接暴露 UI，等于任何能通
10.100.10.251:32298 的人都能删除卷/快照，必须补认证。

## 2. 方案

在 `longhorn-frontend` 前面加一层 nginx Basic Auth 反代（与官方推荐一致）：

```
浏览器 → Gateway(32298) → HTTPRoute longhorn-route
       → svc/wxq-longhorn-auth-proxy (80→8080, nginx, Basic Auth)
       → svc/longhorn-frontend.longhorn-system:80 (原样，未动)
```

新增资源（全部带 `wxq-` 前缀，与 Longhorn 升级互不干扰，均在 ns `longhorn-system`）：

| 资源 | 说明 |
|---|---|
| Secret `wxq-longhorn-basic-auth` | key `.htpasswd`（apr1 哈希，用户 `admin`） |
| ConfigMap `wxq-longhorn-nginx` | nginx 配置：8080 监听、auth_basic、WebSocket Upgrade 头、免认证 `/healthz` |
| Deployment `wxq-longhorn-auth-proxy` | 2 副本，镜像 `harbor.wuxing.local/library/nginx:1.27-alpine`，50m/64Mi |
| Service `wxq-longhorn-auth-proxy` | 80 → 8080 |

唯一对既有资源的改动：HTTPRoute `longhorn-route`（ns `gateway`）rule[1] 的 backendRefs
`longhorn-frontend` → `wxq-longhorn-auth-proxy`（rule[0] 的 HTTP→HTTPS 跳转未动）。

### nginx 配置要点（ConfigMap `wxq-longhorn-nginx`）

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}
server {
    listen 8080;
    location = /healthz { auth_basic off; access_log off; return 200 "ok"; }  # 探针免认证
    auth_basic "Longhorn UI";
    auth_basic_user_file /etc/nginx/.htpasswd;
    location / {
        proxy_pass http://longhorn-frontend.longhorn-system.svc.cluster.local:80;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;          # WebSocket（UI 实时刷新需要）
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        client_max_body_size 0;
    }
}
```

> ⚠️ 踩坑：readinessProbe 最初打 `/`，被 auth 拦成 401 → Pod 永远 NotReady。
> 探针必须打免认证的 `/healthz`。

## 3. 部署 / 重做步骤

一键脚本（幂等，自动备份 HTTPRoute，凭据复用 `/data1/ssdxt/storage/longhorn-ui-credentials.txt`）：

```bash
bash /data1/ssdxt/storage/07-longhorn-ui-auth-proxy.sh    # control-01 上执行，KUBECONFIG 已内置
```

脚本做：生成/复用密码 → `openssl passwd -apr1` 生成哈希 → Secret/ConfigMap/Deployment/Service
apply → rollout → 备份 HTTPRoute 到 `/data1/ssdxt/storage/backup/longhorn-route-<ts>.yaml` →
patch 路由后端 → 写凭据文件（600）。

## 4. 凭据

- 用户名 `admin`；密码在 **control-01 `/data1/ssdxt/storage/longhorn-ui-credentials.txt`**（权限 600）。
- **密码重置**：
  ```bash
  PW='<新密码>'
  kubectl -n longhorn-system create secret generic wxq-longhorn-basic-auth \
    --from-literal=.htpasswd="admin:$(openssl passwd -apr1 "$PW")" \
    --dry-run=client -o yaml | kubectl apply -f -
  kubectl -n longhorn-system rollout restart deploy/wxq-longhorn-auth-proxy
  # 同步更新凭据文件！subPath 挂载的 Secret 不会热更新，必须重启 proxy
  ```

## 5. 验证（2026-09-30 实测输出）

```bash
B="https://10.100.10.251:32298"; H="Host: longhorn.wuxing.local"
curl -sk -o /dev/null -w '%{http_code}' -H "$H" $B                          # → 401（无凭据被拦）
curl -sk -o /dev/null -w '%{http_code}' -u admin:xxx -H "$H" $B             # → 401（错误密码被拦）
curl -sk -o /dev/null -w '%{http_code}' -u admin:<密码> -H "$H" $B          # → 200（UI 正常）
curl -sk -o /dev/null -w '%{http_code}' -H "$H" http://10.100.10.251:32298/ # → 301（HTTP 跳 HTTPS 未受影响）
# 其他域名回归：grafana 302 / argocd 200 / prometheus 302 / alertmanager 200 / hubble 200 均不变
# 路由状态：Accepted=True ResolvedRefs=True；proxy 2/2 Running
# GET / 返回真实 Longhorn UI index.html（content-type: text/html）
```

浏览器打开 `https://longhorn.wuxing.local:32298` → 弹 Basic Auth → 输入凭据后 UI 正常加载
（WebSocket 走同一条代理，`Upgrade/Connection` 头已透传）。

## 6. 回滚

把路由后端改回即恢复"无认证直连"（nginx 层原样保留，随时可再切回）：

```bash
kubectl -n gateway patch httproute longhorn-route --type=json -p \
  '[{"op":"replace","path":"/spec/rules/1/backendRefs/0/name","value":"longhorn-frontend"}]'
```

彻底移除：`kubectl -n longhorn-system delete deploy/svc/wxq-longhorn-auth-proxy cm/wxq-longhorn-nginx secret/wxq-longhorn-basic-auth`。

## 7. 顺带提示（尚未实施）

Prometheus / Alertmanager / Hubble UI 等入口同样无认证。同一套模式可批量套用：
复制 ConfigMap（改 proxy_pass 目标）+ 复用同一个 Secret（或独立凭据）+ Deployment + Service +
改对应 HTTPRoute 后端。建议后续逐个收敛。

## 8. 资产清单

- 脚本：control-01 `/data1/ssdxt/storage/07-longhorn-ui-auth-proxy.sh`（本机副本 `kk-full` 同步）
- 凭据：control-01 `/data1/ssdxt/storage/longhorn-ui-credentials.txt`（600）
- 路由备份：control-01 `/data1/ssdxt/storage/backup/longhorn-route-20260930-1453.yaml`
- 镜像：`harbor.wuxing.local/library/nginx:1.27-alpine`
