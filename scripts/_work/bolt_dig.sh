#!/bin/bash
DB=/deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db
TARGET=37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3

echo "########## 1. bolt 数据库大小 ##########"
sudo ls -la $DB

echo
echo "########## 2. 目标 chainID 在 bolt 里出现几次 ##########"
sudo strings $DB | grep -c "$TARGET" | sed 's/^/  次数: /'
sudo strings $DB | grep "$TARGET" | head -5 | sed 's/^/  /'

echo
echo "########## 3. bolt 里所有 sha256: 开头的 key（应该就是 snapshot chainID）##########"
sudo strings $DB | grep -oE "^sha256:[0-9a-f]{64}$" | sort -u > /tmp/bolt_keys.txt
echo "  唯一 sha256 key 数: $(wc -l < /tmp/bolt_keys.txt)"
echo "--- 全部列出 ---"
cat /tmp/bolt_keys.txt | sed 's/^/  /'

echo
echo "########## 4. ctr ls 看得到的 vs bolt 里有的 ##########"
SOCK=/var/run/docker/containerd/containerd.sock
sudo ctr -a $SOCK -n moby snapshots --snapshotter overlayfs ls 2>/dev/null \
  | tail -n +2 | awk '{print $1}' | grep "^sha256:" | sort -u > /tmp/ctr_keys.txt
echo "  ctr 可见: $(wc -l < /tmp/ctr_keys.txt) 条"
echo "  bolt 里有: $(wc -l < /tmp/bolt_keys.txt) 条"
echo "--- 在 bolt 里但 ctr 看不到的（幽灵）---"
comm -23 /tmp/bolt_keys.txt /tmp/ctr_keys.txt | sed 's/^/  /'

echo
echo "########## 5. 找出幽灵链的顺序（谁是叶子）##########"
echo "  目标: $TARGET"
sudo strings $DB | grep -B2 -A2 "$TARGET" | head -20 | sed 's/^/  /'
