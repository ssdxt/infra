#!/bin/bash
# ==============================================================================
#  景嘉微 JM9230 显卡 3D 加速失效 —— 诊断 + 修复 + 回滚
# ==============================================================================
#  适用机器 : Kylin V10 Server (GFB), 内核 4.19.90-52.23.v2207.gfb08.ky10.aarch64
#  显卡     : 景嘉微 JM9230 (PCI 0731:9230), 驱动 mwv207 1.4.4
#  症状     : /proc/gpuinfo_0 里 "GPU Utilize Rate(3d)" 恒为 0.00%
#
# ------------------------------------------------------------------------------
#  【完整分析链路】—— 每一步都是实际验证过的
# ------------------------------------------------------------------------------
#
#  第 1 层：看现象
#    $ cat /proc/gpuinfo_0
#        GPU Utilize Rate(2d)        : 2.01%      <- 2D 走硬件，正常
#        GPU Utilize Rate(3d)        : 0.00%      <- 3D 恒为零，异常
#
#  第 2 层：问 OpenGL 到底在用谁渲染
#    $ DISPLAY=:0 glxinfo -B
#        libGL error: MESA-LOADER: failed to open jmgpu (search paths /usr/lib64/dri)
#        libGL error: failed to load driver: jmgpu
#        OpenGL renderer string: llvmpipe (LLVM 10.0.1, 128 bits)   <- CPU 软渲染！
#        Accelerated: no
#    => 3D 根本没上显卡，在拿 CPU 算。
#
#  第 3 层：Xorg 侧的原始报错
#    $ grep -iE "AIGLX|swrast" /var/log/Xorg.0.log
#        (EE) AIGLX error: dlopen of /usr/lib64/dri/jmgpu_dri.so failed
#             (libGLX_mwv207.so.0: cannot open shared object file: No such file or directory)
#        (EE) AIGLX error: unable to load driver jmgpu
#        (II) IGLX: Loaded and initialized swrast              <- 被迫回退软件渲染
#    => 问题在 Mesa 的 DRI 驱动 jmgpu_dri.so 加载失败。
#
#  第 4 层：jmgpu_dri.so 到底缺什么
#    $ ldd /usr/lib64/dri/jmgpu_dri.so | grep "not found"
#        libGLX_mwv207.so.0 => not found
#        libJMC.so          => not found
#    $ readelf -d /usr/lib64/dri/jmgpu_dri.so | grep NEEDED
#        NEEDED  Shared library: [libGLX_mwv207.so.0]
#        NEEDED  Shared library: [libdrm_jmgpu.so.1.0.0]     <- 这个在，OK
#        NEEDED  Shared library: [libJMC.so]
#
#  第 5 层：这两个库该由谁提供、去哪了
#    $ rpm -ql mwv207-dev | grep -E "\.so"
#        /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0            <- 包说提供这些
#        /usr/lib64/mwv207/libJMC.so
#        ... 共 15 个
#    $ ls -d /usr/lib64/mwv207
#        ls: cannot access '/usr/lib64/mwv207': No such file or directory   <- 目录整个没了！
#    $ rpm -V mwv207-dev
#        missing  /usr/lib64/mwv207/libCLC.so
#        missing  /usr/lib64/mwv207/libGLX_mwv207.so.1.2.0
#        missing  /usr/lib64/mwv207/libJMC.so
#        ... 共 15 个 missing
#    => 决定性证据：包状态是「已安装」，但文件全丢了。
#
#  第 6 层：为什么 2D 正常、只有 3D 不行
#    2D 走的是 Xorg 的 DDX 驱动  /usr/lib64/xorg/modules/drivers/mwv207_drv.so   <- 文件在，OK
#    3D 走的是 Mesa -> jmgpu_dri.so -> libGLX_mwv207.so.0 + libJMC.so           <- 依赖缺失，挂
#    两者是完全独立的两条路径，所以只有 3D 受影响。
#
#  第 7 层：根因归纳
#    mwv207-dev 包在安装时 %post 脚本执行失败（它引用了 Debian 系的 /etc/bash.bashrc，
#    而本机是 RPM 系 Kylin，没有这个文件），导致 /usr/lib64/mwv207/ 下 15 个用户态
#    GL 库没有落地；同时 /usr/lib64/mwv207 也没被写进 ld 搜索路径。
#    => Mesa 找不到 jmgpu_dri.so 的依赖 -> 加载失败 -> 回退 llvmpipe -> 3D 恒为 0%。
#
# ------------------------------------------------------------------------------
#  【重要坑点】修的时候注意
# ------------------------------------------------------------------------------
#  1. 直接 `rpm -Uvh --force` 重装【无效】。实测 rpm 报告成功但文件依然不落地，
#     因为 %post 还是失败。必须用 rpm2cpio 手工解包提取。
#  2. 驱动包里的文件名和 SONAME 不一致：
#        libGLX_mwv207.so.1.2.0  -> SONAME = libGLX_mwv207.so.0
#        libEGL_mwv207.so.1.5.0  -> SONAME = libEGL_mwv207.so.0
#     而 jmgpu_dri.so 要的是 SONAME（.so.0）。这一步不用手工建软链接——
#     只要把目录加进 ld 搜索路径再 ldconfig，ldconfig 会按 SONAME 自动建好。
#  3. 驱动包自带的官方切换脚本 /opt/mwv207/usr/sbin/switch-gl.sh 在本机【跑不了】，
#     它内部用 `dpkg -l` 判断，而本机是 RPM 系（dpkg: command not found）。
#  4. 修完必须重启 lightdm / Xorg，AIGLX 只在启动时加载一次 DRI 驱动。
#
# ------------------------------------------------------------------------------
#  【使用方法】
# ------------------------------------------------------------------------------
#   只诊断不修改 :  bash 本脚本 diag
#   执行修复     :  bash 本脚本 fix
#   修复后验证   :  bash 本脚本 verify
#   回滚         :  bash 本脚本 rollback
#   不带参数     :  只做诊断（安全，不做任何修改）
# ==============================================================================

set -u

RPM_PKG="/root/JM9230/mwv207-dev-1.4.4-release.ky3.aarch64.rpm"
LIBDIR="/usr/lib64/mwv207"
LDCONF="/etc/ld.so.conf.d/mwv207-aarch64.conf"
DRI="/usr/lib64/dri/jmgpu_dri.so"
EXTRACT_DIR="/tmp/mwv207-extract-$$"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="/root/mwv207-fix-backup-$TS"

case "${1:-diag}" in

# ==============================================================================
#  诊断（只读，不做任何修改）
# ==============================================================================
diag)
  echo "==================== 1. 现象：3D 利用率 ===================="
  grep -iE "Utilize|Temperature|Memory Remain" /proc/gpuinfo_0 2>&1

  echo
  echo "==================== 2. OpenGL 实际渲染器 ===================="
  echo "（期望看到 mwv207；若显示 llvmpipe 就是软件渲染）"
  DISPLAY=:0 glxinfo -B 2>&1 | head -14

  echo
  echo "==================== 3. Xorg 的 AIGLX 报错 ===================="
  grep -iE "AIGLX|swrast|Initialized.*GLX|unable to load driver" /var/log/Xorg.0.log 2>/dev/null | tail -10

  echo
  echo "==================== 4. jmgpu_dri.so 缺哪些依赖 ===================="
  echo "--- ldd 的 not found ---"
  ldd "$DRI" 2>&1 | grep -i "not found" || echo "  （无缺失）"
  echo "--- not found 计数 ---"
  ldd "$DRI" 2>&1 | grep -c "not found"
  echo "--- ELF NEEDED 列表 ---"
  readelf -d "$DRI" 2>/dev/null | grep -iE "NEEDED"

  echo
  echo "==================== 5. 提供这些库的包是否完整 ===================="
  echo "--- mwv207-dev 包状态 ---"
  rpm -q mwv207-dev 2>&1
  echo "--- rpm -V 校验（missing 就是丢了）---"
  rpm -V mwv207-dev 2>&1 | head -25
  echo "--- missing 条目数 ---"
  rpm -V mwv207-dev 2>&1 | grep -c "^missing"

  echo
  echo "==================== 6. 库目录与搜索路径 ===================="
  printf "  %-28s " "$LIBDIR"
  if [ -d "$LIBDIR" ]; then echo "存在 ($(ls $LIBDIR 2>/dev/null | wc -l) 项)"; else echo "不存在  <-- 问题所在"; fi
  echo "--- ld 搜索路径里有没有 mwv207 ---"
  grep -rl "mwv207" /etc/ld.so.conf.d/ 2>/dev/null || echo "  没有配置文件包含 mwv207"
  echo "--- ldconfig 缓存里的 mwv207 ---"
  ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC" || echo "  缓存里没有 mwv207/JMC"

  echo
  echo "==================== 7. 对照：2D 路径是否正常 ===================="
  ls -la /usr/lib64/xorg/modules/drivers/mwv207_drv.so 2>&1
  ls -la /dev/jmgpu /dev/dri/card0 /dev/dri/renderD128 2>&1

  echo
  echo "==================== 8. 安装介质是否完好 ===================="
  ls -la "$RPM_PKG" 2>&1
  echo "--- 包内是否含所需库 ---"
  rpm -qlp "$RPM_PKG" 2>/dev/null | grep -E "libGLX_mwv207|libJMC|libEGL_mwv207" || echo "  查不到"
  ;;

# ==============================================================================
#  修复
# ==============================================================================
fix)
  echo "==================== 0. 备份现场 ===================="
  mkdir -p "$BACKUP_DIR"
  rpm -qa | grep -i mwv > "$BACKUP_DIR/mwv-pkgs-before.txt" 2>&1
  cp -a /etc/ld.so.conf.d "$BACKUP_DIR/ld.so.conf.d.bak" 2>/dev/null
  [ -d "$LIBDIR" ] && cp -a "$LIBDIR" "$BACKUP_DIR/mwv207-lib-before" 2>/dev/null
  echo "  备份目录: $BACKUP_DIR"

  echo
  echo "==================== 1. 解包 rpm（绕过失败的 %post）===================="
  # 注意：这里【不能】用 rpm -Uvh --force，实测它报告成功但文件不落地。
  # 必须用 rpm2cpio 手工解包再复制。
  rm -rf "$EXTRACT_DIR"
  mkdir -p "$EXTRACT_DIR"
  cd "$EXTRACT_DIR" || exit 1
  rpm2cpio "$RPM_PKG" | cpio -idm 2>&1 | tail -3
  echo "  解包文件数: $(find "$EXTRACT_DIR" -type f 2>/dev/null | wc -l)"
  echo "  解出的 mwv207 库数: $(ls "$EXTRACT_DIR/usr/lib64/mwv207" 2>/dev/null | wc -l)"

  echo
  echo "==================== 2. 复制库文件到位 ===================="
  mkdir -p "$LIBDIR"
  cp -avf "$EXTRACT_DIR/usr/lib64/mwv207/." "$LIBDIR/" 2>&1 | tail -20

  # 顺带把配套的 libdrm_jmgpu 和 dri 也同步一份（幂等）
  [ -f "$EXTRACT_DIR/usr/lib64/libdrm_jmgpu.so.1.0.0" ] && \
    cp -avf "$EXTRACT_DIR/usr/lib64/libdrm_jmgpu.so.1.0.0" /usr/lib64/ 2>&1 | tail -2
  [ -f "$EXTRACT_DIR/usr/lib64/dri/jmgpu_dri.so" ] && \
    cp -avf "$EXTRACT_DIR/usr/lib64/dri/jmgpu_dri.so" /usr/lib64/dri/ 2>&1 | tail -2

  echo "  --- 复制后 $LIBDIR ---"
  ls -la "$LIBDIR" 2>&1

  echo
  echo "==================== 3. 加入 ld 搜索路径 + ldconfig ===================="
  # ldconfig 会读取各库的 SONAME，自动建立 .so.0 软链接
  # （libGLX_mwv207.so.1.2.0 的 SONAME 是 libGLX_mwv207.so.0，所以不用手工 ln -s）
  echo "$LIBDIR" > "$LDCONF"
  echo "  写入: $LDCONF -> $(cat $LDCONF)"
  ldconfig 2>&1 | head -3
  echo "  --- ldconfig 缓存 ---"
  ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC"

  echo
  echo "==================== 4. 校验依赖是否补齐 ===================="
  echo "--- ldd not found（应为空）---"
  ldd "$DRI" 2>&1 | grep -i "not found" || echo "  （无缺失）✓"
  echo "--- not found 计数（应为 0）---"
  ldd "$DRI" 2>&1 | grep -c "not found"
  echo "--- rpm -V（应无 missing）---"
  rpm -V mwv207-dev 2>&1 | head -5

  echo
  echo "==================== 5. 重启 X 让 AIGLX 重新加载 ===================="
  # AIGLX 只在 Xorg 启动时加载一次 DRI 驱动，不重启不会生效
  echo "  当前 lightdm: $(systemctl is-active lightdm 2>&1)"
  systemctl restart lightdm 2>&1
  for i in $(seq 1 12); do
    sleep 5
    X=$(ps -ef 2>/dev/null | grep -cE "[X]org")
    echo "  [$((i*5))s] lightdm=$(systemctl is-active lightdm 2>&1)  Xorg进程=$X"
    [ "$X" -ge 1 ] && break
  done

  echo
  echo "==================== 6. 修复后验证 ===================="
  DISPLAY=:0 glxinfo -B 2>&1 | head -14

  rm -rf "$EXTRACT_DIR"
  echo
  echo "修复完成。若 glxinfo 仍显示 llvmpipe，请执行:  bash $0 diag  复查。"
  ;;

# ==============================================================================
#  验证（只读）
# ==============================================================================
verify)
  echo "==================== 1. 依赖完整性 ===================="
  echo "  not found 计数: $(ldd $DRI 2>&1 | grep -c 'not found')   （0 = 正常）"

  echo
  echo "==================== 2. OpenGL 渲染器（关键）===================="
  echo "  期望: OpenGL renderer string: MWV207... / Accelerated: yes"
  DISPLAY=:0 glxinfo -B 2>&1 | grep -iE "OpenGL renderer|OpenGL vendor|OpenGL version|Accelerated|Device:|Vendor:" | head -8

  echo
  echo "==================== 3. Xorg 日志 ===================="
  grep -iE "AIGLX|swrast|load driver jmgpu|Initialized DRISWRAST" /var/log/Xorg.0.log 2>/dev/null | tail -8

  echo
  echo "==================== 4. 实测 3D 负载（可选，需 glmark2/mesa-demos）===================="
  if command -v glmark2 >/dev/null 2>&1; then
    echo "  跑 15 秒 glmark2，同时观察 3D 利用率..."
    ( DISPLAY=:0 timeout 15 glmark2 >/dev/null 2>&1 & )
    for i in 1 2 3 4 5; do
      sleep 3
      echo "    采样$i: $(grep -i 'Utilize Rate(3d)' /proc/gpuinfo_0)"
    done
  else
    echo "  未装 glmark2，直接看空闲值（空闲时 3d 本来就接近 0）"
    grep -iE "Utilize" /proc/gpuinfo_0
  fi

  echo
  echo "==================== 5. 当前配置 ===================="
  echo "  $LDCONF: $(cat $LDCONF 2>/dev/null || echo '<不存在>')"
  echo "  $LIBDIR 库数: $(ls $LIBDIR 2>/dev/null | wc -l)"
  ;;

# ==============================================================================
#  回滚
# ==============================================================================
rollback)
  echo "==================== 回滚 ===================="
  echo "  说明：库文件本身是 rpm 数据库认可的（rpm -V 现在应该是干净的），"
  echo "        保留它们无害。回滚主要是撤掉我们新增的 ld 配置。"
  echo
  if [ -f "$LDCONF" ]; then
    rm -f "$LDCONF"
    echo "  已删除 $LDCONF"
  else
    echo "  $LDCONF 不存在，无需删除"
  fi
  ldconfig 2>&1 | head -3
  echo "  --- 回滚后 ldconfig 缓存 ---"
  ldconfig -p 2>/dev/null | grep -iE "mwv207|JMC" || echo "  已无 mwv207/JMC 条目"
  echo
  echo "  如需连库文件一起还原（回到修复前状态）："
  echo "    最新备份在: $(ls -dt /root/mwv207-fix-backup-* 2>/dev/null | head -1)"
  echo "    还原命令  : cp -a <备份目录>/mwv207-lib-before/. $LIBDIR/   （若备份存在）"
  echo "    或直接删除 : rm -rf $LIBDIR  然后 ldconfig"
  echo
  echo "  注意：删除库后 3D 会重新退回 llvmpipe 软件渲染。"
  ;;

*)
  echo "用法: bash $0 {diag|fix|verify|rollback}"
  echo
  echo "  diag     只诊断，不修改（默认）"
  echo "  fix      执行修复"
  echo "  verify   修复后验证"
  echo "  rollback 回滚（撤掉 ld 配置）"
  ;;
esac
