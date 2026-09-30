# Longhorn 逐版本升级：v1.7.2 → v1.13.0（2026-09-30）

> 离线集群逐版本升级实录。每步：helm upgrade（Harbor 化镜像）→ Pod 全 Running →
> Loki 卷 healthy/Bound → CSI 快照 READYTOUSE=true。全程业务无中断。

## 0. 升级链与耗时

| 步骤 | 版本 | 结果 | 备注 |
|---|---|---|---|
| 0 | 1.7.2（起点） | — | webhook static 注解修复运行中 |
| 1 | 1.8.2 | ✅ | ~10min（8 节点拉镜像） |
| 2 | 1.9.2 | ✅ | ~12min |
| 3 | 1.10.2 | ⚠️→✅ | 3 次 hook 失败后成功，见坑②③ |
| 4 | 1.11.3 | ✅ | ~13min |
| 5 | 1.12.1 | ✅ | ~12min |
| 6 | 1.13.0 | ✅ | ~12min |

官方不允许跳版本（`checkLHUpgradePath`），且 1.10+ 的 pre-upgrade hook 会强制校验升级路径与引擎 API 兼容性。

## 1. 升级前保险（已完成）

- 资源导出：`/data1/ssdxt/storage/backup/upgrade-20260930-1027/`（volumes/settings/nodes/deployments/webhook-secrets/helm-values）；
  每步 helm 前另有 `upgrade-step-<v>-<hhmm>/` 快照备份。
- Loki 卷快照（零成本，无需 backup target）：`kubectl -n logging get vs loki-pre-upgrade` → READYTOUSE=true。
- 卷健康：storage-loki-0，2/2 副本 running（wxq-run-02/06），robustness=healthy。

## 2. 镜像资产（WSL skopeo → Harbor longhorn/，amd64）

- 6 个版本 × 14 镜像 = **71 个**（6 个 chart 渲染取并集；engine/manager/ui/instance-manager/
  share-manager/backing-image-manager × 6 + support-bundle-kit × 6 + CSI sidecar 各版本 pinned tag × 24 + snapshot-controller v8.0.1）。
- chart tgz 全部在 `/data1/ssdxt/charts/longhorn-upgrade/`（含每版 `values-harbor-<v>.yaml`、`custom-values.yaml`）。
- mirror.sh 已补 `LIST_LONGHORN_UPGRADE`。

## 3. 踩坑（每步"现象→根因→解法"）

1. **CSI 快照一直不 READYTOUSE（即用户看到的 backup 报错根因，见 §5）**：
   独立部署的 `csi-snapshotter`（CSI 侧车）只处理 VolumeSnapshotContent，缺
   **snapshot-controller**（VS→VSC 控制器，上游 external-snapshotter 组件）。
   补：`storage/crds/rbac-snapshot-controller.yaml` + `storage/snapshot-controller.yaml`
   （镜像 `harbor.wuxing.local/longhorn/snapshot-controller:v8.0.1`，2 副本，SA=snapshot-controller）。
   注意 SA 必须用专用 `snapshot-controller`（longhorn-service-account 无 volumesnapshots/status 权限）。
2. **VolumeSnapshotClass 必须带 `parameters: {"type": "snap"}`**：
   Longhorn 1.7.2 CSI 源码（csi/controller_server.go）对空 `type` 的兼容行为是 **按 backup 处理**
   （"For backward compatibility, empty type is considered as csiSnapshotTypeLonghornBackup"），
   backup-target 为空时报 `failed to create backup ... missing input parameter`。
   加 `type: snap` 后快照 10 秒 READY。
3. **1.10+ chart 默认 `global.imageRegistry: "docker.io"` 会拼进所有镜像**：
   渲染结果变 `docker.io/harbor.wuxing.local/...`（pre-upgrade job 拉不到镜像 → DeadlineExceeded，
   helm 报 "pre-upgrade hooks failed"）。解法：values 里显式
   `global.imageRegistry: harbor.wuxing.local` + `privateRegistry.registryUrl: harbor.wuxing.local` +
   repository 用短名 `longhorn/<name>`（1.8/1.9 chart 无此逻辑，全路径写法仍可用）。
4. **pre-upgrade job 镜像拉取超时**：hook job 有 activeDeadlineSeconds，100Mbps 下 8 节点拉
   ~120MB manager 镜像会超。解法：升级前 `/usr/local/sbin/lh-prepull.sh <ver>` 全节点 ctr pull。
5. **1.13 卷 CRD 无 `spec.engineImage`（已改名 `spec.image`）**：引擎升级改用
   Setting `concurrent-automatic-engine-upgrade-per-node-limit`（临时置 1，升完还原 0），
   `default-engine-image` 已是 v1.13.0，30 秒完成 storage-loki-0 在线引擎升级，healthy。

## 4. 各版本镜像 tag 一览（values-harbor-<v>.yaml 固化）

| 组件 | 1.8.2 | 1.9.2 | 1.10.2 | 1.11.3 | 1.12.1 | 1.13.0 |
|---|---|---|---|---|---|---|
| longhorn-engine/manager/ui/instance-manager/share-manager/backing-image-manager | v1.8.2 | v1.9.2 | v1.10.2 | v1.11.3 | v1.12.1 | v1.13.0 |
| support-bundle-kit | v0.0.56 | v0.0.69 | v0.0.79 | v0.0.88 | v0.0.92 | v0.0.98 |
| csi-attacher | v4.9.0 | v4.9.0-20250709 | v4.10.0-20251226 | v4.12.0 | v4.12.0 | v4.13.0 |
| csi-provisioner | v5.3.0 | v5.3.0-20250709 | v5.3.0-20251226 | v6.3.0 | v5.3.0 | v6.3.0 |
| csi-node-driver-registrar | v2.14.0 | v2.14.0-20250709 | v2.15.0-20251226 | v2.17.0 | v2.17.0 | v2.18.0 |
| csi-resizer | v1.13.2 | v1.14.0-20250709 | v1.14.0-20260119 | v2.2.0 | v2.2.1 | v2.2.1 |
| csi-snapshotter | v8.2.0 | v8.3.0-20250709 | v8.4.0-20251226 | v8.6.0 | v8.6.0 | v8.6.0 |
| livenessprobe | v2.16.0 | v2.16.0-20250709 | v2.17.0-20251226 | v2.19.0 | v2.19.0 | v2.20.0 |

（chart 渲染均为显式 `repo:tag`，无 @sha256 摘要，无需剥摘要。）

## 5. backup 报错根因（结论）

用户在 UI/告警看到的 backup 相关报错有两层，均已查明：

1. **backup-target 本来就是空的（正常空态）**：
   `settings.longhorn.io backup-target` 与 `backup-target-credential-secret` 的 value 均为 `""`。
   用户明确"loki 不做备份"，UI Backup 页在未配置 backup target 时创建备份必然报错——属预期空态，不是故障。
2. **CSI 快照被误当成 backup（真 bug，已修复）**：
   VolumeSnapshotClass 缺 `parameters.type=snap` 时，1.7.2 把 CSI 快照当 backup 走
   → `missing input parameter`（见坑②）→ UI/事件里表现为 backup 相关报错，快照永远不 ready。
   修复后 `kubectl -n logging get vs` READYTOUSE=true。
3. **csi-snapshotter CrashLoop 历史**：110+ 次重启是 webhook TLS 风暴期（#13012，2026-09-29 已修）
   leader-election 失租的遗留；升级后 chart 管理的 csi-snapshotter 已是 v8.6.0，重启计数归零重新累计。

## 6. webhook TLS（上游 #13012）收尾

- 升级到 1.12.1（含官方修复）后：移除两个 Secret 的 `listener.cattle.io/static=true` 注解
  （`kubectl -n longhorn-system annotate secret longhorn-webhook-{ca,tls} listener.cattle.io/static-`）
  并滚动重启 longhorn-manager。
- 观察 10 分钟验证数据见 40-存储/README.md §2 更新——resourceVersion 稳定、secrets PUT 409 ≈0，
  官方修复生效，**"2027-08 手工轮转证书"待办作废**（dynamiclistener 自动管理恢复）。

## 7. 升级后终态

- helm release：longhorn-1.13.0（rev 13），ns longhorn-system
- 新组件形态：`longhorn-global-manager`、`wxq-longhorn-auth-proxy`（1.13 新增）、
  csi-snapshotter（chart 管理，v8.6.0，3 副本）、snapshot-controller（自建，v8.0.1，2 副本）
- storage-loki-0：engine v1.13.0、robustness=healthy、loki-0 正常写入（15 分钟 6 万行）
- CSI 快照链路可用（VS→snapshot-controller→VSC→csi-snapshotter→Longhorn snapshot）
- UI：Gateway `longhorn.wuxing.local`（https，走 auth-proxy）；集群内无 NodePort 30800（此前文档口径有误）

## 8. 回滚

- helm 层面：`helm rollback longhorn <rev>`（保留每版 tgz + upgrade-step 备份）；但 Longhorn 官方不支持降级 CRD，回滚仅限"升级失败停在当前版"场景，跨版回滚需恢复 etcd/资源备份。
- 本次全程未触发回滚。

## 9. 工具脚本（control-01）

- `/usr/local/sbin/lh-upgrade-step.sh <ver>`：备份→helm upgrade→rollout→验证
- `/usr/local/sbin/lh-prepull.sh <ver>`：全节点预拉 manager 镜像（避免 hook 超时）
- `/usr/local/sbin/lh-verify-step.sh`：Pod/卷/快照验证
- WSL：`~/mirror-longhorn-upgrade.sh`（71 镜像）、`~/longhorn-upgrade/*.tgz`
