# 部署、备份与验收

## 生产前置条件

1. 从 `.env.example` 创建受权限保护的 `.env`，设置强数据库密码。
2. 设置 `ENVIRONMENT=production`。此时开发身份请求头会被拒绝；必须先接入企业微信身份验证适配器。
3. 将 `CORS_ORIGINS` 限制为实际前端域名，多个域名以逗号分隔。
4. 仅在获批后设置 `AI_PROVIDER=openai`、`OPENAI_API_KEY`、`WECOM_PUSH_ENABLED=true` 和 `WECOM_WEBHOOK_URL`。密钥与 Webhook 不得提交到 Git。
5. 确认 `REPORT_SOURCE_HOST_PATH` 只指向 `tang_yu_heng/workspace`，并保持容器挂载为只读。

## 运行与检查

```sh
docker-compose up -d --build
./scripts/smoke_test.sh
```

验证 API 健康检查、驾驶舱指标、部门越权返回 `403`、来源挂载 `rw=false`，以及未启用推送时推送记录为 `skipped`。

## 备份与恢复

每天执行一次：

```sh
./scripts/backup_postgres.sh
```

恢复前先停止 API 写入，并使用明确的备份文件：

```sh
gunzip -c backups/business-dashboard-YYYYMMDD-HHMMSS.sql.gz | docker-compose exec -T db psql -U business_app business_dashboard
```

备份目录应位于加密磁盘或受控对象存储，并按公司保留策略清理。
