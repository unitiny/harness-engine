# MVP 落地路线

## MVP 目标

先做一个可验证闭环，而不是一次性接入所有系统。

MVP 建议覆盖：

```text
2-3 个业务系统
3-5 个核心驾驶舱指标
2-3 个智能体查询 workflow
1 套统一用户映射
1 套 AI 权限网关原型
1 套审计日志
```

## 阶段 1：权限与系统盘点

### 任务

1. 梳理首批接入系统。
2. 确认每个系统的身份模型。
3. 确认每个系统的权限模型。
4. 确认是否支持用户级 token、OAuth、SSO 或只能系统级 token。
5. 确认字段敏感级别。

### 输出

```text
系统清单
账号映射表设计
权限适配方式表
敏感字段清单
首批智能体工具清单
```

### 重点问题

每个系统都要回答：

```text
这个系统怎么识别用户？
这个系统怎么判断用户能看哪些组织数据？
这个系统怎么控制字段？
这个系统是否有接口级权限？
这个系统是否能返回当前用户权限范围？
这个系统是否能用用户身份调用 API？
```

## 阶段 2：建立统一用户映射

### 任务

建设驾驶舱用户到业务系统用户的绑定关系。

建议表结构：

```text
cockpit_user_id
employee_id
system_code
system_user_id
binding_status
auth_mode
last_sync_at
```

### 绑定模式

```text
统一工号自动绑定
手机号/邮箱匹配绑定
管理员手动绑定
OAuth 首次授权绑定
```

## 阶段 3：工具注册中心

### 任务

把 openclaky skill 和 Dify workflow 注册为受控工具。

首批建议：

```text
经营收入查询
项目进度查询
客户综合查询
回款情况查询
人员投入汇总查询
```

### 每个工具必须登记

```text
访问系统
访问资源
读取字段
敏感字段
所需权限
是否允许明细
是否允许导出
是否允许跨系统联动
```

## 阶段 4：AI 权限网关原型

### MVP 能力

1. 校验用户是否能调用某个工具。
2. 根据用户映射找到各系统账号。
3. 查询或加载各系统权限。
4. 判断请求字段和组织范围。
5. 生成授权后的 Dify 调用参数。
6. 对结果做脱敏和降级。
7. 记录审计日志。

### 推荐接口

```text
POST /ai-gateway/authorize-tool
POST /ai-gateway/invoke-tool
POST /ai-gateway/filter-result
GET  /ai-gateway/audit-log
```

### 调用路径

```text
openclaky
  -> /ai-gateway/authorize-tool
  -> /ai-gateway/invoke-tool
  -> Dify workflow
  -> 中台受控工具 API
  -> /ai-gateway/filter-result
  -> openclaky
```

## 阶段 5：中台受控工具 API

### 原则

不要让 Dify 直接面对大量原始 API。

建议中台先封装稳定的业务工具 API：

```text
query_revenue_summary
query_project_progress
query_customer_contract_summary
query_payment_summary
query_staffing_summary
```

每个工具 API 都要：

```text
固定入参
固定出参
声明权限要求
支持 trace ID
支持用户身份透传
支持字段过滤
支持组织范围过滤
```

## 阶段 6：智能体回答策略

### 权限不足时的回答策略

```text
完全无权限 -> 明确拒绝
部分无权限 -> 返回可见部分
明细无权限 -> 返回汇总
敏感字段无权限 -> 脱敏
跨系统联动无权限 -> 分系统返回摘要
```

### 示例

```text
你当前权限可以查看该客户的合同摘要和回款汇总，
但不能查看回款流水和项目交付明细。
以下是授权范围内的结果。
```

## 阶段 7：审计与安全验证

### 必须记录

```text
谁问的
什么时候问的
问了什么
调用了什么工具
访问了哪些系统
请求了哪些字段
返回了哪些字段
哪些字段被脱敏
哪些系统被拒绝
最终回答是什么
```

### 安全测试用例

```text
无权限用户请求敏感数据
有汇总权限用户请求明细
A 部门用户请求 B 部门数据
通过换说法绕过字段限制
通过跨系统联动间接推断敏感信息
通过导出或批量查询绕过界面限制
```

## 建议首批里程碑

### M1：文档和设计确认

完成：

```text
系统权限盘点
统一身份映射方案
工具注册中心设计
AI 权限网关接口设计
审计日志设计
```

### M2：单系统权限闭环

完成：

```text
openclaky -> AI 权限网关 -> Dify -> 中台 API -> 单业务系统
```

验证：

```text
同一个问题，不同权限用户返回不同结果。
```

### M3：双系统联动闭环

完成：

```text
客户信息 + 合同信息
项目进度 + 回款汇总
```

验证：

```text
一个系统有权限、另一个系统无权限时，智能体能做部分回答和权限说明。
```

### M4：驾驶舱可视化与智能体联动

完成：

```text
领导查看指标
点击指标发起智能体追问
智能体基于当前用户权限联动查询
```

## 技术选型与架构

### 驾驶舱后端技术选型

```text
后端框架: Ruby on Rails API
前端/入口: openclaky
工作流引擎: Dify
权限裁决: MVP 阶段 Rails Service Object → 后期引入 Cerbos
SSO/统一身份: 复用公司现有 SSO，无则用 Keycloak 或 MaxKey
审计: Rails concern + 数据库
权限缓存: Redis 或数据库
脱敏: Rails service 层
```

### 后端架构（三层）

```text
┌─────────────────────────────────────────────┐
│  驾驶舱 Rails API（自研）                     │
│                                             │
│  ┌─ 权限网关 Service ─────────────────────┐ │
│  │  账号映射（DB 表）                       │ │
│  │  权限裁决 → MVP: Rails Service Object   │ │
│  │            → 后期: Cerbos API            │ │
│  │  脱敏过滤（Ruby service）               │ │
│  │  审计日志（DB 表 + concern）             │ │
│  └─────────────────────────────────────────┘ │
│                                             │
│  ┌─ 受控工具 API ─────────────────────────┐ │
│  │  query_revenue_summary                 │ │
│  │  query_project_progress                │ │
│  │  query_customer_summary                │ │
│  └─────────────────────────────────────────┘ │
├─────────────────────────────────────────────┤
│  Cerbos（权限策略引擎，MVP 后期独立部署）      │
├─────────────────────────────────────────────┤
│  Keycloak / MaxKey / 现有 SSO                │
├─────────────────────────────────────────────┤
│  Dify → 业务系统 API                         │
└─────────────────────────────────────────────┘
```

### 调用流程

```text
openclaky
  → POST /ai-gateway/invoke-tool       (Rails controller)
    → PermissionGateway.check          (账号映射 + 权限裁决)
    → 如果允许 → 调 Dify workflow      (受控参数)
    → Dify 返回结果
    → ResultFilter.mask                (按权限裁决结果脱敏)
    → AuditLog.record                  (写入审计表)
  → 返回给 openclaky
```

### 权限引擎引入策略

```text
M1-M2（单系统闭环）: 纯 Rails Service Object 硬编码权限检查
M3（双系统联动）:    评估是否引入 Cerbos，迁移成本低
M4+（多系统）:      如规则已复杂，正式引入 Cerbos 做策略管理
```

### 自建 vs 开源分工

| 自建（Rails） | 引入开源 |
|---|---|
| 账号映射管理 | Cerbos — 权限策略引擎（MVP 后期） |
| 受控工具 API 封装 | Keycloak / MaxKey — SSO（已有则复用） |
| 脱敏过滤逻辑 | |
| 审计日志 | |
| 结果降级策略 | |
| Dify / openclaky API 对接 | |

## 一句话路线

先做”统一身份 + 账号映射 + 网关裁决 + 单系统闭环”，再扩展到多系统联动。权限裁决 MVP 阶段用 Rails 硬编码，等规则变复杂再抽到 Cerbos。
