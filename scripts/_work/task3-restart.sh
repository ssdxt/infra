#!/bin/bash
# ============================================================
#  让 rule_files 通配符改动生效: 重启 wxq-prometheus 容器
#
#  为什么必须重启:
#    /etc/prometheus/prometheus.yml 是单文件 bind mount。
#    历史上对该文件的任何编辑(sed -i / install / cp 覆盖)都换了 inode,
#    容器内进程仍绑在最初那个已被 unlink 的 inode(2097190)上,
#    所以 /-/reload 再怎么点, 读到的永远是旧内容。
#    只有重建容器才会重新按路径 bind, 看到宿主机当前文件。
#
#  复用任务1 已验证过的重建逻辑(参数从当前容器读取 + 保留新参数)。
# ============================================================
set -u
DRYRUN=${DRYRUN:-0}
BACKUP=/data1/apps/wxq-plant01-monitor/BACKUP-20260929-141202
C=wxq-prometheus

echo "===== [1] 重启前: 确认宿主机文件已正确 ====="
YML=/data1/apps/wxq-plant01-monitor/prometheus/prometheus.yml
grep -n 'rule_files' -A2 "$YML" | sed 's/^/  /'
echo "  宿主机 md5: $(md5sum "$YML" | cut -c1-32)"

# ---------- 读取当前容器事实 ----------
IMAGE=$(docker inspect $C --format '{{.Config.Image}}')
NETMODE=$(docker inspect $C --format '{{.HostConfig.NetworkMode}}')
mapfile -t ALIASES < <(docker inspect $C --format '{{range $k,$v := .NetworkSettings.Networks}}{{range $v.Aliases}}{{.}}{{"\n"}}{{end}}{{end}}' | grep -v '^$')
RESTART=$(docker inspect $C --format '{{.HostConfig.RestartPolicy.Name}}')
mapfile -t PORTS < <(docker inspect $C --format '{{range $p,$b := .HostConfig.PortBindings}}{{range $b}}{{.HostPort}}:{{$p}}{{"\n"}}{{end}}{{end}}' | sed 's#/tcp$##; s#/udp$##' | grep -v '^$')
mapfile -t ARGS < <(docker inspect $C --format '{{range .Args}}{{.}}{{"\n"}}{{end}}' | grep -v '^$')
mapfile -t MOUNTS < <(docker inspect $C --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{else}}{{.Source}}{{end}}:{{.Destination}}:{{if .RW}}rw{{else}}ro{{end}}{{"\n"}}{{end}}' | grep -v '^$')

echo
echo "===== [2] 当前容器事实(将原样保留) ====="
echo "  IMAGE=$IMAGE  NET=$NETMODE  RESTART=$RESTART"
echo "  ALIASES=${ALIASES[*]}"
echo "  PORTS=${PORTS[*]}"
echo "  ARGS(${#ARGS[@]}):"; for a in "${ARGS[@]}"; do echo "    $a"; done
echo "  MOUNTS(${#MOUNTS[@]}):"; for m in "${MOUNTS[@]}"; do echo "    $m"; done

RUNCMD=(docker run -d --name "$C")
[ -n "$RESTART" ] && RUNCMD+=(--restart "$RESTART")
RUNCMD+=(--network "$NETMODE")
for al in "${ALIASES[@]}"; do RUNCMD+=(--network-alias "$al"); done
for m in "${MOUNTS[@]}"; do RUNCMD+=(-v "$m"); done
for pb in "${PORTS[@]}"; do RUNCMD+=(-p "$pb"); done
RUNCMD+=("$IMAGE")
for a in "${ARGS[@]}"; do RUNCMD+=("$a"); done

echo
echo "===== [3] 将执行 ====="
printf ' %q' "${RUNCMD[@]}"; echo

if [ "$DRYRUN" = "1" ]; then echo "[DRYRUN] 未改动"; exit 0; fi

echo
echo "===== [4] 重建容器 ====="
docker inspect $C > "$BACKUP/inspect/pre-restart-$C.json" 2>/dev/null || true
docker rm -f "$C" || { echo "!! 删除失败"; exit 1; }
sleep 2
NEWID=$("${RUNCMD[@]}" 2>&1) || { echo "!! 启动失败: $NEWID"; exit 1; }
echo "  新容器: ${NEWID:0:12}"
sleep 12

echo
echo "===== [5] 容器状态 ====="
docker ps --filter "name=^/${C}$" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

echo
echo "===== [6] 容器内现在读到的 rule_files(应为 *.y*ml) ====="
docker exec $C sh -c 'grep -n "rule_files" -A2 /etc/prometheus/prometheus.yml' | sed 's/^/  /'
echo -n "  两侧 md5: 宿主机 $(md5sum "$YML" | cut -c1-32) / 容器 $(docker exec $C md5sum /etc/prometheus/prometheus.yml | cut -c1-32)"
echo
echo -n "  inode  : 宿主机 $(stat -c '%i' "$YML") / 容器 $(docker exec $C stat -c '%i' /etc/prometheus/prometheus.yml)"

echo
echo "===== [7] promtool 校验(应 9 个规则文件) ====="
docker exec $C promtool check config /etc/prometheus/prometheus.yml 2>&1 | grep -E 'rule files found|SUCCESS: /etc|FAILED|lint error'

echo
echo "===== [8] 接口可用性 ====="
for p in /api/v1/status/runtimeinfo /-/ready; do
  printf '  %-34s HTTP %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:9091$p)"
done
printf '  POST /api/v1/write (空体, 期望400)  HTTP %s\n' "$(curl -s -o /dev/null -w '%{http_code}' -XPOST http://127.0.0.1:9091/api/v1/write)"
