#!/usr/bin/env python3
"""
通用工具：把 helm chart 的 values.yaml 里所有镜像改写为 Harbor 地址。
用法: python3 fix-chart-images.py <chart包或values.yaml> <Harbor项目名> <Harbor域名> [输出文件]

规则: 任何含 repository 的字典 → 把它指向 Harbor 的 <项目>/<原仓库末段>
      - 若该字典同时含 registry 字段：registry=<域名>，repository=<项目>/<仓库末段>
        （因为多数 chart 的 image helper 会拼成 registry/repository）
      - 若不含 registry 字段：repository=<域名>/<项目>/<仓库末段>
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
                if 'registry' in node:
                    # helper 通常拼 registry/repository，故 registry 放域名、repository 放 项目/仓库名
                    node['registry'] = harbor
                    node['repository'] = f"{project}/{name}"
                else:
                    node['repository'] = f"{harbor}/{project}/{name}"
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
