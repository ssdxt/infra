# Loki Ruler 日志告警（60-日志）

> 2026-09-30 首次落地。Loki 3.3.2（chart loki-6.24.0，SingleBinary，ns `logging`）。
> 告警链路：Loki ruler → plant01 Alertmanager（`http://10.100.10.29:9093`）→ 按路由转发钉钉。

## 一、【原有功能】Loki ruler（chart 开箱能力）

Loki 内置 rule 评估器，本地文件规则只需配置 `ruler` 段 + 把规则文件放进目录。

## 二、【后补调整】配置

### 1. helm values 增量 —— `/data1/ssdxt/values/loki-ruler.yaml`

```yaml
loki:
  rulerConfig:                # ⚠️ chart 6.24.0 只认 loki.rulerConfig，写在 loki.ruler 会被模板丢弃
    storage:
      type: local
      local:
        directory: /rules
    rule_path: /tmp/loki/scratch
    alertmanager_url: http://10.100.10.29:9093
    enable_api: true
    ring:
      kvstore:
        store: inmemory
singleBinary:
  extraVolumeMounts:          # ⚠️ chart 只把 sc-rules-volume 挂进 sidecar；loki rootfs 只读，必须补挂
  - name: sc-rules-volume
    mountPath: /rules
```

### 2. 规则文件 —— `/data1/ssdxt/logging/loki-ruler-rules.yaml`（ConfigMap）

- ConfigMap（ns `logging`）打 label `loki_rule: "1"` → chart 自带 `loki-sc-rules` sidecar
  （kiwigrid/k8s-sidecar）WATCH 同步到共享卷 `/rules`。
- **必须加注解** `k8s-sidecar-target-directory: /rules/fake`：ruler 本地存储按租户分子目录，
  `auth_enabled: false` 时租户名固定为 `fake`，即最终路径 `/rules/fake/<任意名>.yaml`。
- 应用：`kubectl -n logging apply -f /data1/ssdxt/logging/loki-ruler-rules.yaml`
  （sidecar WATCH 自动搬运，无需重启 loki；改 values 才需 `helm upgrade`）。

### 3. 安装命令（01-loki.sh 已更新，含以上两步）

```bash
export KUBECONFIG=/etc/kubernetes/admin.conf
R=/data1/ssdxt
kubectl apply -f $R/logging/loki-ruler-rules.yaml
python3 $R/tools/fix-chart-images.py $R/charts/loki-6.24.0.tgz logging harbor.wuxing.local /tmp/loki-values-harbor.yaml
helm upgrade loki $R/charts/loki-6.24.0.tgz -n logging \
  -f /tmp/loki-values-harbor.yaml -f /tmp/loki-custom.yaml -f $R/values/loki-ruler.yaml --timeout 15m
```

## 三、规则语法（当前 3 条）

```yaml
groups:
- name: wxq-log-alerts
  interval: 1m
  rules:
  # 链路测试（常驻 firing，severity=none 不进钉钉路由，勿处理）
  - alert: WxqRulerLinkTest
    expr: sum(count_over_time({namespace=~".+"} [5m])) > -1
    labels: {severity: none}
  # 某命名空间 5 分钟 error 日志 > 500 条
  - alert: WxqLogErrorBurst
    expr: sum by (namespace) (count_over_time({namespace=~".+"} |~ "(?i)error" [5m])) > 500
    labels: {severity: warning, namespace: "{{ $labels.namespace }}"}
  # 5 分钟内 OOMKilled 字样日志 > 10 条
  - alert: WxqOOMKilledDetected
    expr: sum(count_over_time({namespace=~".+"} |~ "OOMKilled" [5m])) > 10
    labels: {severity: warning}
```

## 四、验证（2026-09-30 实测输出）

```bash
# 1) 规则加载（ruler API；或 exec 进 pod curl localhost:3100）
curl http://$(kubectl -n logging get svc loki -o jsonpath='{.spec.clusterIP}'):3100/loki/api/v1/rules
# → wxq-log-rules.yaml: 3 条规则全部列出
# 日志：kubectl -n logging logs loki-0 -c loki | grep ruler → "ruler up and running"

# 2) 链路测试（先 severity=none 跑通，避免误发钉钉）
curl -s http://10.100.10.29:9093/api/v2/alerts | jq -r '.[]|.labels.alertname+" | "+.labels.severity+" | "+.status.state'
# → WxqRulerLinkTest | none | active      ← 进 plant01 AM 的 default receiver，不转发钉钉

# 3) 正式规则实弹：起测试 Pod 打 620 行 error + 15 行 OOMKilled
#    （测试 Pod 曾不被采集：alloy tailer 未发现新文件，重启对应节点 alloy pod 后即恢复）
curl -s http://10.100.10.29:9093/api/v2/alerts | ...
# → WxqLogErrorBurst   | warning | active   （kube-system 5m 内 ~5800 条 error，5m 窗口过后自动 resolve）
# → WxqOOMKilledDetected | warning | active （15 条/5m > 10）
```

## 五、踩坑记录

| 坑 | 现象 | 原因 | 解法 |
|---|---|---|---|
| 1 | ruler 配置不生效 | chart 6.24.0 模板丢弃 `loki.ruler`，只合并 `loki.rulerConfig` | 用 `loki.rulerConfig` |
| 2 | `mkdir /rules: read-only file system` CrashLoop | loki 容器 readOnlyRootFilesystem，chart 未把规则卷挂给主容器 | `singleBinary.extraVolumeMounts` 补挂 `sc-rules-volume` 到 `/rules` |
| 3 | `unable to read rule dir /rules/fake` | 本地存储按租户分子目录，auth 关闭时租户=fake | ConfigMap 注解 `k8s-sidecar-target-directory: /rules/fake` |
| 4 | 每次升级 loki rollout 很慢 | Longhorn 卷重新 attach + 50Gi 卷权限遍历 | 等待即可（约 3~6 分钟），非故障 |

## 六、后续加规则模板

```bash
# 1. 编辑 /data1/ssdxt/logging/loki-ruler-rules.yaml，在 rules: 下追加：
  - alert: <规则名>
    expr: <LogQL>            # 先在 Grafana Explore 用同样 LogQL 验证有数据
    for: 0m
    labels: {severity: warning}
    annotations: {summary: "..."}
# 2. 应用（sidecar 自动同步，约 10s）：
kubectl -n logging apply -f /data1/ssdxt/logging/loki-ruler-rules.yaml
# 3. 验证：
curl http://$(kubectl -n logging get svc loki -o jsonpath='{.spec.clusterIP}'):3100/loki/api/v1/rules
# 4. 注意钉钉：severity=warning 会经 plant01 AM 转发钉钉；链路类/测试规则用 severity: none
```

**回滚**：`helm upgrade loki ... `（去掉 `-f $R/values/loki-ruler.yaml`）并 `kubectl delete cm -n logging loki-ruler-rules`。
