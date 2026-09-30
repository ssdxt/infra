#!/bin/bash
V=/home/kzzk/.vscode-server/data/Machine
sudo mkdir -p $V

echo "########## 1. 写入 Machine 级排除规则（对所有窗口生效）##########"
sudo tee $V/settings.json >/dev/null <<'JSON'
{
  "search.exclude": {
    "**/sys/**": true,
    "**/proc/**": true,
    "**/dev/**": true,
    "**/run/**": true,
    "**/lost+found/**": true,
    "/deploy/docker/**": true,
    "/deploy/models/**": true,
    "/deploy/tar/**": true,
    "/deploy/infra/**/volumes/**": true,
    "/root/ob/**": true,
    "/root/.obd/**": true,
    "/var/lib/**": true,
    "/usr/**": true,
    "/opt/**": true,
    "/snap/**": true
  },
  "files.watcherExclude": {
    "**/sys/**": true,
    "**/proc/**": true,
    "**/dev/**": true,
    "**/run/**": true,
    "/deploy/docker/**": true,
    "/deploy/models/**": true,
    "/deploy/tar/**": true,
    "/deploy/infra/**/volumes/**": true,
    "/root/ob/**": true,
    "/root/.obd/**": true,
    "/var/lib/**": true,
    "/usr/**": true,
    "/opt/**": true,
    "/snap/**": true
  },
  "search.followSymlinks": false
}
JSON
echo "已写入: $V/settings.json"
sudo cat $V/settings.json | head -8

echo
echo "########## 2. 杀掉正在跑的 rg ##########"
sudo pkill -9 -f "ripgrep-universal" 2>/dev/null
sleep 5
echo "剩余 rg: $(pgrep -cf 'ripgrep-universal' 2>/dev/null || echo 0)"

echo
echo "########## 3. 观察负载 ##########"
for i in 1 2 3; do
  sleep 10
  echo "[$((i*10))s] load=$(cut -d' ' -f1-3 /proc/loadavg)  rg数=$(pgrep -cf 'ripgrep-universal' 2>/dev/null || echo 0)"
done

echo
echo "########## 4. rg 重生后带的参数（看排除规则有没有生效）##########"
sleep 5
p=$(pgrep -f "ripgrep-universal" | head -1)
if [ -n "$p" ]; then
  echo "PID $p  cwd=$(sudo readlink /proc/$p/cwd)"
  echo "参数:"
  sudo tr '\0' ' ' < /proc/$p/cmdline | tr ' ' '\n' | grep -E "^-g|^--glob|sys|deploy" | head -20
  echo "--- 打开的 fd ---"
  sudo ls -l /proc/$p/fd 2>/dev/null | awk '{print $NF}' | grep "^/" | grep -vE "vscode-server" | head -6
else
  echo "rg 未重生（可能 VS Code 窗口需要重新加载）"
fi
