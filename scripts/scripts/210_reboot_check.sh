#!/bin/bash
echo '===== /etc/cdi/nvidia.yaml 是否存在/行数 ====='
ls -la /etc/cdi/nvidia.yaml 2>&1
echo '===== udev 规则文件内容 ====='
cat /etc/udev/rules.d/60-nvidia.rules 2>/dev/null
echo '===== modules-load.d ====='
ls -la /etc/modules-load.d/ 2>/dev/null | grep -i nvidia
cat /etc/modules-load.d/nvidia-uvm.conf 2>/dev/null
echo '===== rc.local 的 nvidia 段 ====='
grep -nA8 'NVIDIA device nodes' /etc/rc.local 2>/dev/null
echo '===== rc-local 服务状态 ====='
systemctl is-enabled rc-local 2>&1
ls /etc/systemd/system/multi-user.target.wants/ 2>/dev/null | grep -i rc-local || echo 'rc-local 不在 multi-user.wants（static，开机未必跑）'
echo '===== persistenced 状态 ====='
systemctl is-enabled nvidia-persistenced 2>&1
echo '===== CDI spec 里的 create-devices 钩子（容器自愈关键） ====='
grep -c 'nvidia-cdi-hook create-devices' /etc/cdi/nvidia.yaml 2>/dev/null
grep -m1 'create-symlinks\|create-ldconfig\|create-devices' /etc/cdi/nvidia.yaml 2>/dev/null
