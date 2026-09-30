# 70 — GitOps（ArgoCD）

> ✅ ArgoCD v3.5.3（non-HA 官方清单）已安装并验证（2025-09-29），NodePort 30443 暴露。
> 完整文档见 [argocd.md](<argocd.md>)：镜像搬运清单、安装命令、验证输出、初始密码、GitOps 示例与常见坑。

已覆盖原占位要点：

- 版本与 Harbor 搬运记录：argocd/redis/dex 共 3 镜像（amd64、显式 tag、无 @sha256）✅
- 安装方式：官方 install.yaml（python 重写镜像）+ `kubectl apply --server-side`（非 helm）✅
- 暴露：NodePort 30443(HTTPS)/30080(HTTP)；Gateway API 暴露留待正式域名时切换 ⏳
- 初始 admin 密码获取方式 ✅；内网 Git（Gitea）接入 ⏳ 留待后续
- Application 示例（指向内网 git，占位）✅；验证命令与回滚方法 ✅
