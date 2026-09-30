#!/bin/bash
echo "=== /usr/local/bin 里的相关工具 ==="
ls -la /usr/local/bin/ | grep -i -e regctl -e skopeo -e crane -e oras
echo ""
echo "=== regctl 版本 ==="
/usr/local/bin/regctl version 2>&1 | head -8
echo ""
echo "=== skopeo 版本 ==="
/usr/local/bin/skopeo --version 2>&1 | head -3
echo ""
echo "=== 其他可能位置的 skopeo ==="
command -v skopeo; which -a skopeo 2>/dev/null