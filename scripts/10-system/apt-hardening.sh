#!/bin/bash
# disable auto-update side effects + hold kernel (idempotent)
set -u
echo "== before =="
echo "holds:"; apt-mark showhold
echo "unattended-upgrades: $(systemctl is-active unattended-upgrades 2>/dev/null)"

# 1. ensure 20auto-upgrades exists with required lines
F20=/etc/apt/apt.conf.d/20auto-upgrades
if [ ! -f "$F20" ]; then
  printf 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n' > "$F20"
  echo "20auto-upgrades: created"
else
  grep -q 'Update-Package-Lists' "$F20" || echo 'APT::Periodic::Update-Package-Lists "1";' >> "$F20"
  grep -q 'Unattended-Upgrade' "$F20" || echo 'APT::Periodic::Unattended-Upgrade "1";' >> "$F20"
  echo "20auto-upgrades: exists, ensured keys"
fi

# 2. hardening file 52wxq-hardening
F52=/etc/apt/apt.conf.d/52wxq-hardening
cat > "$F52" <<'EOF'
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
Unattended-Upgrade::Remove-Unused-Dependencies "false";
EOF
echo "52wxq-hardening: written"

# 3. hold kernel if not held
KP=""
for p in $(dpkg -l 'linux-image-[0-9]*' 2>/dev/null | awk '/^ii/{print $2}'); do
  ver=${p#linux-image-}
  if [ "$ver" = "$(uname -r)" ]; then KP="$p"; fi
done
[ -z "$KP" ] && KP=linux-image-generic
if apt-mark showhold | grep -qxE "(linux-image-generic|$KP)"; then
  echo "kernel already held: $(apt-mark showhold | grep linux | tr '\n' ' ')"
else
  # hold meta package (survives version upgrades) + current versioned image if found
  apt-mark hold linux-image-generic >/dev/null 2>&1 && echo "held: linux-image-generic"
  [ -n "$(dpkg -l "$KP" 2>/dev/null | awk '/^ii/')" ] && apt-mark hold "$KP" >/dev/null 2>&1 && echo "held: $KP"
fi
echo "== after =="
apt-mark showhold
apt-config dump 2>/dev/null | grep -E 'Automatic-Reboot|Remove-Unused-Dependencies' | sort -u
echo "RESULT=OK"
