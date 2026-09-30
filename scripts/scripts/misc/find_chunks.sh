#!/bin/bash
cd /tmp
echo "=== 主JS里 login/auth 出现次数 ==="
for pat in login auth "/api/v1" chunk; do
  echo -n "$pat: "; grep -o -i "$pat" panel.js | wc -l
done
echo "=== 动态 import 的 chunk 文件 ==="
grep -o -E '"assets/js/[A-Za-z0-9_-]+\.js"' panel.js | sort -u | head -30
grep -o -E 'assets/js/[A-Za-z0-9_-]+\.js' panel.js | sort -u | head -30
echo "=== 登录页 chunk 猜测 ==="
grep -o -E 'index-[A-Za-z0-9_-]{6,}\.js' panel.js | sort -u | head -30
