# node-exporter（主机指标采集）

镜像：`swr.cn-north-4.myhuaweicloud.com/ddn-k8s/quay.io/prometheus/node-exporter:v1.9.1-linuxarm64`
端口：`9100`（指标 `/metrics`）

## 启动

```bash
mkdir -p /deploy/infra/monitor
cp docker-compose.yml /deploy/infra/monitor/
cd /deploy/infra/monitor
docker-compose up -d
```

> 这台麒麟机器上 `docker compose`（带空格）子命令不可用，要用独立二进制
> **`docker-compose`**（v2.29.7，路径 `/usr/bin/docker-compose`）。

## 验证

```bash
docker-compose ps
curl -s http://127.0.0.1:9100/metrics | grep -c '^node_'      # 约 1000+
curl -s http://127.0.0.1:9100/metrics | grep '^node_load1'
ss -lntp | grep 9100
```

## 停止

```bash
docker-compose down
```

## 两个要点

1. **必须 `network_mode: host` + `pid: host`**
   否则 `node_network_*` / `node_processes_*` 这类采集器拿到的是容器自己的命名空间，
   指标会指向容器而不是宿主机。

2. **`--collector.filesystem.mount-points-exclude` 里的 `$` 要写成 `$$`**
   compose 会对 `$` 做变量插值，漏写会导致这条参数被替换成空字符串。

## Prometheus 抓取

```yaml
scrape_configs:
  - job_name: 'node'
    static_configs:
      - targets: ['<主机IP>:9100']
```

## 相关

昇腾 NPU 机器的完整监控（node-exporter + npu-exporter）见同级目录
`../npu-exporter/README.md`。
