#!/bin/bash
set -e
cd ~/longhorn-upgrade
for v in 1.8.2 1.9.2 1.10.2 1.11.3 1.12.1 1.13.0; do
  helm template test longhorn-$v.tgz -n longhorn-system > /tmp/render-$v.yaml 2>/dev/null
done
# extract image repos+tags per chart
python3 - <<'EOF'
import re, collections
vers=['1.8.2','1.9.2','1.10.2','1.11.3','1.12.1','1.13.0']
allimgs=collections.OrderedDict()
for v in vers:
    imgs=set()
    txt=open(f'/tmp/render-{v}.yaml').read()
    for m in re.finditer(r'image:\s*"([^"]+)"', txt):
        imgs.add(m.group(1))
    for m in re.finditer(r'image:\s*(\S+)', txt):
        imgs.add(m.group(1).strip('"'))
    norm=set()
    for i in imgs:
        if i.startswith('{{') or 'harbor.wuxing.local' in i: continue
        # split repo:tag
        if ':' in i.rsplit('/',1)[-1]:
            repo,tag=i.rsplit(':',1)
        else:
            repo,tag=i,''
        if '@' in repo: repo=repo.split('@')[0]
        norm.add(f'{repo}:{tag}')
    print(f'=== {v} ({len(norm)})')
    for i in sorted(norm): print('  ',i)
    allimgs[v]=norm
# union
union=set()
for s in allimgs.values(): union|=s
print('=== UNION', len(union))
for i in sorted(union): print(i)
EOF
