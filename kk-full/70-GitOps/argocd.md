# 70 — GitOps（ArgoCD）

> 状态：✅ **已安装并验证**（2025-09-29）。non-HA 官方清单部署，NodePort 暴露。
> 本文档分两部分：【原有功能】官方清单开箱能力；【后补调整】我们离线化 + 暴露时的踩坑与改法。

## 快速导航

| 项目 | 值 |
|---|---|
| ArgoCD 版本 | **v3.5.3**（stable，non-HA install.yaml） |
| 命名空间 | `argocd` |
| 访问地址 | **`https://argocd.wuxing.local:32298`**（2026-09-30 起，Gateway 终止 TLS，证书见 30-网络与CNI/gateway-https.md；工位 hosts: `10.100.10.10 argocd.wuxing.local`）。历史 NodePort `https://<节点IP>:30443` 已清理 |
| 用户名 | `admin` |
| 初始密码 | `<ARGOCD_INITIAL_PASSWORD>`（2025-09-29 安装时生成；改密后即失效，重取方式见下） |
| 安装清单 | control-01 `/data1/ssdxt/gitops/argocd-install-harbor.yaml`（已 Harbor 化） |
| 安装脚本 | control-01 `/data1/ssdxt/gitops/01-install-argocd.sh`（幂等，可重跑） |

---

## 【原有功能】

官方 non-HA 安装清单（`https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml`）开箱提供：

- **argocd-server**：API + Web UI（HTTPS 8080/HTTP 8080? 容器内 8080，TLS 自签证书）
- **argocd-repo-server**：拉取/渲染 Git 仓库与 Helm chart
- **argocd-application-controller**：持续比对 Git 与集群实际状态并同步（StatefulSet 单副本）
- **argocd-redis**：缓存
- **applicationset-controller / notifications-controller / dex-server**：ApplicationSet、通知、dex SSO（dex 默认未配置，处于待机不参与认证）
- CRD：`applications.argoproj.io`、`appprojects.argoproj.io`、`applicationsets.argoproj.io`

## 【后补调整】

### 1. 镜像搬运清单（Harbor `argocd/` 项目）

| 官方镜像 | Harbor 镜像 | 用途 |
|---|---|---|
| `quay.io/argoproj/argocd:v3.5.3` | `harbor.wuxing.local/argocd/argocd:v3.5.3` | 全部 argocd 组件共用（清单中出现 8 次） |
| `public.ecr.aws/docker/library/redis:8.2.3-alpine` | `harbor.wuxing.local/argocd/redis:8.2.3-alpine` | argocd-redis |
| `ghcr.io/dexidp/dex:v2.45.1` | `harbor.wuxing.local/argocd/dex:v2.45.1` | dex（默认未启用，为防 Pod 卡 ImagePullBackOff 一并搬运） |

已同步补进 `/data1/ssdxt/images/mirror.sh`（新增 `LIST_ARGOCD`，支持 `bash mirror.sh argocd` 单独重搬；改动前备份为 `mirror.sh.bak.*`）。

WSL 搬运命令（幂等可重跑）：

```bash
export HTTPS_PROXY=http://127.0.0.1:12450
export NO_PROXY=harbor.wuxing.local,10.100.10.29
# Harbor 项目不存在先建（幂等，409=已存在可忽略）
curl -sk --noproxy '*' -X POST https://10.100.10.29/api/v2.0/projects \
  -u 'admin:<HARBOR_PASSWORD>' -H 'Content-Type: application/json' \
  -d '{"project_name":"argocd","public":true}'
for img in \
  quay.io/argoproj/argocd:v3.5.3 \
  public.ecr.aws/docker/library/redis:8.2.3-alpine \
  ghcr.io/dexidp/dex:v2.45.1 ; do
  name=$(basename "${img%:*}"); case "$img" in *docker/library/*) name=redis;; esac
  skopeo copy --override-arch amd64 --retry-times 3 \
    --dest-tls-verify=false --dest-creds 'admin:<HARBOR_PASSWORD>' \
    "docker://$img" "docker://10.100.10.29/argocd/${name}:${img##*:}"
done
```

### 2. 清单镜像重写方法（python，不用 sed 链）

本地 `rewrite.py`（逻辑：逐行正则匹配 `image:` 行，按 repo 精确映射到 `harbor.wuxing.local/argocd/<同名:同tag>`，未映射镜像打印告警）：

```python
MAPPING = {
    "quay.io/argoproj/argocd": "harbor.wuxing.local/argocd/argocd",
    "public.ecr.aws/docker/library/redis": "harbor.wuxing.local/argocd/redis",
    "docker.io/library/redis": "harbor.wuxing.local/argocd/redis",
    "ghcr.io/dexidp/dex": "harbor.wuxing.local/argocd/dex",
}
# 匹配 ^(\s*-?\s*image:\s*)(\S+)$，repo=镜像名rpartition(':')[0]，命中 MAPPING 则替换
```

WSL 执行：

```bash
curl -x $HTTPS_PROXY -L https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml -o /tmp/argocd-install.yaml
python3 rewrite.py   # 输出 /tmp/argocd-install-harbor.yaml
```

### 3. 安装命令（幂等）

在 control-01（`KUBECONFIG=/etc/kubernetes/admin.conf`）：

```bash
bash /data1/ssdxt/gitops/01-install-argocd.sh
```

脚本做四件事：① 检查 Harbor 镜像存在性（缺则提示回 WSL 补搬）；② `kubectl apply --server-side --force-conflicts -n argocd -f argocd-install-harbor.yaml`；③ patch argocd-server 为 NodePort；④ wait deployments available 并打印 admin 密码。

**⚠️ 必须用 `--server-side` apply（见坑 2）。**

### 4. 暴露方式：NodePort（历史方案，**2026-09-30 已被 Gateway HTTPS 替代并清理**）

> ⚠️ **现状**：argocd-server 已改回 ClusterIP（30443/30080 已回收），统一走域名
> `https://argocd.wuxing.local:32298`——Gateway 终止 TLS，后端
> `server.insecure=true` + HTTPRoute → `argocd-server.argocd:80`。
> 配置与验证见 **30-网络与CNI/gateway-https.md §4**；以下为历史记录。

- **改前现象**：argocd-server 默认 `ClusterIP`，集群外无法访问。
- **原因**：官方清单不给对外暴露方式，各环境自行选择。本集群 Grafana 已有 NodePort 32298 先例，保持一致走 NodePort，Gateway API 暴露留待后续（做正式域名/证书时再切）。
- **精确改法**（已写入安装脚本第 3 步）：

```bash
kubectl -n argocd patch svc argocd-server --type merge \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"https","port":443,"targetPort":8080,"nodePort":30443},{"name":"http","port":80,"targetPort":8080,"nodePort":30080}]}}'
```

- **验证输出**（实际返回）：

```
$ curl -sk -o /dev/null -w '%{http_code}' https://10.100.10.33:30443/
200
$ curl -sk https://10.100.10.33:30443/api/version
{"Version":"v3.5.3"}
```

Pod 状态（安装后实测，7/7 Running）：

```
argocd-application-controller-0                    1/1   Running
argocd-applicationset-controller-8578799bf-pnvq5   1/1   Running
argocd-dex-server-cbfc57d98-sscsv                  1/1   Running
argocd-notifications-controller-5fdffb46bb-q8gmz   1/1   Running
argocd-redis-764dfccc65-fp9wk                      1/1   Running
argocd-repo-server-6d7cf86d6b-2mhpn                1/1   Running
argocd-server-d754648b4-j5v8r                      1/1   Running
$ kubectl -n argocd get svc argocd-server
argocd-server   NodePort   10.233.47.131   <none>   443:30443/TCP,80:30080/TCP
```

### 5. 初始密码获取

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
# 用户名 admin。改过密码后此 secret 可能被删，重置密码：
# argocd account update-password / 或 kubectl -n argocd patch secret argocd-secret
```

### 6. 最小 GitOps 示例（Application）

> ⚠️ **需要 ArgoCD 能网络可达 git 仓库**。离线环境可指向内网 git（如后续部署的 Gitea），或先把 yaml 用 repo-server 可达的 git 服务托管。以下示例留待 Gitea 就绪后启用：

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: demo
  namespace: argocd
spec:
  project: default
  source:
    repoURL: http://<GITEA_IP>:3000/admin/demo.git   # 内网 git，留待后续
    targetRevision: main
    path: apps/demo
  destination:
    server: https://kubernetes.default.svc
    namespace: demo
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### 常见坑（本环境实测）

1. **redis 镜像源是 `public.ecr.aws/docker/library/redis` 不是 `docker.io/library/redis`** —— 解析镜像清单时两个都要映射，否则漏搬。
2. **客户端 `kubectl apply` 大 CRD 报错 `metadata.annotations: Too long: may not be more than 262144 bytes`**（applicationsets CRD 的 last-applied 注解超 256KB）—— 必须用 `kubectl apply --server-side --force-conflicts`。现象：apply 中途断掉，一半资源已建。
3. **argocd-server 默认 TLS 自签** —— 浏览器警告属正常，`curl -k` / 忽略证书；正式证书需后续接 cert-manager + Gateway/Ingress。
4. **dex 默认未启用但 Deployment 存在** —— 不配 dex 时它照样拉起（用 argocd 镜像做 proxy sidecar + dex 容器），所以 `ghcr.io/dexidp/dex` 也得搬，否则 Pod 卡 ImagePullBackOff（wait deployment 会一直不过）。
5. **WSL 内 curl 访问 `https://harbor.wuxing.local` 走代理返回 000** —— WSL 的 NO_PROXY 对该场景未生效，统一改用 `https://10.100.10.29` + `--noproxy '*'` 直连。

### 回滚

```bash
kubectl delete namespace argocd          # 删 ns 即全清（含 CRD 需手动）：
kubectl delete crd applications.argoproj.io appprojects.argoproj.io applicationsets.argoproj.io
```

重装：重跑 `01-install-argocd.sh` 即可（镜像已在 Harbor，无需外网）。
