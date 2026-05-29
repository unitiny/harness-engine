# M4: Dashboard 可视化 + Agent 联动 Backlog

1. 实现 cockpit-api 登录页（ERB 模板 + JWT cookie + 重定向到 OpenClacky）
2. 实现 Auth Proxy middleware（JWT 验证 + 用户身份注入 + 未登录重定向）
3. 实现 OpenClacky Dashboard 面板（侧边栏导航 + 指标卡片 + ECharts 图表）
4. 实现 WebSocket JWT 捕获（on_open 提取 JWT 存入 session context）
5. 实现 cockpit_gateway Tool（原生 Ruby Tool 调 cockpit-api 权限网关）
6. Dashboard 点击指标触发 Agent 追问（点击卡片跳转对话预填问题）
7. 端到端集成测试（admin 完整数据 / viewer 脱敏数据 / 审计日志校验）
8. 补丁注入脚本（patches/ 目录结构 + 自动应用 + 升级冲突检测）