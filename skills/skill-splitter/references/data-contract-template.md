# 数据契约模板 — 子 Skill 间接口规范

> 拆解后子 Skill 之间的数据传递必须显式定义契约，保证可独立测试与串联。

---

## 一、契约文件规范

每个子 Skill 的输入/输出契约存放在其 `references/contract.json`：

```json
{
  "skill": "signal-extractor",
  "version": "1.0.0",
  "input": {
    "type": "object",
    "required": ["contact_id", "tracks"],
    "properties": {
      "contact_id": {"type": "string", "description": "ERP 客户 ID"},
      "tracks": {
        "type": "array",
        "description": "跟进记录列表",
        "items": {
          "type": "object",
          "required": ["content", "created_at"],
          "properties": {
            "content": {"type": "string"},
            "created_at": {"type": "string", "format": "date-time"}
          }
        }
      }
    }
  },
  "output": {
    "type": "object",
    "required": ["status", "signals"],
    "properties": {
      "status": {"type": "string", "enum": ["success", "partial", "failed"]},
      "signals": {"type": "array", "items": {"type": "object"}}
    }
  }
}
```

## 二、字段命名规范

| 规则 | 说明 |
|------|------|
| snake_case | 所有字段用小写下划线命名 |
| 必须有 description | 每个字段注明业务含义 |
| 时间统一 ISO 8601 | `YYYY-MM-DDTHH:MM:SS+08:00` |
| 金额统一数字 | 单位为分或元需在 description 注明 |
| 状态枚举明确 | 用 `enum` 列出所有可能值 |

## 三、标准状态枚举

所有子 Skill 输出统一使用 `status` 字段：

| 值 | 含义 | 后续动作 |
|----|------|----------|
| `success` | 完整成功 | 正常传递下游 |
| `partial` | 部分成功（部分数据失败） | 传递成功部分 + 标记错误 |
| `failed` | 完全失败 | 编排器记录错误，跳过下游或重试 |
| `skipped` | 条件不满足主动跳过 | 编排器不视为错误 |

## 四、错误字段规范

```json
{
  "status": "failed",
  "error": {
    "code": "CONTACT_NOT_FOUND",
    "message": "客户 C2026064544516 不存在",
    "retryable": false
  }
}
```

- `code`：机器可读错误码（大写 snake_case）
- `message`：人类可读描述
- `retryable`：是否可重试（超时/限流 → true；数据不存在 → false）

## 五、链式传递约定

```
子 Skill A 的输出 = 子 Skill B 的输入（字段名需一致）
```

若字段名不同，编排器在调用 B 前做字段映射：

```json
{
  "from_skill": "a",
  "to_skill": "b",
  "mapping": {
    "a.contact_id": "b.customer_id",
    "a.signals[].type": "b.intent_type"
  }
}
```

## 六、契约验证清单

- [ ] 输入字段与代码实际读取的参数一致
- [ ] 输出字段与代码实际返回的字段一致
- [ ] required 字段无遗漏
- [ ] 状态枚举覆盖代码所有 return 分支
- [ ] 字段名 snake_case 且前后链路一致
