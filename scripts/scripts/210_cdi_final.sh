#!/bin/bash
echo '== regenerate CDI =='
nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml 2>&1 | tail -2
echo '== uvm in yaml? =='
grep -c 'nvidia-uvm' /etc/cdi/nvidia.yaml
echo '== container device test =='
docker run --rm --device nvidia.com/gpu=all redis:8.6.2 sh -c 'ls /dev/nvidia* 2>/dev/null'
echo '== boot persistence: rc.local mknod block =='
grep -q 'nvidia-uvm' /etc/rc.local 2>/dev/null || cat >> /etc/rc.local <<'EOF'

# NVIDIA device nodes (driver rpm installs no udev rules)
[ -e /dev/nvidia0 ] || mknod -m 666 /dev/nvidia0 c 195 0
[ -e /dev/nvidia1 ] || mknod -m 666 /dev/nvidia1 c 195 1
[ -e /dev/nvidiactl ] || mknod -m 666 /dev/nvidiactl c 195 255
[ -e /dev/nvidia-modeset ] || mknod -m 666 /dev/nvidia-modeset c 195 254
[ -e /dev/nvidia-uvm ] || mknod -m 666 /dev/nvidia-uvm c 195 253
EOF
chmod +x /etc/rc.local /etc/rc.d/rc.local 2>/dev/null
systemctl enable rc-local 2>&1 | tail -1
echo '--- rc.local tail ---'
tail -8 /etc/rc.local
