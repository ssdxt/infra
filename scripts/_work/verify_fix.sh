#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python
T=/tmp/fa_verify

echo "########## 1. 网络 / pip 源 ##########"
$PY -m pip config list 2>&1 | head -5
timeout 10 curl -sI https://pypi.tuna.tsinghua.edu.cn/simple/ 2>&1 | head -2 || echo "  清华源不可达"
echo "--- 本地 wheel 缓存里有没有 fastapi 0.104.1 ---"
find /root/anaconda3/pkgs /root/.cache/pip -iname "fastapi*0.104*" 2>/dev/null | head -5 || true
find /root/anaconda3/pkgs -maxdepth 1 -iname "fastapi*" 2>/dev/null | head -5 || echo "  无 conda 缓存"

echo
echo "########## 2. 0.104.1 的 RECORD 里 _compat 是文件还是目录 ##########"
grep -E "_compat" $PKG/fastapi-0.104.1.dist-info/RECORD 2>/dev/null | head -5

echo
echo "########## 3. 0.124.4 的 RECORD 里有而 0.104.1 没有的文件（= 多余残留）##########"
cut -d, -f1 $PKG/fastapi-0.124.4.dist-info/RECORD 2>/dev/null | sort > /tmp/r124.txt
cut -d, -f1 $PKG/fastapi-0.104.1.dist-info/RECORD 2>/dev/null | sort > /tmp/r104.txt
comm -23 /tmp/r124.txt /tmp/r104.txt | head -20

echo
echo "########## 4. 0.104.1 有而磁盘上缺失的文件 ##########"
while IFS= read -r f; do
  [ -z "$f" ] && continue
  [ "${f: -1}" = "/" ] && continue
  [ ! -e "$PKG/$f" ] && echo "  缺失: $f"
done < /tmp/r104.txt | head -20
echo "(以上为空=0.104.1 的文件齐全)"

echo
echo "########## 5. 临时目录验证：删掉 _compat/ 目录后能否导入 ##########"
rm -rf $T && mkdir -p $T
cp -a $PKG/fastapi $T/fastapi
rm -rf $T/fastapi/_compat $T/fastapi/__pycache__
find $T/fastapi -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
rm -f $T/fastapi/temp_pydantic_v1_params.py $T/fastapi/cli.py $T/fastapi/__main__.py

cd $T || exit 1
$PY - <<'EOF'
import sys
sys.path.insert(0, "/tmp/fa_verify")
import fastapi
print("  fastapi.__file__ :", fastapi.__file__)
print("  __version__      :", fastapi.__version__)
try:
    from fastapi import FastAPI
    print("  >>> from fastapi import FastAPI  【成功】")
except Exception as e:
    print("  >>> 失败:", type(e).__name__, e)
try:
    from fastapi._compat import ErrorWrapper
    print("  >>> ErrorWrapper 可导入  【成功】")
except Exception as e:
    print("  >>> ErrorWrapper 失败:", e)
EOF

echo
echo "########## 6. 还原确认：原环境目前的状态（只读检查）##########"
$PY -c "
import fastapi, sys
print('  原始 fastapi 路径:', fastapi.__file__)
print('  原始 __version__:', fastapi.__version__)
"
rm -rf $T
