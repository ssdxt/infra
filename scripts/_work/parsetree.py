#!/usr/bin/env python3
"""从 containerd 的 meta.db 解析 snapshot 的 (key, parent) 关系，只读分析。"""
import re, sys, collections

DB = "/deploy/docker/containerd/daemon/io.containerd.metadata.v1.bolt/meta.db"
data = open(DB, "rb").read()
print(f"  文件大小: {len(data)} 字节")

# 解析 name(<NAME>)parent(<PARENT>) 结构
pat = re.compile(rb"name([A-Za-z0-9/._:+-]{4,140}?)parent(sha256:[0-9a-f]{64})")
pairs = pat.findall(data)
print(f"  解析出 name/parent 对: {len(pairs)} 组")

# 归一化 key：去掉 moby/N/ 前缀
def norm(k):
    k = k.decode()
    m = re.match(r"moby/\d+/(.+)$", k)
    return m.group(1) if m else k

rel = collections.defaultdict(set)   # parent -> {children}
nodes = set()
for name, parent in pairs:
    k = norm(name)
    p = parent.decode()
    nodes.add(k); nodes.add(p)
    rel[p].add(k)

# 找出 mis-tei 相关的链
mis = [n for n in nodes if n == "sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3"]
print(f"\n  节点总数: {len(nodes)}")

TARGET = "sha256:37250a17e932419f4b54e624c819baf38c0025e7f9c4ba0e15af15f14a3d74c3"
print(f"\n=== 以 {TARGET[:20]}... 为根的子树 ===")
def dump(node, depth=0, seen=None):
    seen = seen or set()
    if node in seen or depth > 50:
        return
    seen.add(node)
    kids = sorted(rel.get(node, []))
    print("  " + "  " * depth + f"{node}   (children={len(kids)})")
    for k in kids:
        dump(k, depth + 1, seen)

dump(TARGET)

print("\n=== 反向：谁是它的 parent ===")
for p, kids in rel.items():
    if TARGET in kids:
        print(f"  parent = {p}")

print("\n=== 从叶子往根排序（删除顺序）===")
order = []
def post(node, seen):
    if node in seen:
        return
    seen.add(node)
    for k in sorted(rel.get(node, [])):
        post(k, seen)
    order.append(node)
post(TARGET, set())
for i, n in enumerate(order):
    print(f"  {i+1:2d}. {n}")
