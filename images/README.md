# 镜像搬运（skopeo → Harbor）

## 为什么需要
集群内网无外网，所有镜像必须先在 Harbor 里。搬运机需要有外网的机器（当前用工作站的 WSL，已装 skopeo + regctl）。

## 怎么用
```bash
# 在 WSL 里执行（Harbor 走 NO_PROXY 直连，上游走代理）
bash mirror.sh all            # 全部
bash mirror.sh longhorn       # 只搬 Longhorn 的 13 个镜像
bash mirror.sh logging        # Loki + Alloy
bash mirror.sh metrics        # metrics-server
bash mirror.sh nfs            # NFS provisioner
```

## 镜像清单（脚本里维护，改这里即可）
| 组件 | 镜像数 | 说明 |
|---|---|---|
| longhorn | 13 | manager/engine/instance-manager/share-manager/ui/backing-image-manager + CSI sidecars |
| logging | 2 | loki:3.3.2 + alloy:v1.7.0 |
| metrics | 1 | metrics-server:v0.7.2 |
| nfs | 1 | nfs-subdir-external-provisioner:v4.0.2 |

## 单架构说明
用 `--override-arch amd64` 只搬 amd64（集群全是 amd64）。
**注意**：`--multi-arch all` 会带上用不到的冷门架构；`--multi-arch <平台列表>` 在 skopeo 1.24 有 bug（报 blob unknown），别用。

## 新增镜像时
1. 在 `mirror.sh` 对应清单里加一行：`上游镜像|Harbor项目/仓库:tag`
2. 重跑 `bash mirror.sh <组件>`
3. 在 `tools/fix-chart-images.py` 生成的 values 里确认目标仓库名对得上
