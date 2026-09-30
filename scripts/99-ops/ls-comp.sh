#!/bin/bash
for ip in 10.100.10.10 10.100.10.33; do
  echo "@@@@@ $ip"
  timeout 20 ssh -o BatchMode=yes -o StrictHostKeyChecking=no root@$ip 'ls -la /etc/bash_completion.d/ | grep -E "kubectl|helm|crictl|nerdctl|kubeadm"; echo "---"; wc -l /etc/bash_completion.d/kubectl /etc/bash_completion.d/helm 2>/dev/null' 2>/dev/null
done