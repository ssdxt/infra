#!/bin/bash
###############################################################################
#  CANN toolkit 8.1.RC1 安装结果验证
#  目标机: kzzk-pc (192.168.21.111) / aarch64 / Atlas 300I Duo (310P3)
#
#  用法:  bash CANN安装验证.sh
#  从 Windows 复制过来先:  sed -i 's/\r$//' CANN安装验证.sh
#
#  分四层验证:
#    第1层  安装器自述（退出码 + 安装日志）
#    第2层  文件/版本落地（目录结构、version.cfg、动态库依赖）
#    第3层  环境变量生效（set_env.sh 是否把路径都挂上）
#    第4层  端到端：pyACL 真正 init + 打开 NPU 设备  ← 唯一的硬指标
###############################################################################

TK=/usr/local/Ascend/ascend-toolkit
LOG=/var/log/ascend_seclog/ascend_toolkit_install.log
OK=0; BAD=0; WARN=0

pass(){ echo "  [PASS] $1"; OK=$((OK+1)); }
fail(){ echo "  [FAIL] $1"; BAD=$((BAD+1)); }
warn(){ echo "  [WARN] $1"; WARN=$((WARN+1)); }
hd(){ echo; echo "==================== $* ===================="; }

#==============================================================================
hd "第 1 层  安装器自述"
#==============================================================================
if [ -f "$LOG" ]; then
  echo "  日志: $LOG"
  echo "  ---- 末尾 12 行 ----"
  tail -12 "$LOG" | sed 's/^/    /'
  echo "  ---- 错误行（若有）----"
  if grep -inE "\[ERROR\]|failed|not empty" "$LOG" | tail -8 | sed 's/^/    /'; then :; fi
  if grep -qE "install success|success" "$LOG" && ! grep -qE "package install failed" "$LOG"; then
    pass "安装日志未见 failed"
  else
    fail "安装日志里有 failed/ERROR，见上面"
  fi
else
  warn "找不到 $LOG（可能用 --quiet 装到了别处，或压根没跑）"
fi

echo
echo "  ---- 各子包安装记录 ----"
grep -aiE "install package|success|failed" /var/log/ascend_seclog/ascend_install.log 2>/dev/null | tail -15 | sed 's/^/    /'

#==============================================================================
hd "第 2 层  文件 / 版本 / 依赖"
#==============================================================================
if [ -e "$TK/latest" ]; then
  pass "存在 $TK/latest -> $(readlink -f $TK/latest)"
else
  fail "缺少 $TK/latest 软链（安装没完成，典型症状就是它）"
fi

echo
echo "  ---- latest 下应有的顶层目录 ----"
for d in aarch64-linux bin compiler include lib64 opp python script tools set_env.sh version.cfg; do
  if [ -e "$TK/latest/$d" ]; then
    printf "    [ok]   %-16s\n" "$d"
  else
    printf "    [MISS] %-16s\n" "$d"
  fi
done

echo
echo "  ---- version.cfg（必须是【非空】且含 8.1.RC1）----"
VCFG=$(cat "$TK/latest/version.cfg" 2>/dev/null)
echo "    内容: [${VCFG}]"
if [ -n "$VCFG" ] && echo "$VCFG" | grep -q "8.1.RC1"; then
  pass "version.cfg 非空且版本正确"
elif [ -z "$VCFG" ]; then
  fail "version.cfg 为空 —— 这正是上次 latest manager 摘链失败的元凶，说明仍是半成品"
else
  warn "version.cfg 有内容但没看到 8.1.RC1"
fi

echo
echo "  ---- 卸载脚本是否补齐（有它才说明装完整）----"
for u in "$TK/latest/script/uninstall.sh" "$TK/latest/cann_uninstall.sh"; do
  [ -f "$u" ] && pass "存在 $u" || warn "缺 $u"
done

echo
echo "  ---- 关键动态库是否存在 ----"
for so in libascendcl.so libacl_dvpp.so libhccl.so libnnopbase.so libge_runner.so; do
  if [ -e "$TK/latest/lib64/$so" ]; then
    printf "    [ok]   %s\n" "$so"
  else
    printf "    [MISS] %s\n" "$so"
  fi
done

echo
echo "  ---- 动态库依赖是否都能解析（仿 JM9230 那套，看 not found）----"
source "$TK/set_env.sh" 2>/dev/null
NF=$(ldd "$TK/latest/lib64/libascendcl.so" 2>/dev/null | grep -c "not found")
echo "    libascendcl.so 的 not found 条数: $NF"
[ "$NF" = "0" ] && pass "libascendcl.so 依赖完整" || fail "有 $NF 个依赖没解析到，检查 LD_LIBRARY_PATH"

echo
echo "  ---- /etc/ascend_install.info 是否登记 ----"
grep -i -A1 -B1 "toolkit" /etc/ascend_install.info 2>/dev/null | sed 's/^/    /' || echo "    (无工具包条目)"
grep -qi "toolkit" /etc/ascend_install.info 2>/dev/null && pass "install.info 已登记" || warn "install.info 未登记 toolkit"

#==============================================================================
hd "第 3 层  环境变量"
#==============================================================================
echo "  ---- set_env.sh 内容概览 ----"
grep -vE "^\s*#|^\s*$" "$TK/set_env.sh" 2>/dev/null | head -12 | sed 's/^/    /'

echo
echo "  ---- source 之后的实际值 ----"
source "$TK/set_env.sh" 2>/dev/null
for v in ASCEND_HOME_PATH ASCEND_OPP_PATH ASCEND_AICPU_PATH ASCEND_TOOLKIT_HOME; do
  printf "    %-20s = %s\n" "$v" "${!v:-<未设置>}"
done
echo "    PATH 含 toolkit/bin       : $(echo $PATH | tr ':' '\n' | grep -c ascend-toolkit)"
echo "    LD_LIBRARY_PATH 含 toolkit: $(echo $LD_LIBRARY_PATH | tr ':' '\n' | grep -c ascend-toolkit)"
echo "    PYTHONPATH 含 toolkit     : $(echo $PYTHONPATH | tr ':' '\n' | grep -c ascend-toolkit)"

[ -n "$ASCEND_HOME_PATH" ] && pass "ASCEND_HOME_PATH 已设置" || fail "ASCEND_HOME_PATH 未设置（没 source set_env.sh?）"

echo
echo "  ---- 是否已写进 /root/.bashrc（重启后仍生效）----"
grep -q "ascend-toolkit/set_env.sh" /root/.bashrc 2>/dev/null \
  && pass "已写入 /root/.bashrc" \
  || warn "未写入 /root/.bashrc，新开终端需手动 source"

#==============================================================================
hd "第 3.5 层  工具可用性"
#==============================================================================
if command -v atc >/dev/null 2>&1; then
  pass "ATC 可用: $(command -v atc)"
  atc --version 2>&1 | head -4 | sed 's/^/    /'
else
  fail "atc 不在 PATH（模型转换要用它）"
fi

echo
echo "  ---- Ascend C 编译器 ----"
ls "$TK/latest/compiler/ccec_compiler/bin/" 2>/dev/null | head -5 | sed 's/^/    /' || warn "无 ccec_compiler/bin"

echo
echo "  ---- 算子库 OPP（注意：310P 的 .o 算子靠 kernels-310p 包，toolkit 单独装不全）----"
ls "$ASCEND_OPP_PATH/built-in/op_impl/" 2>/dev/null | sed 's/^/    /'
if [ -d "$ASCEND_OPP_PATH/built-in/op_impl/aicore/kernel" ]; then
  pass "aicore/kernel 存在（算子包已装）"
else
  warn "缺 aicore/kernel —— 还需装 Ascend-cann-kernels-310p_8.1.RC1"
fi

#==============================================================================
hd "第 4 层  端到端：pyACL 打开 NPU（硬指标）"
#==============================================================================
echo "  ---- pyACL 装到哪个解释器了（conda 坑的照妖镜）----"
python3 -c "import acl, sys; print('    python :', sys.executable); print('    acl at :', acl.__file__)" 2>&1 | sed 's/^/  /'
python3 -c "import acl; print(acl.__file__)" 2>/dev/null | grep -q anaconda && \
  warn "pyACL 装进了 anaconda(3.11)，系统 python3.8 可能 import 不到" || true

echo
echo "  ---- 真机设备探测 ----"
python3 - <<'PY' 2>&1 | sed 's/^/    /'
import sys
try:
    import acl
except Exception as e:
    print("import acl 失败:", e); sys.exit(1)
print("acl 模块加载 OK")
ret = acl.init()
print("acl.init()                 ret =", ret)

# 注意: 新版 pyACL 的 get_device_count() 返回 (设备数, 返回码) 元组，不是裸 int
dc = acl.rt.get_device_count()
if isinstance(dc, tuple):
    cnt, ret = dc
    print(f"get_device_count()         -> 设备数={cnt}  返回码={ret}")
else:
    cnt = dc
    print("get_device_count()             =", cnt)

if not cnt:
    print(">>> 探测不到设备，检查 npu-smi / 驱动")
else:
    allok = True
    for i in range(cnt):
        r1 = acl.rt.set_device(i)
        soc = acl.get_soc_name()
        r2 = acl.rt.reset_device(i)
        flag = "OK" if r1 == 0 else "FAIL"
        if r1 != 0:
            allok = False
        print(f"  chip{i}: set_device={r1}({flag})  soc={soc}  reset={r2}")
    if allok:
        print(f">>> {cnt} 张卡全部可正常打开，pyACL 端到端 OK")
    else:
        print(">>> 有卡 set_device 失败！结合 npu-smi 与 dmesg 排查（本机有硬件故障史）")
acl.finalize()
PY

echo
echo "  ---- 驱动侧对照 ----"
npu-smi info 2>&1 | head -14 | sed 's/^/    /'

#==============================================================================
hd "汇总"
#==============================================================================
echo "  PASS=$OK   FAIL=$BAD   WARN=$WARN"
if [ "$BAD" = "0" ]; then
  echo "  >>> 未发现硬性失败。若第4层打印了 '设备可正常打开'，toolkit 就算装成了。"
else
  echo "  >>> 有 $BAD 项失败，先解决 FAIL 项。"
fi
echo
echo "  下一步（MindIE 的直接依赖，toolkit 装完必须补）:"
echo "    cd /deploy/driver/Ascend"
echo "    ./Ascend-cann-kernels-310p_8.1.RC1_linux.run --install --quiet"
echo "    ./Ascend-cann-nnal_8.1.RC1_linux-aarch64.run  --install --quiet"
echo "    ./Ascend-cann-nnrt_8.1.RC1_linux-aarch64.run  --install --quiet   # 按需"
echo "    source /usr/local/Ascend/ascend-toolkit/set_env.sh"
echo "    source /usr/local/Ascend/nnal/atb/set_env.sh   # ATB 环境"
