#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. fastapi 目录内文件时间分布 ##########"
echo "--- 旧文件（0.104.1 时代）---"
find $PKG/fastapi -maxdepth 1 -name "*.py" -newermt "2025-01-01" ! -newermt "2025-09-01" -printf "%TY-%Tm-%Td  %f\n" 2>/dev/null | sort | head -20
echo "--- 新文件（9月11日之后）---"
find $PKG/fastapi -maxdepth 2 -newermt "2026-09-11" -printf "%TY-%Tm-%Td %TH:%TM  %P\n" 2>/dev/null | sort | head -20
echo
echo "文件总数: $(find $PKG/fastapi -type f | wc -l)"

echo
echo "########## 2. 两个 dist-info 里的版本记录 ##########"
for d in $PKG/fastapi-*.dist-info; do
  echo "--- $(basename $d) ---"
  ls -la $d 2>/dev/null | head -6
  echo "  METADATA Version: $(grep -m1 '^Version:' $d/METADATA 2>/dev/null)"
  echo "  RECORD 行数: $(wc -l < $d/RECORD 2>/dev/null)"
done

echo
echo "########## 3. pydantic 状态 ##########"
ls -d $PKG/pydantic* 2>/dev/null
echo "--- pydantic/version.py 里的 VERSION ---"
grep -m3 -E "^VERSION|^__version__" $PKG/pydantic/version.py 2>/dev/null
echo "--- 关键文件时间 ---"
stat -c '%y  %n' $PKG/pydantic/__init__.py $PKG/pydantic/version.py 2>/dev/null
echo "--- pydantic 是否有 v1 兼容目录 ---"
ls -d $PKG/pydantic/v1 2>/dev/null && echo "  (有 pydantic/v1，说明是 pydantic v2 的布局)" || echo "  (无 pydantic/v1)"
echo "--- pydantic v2 专属文件 ---"
ls $PKG/pydantic/_internal 2>/dev/null | head -3 && echo "  (有 _internal，是 pydantic v2)" || echo "  (无 _internal)"

echo
echo "########## 4. 用 python 实际探测 pydantic ##########"
$PY - <<'EOF'
import pydantic, os
print("  pydantic.__file__ :", pydantic.__file__)
print("  VERSION           :", getattr(pydantic, "VERSION", "?"))
print("  __version__       :", getattr(pydantic, "__version__", "?"))
print("  has pydantic.v1   :", os.path.isdir(os.path.join(os.path.dirname(pydantic.__file__), "v1")))
try:
    from pydantic import BaseModel
    print("  BaseModel OK")
except Exception as e:
    print("  BaseModel 失败:", e)
try:
    import pydantic_core
    print("  pydantic_core     :", pydantic_core.__version__)
except Exception as e:
    print("  pydantic_core 不可用:", e)
EOF

echo
echo "########## 5. 两个 fastapi 版本各自需要什么 pydantic ##########"
echo "--- 0.104.1 的 METADATA 依赖 ---"
grep -iE "^Requires-Dist: (pydantic|starlette)" $PKG/fastapi-0.104.1.dist-info/METADATA 2>/dev/null
echo "--- 0.124.4 的 METADATA 依赖 ---"
grep -iE "^Requires-Dist: (pydantic|starlette)" $PKG/fastapi-0.124.4.dist-info/METADATA 2>/dev/null

echo
echo "########## 6. fastapi 目录里顶层文件是哪个版本的 ##########"
grep -m1 -n "version" $PKG/fastapi/__init__.py 2>/dev/null | head -5
stat -c '%y  %n' $PKG/fastapi/__init__.py $PKG/fastapi/applications.py $PKG/fastapi/routing.py $PKG/fastapi/dependencies/utils.py 2>/dev/null
