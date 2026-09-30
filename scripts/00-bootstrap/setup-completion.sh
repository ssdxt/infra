#!/bin/bash
# 为节点配置 kubectl/helm/crictl/nerdctl/kubeadm 的 bash 自动补全（幂等，可重复执行）
# 用法：bash setup-completion.sh
set -u

echo "=== 1. 检查 bash-completion 包"
if [ ! -f /usr/share/bash-completion/bash_completion ]; then
  echo "  未安装，尝试安装..."
  apt-get install -y bash-completion >/dev/null 2>&1 \
    || { apt-get update -qq >/dev/null 2>&1; apt-get install -y bash-completion >/dev/null 2>&1; }
fi
if [ -f /usr/share/bash-completion/bash_completion ]; then
  echo "  bash-completion 就绪"
else
  echo "  !! bash-completion 缺失（补全功能可能不完整）"
fi

echo "=== 2. 生成各工具的补全脚本到 /etc/bash_completion.d/"
mkdir -p /etc/bash_completion.d

if command -v kubectl >/dev/null 2>&1; then
  kubectl completion bash > /etc/bash_completion.d/kubectl 2>/dev/null && echo "  kubectl   OK"
else
  echo "  kubectl   未安装，跳过"
fi

if command -v helm >/dev/null 2>&1; then
  helm completion bash > /etc/bash_completion.d/helm 2>/dev/null && echo "  helm      OK"
else
  echo "  helm      未安装，跳过"
fi

if command -v crictl >/dev/null 2>&1; then
  crictl completion bash > /etc/bash_completion.d/crictl 2>/dev/null && echo "  crictl    OK"
else
  echo "  crictl    未安装，跳过"
fi

if command -v nerdctl >/dev/null 2>&1; then
  nerdctl completion bash > /etc/bash_completion.d/nerdctl 2>/dev/null && echo "  nerdctl   OK"
else
  echo "  nerdctl   未安装，跳过"
fi

if command -v kubeadm >/dev/null 2>&1; then
  kubeadm completion bash > /etc/bash_completion.d/kubeadm 2>/dev/null && echo "  kubeadm   OK"
else
  echo "  kubeadm   未安装，跳过"
fi

echo "=== 3. 写入 /root/.bashrc（幂等）"
MARK="# === k8s-tools-completion ==="
if ! grep -q "$MARK" /root/.bashrc 2>/dev/null; then
  cat >> /root/.bashrc <<'RC'

# === k8s-tools-completion ===
# admin.conf 存在（控制节点）才设置 KUBECONFIG
if [ -f /etc/kubernetes/admin.conf ]; then
  export KUBECONFIG=/etc/kubernetes/admin.conf
fi
# 加载 bash-completion 框架
if [ -f /usr/share/bash-completion/bash_completion ]; then
  . /usr/share/bash-completion/bash_completion
fi
# 加载各工具补全
for _f in /etc/bash_completion.d/kubectl /etc/bash_completion.d/helm \
          /etc/bash_completion.d/crictl /etc/bash_completion.d/nerdctl \
          /etc/bash_completion.d/kubeadm; do
  [ -f "$_f" ] && . "$_f"
done
# k 作为 kubectl 的简写
alias k=kubectl
if declare -F __start_kubectl >/dev/null 2>&1; then
  complete -o default -F __start_kubectl k
fi
# === end k8s-tools-completion ===
RC
  echo "  /root/.bashrc 已写入"
else
  echo "  /root/.bashrc 已存在该配置，跳过"
fi

echo "=== 4. 验证（模拟新开一个登录 shell）"
bash -lc 'echo -n "  kubectl 补全: "; complete -p kubectl 2>/dev/null | head -c 60 || echo "无"'
echo ""
bash -lc 'echo -n "  k 别名补全:  "; complete -p k 2>/dev/null | head -c 60 || echo "无"'
echo ""
bash -lc 'echo -n "  helm 补全:    "; complete -p helm 2>/dev/null | head -c 60 || echo "无"'
echo ""
bash -lc 'echo -n "  KUBECONFIG:   "; echo "${KUBECONFIG:-未设置}"'
echo "Done."
