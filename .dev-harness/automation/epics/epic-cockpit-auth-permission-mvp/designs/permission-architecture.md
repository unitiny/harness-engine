# 智能体权限控制方案

## 目标

集团数据中台驾驶舱需要同时满足：

1. 领导可以通过驾驶舱查看多个系统的核心数据。
2. 智能体可以跨系统查询、联动和汇总信息。
3. 不同业务系统已有不同权限架构。
4. 同一个人在驾驶舱、系统 1、系统 2、系统 3 中可能有不同账号或不同权限。
5. AI 调接口时不能越过源系统权限。

本方案目标是建立一套可落地的跨系统权限控制架构。

## 核心原则

### AI 不拥有天然全局权限

智能体不能因为能调用工具，就默认拥有所有系统数据访问权。

每次工具调用都必须带上：

```text
当前用户是谁
当前用户绑定了哪些源系统账号
本次请求要访问哪些系统
本次请求要读取哪些对象和字段
本次请求是否涉及跨系统联动
本次请求需要明细还是汇总
```

### 不合并权限包，按系统分别裁决

驾驶舱账号 A 不应简单合并系统 1-A、系统 2-A、系统 3-A 的全部权限。

正确模型是：

```text
驾驶舱账号 A
  -> 系统 1 身份 A1
  -> 系统 2 身份 A2
  -> 系统 3 身份 A3
```

当用户发起一次跨系统查询时，分别判断：

```text
A1 在系统 1 中能看什么？
A2 在系统 2 中能看什么？
A3 在系统 3 中能看什么？
这些结果能否在驾驶舱中被联动展示？
是否需要脱敏、聚合或拒绝？
```

### 源系统权限兜底

中台和 AI 权限网关可以做统一裁决，但不能绕开源系统权限。

如果源系统支持用户级 token、OAuth、SSO 或 delegated access，优先用用户身份访问。

如果源系统只能用系统级接口 token，则必须在中台侧补齐：

- 用户到源系统账号的映射。
- 组织范围过滤。
- 资源范围过滤。
- 字段级过滤。
- 明细级别控制。
- 审计日志。

### 结果可降级

权限不足时，不一定只能报错。

智能体可以做权限降级回答：

```text
无权看明细 -> 返回汇总
无权看敏感字段 -> 脱敏
无权看某个系统 -> 只回答已授权系统的部分
无权跨系统 join -> 分系统返回可见摘要
```

## 推荐总体架构

```text
用户 / 领导
  ↓
驾驶舱前端 / openclaky
  ↓
统一身份中心 SSO / IAM
  ↓
AI 权限网关
  ↓
工具注册中心
  ↓
Dify workflow
  ↓
中台受控工具 API
  ↓
中台 API 网关
  ↓
业务系统 API
```

## 关键组件

### 统一身份中心

统一身份中心负责确认当前驾驶舱用户。

建议字段：

```text
cockpit_user_id
employee_id
name
department_id
company_id
position
roles
status
```

### 多系统账号映射

用于绑定驾驶舱用户和各业务系统账号。

示例：

```text
cockpit_user_id: U10001
employee_id: E10001
system_bindings:
  finance:
    system_user_id: FIN_A
    auth_mode: delegated
  project:
    system_user_id: PRJ_A
    auth_mode: acl_snapshot
  hr:
    system_user_id: HR_A
    auth_mode: gateway_policy
```

绑定关系可以来自：

- 统一身份目录。
- 各系统账号同步。
- 人工绑定。
- 首次访问时 OAuth 授权。

### 系统权限适配器

每个业务系统一个权限适配器，把源系统不同权限模型翻译为统一结构。

统一输出建议：

```json
{
  "system": "finance",
  "system_user_id": "FIN_A",
  "resource": "revenue",
  "actions": ["read"],
  "org_scope": ["group", "company_001"],
  "data_scope": ["summary", "department_detail"],
  "field_scope": ["amount", "period", "company_name"],
  "denied_fields": ["contract_no", "customer_sensitive_name"],
  "constraints": {
    "max_detail_level": "department",
    "allow_export": false,
    "allow_cross_system_join": true
  }
}
```

适配器模式：

```text
实时查询源系统权限
同步 ACL 快照
使用中台自建权限策略
混合模式
```

### AI 工具注册中心

每个 openclaky skill 和 Dify workflow 都必须注册。

注册内容：

```text
工具 ID
工具名称
对应 Dify workflow
会访问哪些系统
会访问哪些资源
可能读取哪些字段
是否涉及敏感数据
是否允许跨系统联动
是否允许明细查询
是否允许导出
需要的权限码
默认结果粒度
```

示例：

```json
{
  "tool_id": "customer_360_query",
  "name": "客户综合查询",
  "workflow": "dify_customer_360",
  "systems": ["crm", "contract", "finance", "project"],
  "resources": ["customer", "contract", "payment", "delivery"],
  "required_permissions": [
    "crm.customer.read",
    "contract.summary.read",
    "finance.payment.summary.read",
    "project.delivery.read"
  ],
  "sensitive_fields": ["contract_amount", "payment_detail", "contact_phone"],
  "allow_cross_system_join": true,
  "allow_export": false,
  "default_detail_level": "summary"
}
```

### AI 权限网关

AI 权限网关是核心控制点。

职责：

1. 校验用户是否能使用某个 skill / workflow。
2. 校验本次请求是否能访问目标系统。
3. 校验字段、组织、资源、明细级别。
4. 给 Dify 下发受控参数。
5. 对返回结果做脱敏、过滤、聚合。
6. 记录完整审计日志。

推荐请求流程：

```text
用户自然语言问题
  -> openclaky 判断候选 skill
  -> AI 权限网关校验 skill 是否可用
  -> 网关解析本次请求涉及系统和字段
  -> 查询账号映射和系统权限
  -> 生成授权后的工具调用参数
  -> 调用 Dify workflow
  -> Dify 调用中台受控工具 API
  -> 中台 API 网关二次鉴权和过滤
  -> 结果返回 AI 权限网关
  -> 脱敏/降级/审计
  -> openclaky 生成最终回答
```

### 中台受控工具 API

不要让 Dify 直接调用大量原始业务 API。

中台应暴露受控工具 API：

```text
query_revenue_summary
query_project_progress
query_customer_contract_summary
query_payment_status
query_hr_staffing_summary
```

每个工具 API 都有固定入参、固定出参和明确权限要求。

### 审计日志

每次 AI 查询必须记录：

```text
用户 ID
用户问题
识别意图
调用 skill
调用 workflow
访问系统
访问资源
请求字段
返回字段
权限裁决结果
是否脱敏
是否降级
是否拒绝
最终回答
时间
会话 ID
trace ID
```

## 权限裁决示例

用户提问：

```text
帮我查一下华东区某客户的合同、回款、项目交付情况。
```

系统拆解：

```text
CRM: 客户基本信息
合同系统: 合同摘要
财务系统: 回款情况
项目系统: 交付进度
```

权限裁决：

```text
CRM: 允许查看该客户摘要
合同系统: 允许查看合同数量和合同总额，不允许查看合同附件
财务系统: 允许查看回款汇总，不允许查看回款流水
项目系统: 无权限查看项目交付明细
```

智能体回答：

```text
我可以查看该客户的基本信息、合同摘要和回款汇总。
你当前权限不能查看项目交付明细，因此以下结果不包含项目交付明细。
```

## 不推荐做法

### 不推荐：Dify 持有超级账号

风险：

- 用户可通过自然语言绕过系统页面权限。
- workflow 一旦配置错误会泄漏大量数据。
- 难以追踪“谁真正访问了数据”。

### 不推荐：只控制菜单权限

菜单权限只能控制用户看到哪些入口，不能控制 AI 是否能通过工具查到数据。

AI 权限必须控制到：

```text
系统
资源
组织范围
字段
明细级别
跨系统关联
导出
```

### 不推荐：把所有权限合并成一个大角色

例如：

```text
驾驶舱领导 = 可访问所有系统所有数据
```

这会破坏原业务系统权限边界。

## 权限引擎选型

### 为什么需要独立授权引擎

当权限规则从 1 个系统扩展到多个系统时，规则复杂度急剧上升：

```text
单系统: 用户 A 能看华东区回款汇总 → 几条 if/else
双系统: 用户 A 在财务能看回款汇总，在项目系统不能看交付明细 → 十几条规则
多系统: ×组织范围 ×字段级别 ×明细级别 ×导出控制 ×跨系统关联 → 成百上千条规则
```

硬编码在 Rails Service Object 里的权限检查会变成难以维护的面条代码。授权引擎把权限规则从业务代码中抽离，用策略语言声明式管理。

### 候选方案对比

| | Cerbos | OPA (Open Policy Agent) | OpenFGA |
|---|---|---|---|
| GitHub Stars | 3K+ | 10K+ | 3K+ |
| 技术栈 | Go，HTTP API | Go，REST/gRPC | Go，gRPC/REST |
| 策略语言 | YAML + CEL 表达式 | Rego 语言 | 关系元组建模 |
| 适合场景 | 应用级细粒度权限 | 通用策略，云原生 | 组织层级关系型权限 |
| AI Agent 支持 | 原生支持 | 无特定支持 | 无特定支持 |
| 学习曲线 | 低，YAML 可读性好 | 中，需学习 Rego | 中，需理解 Zanzibar 模型 |
| 与 Rails 集成 | HTTP POST | HTTP API / sidecar | HTTP API |

### 推荐 Cerbos

理由：

1. 策略可读性最好——权限规则用 YAML 写，业务人员能看懂
2. 原生支持 AI Agent 场景
3. 条件表达式灵活——能表达"如果是财务系统 + 华东区 + 只看汇总 → 允许"
4. 与 Rails 集成最简单——一个 HTTP POST 做权限判断

Cerbos 策略示例（对应本文档权限裁决场景）：

```yaml
apiVersion: "api.cerbos.dev/v1"
resourcePolicy:
  resource: "finance_data"
  version: "1.0"
  rules:
    - actions: ["read_summary"]
      effect: EFFECT_ALLOW
      roles: ["finance_viewer"]
      condition:
        match:
          expr: >
            request.resource.attr.org_scope == "east_china" &&
            !hasIntersection(request.resource.attr.requested_fields, ["contract_no", "customer_sensitive_name"])
      output:
        when:
          ruleActivated:
            max_detail_level: "department"
            allow_export: false
            denied_fields: ["contract_no", "customer_sensitive_name"]

    - actions: ["read_detail"]
      effect: EFFECT_DENY
      roles: ["finance_viewer"]
```

Rails 调用 Cerbos 示例：

```ruby
# app/services/permission_gateway.rb
class PermissionGateway
  CERBOS_URL = Rails.configuration.cerbos_url

  def check(user:, system:, resource:, fields:, org_scope:, detail_level:)
    response = Faraday.post("#{CERBOS_URL}/api/check") do |req|
      req.headers['Content-Type'] = 'application/json'
      req.body = {
        requestId: SecureRandom.uuid,
        principal: {
          id: user.cockpit_user_id,
          roles: user.roles_for(system),
          attr: { org_scope: org_scope }
        },
        resource: {
          kind: system,
          attr: {
            requested_fields: fields,
            detail_level: detail_level
          }
        },
        actions: ["read_summary", "read_detail"]
      }.to_json
    end

    result = JSON.parse(response.body)
    {
      allowed: result.dig("actionEffects", "read_summary") == "EFFECT_ALLOW",
      denied_fields: result.dig("outputs", "denied_fields") || [],
      max_detail_level: result.dig("outputs", "max_detail_level"),
      allow_export: result.dig("outputs", "allow_export")
    }
  end
end
```

### 引入节奏

```text
M1-M2（单系统闭环）: Rails Service Object 硬编码，先跑通闭环
M3（双系统联动）:    规则增多时评估引入 Cerbos
M4+（多系统）:      正式引入 Cerbos，迁移成本很低（本质就是加一个 HTTP API 调用）
```

## 推荐最终原则

```text
统一身份
分系统授权
账号绑定
工具注册
网关裁决
源系统兜底
结果脱敏
完整审计
```
