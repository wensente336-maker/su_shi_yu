# Business Dashboard

企业 AI 经营驾驶舱的 MVP 项目骨架。

## 当前阶段

本阶段只提供运行基础设施：Next.js 前端、FastAPI 后端和 PostgreSQL 数据库。业务表、动态表单、身份权限与 AI 分析在后续阶段实现。

第二阶段已将部门、员工、统计周与表单字段配置纳入数据库。开发环境默认以 `admin` 身份访问，也可通过 `X-Development-User` 请求头模拟其他员工；生产接入时需替换为企业微信身份验证。

## 启动

1. 复制 `.env.example` 为 `.env` 并设置强密码。
2. 执行 `docker-compose up --build`。
3. 打开前端 `http://localhost:3100`；后端健康检查为 `http://localhost:8100/health`。端口可在 `.env` 中调整。

## 第二阶段验证接口

- `GET /api/v1/me`：当前开发身份。
- `GET /api/v1/departments`：已启用部门。
- `GET /api/v1/reporting-weeks/current`：当前统计周。
- `GET /api/v1/form-schemas`：当前身份可用的表单。
- `GET /api/v1/form-schemas/sales-weekly-v1`：动态销售表单结构。

## 周报快照与 AI 分析

`api` 容器只读挂载 `tang_yu_heng` 的工作区到 `/report-source`。读取器优先读取命名匹配统计周的 Markdown；不存在时仅读取 `daily_reports/YYYY-MM-DD.json`，并以 `weekly_pipeline_runs` 元数据补充覆盖情况。快照写入本项目数据库，不会向来源 Profile 写入文件。

- `POST /api/v1/report-snapshots`：生成当前周的只读来源快照。
- `POST /api/v1/business-analyses`：合并快照与结构化提交数据；默认仅保存待生成记录。
- `POST /api/v1/business-analyses/{id}/review`：人工审核通过或驳回。

配置 `AI_PROVIDER=openai` 和未提交到 Git 的 `OPENAI_API_KEY` 后，分析接口才会调用模型；未配置时不会产生伪造结论。

## 驾驶舱与企业微信推送

- `GET /api/v1/dashboard/overview`：当前统计周的经营指标、周报快照和最新分析状态。
- `POST /api/v1/wecom-deliveries/weekly`：管理员手动触发推送（默认只记录“未启用”，不会向外发送）。
- `GET /api/v1/wecom-deliveries`：推送审计记录。

仅当 `WECOM_PUSH_ENABLED=true`、配置未提交到 Git 的 `WECOM_WEBHOOK_URL`，且存在人工审核通过的 AI 分析时，系统才会发送企业微信机器人 Markdown 消息。启用后会在 `WECOM_PUSH_WEEKDAY`（默认周五）`WECOM_PUSH_HOUR`（默认 18 点）定时执行。

## 目录

- `frontend/`：Next.js 响应式 Web 应用。
- `backend/`：FastAPI 服务与后续数据库迁移。
- `docs/`：架构、数据字典与部署说明。
