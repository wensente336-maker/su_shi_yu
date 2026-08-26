# MVP 架构基线

```text
Web（Next.js） → API（FastAPI） → PostgreSQL
                         ↓
      后续：周报读取器 / AI Adapter / 企业微信 Adapter
```

周报来源配置为跨 profile 的只读路径：优先读取 Markdown 周报；未生成时，从
`tang_yu_heng/workspace/daily_reports/YYYY-MM-DD.json` 聚合，并同时记录
`weekly_pipeline_runs` 的运行元数据。业务实现阶段不得写入来源 profile。
