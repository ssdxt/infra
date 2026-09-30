#!/bin/bash
# =============================================================================
# OceanBase 保序启动（当前机器过渡方案 · 路径2）
# -----------------------------------------------------------------------------
# 背景：现有集群数据绑定 172.17.0.2（docker0 第一个地址）。docker0 按"启动顺序"
#       分配 IP，一旦 polardb 等容器先起，oceanbase 拿不到 .2 → observer 起不来。
#
# 本脚本铁律：oceanbase 先起并确认拿到 172.17.0.2，其它容器（polardb）后起。
# 数据不动，仅控制启停顺序。彻底解决请看 README.md 路径1（compose 固定IP）。
#
# 用法：
#   ./ob-start.sh     # 按序启动 + 自检（IP 确认 + 连通性确认）
#   ./ob-stop.sh      # 停止（先 polardb 后 oceanbase，顺序无所谓但保持一致）
# =============================================================================

set -u

OB_CONTAINER="oceanbase-ce"
OB_EXPECT_IP="172.17.0.2"
OTHER_CONTAINERS="polardb"          # 空格分隔，可按需增减
WAIT_SEC=90

log() { echo "[$(date '+%F %T')] $*"; }

# 1. 先全部停掉（保证 IP 分配顺序可控）
log "stopping containers ..."
for c in $OTHER_CONTAINERS $OB_CONTAINER; do
    if docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
        docker stop -t 120 "$c" >/dev/null 2>&1 || true
    fi
done
sleep 2

# 2. oceanbase 先起
log "starting $OB_CONTAINER first ..."
docker start "$OB_CONTAINER" >/dev/null

# 3. 确认拿到期望 IP
ip=""
for i in $(seq 1 $((WAIT_SEC / 2))); do
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$OB_CONTAINER" 2>/dev/null)
    [ "$ip" = "$OB_EXPECT_IP" ] && break
    sleep 2
done
if [ "$ip" != "$OB_EXPECT_IP" ]; then
    log "ERROR: $OB_CONTAINER got IP=$ip (expect $OB_EXPECT_IP), abort before starting others!"
    log "       处理：排查是否还有别的容器占了 $OB_EXPECT_IP: docker ps -q | xargs docker inspect -f '{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'"
    exit 1
fi
log "$OB_CONTAINER got $ip OK"

# 4. 其它容器后起
for c in $OTHER_CONTAINERS; do
    if docker ps -a --format '{{.Names}}' | grep -qx "$c"; then
        log "starting $c ..."
        docker start "$c" >/dev/null
    fi
done

# 5. 连通性自检（observer 就绪需要时间，最多等 3 分钟）
log "waiting for observer ready (max 180s) ..."
ok=0
for i in $(seq 1 36); do
    if docker exec "$OB_CONTAINER" obclient -h127.0.0.1 -P2881 -uroot@test -p12345 -e "select 1" >/dev/null 2>&1; then
        ok=1; break
    fi
    sleep 5
done
if [ "$ok" = "1" ]; then
    log "SUCCESS: oceanbase is connectable (root@test)"
else
    log "WARN: not ready yet, check: docker logs $OB_CONTAINER --tail 50"
    exit 1
fi

docker ps --filter name=oceanbase --filter name=polardb --format 'table {{.Names}}\t{{.Status}}'
