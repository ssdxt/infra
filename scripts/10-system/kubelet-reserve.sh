#!/bin/bash
# kubelet resource reservation - idempotent, with auto-rollback
set -u
F=/var/lib/kubelet/config.yaml
DATE=$(date +%Y%m%d)
BAK="$F.bak.$DATE"

# 1. backup (keep first backup of the day, idempotent)
if [ ! -f "$BAK" ]; then cp -a "$F" "$BAK" || exit 1; fi
echo "BACKUP=$BAK"

# 2. merge via python/PyYAML
python3 - <<'PYEOF'
import yaml
F='/var/lib/kubelet/config.yaml'
with open(F) as f: cfg=yaml.safe_load(f)
sr=cfg.get('systemReserved') or {}
sr.update({'cpu':'300m','memory':'500Mi'})
cfg['systemReserved']=sr
kr=cfg.get('kubeReserved') or {}
kr.update({'cpu':'300m','memory':'500Mi','ephemeral-storage':'5Gi'})
cfg['kubeReserved']=kr
with open(F,'w') as f: yaml.safe_dump(cfg,f,default_flow_style=False,sort_keys=True)
print("MERGED OK")
PYEOF
if [ $? -ne 0 ]; then echo "PYFAIL: rollback"; cp -a "$BAK" "$F"; exit 1; fi

# 3. restart kubelet, verify, rollback on failure
systemctl restart kubelet
sleep 6
if [ "$(systemctl is-active kubelet)" != "active" ]; then
  echo "KUBELET DOWN: ROLLBACK"
  cp -a "$BAK" "$F"
  systemctl restart kubelet
  sleep 5
  systemctl is-active kubelet
  journalctl -u kubelet --no-pager -n 20
  exit 1
fi
# config sanity: kubelet validates config at start; also check healthz
sleep 2
curl -s -o /dev/null -w "healthz=%{http_code}\n" http://127.0.0.1:10248/healthz
echo "--- new reserved blocks ---"
python3 -c "import yaml;c=yaml.safe_load(open('$F'));print('systemReserved:',c['systemReserved']);print('kubeReserved:',c['kubeReserved'])"
echo "RESULT=OK"
