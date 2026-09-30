#!/bin/bash
SOCK=/var/run/docker/containerd/containerd.sock
CTR="sudo ctr -a $SOCK -n moby"

echo "########## 1. snapshots 完整列表 ##########"
$CTR snapshots ls 2>/dev/null | sed 's/^/  /'

echo
echo "########## 2. content 里 mis-tei 相关的 blob（含 label）##########"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | grep -i "mis-tei" | sed 's/^/  /'

echo
echo "########## 3. 所有带 uncompressed label 的 content（= 已解压标记）##########"
sudo ctr -a $SOCK -n moby content ls 2>/dev/null | grep -c "uncompressed" | sed 's/^/  条数: /'

echo
echo "########## 4. 交叉比对：哪些 uncompressed digest 没有对应 snapshot ##########"
python3 - <<'PYEOF'
import subprocess, re, sys

SOCK = "/var/run/docker/containerd/containerd.sock"

def run(args):
    r = subprocess.run(["sudo", "ctr", "-a", SOCK, "-n", "moby"] + args,
                       capture_output=True, text=True)
    return r.stdout

# snapshots
snap_keys = set()
for line in run(["snapshots", "ls"]).splitlines():
    line = line.strip()
    if not line or line.startswith("KEY"):
        continue
    snap_keys.add(line.split()[0])
print(f"  snapshot key 数: {len(snap_keys)}")

# content with uncompressed label
content = run(["content", "ls"])
orphans = []
for line in content.splitlines():
    if "uncompressed=" not in line:
        continue
    parts = line.split()
    digest = parts[0]
    m = re.search(r"uncompressed=(sha256:[0-9a-f]+)", line)
    if not m:
        continue
    unc = m.group(1)
    src = "?"
    m2 = re.search(r"distribution\.source\.[^=]+=([^,\s]+)", line)
    if m2:
        src = m2.group(1)
    if unc not in snap_keys:
        orphans.append((digest, unc, src))

print(f"\n  孤儿 content（有 uncompressed 标记但没有对应 snapshot）: {len(orphans)}")
for d, u, s in orphans:
    print(f"    blob     : {d}")
    print(f"    uncompressed -> {u}   <-- 缺失")
    print(f"    来源     : {s}")
    print()
PYEOF

echo
echo "########## 5. 该镜像在 docker 侧的引用 ##########"
sudo docker images 2>/dev/null | grep -i "mis-tei" | sed 's/^/  /'

echo
echo "########## 6. content 总量与磁盘占用 ##########"
echo "  content 条数: $(sudo ctr -a $SOCK -n moby content ls 2>/dev/null | wc -l)"
sudo du -sh /deploy/docker/containerd/daemon/io.containerd.content.v1.content 2>/dev/null | sed 's/^/  /'
