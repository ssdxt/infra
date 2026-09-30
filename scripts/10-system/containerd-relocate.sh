#!/bin/bash
# ============================================================================
# 08-containerd-relocate.sh — 将本机 containerd 数据目录迁移到 /data1/containerd
#
# ⚠️ 方案脚本，【默认不执行】。等维护窗口，逐台手动跑（每次只做一台）：
#      在【目标节点】上执行：
#      bash 08-containerd-relocate.sh check              # 预检，不改动
#      bash 08-containerd-relocate.sh migrate            # 迁移本机
#      bash 08-containerd-relocate.sh rollback           # 回滚本机
#      bash 08-containerd-relocate.sh status             # 查看当前状态
#    前一台验证稳定 30 分钟后再做下一台。需要能 ssh 免密到 control-01（10.100.10.10）执行 kubectl。
#
# 前提 / 假设：
#   - /data1 为独立大盘，Longhorn 副本已占用部分空间（共用，见方案文档三规矩）
#   - containerd 配置 /etc/containerd/config.toml，root 当前为 "/var/lib/containerd"
#   - 幂等：重跑不炸；每步先检查是否已完成；迁移前自动备份
# ============================================================================
set -o pipefail

CTRL=10.100.10.10
CONF=/etc/containerd/config.toml
NEWROOT=/data1/containerd
OLDROOT=/var/lib/containerd
DATE=$(date +%Y%m%d)
BAK="${CONF}.bak.relocate.${DATE}"
STAMP=/data1/ssdxt/storage/.relocate-done.$(hostname -s)

log() { echo "[$(date '+%F %T')] $*"; }
die() { log "!!! $*"; exit 2; }
# 集群操作一律回 control-01 执行
kctl() { ssh -o StrictHostKeyChecking=no root@$CTRL \
         "export KUBECONFIG=/etc/kubernetes/admin.conf; kubectl $*"; }
MYNODE=$(ssh -o StrictHostKeyChecking=no root@$CTRL \
  "export KUBECONFIG=/etc/kubernetes/admin.conf; kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'" \
  | while read -r n; do ssh -o StrictHostKeyChecking=no root@$n hostname 2>/dev/null | grep -qx "$(hostname)" && echo "$n"; done | head -1)
[ -n "$MYNODE" ] || MYNODE=$(hostname)   # 兜底用主机名

preflight() {
  [ "$(id -u)" = 0 ] || die "必须 root 执行"
  [ -f "$CONF" ] || die "$CONF 不存在"
  df /data1 >/dev/null 2>&1 || die "/data1 不存在"
  [ "$(df -P /data1 | awk 'NR==2{print $1}')" != "$(df -P / | awk 'NR==2{print $1}')" ] \
    || die "/data1 与 / 同一文件系统，迁移无意义"
  AVAIL_GB=$(df -BG --output=avail /data1 | tail -1 | tr -dc '0-9')
  USED_GB=$(du -sg "$OLDROOT" 2>/dev/null | awk '{print $1}')
  log "/data1 可用 ${AVAIL_GB}G；/var/lib/containerd 占用 ${USED_GB}G；节点名=$MYNODE"
  [ "$AVAIL_GB" -gt $((USED_GB * 2 + 100)) ] || die "/data1 空间不足（需 2×现有占用+100G 以上余量，给 Longhorn 留水位）"
  log "预检通过"
}

do_migrate() {
  preflight
  [ -f "$STAMP" ] && { log "本机已完成迁移（$STAMP 存在）；如需重做先 rollback"; exit 0; }

  if ! grep -q "^root = \"$NEWROOT\"" "$CONF"; then
    # 1. 备份配置
    [ -f "$BAK" ] || cp -a "$CONF" "$BAK"
    log "备份: $BAK"

    # 2. drain（API 在 control-01）
    log "drain $MYNODE ..."
    kctl drain "$MYNODE" --ignore-daemonsets --delete-emptydir-data --timeout=300s \
      || die "drain 失败，本机未做任何改动，中止"

    # 3. 停 kubelet + containerd
    systemctl stop kubelet; systemctl stop containerd; sleep 3
    systemctl is-active --quiet containerd && die "containerd 未停下，中止"

    # 4. rsync 数据 + 校验
    mkdir -p "$NEWROOT"
    log "rsync $OLDROOT -> $NEWROOT ..."
    rsync -a "$OLDROOT"/ "$NEWROOT"/ || die "rsync 失败（原目录未动，直接 systemctl start containerd 即可恢复）"
    SRC_N=$(find "$OLDROOT" -xdev | wc -l); DST_N=$(find "$NEWROOT" -xdev | wc -l)
    [ "$SRC_N" = "$DST_N" ] || die "文件数不一致 src=$SRC_N dst=$DST_N，中止（直接 start containerd 恢复）"
    log "rsync 完成，文件数一致 ($DST_N)"

    # 5. 改 root 并保留旧目录（回滚数据源）
    sed -i "s|^root = .*|root = \"$NEWROOT\"|" "$CONF"
    grep -q "^root = \"$NEWROOT\"" "$CONF" || die "root 修改失败"
    mv "$OLDROOT" "${OLDROOT}.old.${DATE}"
    log "config.toml: root -> $NEWROOT；旧数据 → ${OLDROOT}.old.${DATE}"
  fi

  # 6. 起服务，任何失败走回滚
  systemctl start containerd || { log "containerd 起不来"; do_rollback; }
  systemctl start kubelet    || { log "kubelet 起不来"; do_rollback; }
  sleep 10
  systemctl is-active --quiet containerd || do_rollback
  systemctl is-active --quiet kubelet    || do_rollback
  log "镜像可见性: $(ctr -n k8s.io images ls -q | wc -l) 个"

  # 7. Ready + Pod 验证 → uncordon
  R=""
  for i in $(seq 1 36); do
    R=$(kctl get node "$MYNODE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    [ "$R" = "True" ] && break; sleep 5
  done
  [ "$R" = "True" ] || { log "节点未 Ready"; do_rollback; }
  sleep 30   # 给异常 Pod 一点暴露时间
  BAD=$(kctl get pods -A --field-selector spec.nodeName="$MYNODE" --no-headers 2>/dev/null | grep -Ev 'Running|Completed')
  if [ -n "$BAD" ]; then
    log "!!! 节点上有异常 Pod（先人工确认，必要时 rollback）："; echo "$BAD"; exit 2
  fi
  kctl uncordon "$MYNODE"
  touch "$STAMP"
  log "=== 本机迁移完成。稳定 1 周后可删除 ${OLDROOT}.old.${DATE} ==="
  log "⚠️ 三规矩见方案文档：/data1 容量巡检 cron、kubelet imageGC 对新目录失效、Longhorn 水位核对"
}

do_rollback() {
  log "回滚开始"
  kctl drain "$MYNODE" --ignore-daemonsets --delete-emptydir-data --timeout=300s 2>/dev/null
  systemctl stop kubelet; systemctl stop containerd
  # config.toml 改回
  if [ -f "$BAK" ]; then cp -a "$BAK" "$CONF"; else sed -i "s|^root = .*|root = \"$OLDROOT\"|" "$CONF"; fi
  # 数据迁回（新目录期间的增量合回旧目录）
  if [ -d "${OLDROOT}.old.${DATE}" ] && [ -d "$NEWROOT" ]; then
    rsync -a "$NEWROOT"/ "${OLDROOT}.old.${DATE}"/
    rm -rf "$NEWROOT"
    mv "${OLDROOT}.old.${DATE}" "$OLDROOT"
  fi
  systemctl start containerd && systemctl start kubelet
  sleep 10
  kctl uncordon "$MYNODE"
  rm -f "$STAMP"
  log "回滚完成：kubelet=$(systemctl is-active kubelet) containerd=$(systemctl is-active containerd) root=$(grep '^root' $CONF)"
}

do_status() {
  echo "root=$(grep -m1 '^root' $CONF 2>/dev/null)"
  echo "stamp=$(ls $STAMP 2>/dev/null || echo 无)"
  echo "old_dirs=$(ls -d ${OLDROOT}.old.* 2>/dev/null || echo 无)"
  echo "new_usage=$(du -sh $NEWROOT 2>/dev/null | awk '{print $1}')"
  echo "data1: $(df -h /data1 | awk 'NR==2{print $3" used / "$4" avail ("$5")"}')"
}

case "$1" in
  check)    preflight ;;
  migrate)  do_migrate ;;
  rollback) do_rollback ;;
  status)   do_status ;;
  *) echo "用法: $0 {check|migrate|rollback|status}   （在目标节点上执行）"; exit 1 ;;
esac
