#!/bin/bash
# 安装 metrics-server（让 kubectl top / HPA 可用）
# 说明: metrics-server 提供 metrics.k8s.io API，prometheus-stack 不提供这个
set -e
export KUBECONFIG=/etc/kubernetes/admin.conf
H=harbor.wuxing.local
IMG=$H/metrics-server/metrics-server:v0.7.2

cat <<YAML | kubectl apply -f -
apiVersion: v1
kind: ServiceAccount
metadata: {name: metrics-server, namespace: kube-system}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata: {name: system:metrics-server}
rules:
- apiGroups: [""]
  resources: [nodes/metrics, nodes/stats, pods, nodes]
  verbs: [get, list, watch]
- apiGroups: [""]
  resources: [pods/stats]
  verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: system:metrics-server}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:metrics-server}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata: {name: metrics-server-auth-reader, namespace: kube-system}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: Role, name: extension-apiserver-authentication-reader}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata: {name: metrics-server:system:auth-delegator}
roleRef: {apiGroup: rbac.authorization.k8s.io, kind: ClusterRole, name: system:auth-delegator}
subjects: [{kind: ServiceAccount, name: metrics-server, namespace: kube-system}]
---
apiVersion: apiregistration.k8s.io/v1
kind: APIService
metadata:
  name: v1beta1.metrics.k8s.io
spec:
  service: {name: metrics-server, namespace: kube-system}
  group: metrics.k8s.io
  version: v1beta1
  insecureSkipTLSVerify: true
  groupPriorityMinimum: 100
  versionPriority: 100
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: metrics-server, namespace: kube-system, labels: {k8s-app: metrics-server}}
spec:
  replicas: 1
  selector: {matchLabels: {k8s-app: metrics-server}}
  template:
    metadata: {labels: {k8s-app: metrics-server}}
    spec:
      serviceAccountName: metrics-server
      priorityClassName: system-cluster-critical
      nodeSelector: {kubernetes.io/os: linux}
      containers:
      - name: metrics-server
        image: $IMG
        args:
        - --cert-dir=/tmp
        - --secure-port=10250
        - --kubelet-preferred-address-types=InternalIP
        - --kubelet-use-node-status-port
        - --metric-resolution=30s
        # 关键: kubelet 是自签证书，必须跳过校验
        - --kubelet-insecure-tls
        ports:
        - {name: https, containerPort: 10250, protocol: TCP}
        livenessProbe:
          httpGet: {path: /livez, port: https, scheme: HTTPS}
          initialDelaySeconds: 20
        readinessProbe:
          httpGet: {path: /readyz, port: https, scheme: HTTPS}
          initialDelaySeconds: 20
---
apiVersion: v1
kind: Service
metadata: {name: metrics-server, namespace: kube-system, labels: {k8s-app: metrics-server}}
spec:
  selector: {k8s-app: metrics-server}
  ports: [{name: https, port: 443, targetPort: https}]
YAML

echo "等 30 秒后验证:"
echo "  kubectl top nodes"
echo "  kubectl top pods -A | head"
