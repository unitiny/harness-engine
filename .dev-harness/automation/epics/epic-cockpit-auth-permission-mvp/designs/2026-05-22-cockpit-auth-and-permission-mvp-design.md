# 驾驶舱认证与权限 MVP 设计

## 目标

实现"身份 + 单系统查询"闭环：用户登录后，能用自然语言查询一个业务系统的数据，且只能看到自己有权限的数据。架构可扩展到全链路权限闭环。

## 整体架构

```
用户（领导/员工）
  ↓ 浏览器 / 飞书 / 企微 / 微信（IM 集成）
  ↓
┌─────────────────────────────────────────────────┐
│ OpenClacky（智能体引擎层）                         │
│  - Skill 调度：注册驾驶舱查询 skills                │
│  - Skill 自进化：根据执行结果优化查询 skill          │
│  - Cron 调度：定时推送报表、刷新指标                │
│  - IM 集成：飞书/企微/微信消息驱动查询              │
│  - 自然语言理解：解析领导问题为结构化工具调用         │
│  - BYOK：灵活选择 LLM 模型                        │
│  - 子 Agent 路由：复杂查询拆解为多步骤              │
└─────────────────────────────────────────────────┘
  ↓ 权限校验请求（每次工具调用前）
驾驶舱后端服务（Rails API）
  ├── POST /auth/login           → 用户认证
  ├── POST /auth/verify          → token 校验（供 openclacky 每次调用用）
  ├── GET  /users/:id/mappings   → 获取账号映射
  ├── POST /gateway/authorize    → 权限裁决
  ├── POST /gateway/invoke       → 代理调用业务系统 API
  ├── POST /gateway/filter       → 结果脱敏/降级
  ├── GET  /audit-log            → 审计日志查询
  └── CRUD /admin/*              → 管理后台（用户管理、映射管理）
       ↓
  出租管理系统 API（通过账号映射以用户身份访问）
```

### 调用链路示例

```
领导在飞书问："本月出租率怎么样？"
  → OpenClacky IM 集成接收消息
  → Skill 识别为"出租率查询"
  → 调用驾驶舱后端 POST /gateway/authorize（带用户身份+工具ID）
  → 后端查映射表，获取该用户在出租系统的账号
  → 后端校验该账号是否有权查看出租率
  → 授权通过 → POST /gateway/invoke（代理调用出租系统 API）
  → 结果返回 → POST /gateway/filter（脱敏/降级）
  → OpenClacky 生成自然语言回答
  → 回复到飞书
  → 审计日志记录全过程
```

### MVP 范围

| 组件 | MVP 做什么 | 未来扩展 |
|------|-----------|---------|
| 用户认证 | 账号+密码登录，管理员建表 | SSO、OAuth、多因素认证 |
| 账号映射 | 手动映射驾驶舱用户到出租系统账号 | 自动绑定、批量同步 |
| 权限网关 | 硬编码权限规则 + 接口级校验 | 动态权限策略、字段级脱敏 |
| 查询代理 | 先用模拟数据跑通链路 | 对接真实出租系统 API |
| 审计日志 | 记录每次查询的关键信息 | 完整审计链路、异常检测 |
| 前端 | 登录页 + 简单查询界面 | 驾驶舱可视化大屏 |

## 数据模型

### cockpit_users

```sql
CREATE TABLE cockpit_users (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  username      VARCHAR(50)  NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  employee_id   VARCHAR(50),
  name          VARCHAR(100) NOT NULL,
  department_id VARCHAR(50),
  company_id    VARCHAR(50),
  position      VARCHAR(100),
  roles         VARCHAR(255) DEFAULT 'viewer',
  status        VARCHAR(20)  DEFAULT 'active',
  created_at    DATETIME    DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### system_account_mappings

```sql
CREATE TABLE system_account_mappings (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  cockpit_user_id BIGINT NOT NULL,
  system_code     VARCHAR(50) NOT NULL,
  system_user_id  VARCHAR(100) NOT NULL,
  auth_mode       VARCHAR(50) DEFAULT 'gateway_policy',
  binding_status  VARCHAR(20) DEFAULT 'active',
  last_sync_at    DATETIME,
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_user_system (cockpit_user_id, system_code)
);
```

auth_mode 说明：

| 模式 | 含义 | MVP 使用 |
|------|------|---------|
| `gateway_policy` | 中台侧自建权限策略控制 | 默认模式 |
| `delegated` | 用用户身份直接调源系统 | 未来 SSO 对接时 |
| `acl_snapshot` | 同步源系统权限快照 | 未来扩展 |

### registered_tools

```sql
CREATE TABLE registered_tools (
  id                     BIGINT PRIMARY KEY AUTO_INCREMENT,
  tool_id                VARCHAR(100) NOT NULL UNIQUE,
  name                   VARCHAR(200) NOT NULL,
  description            TEXT,
  system_code            VARCHAR(50) NOT NULL,
  endpoint               VARCHAR(500),
  required_permissions   JSON,
  sensitive_fields       JSON,
  allow_detail           BOOLEAN DEFAULT false,
  allow_export           BOOLEAN DEFAULT false,
  default_detail_level   VARCHAR(50) DEFAULT 'summary',
  status                 VARCHAR(20) DEFAULT 'active',
  created_at             DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### permission_policies

```sql
CREATE TABLE permission_policies (
  id              BIGINT PRIMARY KEY AUTO_INCREMENT,
  cockpit_user_id BIGINT,
  role            VARCHAR(50),
  system_code     VARCHAR(50) NOT NULL,
  resource        VARCHAR(100) NOT NULL,
  actions         JSON NOT NULL,
  org_scope       JSON,
  field_scope     JSON,
  denied_fields   JSON,
  max_detail_level VARCHAR(50) DEFAULT 'summary',
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

策略优先级：用户级策略 > 角色级策略。cockpit_user_id 不为 NULL 时为用户级策略。

### audit_logs

```sql
CREATE TABLE audit_logs (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  trace_id         VARCHAR(100) NOT NULL,
  user_id          BIGINT NOT NULL,
  username         VARCHAR(50),
  session_id       VARCHAR(100),
  question         TEXT,
  intent           VARCHAR(200),
  tool_id          VARCHAR(100),
  system_code      VARCHAR(50),
  resource         VARCHAR(100),
  requested_fields JSON,
  returned_fields  JSON,
  auth_decision    VARCHAR(20),
  masked_fields    JSON,
  degraded         BOOLEAN DEFAULT false,
  error_message    TEXT,
  response_summary TEXT,
  duration_ms      INT,
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_trace (trace_id),
  INDEX idx_user_time (user_id, created_at)
);
```

## 认证设计

- 登录方式：账号 + 密码，无注册流程
- 密码存储：bcrypt 哈希
- Token：JWT，有效期 24h（可配置）
- JWT payload：`{ "sub": user_id, "username": "huangjw", "roles": "viewer", "exp": ... }`
- 管理员直接在数据库或管理后台创建用户

### 认证 API

```
POST /api/v1/auth/login      → 登录，返回 JWT
POST /api/v1/auth/verify      → 校验 token 有效性
POST /api/v1/auth/logout      → 注销（可选）
```

## 权限网关裁决流程

```
1. OpenClacky 识别 skill → 携带 JWT + tool_id 请求后端
2. 后端解析 JWT 获取 user_id
3. 查映射表 → 该用户是否绑定了目标系统账号
4. 查权限策略 → 该用户是否有权使用该工具
5. 裁决结果：
   ✅ 授权 → 代理调用业务系统 API（MVP 先返回模拟数据）
   ⚠️ 部分授权 → 返回可见部分 + 说明
   ❌ 拒绝 → 返回拒绝原因
6. 记录审计日志
```

### 网关 API

```
POST /api/v1/gateway/authorize    → 权限校验
POST /api/v1/gateway/invoke       → 授权后代理调用
POST /api/v1/gateway/filter       → 结果过滤/脱敏
```

### MVP 权限策略示例

```sql
-- 管理员可查看所有出租数据
INSERT INTO permission_policies (role, system_code, resource, actions, org_scope, field_scope, max_detail_level)
VALUES ('admin', 'rental_management', 'rental_data', '["read"]', '["all"]', '["all"]', 'detail');

-- 普通用户只能看汇总
INSERT INTO permission_policies (role, system_code, resource, actions, org_scope, field_scope, max_detail_level)
VALUES ('viewer', 'rental_management', 'rental_data', '["read"]', '["own_department"]', '["summary_fields"]', 'summary');
```

## 管理后台 API

```
GET    /api/v1/admin/users              → 用户列表
POST   /api/v1/admin/users              → 创建用户
PUT    /api/v1/admin/users/:id          → 更新用户
DELETE /api/v1/admin/users/:id          → 禁用用户

GET    /api/v1/admin/mappings           → 所有映射
POST   /api/v1/admin/mappings           → 创建映射
PUT    /api/v1/admin/mappings/:id       → 更新映射
DELETE /api/v1/admin/mappings/:id       → 删除映射

GET    /api/v1/admin/tools              → 工具列表
POST   /api/v1/admin/tools              → 注册工具
PUT    /api/v1/admin/tools/:id          → 更新工具

GET    /api/v1/admin/policies           → 策略列表
POST   /api/v1/admin/policies           → 创建策略
PUT    /api/v1/admin/policies/:id       → 更新策略
DELETE /api/v1/admin/policies/:id       → 删除策略

GET    /api/v1/audit-logs               → 分页查询审计日志
GET    /api/v1/audit-logs/:trace_id     → 按链路ID查完整调用链
```

## OpenClacky Skill 注册

驾驶舱查询 skills 通过 openclacky skill 系统注册：

```yaml
- skill_id: rental_occupancy_query
  name: 出租率查询
  description: 查询指定时间段和区域的出租率数据
  tool_id: query_rental_occupancy
  systems: [rental_management]
  parameters:
    - period: 时间范围
    - region: 区域（可选）
```

## 技术选型

- 后端：Rails API（独立服务）
- 数据库：MySQL 或 PostgreSQL
- 认证：bcrypt + JWT
- 前端/智能体入口：OpenClacky
- 查询代理：MVP 阶段使用模拟数据
