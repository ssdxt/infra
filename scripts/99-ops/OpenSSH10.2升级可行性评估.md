# OpenSSH 升级到 10.2 可行性评估（吴兴区工业智能体公共底座集群）

- 评估时间：2026-09-22
- 依据：上游发行说明 + 全 14 台实机核查（证据见 `fleet_ssh_probe.json`）

## 一、结论先行

**技术上完全可行，但"按现在这批机器上的装法"不可持续——那套装法本身就是本次 .14/.34 事故和 12 台 SFTP 集体瘫痪的根源。** 要上 10.2 必须换正确姿势重建一遍；若无版本号硬性要求，更推荐收敛回发行版 8.9p1（Ubuntu 官方持续 backport 安全修复）。

## 二、上游事实（来源：openssh.org 官方发行说明）

- [10.2p1（2025-10-10）](https://www.openssh.org/txt/release-10.2)：纯 bugfix 版（修 ControlPersist 终端、PKCS#11 取 key、agent 里的 CA 签名）。
- [10.0（2025-04-09）](https://www.openssh.org/txt/release-10.0) 才是破坏性变更所在：
  - 彻底移除 DSA（ssh-dss）算法；
  - 认证阶段拆到独立 `sshd-auth` 二进制（发行版打包需跟进）；
  - sshd 默认禁用 modp Diffie-Hellman 系列 KEX；
  - 客户端默认启用后量子 `mlkem768x25519-sha256` 密钥协商；
  - 官方明示：`OpenSSH_10.*` 的版本号会混淆用 `OpenSSH_1*` 通配匹配的老软件——**过漏扫/等保的环境可能出现版本误报，需提前跟扫描方确认规则**。
- libcrypto 依赖：portable 版支持 OpenSSL 1.1.1～3.x / LibreSSL / AWS-LC。**Ubuntu 22.04 自带的 OpenSSL 3.0.2 即可构建 10.2p1，不需要额外装新版 OpenSSL。**

## 三、集群现状矩阵（本次实测）

| 机器 | sshd 二进制 | 服务 | sshd -t | SFTP | 状态判读 |
|---|---|---|---|---|---|
| .14（控制面2） | 发行版 8.9p1-0.17 | active | rc=0 | 正常 | 昨日已修复，全集群唯一健康样板 |
| .34（运行2） | 发行版 8.9 | active | rc=0 | 正常 | **已于 2026-09-22 16:28 按手册修复**（原状态与 .14 事故前同款，修复日志 /root/fix_openssl_shadow_20260922.log） |
| 其余 12 台 | 手装上游 10.2p1（2025-12-04 构建，链接 /usr/local/openssl 3.4.0） | active | rc=0 | **全部坏** | 包被 apt 移除（dpkg=rc），Subsystem 指向不存在的 /usr/lib/openssh/sftp-server |

手装法的四个硬伤：
1. **SFTP 全灭**：openssh 包卸载时 sftp-server 一并消失，配置没改；
2. **全局 OpenSSL 遮蔽**：`/etc/ld.so.conf.d/openssl.conf` 让所有发行版二进制加载 3.4.0 → 任何 apt 操作碰到 openssh 就复刻 .14/.34 事故；且这 12 台的 sshd 硬依赖该遮蔽，**单独删遮蔽会让它们重启即死**；
3. **服务管理退化**：systemd 跑的是 SysV `/etc/init.d/ssh` 兼容脚本（无原生 unit、无 ExecStartPre 校验）；
4. **脱离包管理**：后续 CVE 修复全靠手工重编译，无版本台账。

## 四、两个可选方案

### 方案 A：正规化地上 10.2p1（有版本号硬性要求时）
1. 源码构建：`./configure` 直接对**系统 OpenSSL 3.0.2**，独立 prefix（如 /usr/local/openssh-10.2），不装 /usr/local/openssl、不写 ld.so.conf.d；
2. 配置 `Subsystem sftp internal-sftp`（进程内实现，根除"sftp-server 文件消失"这类事故）；
3. 写原生 systemd unit（ExecStartPre=sshd -t），发行版 openssh 包保持安装但 mask 其 unit，明确谁占 22 端口；
4. 统一构建脚本 + 版本锁定 + 每台 md5sum 台账；安全更新 = 重新构建发布（要有这个觉悟）；
5. 分批灰度：控制面 → 平台 → 运行节点，每台保留旧方案回滚路径。

### 方案 B：全量收敛回发行版 8.9p1（无硬性要求时，推荐）
- .14 即现成样板（修复脚本已验证）；Ubuntu 对 8.9p1 持续 backport CVE 修复，`-3ubuntu0.17` ≠ 2022 年裸 8.9；
- 步骤：各台 `apt install --reinstall openssh-server openssh-sftp-server`（或直接装）→ 移除 ld 遮蔽 → rescue 端口护航下切换 → 回归 SFTP；
- unattended-upgrades 从此安全，运维成本最低。

### 共同前置（无论 A/B）
- **先排 .34 的雷**（照 .14 手册：干跑验证 → 移遮蔽 → rescue 2222 → 换进程 → 回归）；
- 12 台手装机的切换窗口中要一次性完成"新二进制 + 去遮蔽 + 重启"，不能只做一半；
- 与当初安装 10.2 的负责人确认动机（漏扫阈值？功能需求？），避免白折腾。

## 五、遗留风险提示
- 12 台手装机在完成方案 A/B 之前，**保持现状不要动 apt/openssh**，一次误升级就是一次 .14 事故；
- ~~.34 在处置前不能重启~~（已于 16:28 修复并回归验证：banner 回 8.9p1 Ubuntu、sshd -t rc=0、SFTP 往返成功）。
