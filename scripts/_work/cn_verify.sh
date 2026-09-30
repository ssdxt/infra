#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. 确认 abi3.so 属于新版（不在 3.4.1 的 RECORD 里）##########"
echo "--- 3.4.1 RECORD 里跟 .so 相关的行 ---"
grep -E "\.so" $PKG/charset_normalizer-3.4.1.dist-info/RECORD 2>/dev/null
echo
echo "--- 3.5.1 RECORD 里跟 .so 相关的行 ---"
grep -E "\.so" $PKG/charset_normalizer-3.5.1.dist-info/RECORD 2>/dev/null

echo
echo "########## 2. 临时目录验证：删掉 3.5.1 的 abi3.so 后能否导入 ##########"
T=/tmp/cn_verify
rm -rf $T && mkdir -p $T
cp -a $PKG/charset_normalizer $T/charset_normalizer
find $T -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
rm -f $T/charset_normalizer/*.abi3.so
echo "删除后剩余 .so："
ls $T/charset_normalizer/*.so 2>/dev/null | sed 's|.*/|  |'

$PY - <<'EOF'
import sys
sys.path.insert(0, "/tmp/cn_verify")
for m in list(sys.modules):
    if m.startswith("charset_normalizer"):
        del sys.modules[m]
try:
    import charset_normalizer
    print("  charset_normalizer:", charset_normalizer.__version__)
    from charset_normalizer import from_bytes
    r = from_bytes("你好 hello".encode("utf-8"))
    print("  from_bytes OK ->", r.best())
    print("  >>> charset_normalizer 【可用】")
except Exception as e:
    print("  >>> 失败:", type(e).__name__, e)
EOF

echo
echo "########## 3. 原环境当前状态（只读）##########"
$PY -c "
import charset_normalizer as c
print('  版本:', c.__version__)
" 2>&1 | tail -3

rm -rf $T
