#!/bin/bash
###############################################################################
#  CANN 8.1.RC1 工具链安装失败 —— 诊断 / 修复 / 验证 / 回滚
#  目标机: kzzk-pc (192.168.21.111)  银河麒麟桌面 V10 国防版 / aarch64
#
#  用法:
#     bash CANN修复.sh diag       # 只诊断，不改任何东西（先跑这个）
#     bash CANN修复.sh fix        # 装系统 pip3 → 清残留 → 重装 toolkit
#     bash CANN修复.sh verify     # 装完验证
#     bash CANN修复.sh rollback   # 卸载回滚
#
#  从 Windows 复制过去后先去掉 CRLF，否则会报 $'\r': 未找到命令:
#     sed -i 's/\r$//' CANN修复.sh
###############################################################################
#
#  ============================ 病 因 链 ============================
#
#  报错原文:
#     compiler_custom_install.sh:行100: pip3：未找到命令
#     [ERROR] compiler notify latest manager remove softlink in multi version
#             uninstall failed!
#     ERR_NO:0x0090; ERR_DES:failed to uninstall package.
#     [Toolkit] delete operation, the directory
#             /usr/local/Ascend/ascend-toolkit is not empty.
#     exit code 4
#
#  链路:
#     系统 python3 = 3.8.10 且【没有 pip】(/usr/bin/python3 -m ensurepip → No module)
#     pip3 只存在于 /root/anaconda3/bin/  (python 3.11)
#           ↓
#     CANN 的 compiler_custom_install.sh 第 100 行【字面调用 pip3】
#           ↓
#     安装时 PATH 里没有 anaconda → 找不到 pip3 → compiler 装失败
#           ↓
#     触发自动回滚，但 compiler 卸载也失败(softlink 移除失败)
#           ↓
#     残留 893MB: /usr/local/Ascend/ascend-toolkit/{8.1.RC1, latest}
#                 version.cfg 为空，顶层没有 script/uninstall.sh
#
#  ==================== 为什么 .bashrc 救不了这个 ====================
#
#  (本机实测结论，别踩坑)
#
#  1) sudo <命令> 形式下 /root/.bashrc 永远不会生效，原因有三层:
#       a. sudo cmd 直接 exec 命令，根本不经过 bash → .bashrc 不会被读
#       b. sudoers 有 env_reset + secure_path，强制覆盖 PATH:
#            /etc/sudoers:11  Defaults secure_path="/usr/local/sbin:/usr/local/bin:
#                             /usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
#       c. 即便经过 bash: .bashrc 的非交互早退守卫会 return，
#          而 conda init 块在第 103~116 行(文件最末尾)，正好被跳过
#
#  2) 实测矩阵(本机真实结果):
#       sudo bash -c 'command -v pip3'   → NOT_FOUND
#       sudo sh   -c 'command -v pip3'   → NOT_FOUND
#       sudo bash -lc 'command -v pip3'  → NOT_FOUND   ← 登录 shell 也救不了!
#       sudo -E bash -c 'command -v pip3'→ NOT_FOUND   ← secure_path 赢
#       sudo -H bash -c 'command -v pip3'→ NOT_FOUND
#       sudo bash -ic 'command -v pip3'  → /root/anaconda3/bin/pip3   ✓(靠交互式)
#       sudo env PATH=/root/anaconda3/bin:$PATH bash -c 'command -v pip3'
#                                        → /root/anaconda3/bin/pip3   ✓
#       sudo -i 'command -v pip3'        → bash: command -v pip3：未找到命令
#       sudo -s 'command -v pip3'        → 同上
#         ↑ 坑! sudo -i / -s 带参数时不会自动加 -c，把整串当脚本文件名了。
#           要交互式进去敲:   sudo -i   然后手打命令
#
#  3) 【关键】不要把 anaconda 的 pip3 软链到 /usr/local/bin/pip3 了事：
#       pip3 = anaconda python 3.11 → 依赖包装进
#                                   /root/anaconda3/lib/python3.11/site-packages
#       而 CANN 后续脚本调用的是系统 python3 (3.8) → import 不到
#       → 更隐蔽的坏。必须让 pip3 对应【系统 python3.8】。
#
#  4) 所以正解 = 让 /usr/bin/pip3 存在(它本来就在 secure_path 里):
#       apt-get install -y python3-pip
#
#  ========================== 环 境 事 实 ==========================
#   apt 源可用: http://archive.kylinos.cn/kylin/KYLIN-ALL V10-GFB-020
#   源里有包:   python3-pip  20.0.2-5kylin1.8  (universe/arm64)
#   注: https://dl.google.com/linux/chrome-stable/deb 源已过期，
#       apt update 会刷 E: 噪音，但不阻塞安装。想清掉见 fix() 里注释。
#
#  ========================== 安 装 顺 序 ==========================
#   ① Ascend-hdk-310p-npu-driver      ✅ 已装(24.1.0.1，需 KCFLAGS 抑制 GCC 误报)
#   ② Ascend-hdk-310p-npu-firmware    ✅ 已在位(7.5.0.5.220)
#   ③ Ascend-cann-toolkit             ← 本次要修的就是它
#   ④ Ascend-cann-kernels-310p        ← 算子包，必装
#   ⑤ Ascend-cann-nnal (ATB)          ← MindIE 依赖，必装
#   ⑥ Ascend-cann-nnrt                ← 按需(最小运行时)
###############################################################################

set +e

ASCEND_DIR=/deploy/driver/Ascend
TOOLKIT_DIR=/usr/local/Ascend/ascend-toolkit
TOOLKIT_RUN=$ASCEND_DIR/Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run
KERNELS_RUN=$(ls $ASCEND_DIR/Ascend-cann-kernels-310p_*.run 2>/dev/null | head -1)
NNAL_RUN=$ASCEND_DIR/Ascend-cann-nnal_8.1.RC1_linux-aarch64.run
NNRT_RUN=$ASCEND_DIR/Ascend-cann-nnrt_8.1.RC1_linux-aarch64.run

hr() { echo "-------------------------------------------------------------------"; }
say() { echo; echo ">>> $*"; hr; }

#==============================================================================
# diag —— 只读诊断，不改任何东西
#==============================================================================
diag() {
  say "1) pip3 现状"
  echo "  系统 python3 : $(command -v python3)  $(python3 -V 2>&1)"
  echo -n "  系统 pip 模块: "; python3 -m pip --version 2>&1 | head -1
  echo -n "  /usr/bin/pip3: "; ls -l /usr/bin/pip3 2>&1
  echo -n "  anaconda pip3: "; ls -l /root/anaconda3/bin/pip3 2>&1
  echo -n "  当前 PATH 下 : "; command -v pip3 || echo NOT_FOUND
  echo -n "  secure_path 下: "; sudo bash -c 'command -v pip3 || echo NOT_FOUND'

  say "2) 源里有没有 python3-pip"
  apt-cache policy python3-pip 2>&1 | head -6

  say "3) /usr/local/Ascend 全貌（注意别误删 driver/firmware）"
  ls -la /usr/local/Ascend/ 2>&1

  say "4) toolkit 残留明细"
  du -sh $TOOLKIT_DIR 2>/dev/null
  find $TOOLKIT_DIR -maxdepth 2 -type d 2>/dev/null | head -20
  echo "--- latest 软链指向 ---"
  ls -ld $TOOLKIT_DIR/latest 2>&1
  echo "--- version.cfg 内容(空=装了一半) ---"
  cat $TOOLKIT_DIR/latest/version.cfg 2>&1
  echo "--- 自带卸载脚本 ---"
  ls -l $TOOLKIT_DIR/*/cann_uninstall.sh $TOOLKIT_DIR/*/compiler/script/uninstall.sh 2>&1

  say "5) 环境变量是否已被写入"
  grep -n "Ascend\|ascend-toolkit" /root/.bashrc /etc/profile /etc/profile.d/*.sh 2>/dev/null | head
  echo "--- ld.so.conf.d 里的昇腾项 ---"
  grep -rln "Ascend" /etc/ld.so.conf.d/ 2>/dev/null || echo "  (无)"

  say "6) 驱动侧确认(应为已修复状态)"
  npu-smi info 2>&1 | head -12

  say "7) 待装安装包是否齐全"
  ls -lh $ASCEND_DIR/*.run 2>&1
}

#==============================================================================
# fix —— 装系统 pip3 → 清残留 → 重装 toolkit
#==============================================================================
fix() {
  [ "$(id -u)" = "0" ] || { echo "必须以 root 执行"; exit 1; }
  umask 022      # CANN 以 root 安装且 umask 偏严时目录会建成 750，
                 # 而 kernels-310p 的独立校验要求 755 -> "permission is too small"

  say "STEP 1/4  安装系统 python3-pip（得到 /usr/bin/pip3，本就在 secure_path 内）"
  # 可选：先屏蔽已过期的 google chrome 源，消掉 apt update 的 E: 噪音
  #   grep -rl "dl.google.com" /etc/apt/sources.list.d/ 2>/dev/null | \
  #     xargs -r sed -i 's|^deb |#deb |'
  apt-get update 2>&1 | tail -3
  apt-get install -y python3-pip python3-dev 2>&1 | tail -12
  echo "--- 验证 ---"
  ls -l /usr/bin/pip3
  /usr/bin/pip3 --version
  echo -n "  secure_path 下可见性: "
  sudo bash -c 'command -v pip3 || echo NOT_FOUND'     # 期望 /usr/bin/pip3
  # 若 /usr/bin/pip3 版本过老(20.0.2)导致后续装包失败，再执行：
  #   /usr/bin/pip3 install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple

  say "STEP 2/4  清理 toolkit 残留（只删 ascend-toolkit，保留 driver/firmware）"
  if [ -d "$TOOLKIT_DIR" ]; then
    du -sh $TOOLKIT_DIR
    # 2.1 先走官方卸载脚本，处理 compiler 的 softlink
    for u in $TOOLKIT_DIR/*/cann_uninstall.sh; do
      [ -f "$u" ] && { echo "--- 执行 $u ---"; sh "$u" 2>&1 | tail -10; }
    done
    # 2.2 官方 .run 的卸载开关（部分版本支持 --uninstall）
    [ -f "$TOOLKIT_RUN" ] && { echo "--- 尝试 $TOOLKIT_RUN --uninstall ---"
      "$TOOLKIT_RUN" --uninstall 2>&1 | tail -6; }
    # 2.3 收尾：直接删（version.cfg 为空说明没有可用的卸载信息，只能硬删）
    echo "--- 硬删残留 ---"
    rm -rf $TOOLKIT_DIR
    echo "  删除后: $(ls -d $TOOLKIT_DIR 2>&1)"
  else
    echo "  无残留，跳过"
  fi

  # 权限归一化：CANN 以 root 安装时目录默认 750，而 kernels-310p / nnal
  # 内部的权限校验要求 755，不同包之间校验不一致，必装前统一放开。
  # X = 只对目录和已可执行的文件加 x，不会把普通文件变成可执行。
  say "权限归一化（目录 755 / 文件放开读执行位）"
  chmod 755 /usr/local/Ascend "$TOOLKIT_DIR" "$TOOLKIT_DIR"/8.1.RC1 2>/dev/null
  chmod -R u+rwX,go+rX "$TOOLKIT_DIR" 2>/dev/null
  echo "  opp 目录权限: $(stat -c '%a' $TOOLKIT_DIR/8.1.RC1/opp 2>/dev/null || echo '<不存在>')  (应为 755)"
  echo "  /etc/ld.so.conf.d 相关项:"; grep -rln Ascend /etc/ld.so.conf.d/ 2>/dev/null || echo "    (无)"

  say "STEP 3/4  重装 CANN toolkit"
  cd $ASCEND_DIR || exit 1
  ./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --install --quiet 2>&1 | tail -30
  rc=${PIPESTATUS[0]}
  echo "--- 安装退出码: $rc ---"
  [ "$rc" = "0" ] || {
    echo "!! 仍失败。常见后续原因:"
    echo "   - pip 20.0.2 太老 → /usr/bin/pip3 install -U pip -i https://pypi.tuna.tsinghua.edu.cn/simple"
    echo "   - 缺 python3-dev(已在本脚本 STEP1 安装)"
    echo "   - 磁盘空间不足: df -h /usr/local"
    echo "   - /usr/local/Ascend 残留没删干净: rm -rf $TOOLKIT_DIR 后重试"
    return 1
  }

  # 关键：toolkit 刚装完的目录是 750，必须在装算子包之前再归一化一次，
  # 否则 kernels-310p 会在 "[ERROR]: The given dir, or its parents,
  # permission is invalid." 处直接失败。
  say "重装后再归一化一次权限（算子包要求 755，toolkit 默认给 750）"
  chmod 755 /usr/local/Ascend "$TOOLKIT_DIR" "$TOOLKIT_DIR"/8.1.RC1 2>/dev/null
  chmod -R u+rwX,go+rX "$TOOLKIT_DIR" 2>/dev/null
  echo "  opp 目录权限: $(stat -c '%a' $TOOLKIT_DIR/8.1.RC1/opp 2>/dev/null || echo '<不存在>')  (应为 755)"

  say "STEP 4/4  安装算子包 / ATB (nnal)"
  for pkg in "$KERNELS_RUN" "$NNAL_RUN"; do
    if [ -f "$pkg" ]; then
      echo "--- $(basename $pkg) ---"
      "$pkg" --install --quiet 2>&1 | tail -8
      echo "    退出码: ${PIPESTATUS[0]}"
      # 每装一个包再归一化一次，避免下一个包撞同一面墙
      chmod -R u+rwX,go+rX "$TOOLKIT_DIR" /usr/local/Ascend/nnal 2>/dev/null
    else
      echo "!! 缺包: $pkg"
    fi
  done
  # 最小运行时(按交付文档要求再装，非必须):
  #   [ -f "$NNRT_RUN" ] && $NNRT_RUN --install --quiet

  say "把 CANN 环境变量写进 /root/.bashrc（只写一次）"
  if ! grep -q "ascend-toolkit/set_env.sh" /root/.bashrc 2>/dev/null; then
    cat >> /root/.bashrc <<'EOF'

# >>> Ascend CANN >>>
source /usr/local/Ascend/ascend-toolkit/set_env.sh
# <<< Ascend CANN <<<
EOF
    echo "  已写入"
  else
    echo "  已存在，跳过"
  fi

  echo
  echo "=== fix 完成，接着执行: bash $0 verify ==="
}

#==============================================================================
# verify —— 安装后验证
#==============================================================================
verify() {
  say "1) 目录与版本"
  ls -ld $TOOLKIT_DIR $TOOLKIT_DIR/latest 2>&1
  echo "--- version.cfg ---"
  cat $TOOLKIT_DIR/latest/version.cfg 2>&1
  echo "--- 顶层结构 ---"
  ls $TOOLKIT_DIR/latest 2>&1

  say "2) 加载环境变量"
  source $TOOLKIT_DIR/set_env.sh 2>&1
  echo "  ASCEND_HOME_PATH = ${ASCEND_HOME_PATH:-<未设置>}"
  echo "  ASCEND_OPP_PATH  = ${ASCEND_OPP_PATH:-<未设置>}"
  echo "  LD_LIBRARY_PATH 包含 toolkit: $(echo $LD_LIBRARY_PATH | tr ':' '\n' | grep -c ascend-toolkit) 项"

  say "3) pyACL 能否 import（这是 pip3 问题的最终验证）"
  python3 -c "import acl; print('  acl OK ->', acl.__file__)" 2>&1
  python3 -c "import numpy; print('  numpy', numpy.__version__)" 2>&1
  echo -n "  用 anaconda python 再测(应也能 import，不是必须): "
  /root/anaconda3/bin/python3 -c "import acl; print('anaconda acl OK')" 2>&1 | tail -1

  say "4) ATC 模型转换工具"
  command -v atc && atc --version 2>&1 | tail -5

  say "5) 算子包 / ATB"
  ls $TOOLKIT_DIR/latest/opp/built-in/op_impl/ 2>&1 | head
  ls /usr/local/Ascend/nnal/atb 2>&1 | head -5
  find / -maxdepth 6 -name "libatb*.so" 2>/dev/null | head -3

  say "6) 驱动/芯片侧"
  npu-smi info 2>&1 | head -12

  say "7) 交叉确认 pip3 归属"
  echo -n "  pip3 -> "; command -v pip3
  echo -n "  对应解释器 -> "; pip3 --version
}

#==============================================================================
# rollback —— 卸载回滚
#==============================================================================
rollback() {
  say "回滚：卸载 toolkit（driver / firmware 不动）"
  [ -f "$TOOLKIT_RUN" ] && "$TOOLKIT_RUN" --uninstall 2>&1 | tail -8
  for u in $TOOLKIT_DIR/*/cann_uninstall.sh; do
    [ -f "$u" ] && sh "$u" 2>&1 | tail -5
  done
  rm -rf $TOOLKIT_DIR
  echo "  已删除 $TOOLKIT_DIR"
  echo "--- 清理 /root/.bashrc 中的 CANN 环境变量 ---"
  sed -i '/>>> Ascend CANN >>>/,/<<< Ascend CANN <<</d' /root/.bashrc
  grep -n "Ascend" /root/.bashrc || echo "  已清理干净"
}

#==============================================================================
case "$1" in
  diag)     diag ;;
  fix)      fix ;;
  verify)   verify ;;
  rollback) rollback ;;
  *) cat <<EOF
CANN 8.1.RC1 工具链修复脚本

  bash $0 diag      只诊断，不改任何东西（请先跑这个）
  bash $0 fix       装系统 pip3 → 清残留 → 重装 toolkit + 算子包
  bash $0 verify    安装后验证
  bash $0 rollback  卸载回滚

病因: 系统 python3.8 无 pip，pip3 只在 anaconda(3.11) 里；
      CANN 安装脚本字面调用 pip3 → 找不到 → compiler 装失败 → 回滚不干净。
正解: apt-get install -y python3-pip  （/usr/bin/pip3 本就在 secure_path 内）
避坑: 不要把 anaconda 的 pip3 软链过去了事，依赖会装进 3.11，CANN 用 3.8 读不到。
EOF
    ;;
esac
