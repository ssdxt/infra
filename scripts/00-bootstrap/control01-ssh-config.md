# ============ 追加到 C:\Users\CC\.ssh\config 末尾 ============
# VS Code Remote-SSH 连 control01（10.100.10.10），免密走 id_ed25519

Host control01
    HostName 10.100.10.10
    User root
    Port 22
    IdentityFile C:/Users/CC/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
    TCPKeepAlive yes
    ServerAliveInterval 30
    ServerAliveCountMax 20

Host 10.100.10.10
    HostName 10.100.10.10
    User root
    Port 22
    IdentityFile C:/Users/CC/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
    TCPKeepAlive yes
    ServerAliveInterval 30
    ServerAliveCountMax 20
# ============ 追加到这里为止 ============
