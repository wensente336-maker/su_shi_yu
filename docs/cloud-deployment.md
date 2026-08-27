# 腾讯云方案二部署说明

## 选型

本方案不使用 CKafka、RocketMQ 或 RabbitMQ。当前每周只有少量 Hermes 分析任务，
用腾讯云 PostgreSQL 中的 `hermes_analysis_jobs` 表作为持久化任务队列更合适：

```text
浏览器 → HTTPS/Nginx → CVM（Web、API、Worker）→ TencentDB PostgreSQL
                                       ↑                    │
                         macmini Hermes Agent ──────────────┘
                         （仅主动 HTTPS 出站连接）
```

macmini 不开放端口，不接受云端入站连接。每次领取、完成或失败回传都使用 HMAC 签名、
时间戳和一次性随机数；任务有租约和最多三次尝试。周报仍从
`tang_yu_heng/workspace/weekly_reports/YYYY-Www.md` 在 macmini 本地读取，云端只保存不可变快照。

## 腾讯云资源

1. CVM：广州或深圳地域，Ubuntu 24.04、4 核 8 GB、100 GB SSD、5 Mbps 公网带宽。
2. TencentDB for PostgreSQL：同地域、同 VPC，PostgreSQL 16、2 核 4 GB、50 GB、高可用。
3. 私有 VPC 与两个子网：CVM 和 PostgreSQL 位于同一 VPC；数据库只允许 CVM 安全组访问 5432。
4. 域名、DNS 与 SSL 证书：仅开放 CVM 的 80/443；Docker 应用端口只绑定 `127.0.0.1`。

不要创建 CKafka 或 RabbitMQ。RabbitMQ Serverless 默认仅 VPC 接入；为 macmini 增加公网访问会引入额外 CLB、访问策略与证书管理，和本方案的最小暴露原则不符。

## 云端准备

1. 在 CVM 克隆本仓库，复制 `.env.cloud.example` 为 `.env.cloud`，填写 TencentDB 私网连接串和随机密钥，然后执行 `chmod 600 .env.cloud`。
2. 将 `deploy/nginx-business-dashboard.conf.example` 替换为真实域名和证书路径，启用 Nginx。
3. 在 CVM 执行：

```sh
docker compose --env-file .env.cloud -f compose.cloud.yaml up -d --build
curl --fail https://你的域名/health
```

4. 数据库安全组只放行 CVM 安全组；CVM 安全组仅放行 TCP 80/443。不要开放 8100、3100 或数据库端口。

## macmini Agent 准备

1. 在项目根目录复制 `hermes-agent.env.example` 为 `.env.agent`，设置云端 HTTPS 域名，并填入与 `.env.cloud` 完全相同的 `HERMES_AGENT_SHARED_SECRET`。
2. 运行 `chmod 600 .env.agent`，然后先前台测试：

```sh
/opt/homebrew/bin/python3 hermes_agent.py
```

3. 验证日志出现 `Hermes outbound agent started` 后，将 plist 示例复制至
`~/Library/LaunchAgents/com.business-dashboard.hermes-agent.plist`，执行：

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.business-dashboard.hermes-agent.plist
launchctl kickstart -k gui/$(id -u)/com.business-dashboard.hermes-agent
```

## 上线验收

1. 云端 API 健康检查正常，数据库迁移包含 `20260827_hermes_agent_jobs`。
2. 创建一次经营分析，任务状态从 `queued` 到 `leased` 再到 `completed`。
3. 云端生成周报快照与 `generated` 状态的 Hermes 分析；人工审核后，周六 10:00 才允许企业微信推送。
4. 在 macmini 防火墙与路由器上确认没有新增入站端口映射。
5. 故意停止 Agent 超过租约时间，确认任务可重试且不会生成重复分析记录。

## 仍需人工提供的项目

- 腾讯云账号登录、实名与付费资源下单。
- 已备案域名及 DNS/SSL 证书签发（中国大陆公网部署需要）。
- 企业微信 SSO 的 Corp ID、Agent ID、Secret 与可信回调域名。现有代码已在生产环境拒绝开发身份，但真正的企业微信 OAuth/SSO 代理仍需这些企业凭据才可配置。
