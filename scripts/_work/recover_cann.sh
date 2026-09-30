#!/bin/bash
###############################################################################
#  恢复 + 重装 CANN toolkit（上次因非交互 shell 无 pip3 而回滚）
#  顺序: 装系统 pip3 -> 清空 -> 装 toolkit -> 补 opp 软链 -> 装 310P 算子 -> 验证
###############################################################################
set +e
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
TS=$(date +%Y%m%d-%H%M%S)
TK=/usr/local/Ascend/ascend-toolkit
LATEST=$TK/latest
cd /deploy/driver/Ascend || exit 1

echo "############ 阶段 1：装系统 python3-pip（关键，非交互 shell 也能找到）############"
which pip3 || echo "  pip3: 当前不存在"
apt-get install -y python3-pip python3-dev 2>&1 | tail -8
echo "  --- 验证 ---"
ls -l /usr/bin/pip3 2>&1
/usr/bin/pip3 --version 2>&1
echo "  非交互 shell 下 command -v pip3 -> $(command -v pip3 || echo NOT_FOUND)"
echo "  python3 -> $(command -v python3) $(python3 -V 2>&1)"

# 配个国内源，防止 CANN 装 python 依赖时卡在 pypi
if [ ! -f /etc/pip.conf ]; then
  printf '[global]\nindex-url = https://pypi.tuna.tsinghua.edu.cn/simple\ntrusted-host = pypi.tuna.tsinghua.edu.cn\n' > /etc/pip.conf
  echo "  已写 /etc/pip.conf 使用清华源"
else
  echo "  /etc/pip.conf 已存在，保持不动"
fi

echo
echo "############ 阶段 2：清空 toolkit ############"
umask 022
echo "  当前占用: $(du -sh $TK 2>/dev/null | cut -f1)"
echo "  --- 先看残缺状态 ---"
ls $TK 2>&1 | sed 's/^/    /'
rm -rf $TK
echo "  删除后: $(ls -d $TK 2>&1)"
echo "  同级目录保持不动: $(ls /usr/local/Ascend/ | tr '\n' ' ')"

echo
echo "############ 阶段 3：安装 toolkit（约 2-3 分钟）############"
./Ascend-cann-toolkit_8.1.RC1_linux-aarch64.run --install --quiet < /dev/null 2>&1 | tail -30
RC=${PIPESTATUS[0]}
echo
echo "  >>> 安装退出码: $RC"
if [ "$RC" != "0" ]; then
  echo "  !!! 安装仍失败，后续步骤跳过。错误摘要:"
  grep -a -E "\[ERROR\]|failed|未找到命令" /var/log/ascend_seclog/ascend_toolkit_install.log 2>/dev/null | tail -12 | sed 's/^/    /'
  exit 1
fi

echo
echo "############ 阶段 4：补 latest/opp 软链（安装器不生成）############"
cd $LATEST || { echo "  !! $LATEST 不存在"; exit 1; }
[ -e opp ] || ln -sfn ../8.1.RC1/opp opp
[ -e ops ] || ln -sfn ../8.1.RC1/ops ops
ls -la opp ops 2>&1 | sed 's/^/  /'
echo "  opp/built-in/op_impl: $(ls opp/built-in/op_impl/ 2>/dev/null | tr '\n' ' ')"

echo
echo "############ 阶段 5：权限归一化 ############"
cd /usr/local/Ascend || exit 1
chmod 755 /usr/local/Ascend $TK $TK/8.1.RC1 2>/dev/null
chmod -R u+rwX,go+rX $TK 2>/dev/null
echo "  opp 权限: $(stat -c '%a' $TK/8.1.RC1/opp)"

echo
echo "############ 阶段 6：装 310P 算子包 ############"
cd /deploy/driver/Ascend || exit 1
source $TK/set_env.sh
echo "  ASCEND_HOME_PATH=$ASCEND_HOME_PATH"
K=$(ls Ascend-cann-kernels-310p_*.run 2>/dev/null | head -1)
echo "  包: $K"
./$K --install --quiet < /dev/null 2>&1 | tail -15
echo "  >>> 算子包退出码: ${PIPESTATUS[0]}"
if [ -f /var/log/ascend_seclog/ascend_kernels_310p_install.log ]; then
  echo "  --- 算子包日志尾部 ---"
  grep -a -E "\[ERROR\]|failed|success" /var/log/ascend_seclog/ascend_kernels_310p_install.log 2>/dev/null | tail -8 | sed 's/^/    /'
fi
chmod -R u+rwX,go+rX $TK 2>/dev/null

echo
echo "############ 阶段 7：验证 ############"
OPP=$TK/8.1.RC1/opp
echo "  --- 7.1 完整性 ---"
echo "    opp 文件总数  : $(find $OPP -type f 2>/dev/null | wc -l)      (坏之前是 19904)"
echo "    opp 0字节文件 : $(find $OPP -type f -size 0 2>/dev/null | wc -l)      <<< 必须为 0"
echo "    算子 .o 总数  : $(find $OPP -name '*.o' 2>/dev/null | wc -l)   (坏之前是 6019)"
echo "    .o  0字节     : $(find $OPP -name '*.o' -size 0 2>/dev/null | wc -l)"
echo "    .so 0字节     : $(find $OPP -name '*.so*' -size 0 2>/dev/null | wc -l)"
echo "    opp/bin/setenv.bash : $(stat -c '%s 字节' $OPP/bin/setenv.bash 2>&1)"
echo "    op_impl 引擎: $(ls $OPP/built-in/op_impl/ 2>/dev/null | tr '\n' ' ')"
echo "    ai_core/tbe/kernel/ascend310p 算子目录数: $(ls $OPP/built-in/op_impl/ai_core/tbe/kernel/ascend310p 2>/dev/null | wc -l)"
echo "    报错点名的 json: $(stat -c '%s 字节' $OPP/built-in/op_impl/vector_core/tbe/config/vector_core_tbe_ops_info.json 2>&1)"
echo "    libconstant_folding_ops.so: $(find $TK -name 'libconstant_folding_ops.so' -exec stat -c '%s 字节' {} \; 2>/dev/null)"

echo "  --- 7.2 环境变量（交互式 shell）---"
bash -ic 'echo "    ASCEND_HOME_PATH=${ASCEND_HOME_PATH:-<空>}"' 2>/dev/null
bash -ic 'echo "    ASCEND_OPP_PATH=${ASCEND_OPP_PATH:-<空>}"' 2>/dev/null

echo "  --- 7.3 import torch_npu ---"
bash -ic 'python3 -c "import torch,torch_npu;print(\"    torch\",torch.__version__,\"| torch_npu\",torch_npu.__version__)"' 2>&1 | grep -v "任务控制\|进程组"

echo "  --- 7.4 /tmp/t.py 真算子下发 ---"
for d in 0 1; do
  echo "    ===== chip $d ====="
  bash -ic "python3 /tmp/t.py $d" 2>&1 | grep -v "任务控制\|进程组" | tail -20 | sed 's/^/      /'
done

echo "  --- 7.5 ATB ---"
ls /usr/local/Ascend/nnal/atb/latest/ 2>&1 | head -4 | sed 's/^/    /'

echo "  --- 7.6 驱动侧 ---"
npu-smi info 2>&1 | sed -n '1,11p' | sed 's/^/    /'
