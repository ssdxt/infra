#!/bin/bash
set -e
export HTTPS_PROXY=http://127.0.0.1:12450
cd ~/longhorn-upgrade
python3 - <<'EOF'
import subprocess, yaml, json, collections
vers=['1.8.2','1.9.2','1.10.2','1.11.3','1.12.1','1.13.0']
union=collections.OrderedDict()
def walk(d, out):
    if isinstance(d, dict):
        if 'repository' in d and isinstance(d.get('repository'), str) and 'tag' in d and isinstance(d.get('tag'), str):
            repo=d['repository'].split('/')[-1]
            out.append((d['repository'], d['tag'], repo))
        for v in d.values(): walk(v, out)
    elif isinstance(d, list):
        for v in d: walk(v, out)
for v in vers:
    vals=yaml.safe_load(subprocess.run(['helm','show','values',f'longhorn-{v}.tgz'],capture_output=True,text=True,env={'HTTPS_PROXY':'http://127.0.0.1:12450','PATH':'/usr/local/bin:/usr/bin:/bin'}).stdout)
    imgs=[]; walk(vals, imgs)
    print(f'=== {v}: {len(imgs)} images')
    for r,t,name in imgs:
        if '@' in t:
            print(f'  DIGEST-TAG: {r}:{t}')
            t=t.split('@')[0]
        print(f'  {r}:{t} -> harbor.wuxing.local/longhorn/{name}:{t}')
        union[f'longhorn/{name}:{t}']=True
    # write harbor-ized values: rewrite every repository field
    def rewrite(d):
        if isinstance(d, dict):
            if 'repository' in d and isinstance(d.get('repository'), str) and d.get('tag'):
                d['repository']='harbor.wuxing.local/longhorn/'+d['repository'].split('/')[-1]
            for k,val in list(d.items()):
                if k=='tag' and isinstance(val,str) and '@' in val: d[k]=val.split('@')[0]
                rewrite(val)
        elif isinstance(d, list):
            for x in d: rewrite(x)
    rewrite(vals)
    with open(f'/tmp/values-harbor-{v}.yaml','w') as f: yaml.safe_dump(vals,f,sort_keys=False)
print('=== UNION unique images:', len(union))
for i in union: print(i)
EOF
ls /tmp/values-harbor-*.yaml
