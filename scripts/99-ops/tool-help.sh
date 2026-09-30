#!/bin/bash
echo "===================== skopeo 1.24 的 multi-arch 参数 ====================="
skopeo copy --help 2>&1 | grep -i -B1 -A4 'multi-arch'
echo ""
echo "===================== skopeo 是否还接受 --all ====================="
skopeo copy --help 2>&1 | grep -i -E '^\s+--all|--override-arch|--override-os'
echo ""
echo "===================== regctl image copy 的 platform 参数 ====================="
regctl image copy --help 2>&1 | grep -i -B2 -A4 'platform'
echo ""
echo "===================== regctl 全局 platform 参数 ====================="
regctl --help 2>&1 | grep -i -A2 platform