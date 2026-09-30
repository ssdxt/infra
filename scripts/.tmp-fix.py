import re
p='/data1/ssdxt/values/cilium-values-unified.yaml'
lines=open(p).read().splitlines()
targets=['bandwidthManager','egressGateway','bgpControlPlane']
for t in targets:
    idx=[i for i,l in enumerate(lines) if re.match(r'^%s:\s*(#.*)?$'%t,l)]
    if not idx: raise SystemExit('missing '+t)
    i=idx[0]
    j=i+1
    while j<len(lines) and (lines[j].startswith(' ') or lines[j].strip()==''):
        if re.match(r'^  enabled:\s*false\s*$',lines[j]): lines[j]='  enabled: true'
        j+=1
open(p,'w').write('\n'.join(lines)+'\n')
for t in ['encryption','bandwidthManager','egressGateway','bgpControlPlane']:
    i=[l for l in lines if l.startswith(t+':')][0]
    k=lines.index(i)
    print('\n'.join(lines[k:k+4])); print('---')