#!/bin/bash
echo "############ etcd version + systemd env flags (paths/urls only, no key material) ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "/usr/local/bin/etcd --version 2>&1 | head -3" | sed 's/^/   /'
echo "  --- /etc/etcd.env (filtered to url/path/listen flags) ---"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "grep -E 'LISTEN|URL|CERT|KEY|CA|AUTH|NAME|DIR' /etc/etcd.env 2>&1" | sed 's/^/   /'
echo ""
echo "  --- does this etcd binary support --listen-metrics-urls? ---"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "/usr/local/bin/etcd --help 2>&1 | grep -i 'listen-metrics-urls'" | sed 's/^/   /'
echo ""
echo "############ confirm across all 3 control planes: systemd etcd, no 2381 ############"
for ip in 10.100.10.10 10.100.10.14 10.100.10.19; do
  printf "   %-14s etcd=%s  port2381=%s\n" "$ip" \
    "$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip 'systemctl is-active etcd' 2>&1)" \
    "$(ssh -o BatchMode=yes -o ConnectTimeout=6 root@$ip "ss -tln 2>/dev/null | grep -c ':2381'" 2>&1)"
done
echo ""
echo "############ current etcd metrics reachable with CLIENT CERT (proves fix path works) ############"
ssh -o BatchMode=yes -o ConnectTimeout=6 root@10.100.10.10 "curl -s --max-time 6 --cacert /etc/kubernetes/pki/etcd/ca.crt --cert /etc/kubernetes/pki/etcd/client.crt --key /etc/kubernetes/pki/etcd/client.key https://10.100.10.10:2379/metrics 2>&1 | grep -E '^etcd_server_has_leader|^etcd_disk_wal_fsync_duration_seconds_count|^etcd_mvcc_db_total_size_in_bytes|^etcd_server_proposals_committed_total' | head -5" | sed 's/^/   /'
