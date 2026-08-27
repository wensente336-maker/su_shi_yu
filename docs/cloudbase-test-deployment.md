# CloudBase 免费测试环境部署

该环境用于验证表单、经营看板、CloudBase 定时器与 macmini Hermes Agent 的完整链路。
不要录入真实客户、财务或员工敏感数据；CloudBase 默认域名仅限开发测试。

## 架构

```text
CloudBase 静态托管（Web） → CloudBase 云托管（FastAPI） → CloudBase PostgreSQL
                                                   ↑
                         CloudBase Timer ──────────┘
macmini Hermes Agent ─────────────────────────────→ 领取/回传分析任务
```

云托管 API 的最小实例设为 `0`，空闲时缩容；不要部署现有 `worker` 容器。
周六上午 10:00 由 `weekly-cycle` 云函数调用受保护的 API 入口，后端仍以
`WecomDelivery` 记录保证幂等。

## 开通后需要填写的值

创建免费 CloudBase 环境后，记录以下值，但不要提交进 Git：

- `CLOUDBASE_ENV_ID`
- CloudBase PostgreSQL 的连接串（填入 API 服务的 `DATABASE_URL`）
- CloudBase 云托管 API 的 HTTPS 地址
- 随机生成的 `CLOUDBASE_SCHEDULER_TOKEN`
- 与 macmini `.env.agent` 同步的 `HERMES_AGENT_SHARED_SECRET`

## API 服务

在 CloudBase「云托管」中新建 `business-dashboard-api` 服务，从 `backend/`
目录上传代码并使用其中 Dockerfile，服务端口为 `8000`。最小实例设为 `0`。

配置 `DATABASE_URL`、`CLOUDBASE_SCHEDULER_TOKEN`、企业微信机器人配置、
`HERMES_AGENT_ENABLED=true` 等环境变量。测试阶段不要开放真实企业数据。

## 静态前端

在 `frontend/` 目录执行：

```sh
CLOUDBASE_STATIC_EXPORT=true \
NEXT_PUBLIC_API_BASE_URL=https://REPLACE_WITH_CLOUDBASE_API_HOST \
npm run build
```

将 `frontend/out/` 部署到 CloudBase 静态网站托管。测试阶段可使用默认域名。

## 周六定时任务

复制 `cloudbase/cloudbaserc.test.example.json` 为 CloudBase CLI 使用的
`cloudbaserc.json`，填入环境 ID。为 `weekly-cycle` 函数设置：

- `WEEKLY_CYCLE_ENDPOINT=https://REPLACE_WITH_CLOUDBASE_API_HOST/api/v1/internal/cloudbase/weekly-cycle`
- `CLOUDBASE_SCHEDULER_TOKEN=与 API 完全相同的随机值`

定时表达式 `0 0 10 * * 6 *` 表示周六 10:00。部署后必须在控制台核对触发器时区。

## macmini Agent

将 `.env.agent` 的 `HERMES_AGENT_CLOUD_URL` 改为 CloudBase API HTTPS 地址，
重启 Agent 后验证任务能从 `queued` 依次进入 `leased`、`completed`。
