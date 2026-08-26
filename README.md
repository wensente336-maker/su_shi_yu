# Business Dashboard

企业 AI 经营驾驶舱的 MVP 项目骨架。

## 当前阶段

本阶段只提供运行基础设施：Next.js 前端、FastAPI 后端和 PostgreSQL 数据库。业务表、动态表单、身份权限与 AI 分析在后续阶段实现。

## 启动

1. 复制 `.env.example` 为 `.env` 并设置强密码。
2. 执行 `docker compose up --build`。
3. 打开前端 `http://localhost:3000`；后端健康检查为 `http://localhost:8000/health`。

## 目录

- `frontend/`：Next.js 响应式 Web 应用。
- `backend/`：FastAPI 服务与后续数据库迁移。
- `docs/`：架构、数据字典与部署说明。
