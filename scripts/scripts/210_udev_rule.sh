#!/bin/bash
echo '== create udev rule =='
cat > /etc/udev/rules.d/60-nvidia.rules <<'EOF'
# Recreate NVIDIA device nodes when driver modules register devices (driver rpm ships no rules)
KERNEL=="nvidia[0-9]*", RUN+="/bin/mknod -m 666 /dev/%k c 195 %n"
KERNEL=="nvidiactl", RUN+="/bin/mknod -m 666 /dev/nvidiactl c 195 255"
KERNEL=="nvidia-modeset", RUN+="/bin/mknod -m 666 /dev/nvidia-modeset c 195 254"
KERNEL=="nvidia-uvm", RUN+="/bin/mknod -m 666 /dev/nvidia-uvm c 195 253"
EOF
cat /etc/udev/rules.d/60-nvidia.rules
echo '== rc-local enable status =='
ls -la /etc/systemd/system/multi-user.target.wants/ 2>/dev/null | grep -i rc-local || echo 'rc-local NOT in multi-user wants'
echo '== modules-load files =='
ls -la /etc/modules-load.d/
cat /etc/modules-load.d/nvidia-uvm.conf 2>/dev/null
echo '== reload udev rules (no disruption) =='
udevadm control --reload-rules && echo 'udev rules reloaded'
echo '== final file inventory =='
ls -la /etc/cdi/nvidia.yaml /etc/udev/rules.d/60-nvidia.rules /etc/modules-load.d/nvidia-uvm.conf 2>&1
