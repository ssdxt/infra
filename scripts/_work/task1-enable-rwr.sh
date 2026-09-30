#!/bin/bash
# ============================================================
#  任务1: 给 plant01 的 wxq-prometheus 加 --web.enable-remote-write-receiver
#
#  背景: docker-compose.yaml 已丢失(--time-style 显示目录自 2026-09-28 14:30 未变,
#        compose 仍记录旧路径), 无法用 docker compose up -d。
#        因此【只重建 prometheus 单个容器】, 其余 10 个容器一律不动。
#
#  命令来源: 直接读【当前运行容器】的镜像/挂载/端口/网络别名/参数,故与原状零漂移。
#  关键: --network-alias prometheus 必须保留(prometheus.yml 里用 victoria-metrics /
#        alertmanager 服务名连接, 靠的就是 compose 给的网络别名)
#
#  用法: bash /tmp/task1-enable-rwr.sh          # 真实执行
#        DRYRUN=1 bash /tmp/task1-enable-rwr.sh  # 只打印命令
#        ROLLBACK=1 bash /tmp/task1-enable-rwr.sh # 回滚(去掉新参数)
# ============================================================
set -u
DRYRUN=${DRYRUN:-0}
ROLLBACK=${ROLLBACK:-0}
BACKUP=/data1/apps/wxq-plant01-monitor/BACKUP-20260929-141202
NEWFLAG='--web.enable-remote-write-receiver'
C=wxq-prometheus

command -v docker >/dev/null || { echo "!! docker 不可用"; exit 1; }

# ---------- 1. 从当前容器读出全部事实 ----------
IMAGE=$(docker inspect $C --format '{{.Config.Image}}')
NETMODE=$(docker inspect $C --format '{{.HostConfig.NetworkMode}}')
# 网络别名逐个换行输出(不要用 json/Go-slice 形式, 否则会被当成一个带空格的别名)
mapfile -t ALIASES < <(docker inspect $C --format '{{range $k,$v := .NetworkSettings.Networks}}{{range $v.Aliases}}{{.}}{{"\n"}}{{end}}{{end}}' | grep -v '^$')
RESTART=$(docker inspect $C --format '{{.HostConfig.RestartPolicy.Name}}')
# 端口: 去掉 /tcp 后缀
mapfile -t PORTS < <(docker inspect $C --format '{{range $p,$b := .HostConfig.PortBindings}}{{range $b}}{{.HostPort}}:{{$p}}{{"\n"}}{{end}}{{end}}' | sed 's#/tcp$##; s#/udp$##' | grep -v '^$')

echo "=== 当前运行容器事实 ==="
echo "  IMAGE   = $IMAGE"
echo "  NETMODE = $NETMODE"
echo "  ALIASES = ${ALIASES[*]}  (共 ${#ALIASES[@]} 个)"
echo "  RESTART = $RESTART"
echo "  PORTS   = ${PORTS[*]}"
echo

# 参数数组(逐行读取,保留空格)
mapfile -t ARGS < <(docker inspect $C --format '{{range .Args}}{{.}}{{"\n"}}{{end}}' | grep -v '^$')
echo "=== 原始参数 (${#ARGS[@]} 个) ==="
for a in "${ARGS[@]}"; do echo "  $a"; done
echo

# 挂载数组: 用 volume 名(而非 host path)以便精确还原 named volume
mapfile -t MOUNTS < <(docker inspect $C --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}:{{if .RW}}rw{{else}}ro{{end}}{{"\n"}}{{end}}' | grep -v '^$')
echo "=== 挂载 (${#MOUNTS[@]} 个) ==="
for m in "${MOUNTS[@]}"; do echo "  $m"; done
echo

# ---------- 2. 组装最终参数 ----------
mapfile -t FINALARGS < <(
  for a in "${ARGS[@]}"; do
    [ "$a" = "$NEWFLAG" ] && continue          # 幂等: 先剔除, 再按需追加
    echo "$a"
  done
  [ "$ROLLBACK" = "1" ] || echo "$NEWFLAG"
)

# ---------- 3. 组装 docker run ----------
RUNCMD=(docker run -d --name "$C")
[ -n "$RESTART" ] && RUNCMD+=(--restart "$RESTART")
RUNCMD+=(--network "$NETMODE")
# 保留全部网络别名(compose 会在容器名之外再加服务名别名, prometheus.yml 依赖它)
for al in "${ALIASES[@]}"; do RUNCMD+=(--network-alias "$al"); done
for m in "${MOUNTS[@]}"; do RUNCMD+=(-v "$m"); done
for pb in "${PORTS[@]}"; do RUNCMD+=(-p "$pb"); done
RUNCMD+=("$IMAGE")
for a in "${FINALARGS[@]}"; do RUNCMD+=("$a"); done

echo "=== 即将执行的命令 ==="
printf ' %q' "${RUNCMD[@]}"; echo; echo

if [ "$DRYRUN" = "1" ]; then
  echo "[DRYRUN] 未做任何改动。"
  exit 0
fi

# ---------- 4. 二次备份当前参数 ----------
docker inspect $C > "$BACKUP/inspect/pre-change-$C.json" 2>/dev/null || true

# ---------- 5. 重建 ----------
echo "=== 停止并删除旧容器 ==="
docker rm -f "$C" || { echo "!! 删除失败"; exit 1; }
sleep 2

echo "=== 启动新容器 ==="
NEWID=$("${RUNCMD[@]}" 2>&1)
RC=$?
if [ $RC -ne 0 ] || [ -z "$NEWID" ]; then
  echo "!! 启动失败 (rc=$RC): $NEWID"
  echo "!! 立即回滚到无新参数的原始配置"
  ROLLBACK=1 bash "$0"
  echo
  echo "=== 回滚后状态 ==="
  docker ps -a --filter "name=^/${C}$" --format 'table {{.Names}}\t{{.Status}}'
  exit 1
fi
echo "  新容器 ID: ${NEWID:0:12}"

sleep 8
echo
echo "=== 容器状态 ==="
docker ps -a --filter "name=^/${C}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
