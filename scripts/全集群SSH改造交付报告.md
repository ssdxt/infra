# 吴兴区工业智能体公共底座 — 全集群 SSH 改造交付报告（2026-09-22）

## 最终状态：14/14 台全部达标

| 项 | 状态 |
|---|---|
| sshd | 全部 OpenSSH 10.2p1（/usr/local/openssh-10.2，独立 prefix，对系统 OpenSSL 3.0.2 编译/分发） |
| 业务端口 22 | `ssh-10.2.service`（原生 systemd unit，ExecStartPre 自动 `sshd -t`），banner 全部 `SSH-2.0-OpenSSH_10.2` |
| 管理保留端口 2222 | `ssh-admin.service`，独立实例与独立配置，22 被挤满时仍可登录；仅允许 `10.100.200.*`（管理网段）与 `10.100.10.*`（节点网段）的 root |
| SFTP | `internal-sftp`（进程内），抽查 3.3MB 文件往返 sha256 一致 |
| 库遮蔽 | 14 台 `/etc/ld.so.conf.d/openssl.conf` 全部移除（备份在各机 `/root/openssl.conf.backup-20260922`），libcrypto 统一解析系统 3.0.2 |
| 临时密钥 | .34 上用于分发的 dsh-temp 密钥已从全部 8 台 authorized_keys 撤销 |

## 内核锁定（按既有运维手册执行）

- 全部 14 台运行 `5.15.0-125-generic`；`apt-mark hold` 锁定 125 的 image/headers/modules/modules-extra 共 5 个包
- 非 125 内核已 purge（.14 的 191；其余机器的 78/105，连带 image/headers-generic 元包）
- `/etc/apt/apt.conf.d/20auto-upgrades`（及存在 10periodic 的机器）全部 1→0，自动更新关闭；`apt-config dump` 解析通过
- `GRUB_DEFAULT` 显式钉到 125 内核条目，update-grub 完成，确认 125 条目存在
- 解除锁定：`apt-mark unhold <包名>`

## 网络与工具

- **正向代理**：.14 上 tinyproxy（0.0.0.0:8888，仅放行 10.100.0.0/16），无外网机器的 apt 均已写入 `/etc/apt/apt.conf.d/99proxy` 指向它
- **net-tools**：14 台全部安装

## 各机细节与回滚

- 每台配置备份：`/root/sshd_config.backup-20260922-pre102`；构建日志 `/root/build-102/`（编译的 5 台）；源码/二进制包 `/root/openssh-10.2p1.tar.gz`、`/root/openssh-10.2-bin.tar.gz`
- 单台回滚到发行版 8.9（仅 .14/.34 装有发行版包）：`systemctl disable --now ssh-10.2 && systemctl enable --now ssh`
- 10.2 安全更新流程：换新 tarball → 在任一台编译 → 分发 `/usr/local/openssh-10.2` → `systemctl restart ssh-10.2 ssh-admin`

## 已知事项

- 旧手装 sshd 二进制仍在各机 `/usr/sbin/sshd`（10 台）——已不可用（无遮蔽库）也不参与启动，可择机清理
- unattended-upgrades 服务仍在 enabled，但因 periodic 全 0 且内核 hold，不会再自动改动；如需彻底停用可 `systemctl disable unattended-upgrades`
- `KexAlgorithms` 保持原钉死列表；删除该行可启用 10.x 默认后量子协商（老客户端自动回退，无兼容问题）
