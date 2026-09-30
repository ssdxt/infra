#!/bin/bash
cd /tmp
curl -sL -o regctl https://github.com/regclient/regclient/releases/latest/download/regctl-linux-amd64
chmod +x regctl
sudo mv regctl /usr/local/bin/ 2>/dev/null || mv regctl /usr/local/bin/
/usr/local/bin/regctl version 2>&1 | head -6
echo "--- skopeo 是否已有 ---"
command -v skopeo || echo "skopeo 未安装"