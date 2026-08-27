# 无服务器月费的 Cloudflare 部署

本方案将 Web、API、PostgreSQL、Worker、Hermes 和周报文件都保留在 macmini，
只由 `cloudflared` 主动向 Cloudflare 建立出站连接。无需 CVM、托管数据库或公网 IP。

```text
员工浏览器 → Cloudflare Access → Cloudflare Tunnel → macmini Web / API
                                                    └→ Hermes、周报、PostgreSQL
```

## 域名审核期间

已安装 `cloudflared`，现有局域网服务保持不变。不要启用 Quick Tunnel：它没有稳定地址，
也不能作为带经营数据的正式入口。

## 域名审核通过后的配置

1. 在 Cloudflare 添加 `sz-yingjin.top`，按控制台提供的两个名称服务器到注册商修改 DNS。
2. 在 Cloudflare Zero Trust 创建一个 Named Tunnel，名称为 `business-dashboard-macmini`。
3. 将 `deploy/cloudflare-tunnel/config.yml.example` 复制到
   `/Users/yucai/.config/cloudflared/config.yml`，填入 Tunnel UUID；下载的凭据 JSON 保留在同一目录，权限设为 `600`。
4. 添加两个 Public Hostname：
   - `dashboard.sz-yingjin.top` → `http://127.0.0.1:3100`
   - `api.sz-yingjin.top` → `http://127.0.0.1:8100`
5. 在 Cloudflare Access 为两个主机名配置相同的 Allow 策略，只允许指定员工邮箱登录。
6. 将 `.env.cloudflare.example` 中的两个配置合并入实际 `.env`；再以
   `NEXT_PUBLIC_API_BASE_URL=https://api.sz-yingjin.top` 重建 `web` 服务。
7. 将 plist 示例安装到 `~/Library/LaunchAgents/`，再以 `launchctl bootstrap` 启动，确认隧道显示 Healthy。

## 安全边界

- Cloudflare Access 必须同时保护 `dashboard` 与 `api` 两个主机名；仅保护界面会留下 API 绕过路径。
- macmini 不需要也不应新增路由器端口映射。
- 当前应用的身份模型仍是内部 MVP 的开发身份；在员工大规模使用前，应接入企业微信 OAuth 并建立人员角色映射。
