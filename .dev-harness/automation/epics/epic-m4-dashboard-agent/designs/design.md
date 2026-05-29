# M4 技术设计：Dashboard 可视化 + Agent 联动

## 1. 整体架构

### 1.1 系统拓扑

```
[浏览器]
   │
   │ 1. 访问登录页 → cockpit-api POST /auth/login → JWT (HttpOnly cookie)
   │ 2. Redirect → OpenClacky :7070
   │
   ├─ OpenClacky Web UI (主界面, :7070)
   │    ├── 💬 Agent 对话 (分析师主战场)
   │    │    └── cockpit_gateway Tool → cockpit-api /gateway/*
   │    ├── 📊 Dashboard 面板 (M4-3: 领导报表)
   │    │    └── fetch() → cockpit-api /gateway/invoke
   │    └── ⚙️ 现有面板 (Skills/Tasks/Channels/Settings)
   │
   └── Auth Proxy → 验证 JWT → 透传到 OpenClacky HTTP Server

[cockpit-api Rails :3000]          [OpenClacky + Auth Proxy :7070]
  - POST /auth/login (已有)          - Agent 对话 (已有)
  - POST /gateway/authorize (已有)   - cockpit_gateway Tool (新增)
  - POST /gateway/invoke (已有)      - Auth Proxy middleware (新增)
  - POST /gateway/filter (已有)      - Dashboard panel (M4-3 新增)
  - GET  /audit-logs (已有)
  - CRUD /admin/* (已有)
```

### 1.2 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 主界面 | OpenClacky Web UI | 分析师场景先行，Agent 对话是核心交互 |
| 认证 | cockpit-api JWT + Auth Proxy | 不在 OpenClacky 内建用户体系 |
| Agent 调后端 | 自定义 Ruby Tool | 一等公民，可测试，安全，结构化 |
| Dashboard | ECharts CDN + OpenClacky 面板 | 按现有面板模式扩展，无新框架 |
| OpenClacky 管理 | Submodule + 补丁注入 | 保持原版可升级 |

### 1.3 用户身份流转

```
1. 浏览器 → cockpit-api /auth/login
   → 验证用户名密码
   → 生成 JWT (payload: user_id, role, exp)
   → Set-Cookie: cockpit_jwt=<token>; HttpOnly; Path=/

2. cockpit-api → 302 Redirect → http://localhost:7070/
   → 浏览器自动携带 cookie

3. Auth Proxy 拦截请求
   → 读取 cookie 中的 JWT
   → 验证签名和有效期
   → 提取 user_id, role
   → 注入到 Rack env: env['cockpit.jwt'], env['cockpit.user_id'], env['cockpit.role']
   → 透传到 OpenClacky HTTP Server

4. OpenClacky WebSocket on_open
   → 从 Rack env 读取 JWT 信息
   → 存入 session context: { jwt:, user_id:, role: }

5. cockpit_gateway Tool.execute
   → 从 agent session context 读取 JWT
   → 携带 JWT 调用 cockpit-api /gateway/authorize
   → 携带 JWT 调用 cockpit-api /gateway/invoke
   → 返回结构化结果给 Agent
```

## 2. 组件设计

### 2.1 Auth Proxy

**职责**：拦截所有到 OpenClacky 的 HTTP 请求，验证 JWT，注入用户身份，未登录则重定向到登录页。

**位置**：新增文件 `openclacky/lib/clacky/auth_proxy.rb`

**实现**：Rack middleware，挂载在 OpenClacky WEBrick server 前面。

```ruby
# 伪代码
class Clacky::AuthProxy
  COCKPIT_API_URL = ENV.fetch('COCKPIT_API_URL', 'http://localhost:3000')
  LOGIN_PATH = '/auth/login'

  def initialize(app)
    @app = app
  end

  def call(env)
    req = Rack::Request.new(env)

    # 白名单路径不拦截
    return @app.call(env) if whitelisted?(req.path)

    # 读取 JWT cookie
    token = req.cookies['cockpit_jwt']

    if token && valid_jwt?(token)
      # 注入用户上下文
      payload = decode_jwt(token)
      env['cockpit.jwt'] = token
      env['cockpit.user_id'] = payload['user_id']
      env['cockpit.role'] = payload['role']
      @app.call(env)
    else
      # 重定向到登录页
      [302, { 'Location' => "#{COCKPIT_API_URL}#{LOGIN_PATH}" }, []]
    end
  end

  private

  def whitelisted?(path)
    # 静态资源、WebSocket upgrade 不拦截
    path.start_with?('/assets/', '/favicon') ||
    path.end_with?('.js', '.css', '.png', '.ico')
  end

  def valid_jwt?(token)
    # 调用 cockpit-api /auth/verify 或本地验签
  end

  def decode_jwt(token)
    # 解码 JWT payload（不验证签名，由 valid_jwt? 处理）
  end
end
```

**JWT 验证策略**：调用 cockpit-api `POST /auth/verify` 远程验证。本地不持有 JWT 密钥，保持密钥只在 cockpit-api 内部。

**挂载方式**：在 OpenClacky 的 `cli.rb` 启动 server 时，将 AuthProxy 作为 Rack middleware 插入到 WEBrick handler 之前。补丁方式：重写 `http_server.rb` 的 `start` 方法，在 Rack builder 中插入 middleware。

### 2.2 WebSocket JWT 捕获

**职责**：在 WebSocket 连接建立时，从 HTTP 请求中提取 JWT 信息并存入 session context。

**改动**：修改 `http_server.rb` 的 WebSocket `on_open` 回调，约 5 行。

```ruby
# 在 on_open 回调中
def on_open(ws, req)
  session_id = extract_session_id(req)

  # 新增：从 Rack env 捕获 JWT 信息
  jwt_context = {
    jwt: req.env['cockpit.jwt'],
    user_id: req.env['cockpit.user_id'],
    role: req.env['cockpit.role']
  }

  # 存入 session registry
  session = @session_registry.find_or_create(session_id)
  session.cockpit_context = jwt_context  # 新增属性

  # ... 原有逻辑
end
```

**session context 传递**：在 Agent 创建时将 cockpit_context 传入，Tool 通过 agent 实例访问。

### 2.3 cockpit_gateway Tool

**职责**：OpenClacky 原生 Ruby Tool，替代 Skill/curl 方案，负责调用 cockpit-api 权限网关。

**位置**：新增文件 `openclacky/lib/clacky/tools/cockpit_gateway.rb`

```ruby
class Clacky::Tools::CockpitGateway < Clacky::Tools::Base
  self.tool_name = "cockpit_gateway"
  self.tool_description = "通过权限网关查询业务数据。支持出租率、合同额、客户数等数据查询。"
  self.tool_parameters = {
    type: "object",
    properties: {
      query: {
        type: "string",
        description: "用户的自然语言查询，如'查询华东区本月出租率'"
      },
      tool_id: {
        type: "string",
        description: "目标工具 ID，如 'rental_occupancy_query'"
      }
    },
    required: ["query"]
  }
  self.tool_category = "data"

  COCKPIT_API_URL = ENV.fetch('COCKPIT_API_URL', 'http://localhost:3000')

  def execute(query:, tool_id: "rental_occupancy_query", **kwargs)
    # 1. 从 agent session context 获取 JWT
    jwt = agent.session.cockpit_context[:jwt]
    raise "未登录，请先登录" unless jwt

    # 2. 调用权限网关 authorize
    auth_result = post_json("/api/v1/gateway/authorize", {
      tool_id: tool_id,
      query_context: { natural_language_query: query }
    }, jwt)

    case auth_result['decision']
    when 'denied'
      return format_denied(auth_result)
    when 'authorized', 'partial'
      # 3. 调用 gateway invoke 获取数据
      invoke_result = post_json("/api/v1/gateway/invoke", {
        tool_id: tool_id,
        query_context: { natural_language_query: query },
        authorized_fields: auth_result['allowed_fields'],
        max_detail_level: auth_result['max_detail_level']
      }, jwt)

      format_result(invoke_result, auth_result)
    end
  end

  private

  def post_json(path, body, jwt)
    uri = URI.parse("#{COCKPIT_API_URL}#{path}")
    http = Net::HTTP.new(uri.host, uri.port)
    request = Net::HTTP::Post.new(uri.path, {
      'Content-Type' => 'application/json',
      'Authorization' => "Bearer #{jwt}"
    })
    request.body = JSON.generate(body)
    response = http.request(request)
    JSON.parse(response.body)
  rescue => e
    { 'error' => "权限网关调用失败: #{e.message}" }
  end

  def format_denied(auth_result)
    "权限不足：#{auth_result['reason'] || '您当前角色无权执行此查询'}"
  end

  def format_result(invoke_result, auth_result)
    data = invoke_result['data']
    fields = auth_result['allowed_fields']
    denied = auth_result['denied_fields'] || []

    lines = ["查询结果："]
    lines << "可见字段：#{fields.join(', ')}"
    lines << "已脱敏字段：#{denied.join(', ')}" if denied.any?
    lines << "---"

    if data.is_a?(Array)
      data.each_with_index do |row, i|
        lines << "第#{i+1}条："
        row.each { |k, v| lines << "  #{k}: #{v}" }
      end
    else
      data.each { |k, v| lines << "#{k}: #{v}" }
    end

    if auth_result['decision'] == 'partial'
      lines << "---"
      lines << "⚠ 部分数据因权限限制已脱敏，完整数据需申请更高权限"
    end

    lines.join("\n")
  end
end
```

**Tool 注册**：在 `agent.rb` 的 `register_builtin_tools` 中添加一行：

```ruby
@tool_registry.register(Cacky::Tools::CockpitGateway.new)
```

**与 Skill 方案的对比**：

| 维度 | Skill + curl | cockpit_gateway Tool |
|---|---|---|
| 调用方式 | terminal 执行 curl | 原生 Ruby Net::HTTP |
| 可测试性 | 无法单元测试 | 标准 RSpec |
| 输出截断 | 4000 字符 | 无限制 |
| 错误处理 | 解析 stdout | 结构化异常 |
| 安全性 | JWT 在命令行暴露 | 内存传递 |
| 权限保证 | 依赖 LLM 选择调 Skill | Agent 自动调用 |

### 2.4 登录页

**职责**：极简登录页，托管在 cockpit-api 上。

**位置**：`cockpit-api/app/views/auth/login.html.erb`

```erb
<!-- 极简登录页 -->
<form action="/auth/login" method="post">
  <h1>数据驾驶舱</h1>
  <input type="text" name="username" placeholder="用户名" required>
  <input type="password" name="password" placeholder="密码" required>
  <button type="submit">登录</button>
  <% if flash[:error] %>
    <p class="error"><%= flash[:error] %></p>
  <% end %>
</form>
```

**登录成功后**：设置 HttpOnly JWT cookie + 302 重定向到 `ENV['OPENCLACKY_URL']`（默认 `http://localhost:7070`）。

**路由**：`cockpit-api/config/routes.rb` 新增：

```ruby
get  '/auth/login', to: 'auth#login_page'
post '/auth/login', to: 'auth#login_and_redirect'
```

### 2.5 Dashboard 面板（M4-3 后续阶段）

**职责**：在 OpenClacky Web UI 中新增 Dashboard 面板，展示 KPI 指标卡片和图表。

**位置**：OpenClacky Web UI 扩展，按现有面板模式（Tasks/Skills/Channels）添加。

**所需改动**：

| 文件 | 改动 |
|---|---|
| `web/index.html` | 添加 `#dashboard-panel` div 和侧边栏导航项 |
| `web/dashboard.js` (新增) | Dashboard 模块，ECharts 渲染 + fetch 查询 |
| `web/app.js` | PANELS 数组、Router、SIDEBAR_ITEMS 注册 |
| `web/app.css` | Dashboard 样式 |

**ECharts 引入**：CDN 方式，在 `index.html` 添加：

```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

**数据获取**：

```javascript
// dashboard.js 伪代码
const Dashboard = (() => {
  async function onPanelShow() {
    const jwt = getCookie('cockpit_jwt');
    const resp = await fetch('http://localhost:3000/api/v1/gateway/invoke', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${jwt}`
      },
      body: JSON.stringify({
        tool_id: 'rental_occupancy_query',
        query_context: { type: 'dashboard_summary' }
      })
    });
    const data = await resp.json();
    renderCharts(data);
  }

  function renderCharts(data) {
    // ECharts 渲染指标卡片和趋势图
  }

  return { onPanelShow };
})();
```

**点击追问集成**：

```javascript
function onCardClick(metric) {
  Router.navigate('chat');
  setTimeout(() => {
    const input = document.getElementById('message-input');
    input.value = `详细分析${metric.name}的变化趋势`;
    Sessions.sendMessage();
  }, 100);
}
```

## 3. 数据流

### 3.1 分析师查询流程

```
用户输入: "查询华东区本月出租率"
  │
  ├─ Agent (LLM) 识别意图，选择 cockpit_gateway Tool
  │   └─ tool_call: { query: "查询华东区本月出租率", tool_id: "rental_occupancy_query" }
  │
  ├─ cockpit_gateway.execute()
  │   ├─ 读取 session JWT
  │   ├─ POST /api/v1/gateway/authorize
  │   │   └─ 返回: { decision: "authorized", allowed_fields: [...], ... }
  │   ├─ POST /api/v1/gateway/invoke
  │   │   └─ 返回: { data: [...], filtered: [...] }
  │   └─ 格式化结果返回给 Agent
  │
  ├─ Agent (LLM) 基于结果生成自然语言回答
  │
  └─ 审计日志自动记录 (cockpit-api 审计服务)
```

### 3.2 追问流程

```
用户输入: "华北区呢？"
  │
  ├─ Agent 结合上下文理解：查询华北区出租率
  │
  ├─ cockpit_gateway.execute()
  │   └─ 独立走完整权限校验链路（不继承上次授权）
  │
  └─ 返回结果 + 审计记录
```

### 3.3 权限拒绝流程

```
用户输入: "查询所有客户的合同金额明细"
  │
  ├─ cockpit_gateway.execute()
  │   ├─ POST /api/v1/gateway/authorize
  │   │   └─ 返回: { decision: "denied", reason: "当前角色 viewer 无权查看明细数据" }
  │   └─ 返回: "权限不足：当前角色 viewer 无权查看明细数据"
  │
  └─ Agent 基于拒绝信息生成友好提示 + 权限说明
```

## 4. API 契约

### 4.1 cockpit_gateway Tool 参数

```json
{
  "query": "查询华东区本月出租率",
  "tool_id": "rental_occupancy_query"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| query | string | 是 | 自然语言查询 |
| tool_id | string | 否 | 默认 `rental_occupancy_query`，后续扩展其他工具 |

### 4.2 cockpit_gateway Tool 返回

**授权成功**：

```
查询结果：
可见字段：occupancy_rate, period, region
---
第1条：
  occupancy_rate: 0.87
  period: 2026-05
  region: 华东区
```

**部分授权**：

```
查询结果：
可见字段：occupancy_rate, period, region
已脱敏字段：contract_amount, customer_name
---
第1条：
  occupancy_rate: 0.87
  period: 2026-05
  region: 华东区
  contract_amount: [FILTERED]
  customer_name: [FILTERED]
---
⚠ 部分数据因权限限制已脱敏，完整数据需申请更高权限
```

**拒绝**：

```
权限不足：当前角色 viewer 无权查看明细数据。您可查看汇总级别的出租率数据。
```

## 5. 文件清单

### 新增文件

| 文件 | 项目 | 说明 |
|---|---|---|
| `openclacky/lib/clacky/auth_proxy.rb` | OpenClacky | Auth Proxy middleware |
| `openclacky/lib/clacky/tools/cockpit_gateway.rb` | OpenClacky | 权限网关 Tool |
| `cockpit-api/app/views/auth/login.html.erb` | cockpit-api | 登录页 |
| `openclacky/lib/clacky/web/dashboard.js` | OpenClacky | Dashboard 面板 (M4-3) |

### 修改文件

| 文件 | 项目 | 改动量 | 说明 |
|---|---|---|---|
| `openclacky/lib/clacky/server/http_server.rb` | OpenClacky | ~10 行 | WebSocket JWT 捕获 + AuthProxy 挂载 |
| `openclacky/lib/clacky/agent.rb` | OpenClacky | ~3 行 | 注册 cockpit_gateway Tool |
| `openclacky/lib/clacky/web/index.html` | OpenClacky | ~20 行 | Dashboard 面板 HTML + ECharts CDN (M4-3) |
| `openclacky/lib/clacky/web/app.js` | OpenClacky | ~10 行 | Router + PANELS 注册 (M4-3) |
| `cockpit-api/config/routes.rb` | cockpit-api | ~2 行 | 登录页路由 |
| `cockpit-api/app/controllers/api/v1/auth_controller.rb` | cockpit-api | ~15 行 | login_page + login_and_redirect action |

### 不改动的文件

- OpenClacky 核心 dispatch/react loop/session 管理
- OpenClacky WebSocket 协议（仅新增 context 字段）
- cockpit-api 权限网关、审计日志、Admin CRUD（全部复用）
- cockpit-api 数据库 schema

## 6. 补丁注入策略

OpenClacky 以 git submodule 形式存在。保持原版可升级的注入方式：

```
data-cockpit-agent/
├── openclacky/          (git submodule, 原版)
├── cockpit-api/         (Rails 后端)
└── patches/
    └── openclacky/
        ├── auth_proxy.rb           → 复制到 openclacky/lib/clacky/
        ├── cockpit_gateway.rb      → 复制到 openclacky/lib/clacky/tools/
        ├── dashboard.js            → 复制到 openclacky/lib/clacky/web/
        ├── patches.rb              → 自动应用所有补丁的脚本
        └── patch_manifest.yml      → 补丁清单
```

**启动流程**：

```bash
# 1. 应用补丁（复制文件到 OpenClacky 目录）
ruby patches/openclacky/patches.rb

# 2. 启动 cockpit-api
cd cockpit-api && bin/rails server -p 3000

# 3. 启动 OpenClacky (含 Auth Proxy)
COCKPIT_API_URL=http://localhost:3000 clacky server --port 7070
```

**升级 OpenClacky**：

```bash
cd openclacky && git pull origin main
cd .. && ruby patches/openclacky/patches.rb   # 重新应用补丁
# 如果有冲突，补丁脚本会报告并跳过
```

## 7. 环境变量

| 变量 | 位置 | 说明 | 默认值 |
|---|---|---|---|
| `COCKPIT_API_URL` | OpenClacky 进程 | cockpit-api 地址 | `http://localhost:3000` |
| `OPENCLACKY_URL` | cockpit-api 进程 | OpenClacky 地址 | `http://localhost:7070` |
| `JWT_SECRET_KEY` | cockpit-api 进程 | JWT 签名密钥 | (已有) |

## 8. 测试策略

### 8.1 Auth Proxy 测试

- 单元测试：Rack::MockRequest 模拟请求，验证 JWT 验证、重定向、白名单
- 集成测试：完整登录 → 重定向 → 访问 OpenClacky 流程

### 8.2 cockpit_gateway Tool 测试

- 单元测试：mock cockpit-api HTTP 响应，验证 authorize/invoke 调用逻辑
- 三种场景覆盖：authorized / partial / denied
- 边界测试：JWT 缺失、cockpit-api 不可达、超时

### 8.3 端到端测试

```
1. 创建测试用户 (admin + viewer)
2. admin 登录 → Agent 查询 → 验证返回完整数据
3. viewer 登录 → Agent 查询 → 验证返回脱敏数据
4. 未登录访问 → 验证重定向到登录页
5. 审计日志校验：每次查询有记录
```

### 8.4 Dashboard 面板测试（M4-3）

- 指标卡片按权限展示：admin 看到完整数据，viewer 看到汇总
- 点击追问：验证跳转到对话界面并预填问题
- ECharts 渲染：验证图表正确显示

## 9. 分阶段交付

### M4-1: Auth 打通

**交付**：登录页 → Auth Proxy → OpenClacky 带用户身份

- cockpit-api 登录页（ERB）
- Auth Proxy middleware
- WebSocket JWT 捕获
- 端到端登录流程测试

**验收**：登录后进入 OpenClacky，Agent 能读取到当前用户身份。未登录自动重定向。

### M4-2: 权限感知查询

**交付**：Agent 对话中用自然语言查询数据，走权限网关

- cockpit_gateway Tool 实现
- Tool 注册
- 三种授权场景覆盖
- 审计日志记录
- 端到端查询测试

**验收**：分析师登录后输入查询，Agent 返回权限范围内的数据。不同角色看到不同结果。

### M4-3: Dashboard 报表面板

**交付**：指标卡片 + 点击追问

- Dashboard 面板 HTML/JS/CSS
- ECharts 图表渲染
- 点击卡片 → 跳转对话 → 预填追问
- 按权限展示指标

**验收**：领导登录后看到 Dashboard 指标，点击卡片触发 Agent 追问。

## 10. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|
| OpenClacky 升级后补丁冲突 | 中 | 中 | 补丁脚本检测冲突并报告，手动合并 |
| JWT 在 WebSocket 中传递的安全性 | 低 | 高 | HttpOnly cookie + 服务端读取，不经客户端 JS |
| Agent 误判查询意图导致调错 Tool | 中 | 低 | cockpit_gateway 为默认 Tool，兜底处理 |
| cockpit-api 不可达时 Agent 无响应 | 低 | 中 | cockpit_gateway Tool 内置超时 + 友好错误提示 |
| ECharts CDN 加载失败 | 低 | 低 | Dashboard 降级为纯文本指标展示 |
