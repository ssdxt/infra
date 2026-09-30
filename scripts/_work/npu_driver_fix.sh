#!/bin/bash
# NPU 驱动修复：绕过 GCC 9.3.1 的 -Werror=maybe-uninitialized 误报
set -u
cd /deploy/driver/Ascend || exit 1
RUN=./Ascend-hdk-310p-npu-driver_24.1.0.1_linux-aarch64.run
LOG=/tmp/npu_driver_fix.log

echo "########## 0. 前置检查 ##########"
hostname; uname -r
echo "  KCFLAGS 当前值: ${KCFLAGS:-<空>}"
echo "  dkms 里 davinci 状态: $(dkms status 2>/dev/null | grep -i davinci || echo '无')"

echo
echo "########## 1. 清理手工编译的临时产物 ##########"
rm -rf /tmp/drv_extract /tmp/drv_build*.log
echo "  已清理"

echo
echo "########## 2. 卸载旧驱动残留（失败也无妨）##########"
$RUN --uninstall 2>&1 | tail -8 || echo "  卸载返回非0（可能本就没装）"
echo "  dkms 状态: $(dkms status 2>/dev/null | grep -i davinci || echo '无 davinci')"

echo
echo "########## 3. 设置 KCFLAGS（关键）##########"
export KCFLAGS="-Wno-error=maybe-uninitialized -Wno-maybe-uninitialized"
echo "  KCFLAGS=$KCFLAGS"
echo "  验证 export 生效: $(env | grep '^KCFLAGS=')"

echo
echo "########## 4. 开始安装驱动（最长 20 分钟）##########"
: > $LOG
timeout 1200 $RUN --full > $LOG 2>&1
RC=$?
echo "  安装退出码: $RC"

echo
echo "########## 5. 安装日志里的关键行 ##########"
grep -nE "ERROR|error|failed|Failed|成功|success|Success|Percentage" $LOG 2>/dev/null | tail -25

echo
echo "########## 6. 日志尾部 30 行 ##########"
tail -30 $LOG 2>/dev/null

echo
echo "########## 7. 安装结果验证 ##########"
echo "--- dkms 状态 ---"
dkms status 2>/dev/null | grep -i davinci || echo "  无 davinci"
echo "--- 内核模块 ---"
lsmod 2>/dev/null | grep -E "drv_|ascend" | head -15
echo "  ascend 模块数: $(lsmod 2>/dev/null | grep -cE 'drv_|ascend')"
echo "--- 设备节点 ---"
ls -la /dev/davinci* /dev/devmm_svm /dev/hisi_hdc 2>&1 | head -8
echo "--- npu-smi ---"
npu-smi info 2>&1 | head -20
