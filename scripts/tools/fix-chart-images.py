#!/usr/bin/env python3
"""
通用工具：把 helm chart 的 values.yaml 里所有镜像改写为 Harbor 地址。
用法: python3 fix-chart-images.py <chart包或values.yaml> <Harbor项目名> <Harbor域名> [输出文件]

规则: 任何同时含 repository 和 tag 的字典 → repository 改为 <域名>/<项目>/<原仓库末段>
      同时把 registry 字段清空（避免拼成 quay.io/harbor... 这种错路径）
"""
import sys, os, subprocess, yaml

def load_values(src):
    if src.endswith(('.tgz', '.tar.gz')):
        r = subprocess.run(['helm', 'show', 'values', src], capture_output=True, text=True)
        if r.returncode != 0:
            print("helm show values 失败:", r.stderr[:200]); sys.exit(1)
        return yaml.safe_load(r.stdout)
    with open(src) as f:
        return yaml.safe_load(f)

def rewrite(node, project, harbor):
    n = 0
    if isinstance(node, dict):
        if 'repository' in node and isinstance(node['repository'], str):
            repo = node['repository']
            name = repo.rstrip('/').split('/')[-1]          # 取末段作为仓库名
            if name and 'harbor' not in repo:
                node['repository'] = f"{harbor}/{project}/{name}"
                # 清掉 registry 前缀，防止拼成 quay.io/harbor...
                if 'registry' in node:
                    node['registry'] = harbor
                n += 1
        for v in node.values():
            n += rewrite(v, project, harbor)
    elif isinstance(node, list):
        for v in node:
            n += rewrite(v, project, harbor)
    return n

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    src, project, harbor = sys.argv[1], sys.argv[2], sys.argv[3]
    out = sys.argv[4] if len(sys.argv) > 4 else f"/tmp/{project}-values-harbor.yaml"
    v = load_values(src)
    cnt = rewrite(v, project, harbor)
    with open(out, 'w') as f:
        yaml.safe_dump(v, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"已改写 {cnt} 处镜像 -> {harbor}/{project}/...  输出: {out}")
