# 关键词 → 安全模式映射表（Keyword Trigger Map）

> 供 `skill-generator`（Phase 1）与 `skill-factory-orchestrator`（Step 01）在需求收集时
> 做关键词扫描，把 `securityMode` 传递给后续生成/评估环节。

---

## 安全模式分级

| 模式 | 含义 | 注入内容 |
|------|------|----------|
| `data-guard` | L1 强触发 | 完整数据守卫骨架（secure_query.py）+ 数据边界铁律 + description 安全声明 |
| `basic-guard` | L2 部分触发 | stdout 白名单 + 进程内自取凭证约束，不强制加密落盘 |
| `none` | L0 不触发 | 不注入 |

---

## 关键词列表

### L1 强触发（`data-guard`）

命中任意一个即进入完整数据守卫模式。

| 中文 | 英文 |
|------|------|
| 内部知识库 | internal knowledge base |
| 私有知识库 | private knowledge base |
| 私有数据 | private data |
| 敏感数据 | sensitive data |
| 数据加密 | data encryption / encrypt |
| 脱敏 | sanitize / desensitize / mask |
| 防泄露 | leak prevention |
| 禁止输出 | suppress output / never emit |
| 数据隔离 | data isolation |
| 涉密 | classified / confidential |
| 内部接口 | internal API |
| 内部 API | internal endpoint |
| 私有 API | private API |
| 实例 ID / 唯一ID | instance id |

### L2 部分触发（`basic-guard`）

命中任意一个，仅加约束、不强加密落盘。

| 中文 | 英文 |
|------|------|
| 调用接口 | call API |
| 调用 API | invoke API |
| 查询数据 | query data |
| 知识库查询 | kb query / knowledge query |

### L0 不触发（`none`）

- 纯静态内容生成（无 API/DB 访问）
- 不涉及任何接口调用的创作型 Skill

---

## 判定规则

1. **L1 优先**：同时命中 L1 与 L2 时，按 `data-guard` 处理。
2. **词义优先于字面**：如"查一下我们内部的文档库"虽无"知识库"三字，但语义等同 L1，
   应判定为 `data-guard`。
3. **判定结果要显式传递**：生成器把 `securityMode` 写进生成流程，评估器据此决定是否启用
   "数据隔离"维度，编排器据此决定是否在治理登记中记录 `securityMode`。
