#!/bin/bash
PKG=/root/anaconda3/envs/recovery/lib/python3.8/site-packages
PY=/root/anaconda3/envs/recovery/bin/python

echo "########## 1. 所有“同一包存在多个 dist-info”的包（混装嫌疑）##########"
$PY - <<'EOF'
import os, re, collections
PKG = "/root/anaconda3/envs/recovery/lib/python3.8/site-packages"
pat = re.compile(r"^(?P<name>.+?)-(?P<ver>\d[^-]*)\.dist-info$")
groups = collections.defaultdict(list)
for d in os.listdir(PKG):
    m = pat.match(d)
    if m:
        groups[m.group("name").lower().replace("_", "-")].append(m.group("ver"))
dups = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
if dups:
    print(f"  共 {len(dups)} 个包存在多版本 dist-info：")
    for k, v in sorted(dups.items()):
        print(f"    {k:28} {v}")
else:
    print("  无")
EOF

echo
echo "########## 2. charset_normalizer 详情 ##########"
ls -d $PKG/charset_normalizer* 2>/dev/null
echo "--- 目录内容 ---"
ls -la $PKG/charset_normalizer/ 2>/dev/null | head -25

echo
echo "########## 3. charset_normalizer 各 dist-info 的版本与时间 ##########"
for d in $PKG/charset_normalizer-*.dist-info; do
  echo "--- $(basename $d) ---"
  stat -c '  时间: %y' $d 2>/dev/null
  echo "  Version: $(grep -m1 '^Version:' $d/METADATA 2>/dev/null)"
  echo "  RECORD: $(wc -l < $d/RECORD 2>/dev/null) 行"
done

echo
echo "########## 4. md 模块是什么形态 ##########"
ls -la $PKG/charset_normalizer/md* 2>/dev/null
echo "--- 尝试导入 md ---"
$PY -c "import charset_normalizer.md as m; print('  md OK, attrs:', [a for a in dir(m) if not a.startswith('_')][:12])" 2>&1 | tail -5

echo
echo "########## 5. 文件时间分布（看哪些是新的）##########"
find $PKG/charset_normalizer -maxdepth 1 -printf "%TY-%Tm-%Td %TH:%TM  %f\n" 2>/dev/null | sort | head -25

echo
echo "########## 6. 其他关键包是否也混装（requests/urllib3/langchain 等）##########"
for p in requests urllib3 langchain langchain-core pydantic starlette numpy pandas; do
  n=$(ls -d $PKG/${p}-*.dist-info 2>/dev/null | wc -l)
  if [ "$n" -gt 1 ]; then
    echo "  !! $p 有 $n 个 dist-info:"
    ls -d $PKG/${p}-*.dist-info | sed 's|.*/|      |'
  fi
done
echo "(无输出=这几个正常)"
