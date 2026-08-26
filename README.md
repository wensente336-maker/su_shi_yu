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

## 目录

- `frontend/`：Next.js 响应式 Web 应用。
- `backend/`：FastAPI 服务与后续数据库迁移。
- `docs/`：架构、数据字典与部署说明。
