---
name: skill-data-guard
description: |
  ALWAYS invoke this skill when the user asks to build, harden, or wrap a Skill that
  calls internal / private APIs or knowledge bases, and requires data encryption,
  output sanitization, and leak prevention. 为调用内部接口/私有知识库的 Skill 注入
  「数据边界」能力：接口数据加密传输、凭证与实例ID 进程内自取、stdout 只输出脱敏结论、
  原始数据不进 session 上下文、思考过程不透传私有数据。
  Trigger keywords: '数据守卫', '数据隔离', '数据加密', '脱敏', '防泄露', '禁止输出',
  '内部知识库', '私有数据', '敏感数据', '内部接口', '内部API', '涉密', 'data guard',
  'data isolation', 'data encryption', 'sanitize', 'leak prevention', 'private data',
  'sensitive data', 'internal API', 'internal knowledge base'.
  Do not call or leak internal data directly — use this skill first to wrap the data boundary.
  Do NOT use for skills that only produce static content with no API/DB access.
metadata:
  openclaw:
    emoji: "🛡️"
    skillKey: "skill-factory"
---

# Skill Data Guard — 数据守卫能力包

为「需要调用内部接口 / 私有知识库」的 Skill 注入**数据边界封闭**能力，确保私有数据
**不进入 session 会话、不出现在思考（thinking）过程、不以明文落盘**。

本 skill 既可作为**独立加固工具**（给已有 skill 加数据守卫），也是 `skill-generator`
在关键词命中时的**注入素材来源**（模板 + 规范 + 关键词映射）。

## Quick Reference

| Task / 任务 | Guide / 指引 |
|------|------|
| 数据边界脚本骨架（注入用） | Copy [assets/secure-query.py.tmpl](assets/secure-query.py.tmpl) |
| 数据隔离设计模式（数据流/脱敏/白名单/哈希/加密落盘） | Read [references/data-isolation-patterns.md](references/data-isolation-patterns.md) |
| 关键词 → 安全模式映射表 | Read [references/keyword-trigger-map.md](references/keyword-trigger-map.md) |

---

## Overview

调用内部接口的 Skill，最危险的泄露点不是"调用了什么"，而是**接口返回的私有数据被带回上下文**。
数据一旦进入 session，模型就会在思考中复述、在回答中引用，且会随会话历史被持久化。

本能力包遵循一条核心原则：

> **把"取数"和"用数"全部封闭在脚本进程内部，脚本 stdout 只吐出脱敏后的最小结论。**
> 凭证 / 实例ID 在进程内自取（链式签发 / 元数据服务 / 本地身份），原始数据只在脚本内存中存活，从不打印、从不落盘。

三个需求与落点的对应：

| 需求 | 落点 | 手段 |
|------|------|------|
| 接口数据加密 | 传输层 + 存储层 | 强制 HTTPS + 凭证进程内自取 + 数据不落盘（进阶：AES 加密落盘） |
| 禁止输出到 session | 脚本 stdout | 字段白名单 + 敏感字段打码 + 只输出结论不输出原始响应 |
| 思考过程中不透传 | 数据不进上下文 | 数据只在脚本进程内，LLM 只消费结论，无从复述原始数据 |

---

## When to Use

✅ **适用**：
- 新建一个调用内部接口 / 私有知识库 / 私有 API 的 Skill
- 给已有 Skill 加固数据边界（补脚本封装、脱敏、进程内自取凭证）
- 需要保证私有数据不进 session、不进 thinking 的涉敏场景

❌ **不适用**：
- 纯静态内容生成、无任何 API/DB 访问的 Skill
- 数据本身无需保密、用户明确要求明文输出的场景

---

## Workflow

### Step 1 — 判定安全模式

用 [references/keyword-trigger-map.md](references/keyword-trigger-map.md) 扫描需求，
判定 `securityMode`：

- `data-guard`（L1 强触发）：注入完整数据守卫骨架 + 数据边界铁律
- `basic-guard`（L2 部分触发）：只注入 stdout 白名单 + 进程内自取凭证约束，不强制加密落盘
- `none`（L0）：不注入

### Step 2 — 注入数据边界脚本

复制 [assets/secure-query.py.tmpl](assets/secure-query.py.tmpl) 到目标 skill 的
`scripts/secure_query.py`，并完成：

1. 把 `__ENV_PREFIX__` 替换为 skill 名的 `UPPER_SNAKE_CASE`（如 `INTERNAL_KB_QUERY`）
2. 按实际环境调整 `AUTH_API`（内部鉴权接口地址）与 `API`（敏感数据接口地址）的内网默认值
3. 按实际接口调整 `ALLOWED_FIELDS`（字段白名单）与 `SENSITIVE_KEYS`（敏感字段）

> 脚本采用**链式内部调用**（免外部环境变量）：① 自取实例ID → ② 用 ID 换临时 token →
> ③ 用 token 取数据。ID/凭证/原始数据全程只在进程内存，stdout 只输出脱敏结论。

### Step 3 — 写入「数据边界铁律」章节

在目标 skill 的 `SKILL.md` 正文中插入：

```markdown
## Data Boundary / 数据边界铁律

1. **凭证与实例ID 进程内自取**：从元数据服务/链式签发/本地身份获取，禁止硬编码到 SKILL.md 或命令行参数。
2. **数据不进上下文**：脚本 stdout 只输出脱敏结论，禁止 print 原始响应。
3. **思考不透传**：模型只消费脚本返回的结论，不得复述、引用任何原始字段。
4. **字段白名单**：默认只放行非敏感字段，敏感字段走 mask 打码。
5. **可识别标识哈希化**：doc_id / uin 用哈希替代，保留可比对性但不可还原。
6. **不落盘**：原始数据只用内存变量；必须落盘则加密且用后删除。
```

### Step 4 — 在 description 追加安全声明

description 是第 1 层（始终在系统提示中），**只能声明"本 skill 涉及数据隔离"，
绝不能写真实数据**（接口地址、实例 ID、字段名一律不写）：

```yaml
DATA-GUARD: sanitizes all outputs, never emits raw data into context.
```

---

## Examples

### Example 1：加固一个查询内部知识库的 Skill

**用户说：**「帮我给这个知识库查询 skill 加数据守卫，接口数据要加密、不能泄露到会话」

**执行：**
1. 判定 `securityMode = data-guard`
2. 复制 `secure-query.py.tmpl` → `scripts/secure_query.py`，替换 `__ENV_PREFIX__`
3. 在 SKILL.md 写入「Data Boundary 铁律」
4. description 追加 `DATA-GUARD` 声明

**结果：** 凭证进程内自取（链式签发）、stdout 只吐脱敏结论、原始数据不进上下文。

---

## Guidelines / Constraints

- **数据边界是硬约束，不是建议**：违反任意一条铁律即视为加固失败。
- **凭证永不进文件**：接口地址（内网默认内置）、Token（链式签发）、实例 ID（元数据服务自取）都在进程内获取，禁止硬编码。
- **结论 ≠ 数据**：返回"命中 3 条、结论是 X"，而非返回 3 条原始记录。
- **白名单优先**：默认只放行非敏感字段，新增字段需先改白名单再决定放行。

---

## Common Issues / Troubleshooting

### Error: 脚本报 "无法在进程内自取实例ID / 凭证"

**Cause:** 实例元数据服务不可达、或内部鉴权接口返回异常、或本地身份文件缺失。
**Solution:** 确认运行在支持元数据服务的实例上，或临时用 `<PREFIX>_INSTANCE_ID` / `<PREFIX>_TOKEN` 作调试覆盖；不要写进 SKILL.md 或命令行参数。

### Error: 担心原始数据被日志/trace 采集

**Cause:** 接口响应体被框架 trace 记录。
**Solution:** 确认接口调用响应体是否被采集；必要时在 references/data-isolation-patterns.md
中补充"关闭响应体采集"的约定。

---

## Dependencies

- Python3（标准库即可，无需第三方依赖）
- 零外部环境变量：实例ID 自取、凭证链式签发；`<PREFIX>_API` / `<PREFIX>_TOKEN` / `<PREFIX>_INSTANCE_ID` 仅作可选调试覆盖
