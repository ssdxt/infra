#!/bin/bash
# ============================================================
# 创建全部外部网络（与 .105 原配置完全一致）
# 所有 compose 文件都声明这些为 external, 网络被删后必须先重建本脚本
#   work_gptnetwork : bridge / 172.19.0.0/16 / 网关 172.19.0.1  (15个compose用)
#   models_network  : bridge / 172.23.0.0/16 / 网关 172.23.0.1  (qwen3大模型用)
#   1panel-network  : bridge / 172.18.0.0/16 / 网关 172.18.0.1  (windows-arm用)
# 用法: bash create_network.sh   (幂等, 已存在则跳过)
# ============================================================
set -u

create_net(){ # $1=网络名 $2=子网 $3=网关 $4=compose网络名
  local net="$1" subnet="$2" gw="$3" cnet="$4"
  if docker network inspect "$net" >/dev/null 2>&1; then
    echo "[$(date '+%F %T')] 网络 $net 已存在, 跳过创建"
    docker network inspect "$net" --format '   当前配置: driver={{.Driver}} 子网={{range .IPAM.Config}}{{.Subnet}} 网关={{.Gateway}}{{end}}'
    return 0
  fi
  docker network create \
    --driver bridge \
    --subnet "$subnet" \
    --gateway "$gw" \
    --label "com.docker.compose.network=$cnet" \
    "$net"
  echo "[$(date '+%F %T')] 已创建网络 $net: driver=bridge 子网=$subnet 网关=$gw"
  docker network inspect "$net" --format '   验证: {{range .IPAM.Config}}子网={{.Subnet}} 网关={{.Gateway}}{{end}}'
}

create_net work_gptnetwork 172.19.0.0/16 172.19.0.1 gptnetwork
create_net models_network  172.23.0.0/16 172.23.0.1 models_network
create_net 1panel-network  172.18.0.0/16 172.18.0.1 1panel-network
