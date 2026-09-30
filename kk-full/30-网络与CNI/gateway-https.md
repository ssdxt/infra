# 30-网络与CNI §6 — Gateway HTTPS 化（cert-manager 自建 CA + *.wuxing.local 泛域名证书）

> 完成日期：2026-09-30。资产：control-01 `/data1/ssdxt/gateway/`（`wxq-ca.yaml`、`02-gateway-https.sh` 幂等脚本、
> `argocd-httproute.yaml`、`argocd-referencegrant.yaml`、`wxq-root-ca.crt`）。
> 工作站根 CA 副本：`C:\Users\CC\Desktop\dsh\kk-full\30-网络与CNI\wxq-root-ca.crt`。

## 背景

- 用户工位到 Gateway LB IP `10.100.10.251` **无路由**，唯一入口是节点 NodePort
  `10.100.10.10:32298`；hosts 已把 `*.wuxing.local` 指向 `10.100.10.10`。
- 原状态：Gateway 只有 HTTP :80 监听，32298 是 HTTP；ArgoCD（30443）/Longhorn（30800）
  各自开 NodePort，证书全是自签告警。
- 目标：统一域名入口 + HTTPS（自建 CA 泛域名证书）+ 清理多余 NodePort。

## 1. cert-manager 自建 CA 体系（三段式）

清单 `wxq-ca.yaml`（控制面逻辑，直接 apply）：

1. `ClusterIssuer wxq-selfsigned-bootstrap`（selfSigned）→ 自签根 CA；
2. `Certificate wxq-root-ca`（ns cert-manager，`isCA: true`，10 年）→ 生成 Secret `wxq-root-ca`；
3. `ClusterIssuer wxq-ca`（ca.secretName: wxq-root-ca）→ 用根 CA 签业务证书；
4. `Certificate wxq-wildcard-tls`（ns gateway，1 年，renewBefore 24h，
   dnsNames `*.wuxing.local` + `wuxing.local`）→ Secret `wxq-wildcard-tls`。

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
kubectl apply -f /data1/ssdxt/gateway/wxq-ca.yaml
kubectl -n gateway get certificate wxq-wildcard-tls    # READY=True（reason=KeyPairVerified）
```

实测证书信息：

```
根CA:  CN=wxq-local-root-ca, 自签, 2026-09-30 ~ 2036-09-27 (87600h)
叶子:  issuer=CN=wxq-local-root-ca, SAN=DNS:*.wuxing.local,DNS:wuxing.local,
       2026-09-30 ~ 2027-09-30 (8760h)
```

导出根 CA（分发用）：

```bash
kubectl -n cert-manager get secret wxq-root-ca -o jsonpath='{.data.ca\.crt}' | base64 -d \
  > /data1/ssdxt/gateway/wxq-root-ca.crt
```

## 2. Gateway 加 HTTPS 443 监听

```bash
kubectl -n gateway patch gateway monitoring-gateway --type merge -p '{"spec":{"listeners":[
  {"name":"http","protocol":"HTTP","port":80,"allowedRoutes":{"namespaces":{"from":"All"}}},
  {"name":"https","protocol":"HTTPS","port":443,
   "tls":{"certificateRefs":[{"group":"","kind":"Secret","name":"wxq-wildcard-tls"}]},
   "allowedRoutes":{"namespaces":{"from":"All"}}}]}}'
```

最终 listeners（Terminate 模式）：

```
http  :80  HTTP    allowedRoutes: All
https :443 HTTPS   tls: Secret/wxq-wildcard-tls (mode=Terminate), allowedRoutes: All
```

## 3. ⚠️ 关键坑：固定 nodePort 32298 → HTTPS

**改前现象**：用户唯一入口 32298 原本映射 HTTP :80；直接 patch cilium gateway svc 改 nodePort，
Cilium 立刻把 svc 重建为随机端口（32056/32010），且端口名被改成 `port-80`/`port-443`。

**根因**：svc 由 Cilium Gateway 控制器生成，patch 时端口名/字段与控制器期望不一致即触发重建。

**精确改法**：按 Cilium 自己的端口名 patch（实测 patch 后 60s+ 不被回写）：

```bash
kubectl -n gateway patch svc cilium-gateway-monitoring-gateway --type merge -p \
  '{"spec":{"ports":[{"name":"port-80","port":80,"nodePort":32299},
                     {"name":"port-443","port":443,"nodePort":32298}]}}'
```

最终端口分配：**32298 = HTTPS(443)**、32299 = HTTP(80)；`.251:80/:443` 同步可用。
**⚠️ 每次 Gateway 变更触发控制器重建 svc 后，需重跑 02 脚本第 3 步重新固定 nodePort。**

## 4. ArgoCD 接入域名（TLS 由 Gateway 终止）

```bash
# 后端改明文 http（否则 Gateway→后端二次 TLS 报 500）
kubectl -n argocd patch cm argocd-cmd-params-cm --type merge -p '{"data":{"server.insecure":"true"}}'
kubectl -n argocd rollout restart deploy/argocd-server
# 跨 ns 引用放行（argocd-ns ReferenceGrant，HTTPRoute 在 gateway ns）
kubectl apply -f /data1/ssdxt/gateway/argocd-referencegrant.yaml
# HTTPRoute: argocd.wuxing.local -> argocd-server.argocd:80
kubectl apply -f /data1/ssdxt/gateway/argocd-httproute.yaml
```

两个必踩点（实测）：
- 不配 `server.insecure=true` → Gateway 以 http 访问后端，返回 **500**（日志显示 `tls: false` 才对）；
- 不建 ReferenceGrant → HTTPRoute `ResolvedRefs=False (RefNotPermitted)`，同样 500。

## 5. HTTP→HTTPS 跳转

Gateway API 通配 hostname 优先级**低于**精确 hostname，catch-all redirect route 抢不过
现有 5 条精确路由——因此在每条 HTTPRoute 头部插入独立 redirect rule（RequestRedirect 不能与
backendRefs 同 rule）：

```bash
for r in grafana-route prometheus-route alertmanager-route longhorn-route monitoring-routes; do
  kubectl -n gateway patch httproute $r --type json \
    -p '[{"op":"add","path":"/spec/rules/0","value":{"filters":[
      {"type":"RequestRedirect","requestRedirect":{"scheme":"https","port":32298,"statusCode":301}}]}}]'
done
```

验证：`http://grafana.wuxing.local:32299/` → `301 Location: https://grafana.wuxing.local:32298/`，
浏览器跟随落地 `https://…:32298/login`（200），全链路实测可点通（control-01 与工位 curl.exe 均验证）。

**跳转端口的取舍（重要）**：RequestRedirect 不写 `port` 时默认跳 **443**（标准行为，同 nginx——
不是"不跳端口"）。但本环境 443 只以 nodePort 32298 暴露，工位没有 443 路由，跳 443 会断，
因此显式写 `port: 32298`。代价：① URL 带非标端口；② 若有机器从 `.251:80` 进入会被跳到
`.251:32298`（该端口在 LB IP 上不存在）。若客户端环境有 443 路由，把 `requestRedirect.port`
改回 443（或删掉 port 字段）即恢复标准行为。

## 6. NodePort 清理（前后对比）

| Service | 改前 | 改后 |
|---|---|---|
| longhorn-system/longhorn-frontend | NodePort 30800 | **ClusterIP**（仅域名单入口） |
| argocd/argocd-server | NodePort 30443/30080 | **ClusterIP** |
| gateway/cilium-gateway-monitoring-gateway | 80:32298(HTTP) | **443:32298(HTTPS) + 80:32299(HTTP)** ← 保留，工位唯一入口 |

```bash
kubectl -n longhorn-system patch svc longhorn-frontend -p '{"spec":{"type":"ClusterIP"}}'
kubectl -n argocd patch svc argocd-server -p '{"spec":{"type":"ClusterIP"}}'
kubectl get svc -A | grep NodePort   # 仅剩 cilium gateway svc
```

## 7. 端到端验证（control-01 实测输出）

```bash
for h in grafana longhorn alertmanager prometheus argocd; do
  curl -sk --resolve $h.wuxing.local:32298:10.100.10.10 https://$h.wuxing.local:32298/ -o /dev/null -w "%{http_code} "
done
# → 302 200 200 302 200   （grafana/prometheus 302 为登录跳转，正常）

# 不加 -k 的证书链验证（关键）：
curl -s --cacert /data1/ssdxt/gateway/wxq-root-ca.crt \
  --resolve grafana.wuxing.local:32298:10.100.10.10 https://grafana.wuxing.local:32298/ \
  -o /dev/null -w "cert-chain: %{http_code}\n"
# → cert-chain: 302   （argocd/longhorn 为 200；能返回 HTTP 状态码即证书链受信）
```

Windows 工作站验证（先导入根 CA 或临时 --cacert）：

```powershell
# Windows 自带 curl 是 schannel 后端：离线环境 CRL 不可达会报 revoke unknown，
# 必须加 --ssl-no-revoke；--cacert 指定我们签发的根 CA
curl.exe -s --ssl-no-revoke --cacert C:\Users\CC\Desktop\dsh\kk-full\30-网络与CNI\wxq-root-ca.crt `
  --resolve grafana.wuxing.local:32298:10.100.10.10 https://grafana.wuxing.local:32298/api/health -w "%{http_code}"
# → 200 {"database":"ok",...} = 证书链受信（Issuer: CN=wxq-local-root-ca）
# 导入信任库后（见 §8 certutil），浏览器/curl 无需 --cacert
```

## 8. 统一访问地址（工位 hosts: `10.100.10.10 *.wuxing.local`）

| 服务 | 地址 | 备注 |
|---|---|---|
| Grafana | `https://grafana.wuxing.local:32298` | admin/prom-operator |
| Prometheus | `https://prometheus.wuxing.local:32298` | |
| Alertmanager | `https://alertmanager.wuxing.local:32298` | |
| Longhorn | `https://longhorn.wuxing.local:32298` | |
| ArgoCD | `https://argocd.wuxing.local:32298` | admin（密码见 70-GitOps） |
| 有 .251 路由的机器 | `https://<域名>`（443 标准端口） | LB IP 10.100.10.251 |

导入 Windows 信任（管理员 PowerShell，导入后重启浏览器）：

```powershell
certutil -addstore -f Root wxq-root-ca.crt
```

## 9. 回滚

```bash
# 备份在 /data1/ssdxt/gateway/backup/<ts>/
kubectl apply -f backup/<ts>/gateway.yaml            # 还原 listeners
kubectl apply -f backup/<ts>/httproutes.yaml         # 还原路由（去掉 redirect）
kubectl apply -f backup/<ts>/argocd-cm.yaml && kubectl -n argocd rollout restart deploy/argocd-server
kubectl apply -f backup/<ts>/argocd-svc.yaml         # 还原 NodePort 30443
kubectl apply -f backup/<ts>/longhorn-svc.yaml       # 还原 NodePort 30800
kubectl -n gateway delete httproute argocd-route; kubectl -n argocd delete referencegrant allow-gateway-ns
kubectl -n gateway delete certificate wxq-wildcard-tls; kubectl delete clusterissuer wxq-ca wxq-selfsigned-bootstrap
kubectl -n cert-manager delete certificate wxq-root-ca   # 根 CA 最后删
```

幂等重跑：`bash /data1/ssdxt/gateway/02-gateway-https.sh`（自动备份→全量对齐→验证）。
