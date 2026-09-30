#!/bin/bash
echo "=== qwen3_next_80b 容器详情 ==="
docker inspect qwen3_next_80b_a3b_instruct_nvfp4 --format '创建时间: {{.Created}}
镜像: {{.Config.Image}}
重启策略: {{.HostConfig.RestartPolicy.Name}}
运行状态: {{.State.Status}} (StartedAt {{.State.StartedAt}})
GPU显存配额: {{range .HostConfig.DeviceRequests}}{{.Count}} x {{range .Capabilities}}{{.}}{{end}}{{end}}'
echo
echo "=== qwen3_30b 容器详情(对比) ==="
docker inspect qwen3_30b_a3b_instruct_nvfp4 --format '创建时间: {{.Created}}
镜像: {{.Config.Image}}
运行状态: {{.State.Status}}'
echo
echo "=== 模型文件是否存在 ==="
ls -d /root/.cache/modelscope/hub/models/holardata/* 2>/dev/null
echo
echo "=== qwen3_next_80b 当前服务状态 ==="
curl -s -o /dev/null -w "17104 /health -> %{http_code}\n" --connect-timeout 3 -m 8 "http://192.168.21.105:17104/health" 2>/dev/null
curl -s --connect-timeout 3 -m 8 "http://192.168.21.105:17104/v1/models" 2>/dev/null | head -c 300
echo
echo "=== qwen3_next_80b 日志 (tail 8) ==="
docker logs qwen3_next_80b_a3b_instruct_nvfp4 --tail 8 2>&1 | tail -8
