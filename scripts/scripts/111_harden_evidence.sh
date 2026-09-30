#!/bin/bash
# =============================================================================
#  111 取证加固：journald 持久化 + coredump 限制 + 清理
#
#  背景：卡死问题时 journald 是 Storage=volatile，硬复位会销毁全部现场，
#        导致无法定位。本脚本只做取证能力加固，不触碰任何业务配置。
#
#  用法：
#     bash /tmp/dsh_harden.sh            # 只清理 30 天前的 core（保守）
#     bash /tmp/dsh_harden.sh --clean-all # 清空现存全部 coredump
#
#  特点：改前备份原文件、幂等（可重复执行）、每步自动核对。
# =============================================================================
set -u

STAMP=$(date +%Y%m%d-%H%M%S)
MODE="${1:-}"

echo "########## 0. 改前状态 ##########"
df -h / | awk 'NR==2{print "  根分区: 已用 "$3" / "$2" ("$5")，可用 "$4}'
echo "  coredump 占用: $(sudo du -sh /var/lib/systemd/coredump 2>/dev/null | awk '{print $1}')"
echo "  journal boot 数: $(sudo journalctl --list-boots 2>/dev/null | wc -l)"

echo
echo "########## 1. 备份原配置（幂等：已备份则不覆盖）##########"
for f in /etc/systemd/journald.conf /etc/systemd/coredump.conf; do
  if ls "${f}.bak-"* >/dev/null 2>&1; then
    echo "  已存在历史备份，跳过 $f"
  else
    sudo cp -a "$f" "${f}.bak-${STAMP}" && echo "  已备份 $f -> ${f}.bak-${STAMP}"
  fi
done

echo
echo "########## 2. journald 改为持久化 ##########"
# 先把已有的 Storage= 行改写，若不存在则用 drop-in（避免直接编辑不熟悉的文件）
if grep -qE '^\s*Storage\s*=' /etc/systemd/journald.conf; then
  sudo sed -i -E 's|^\s*Storage\s*=.*|Storage=persistent|' /etc/systemd/journald.conf
  echo "  已改写 /etc/systemd/journald.conf 的 Storage 行"
else
  sudo mkdir -p /etc/systemd/journald.conf.d
  sudo tee /etc/systemd/journald.conf.d/99-persistent.conf >/dev/null <<'EOF'
[Journal]
Storage=persistent
SystemMaxUse=1G
EOF
  echo "  已新增 drop-in /etc/systemd/journald.conf.d/99-persistent.conf"
fi
# 持久化后 RuntimeMaxUse 会导致日志落盘前被截断，补一个磁盘侧上限
if ! grep -q 'SystemMaxUse' /etc/systemd/journald.conf; then
  sudo sed -i '/^\[Journal\]/a SystemMaxUse=1G' /etc/systemd/journald.conf
  echo "  已补 SystemMaxUse=1G（磁盘侧上限，避免占满根分区）"
fi
sudo mkdir -p /var/log/journal

echo
echo "  --- 改后关键行 ---"
sudo grep -vE '^\s*#|^\s*$' /etc/systemd/journald.conf

echo
echo "########## 3. coredump 限制 ##########"
sudo tee /etc/systemd/coredump.conf >/dev/null <<'EOF'
[Coredump]
Storage=external
Compress=yes
ProcessSizeMax=2G
ExternalSizeMax=2G
MaxUse=2G
KeepFree=8G
EOF
echo "  已写入 /etc/systemd/coredump.conf（单文件上限 2G，总占用上限 2G，保留 8G 空间）"
sudo grep -vE '^\s*#|^\s*$' /etc/systemd/coredump.conf

echo
echo "########## 4. 清理现存 coredump ##########"
if [ "$MODE" = "--clean-all" ]; then
  echo "  模式：清空全部"
  sudo find /var/lib/systemd/coredump -maxdepth 1 -type f -name 'core.*' -delete
else
  echo "  模式：只清理 30 天前的（保守）"
  sudo find /var/lib/systemd/coredump -maxdepth 1 -type f -name 'core.*' -mtime +30 -delete
fi
echo "  清理后 coredump 占用: $(sudo du -sh /var/lib/systemd/coredump 2>/dev/null | awk '{print $1}')"

echo
echo "########## 5. 生效 ##########"
sudo systemctl restart systemd-journald && echo "  journald 已重启"
sudo systemctl daemon-reload && echo "  daemon-reload 完成"
# systemd-coredump 的 MaxUse 由 sysctl 参数控制，需重新加载
sudo systemctl restart systemd-sysctl 2>/dev/null

echo
echo "########## 6. 核对结果 ##########"
echo "--- journal 落盘目录 ---"
sudo ls -ld /var/log/journal 2>&1
echo "--- 当前 Storage 生效值 ---"
sudo systemctl show systemd-journald -p Storage 2>&1
systemd-analyze cat-config systemd/journald.conf 2>/dev/null | grep -E '^\s*(Storage|SystemMaxUse)' | sed 's/^/  /'
echo "--- coredump 生效值 ---"
systemd-analyze cat-config systemd/coredump.conf 2>/dev/null | grep -vE '^\s*#|^\s*$' | sed 's/^/  /'
echo "--- 磁盘 ---"
df -h / | awk 'NR==2{print "  根分区: 已用 "$3" / "$2" ("$5")，可用 "$4}'

echo
echo "########## 完成 ##########"
echo "注意：journald 变为持久化后，journalctl --list-boots 将能跨重启查看历史。"
echo "      下一次卡死复位后，请执行："
echo "        sudo journalctl -b -1 --no-pager | tail -120"
echo "      即可看到卡死前最后的内核与业务日志。"
