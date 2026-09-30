#!/usr/bin/env bash
# 端到端引导入口：拿到本仓库后，从这里开始复刻整套离线集群。
set -euo pipefail
echo "== 离线 K8s 集群复刻引导 =="
echo "1. 阅读总览与复刻顺序:   README.md"
echo "2. 环境清单:             docs/00-环境清单.md"
echo "3. 全新环境复刻手册:     docs/99-全新环境复刻手册.md"
echo "4. 镜像准备:             images/mirror.sh (skopeo 全量清单 -> Harbor)"
echo "5. 按 README.md 第 0-10 步依次执行 scripts/ 下对应脚本"
echo
echo "快速检查当前节点环境:"
command -v kubectl >/dev/null && kubectl get nodes || echo "kubectl 不可用（尚未装集群，属正常）"
