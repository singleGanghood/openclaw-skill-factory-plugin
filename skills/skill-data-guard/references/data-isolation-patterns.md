# 数据隔离设计模式（Data Isolation Patterns）

> 数据边界封闭的完整设计规范：数据流、脱敏规则、字段白名单、哈希化、env-only、加密落盘。

---

## 一、核心数据流（数据边界图）

```
┌─────────────────────────────────────────────────────────────┐
│  脚本进程（数据边界，LLM 完全不可见）                          │
│                                                             │
│  ① 取 ID：   os.environ["<PREFIX>_INSTANCE_ID"] 或 元数据服务  │
│  ② 取凭证：  os.environ["<PREFIX>_TOKEN"]   ← secrets env-only│
│  ③ 调接口：  <PREFIX>_API + ID 鉴权/路由（强制 HTTPS）          │
│  ④ 拿数据：  raw = resp.json()   ← 只存内存变量               │
│  ⑤ 处理：    白名单 + 脱敏 + 哈希                              │
│  ⑥ stdout：  只 print 脱敏结论（不含 ID、不含 raw）             │
└─────────────────────────────────────────────────────────────┘
        ▲                                    │
   环境注入(ID/Token)                   脱敏结论(唯一出口)
        │                                    ▼
   [不在上下文]                        [进入 session，已脱敏]
```

**关键结论**：私有数据进入 session / thinking 的唯一入口，是脚本的 stdout 返回值。
只要数据不通过 stdout 吐出来，模型就"看不到"它，自然无从泄露。

---

## 二、零泄露的前提：数据不进上下文

| 数据来源 | 是否进上下文 | 是否安全 |
|----------|-------------|---------|
| 环境变量（`INSTANCE_ID` / `TOKEN`） | ❌ 不进 | ✅ 最佳 |
| 实例元数据服务（云上 `169.254.169.254`） | ❌ 不进 | ✅ 脚本内自取 |
| SKILL.md 硬编码 | ✅ 进 | ❌ 绝对禁止 |
| 命令行参数由 Agent 传入 | ✅ 进 | ❌ 命令串进 session |
| 模型从别处查到再传 | ✅ 进 | ⚠️ 已泄露，只能降级 |

---

## 三、脱敏规则

### 字段白名单（默认最小集）

只放行非敏感字段，新增字段需先改白名单再决定放行：

```python
ALLOWED_FIELDS = {"doc_id", "title", "summary"}
```

### 敏感字段打码（mask）

```python
SENSITIVE_KEYS = {"owner", "uin", "phone", "email", "secret"}

def mask(v):
    if not isinstance(v, str) or len(v) <= 2:
        return v
    return v[0] + "*" * (len(v) - 2) + v[-1]
```

### 可识别标识哈希化

`doc_id` / `uin` 等唯一标识，用哈希替代，保留"可比对性"但不可还原：

```python
digest = hashlib.sha256(ids_json.encode()).hexdigest()[:16]
```

---

## 四、凭证与实例 ID：env-only

```bash
# 由运行时/调度器注入，而非写进 SKILL.md / 命令行参数
export <PREFIX>_API="https://internal-kb.example.com/v1/search"
export <PREFIX>_TOKEN="xxxx"
export <PREFIX>_INSTANCE_ID="ins-xxxx"
```

原则：
- skill 文件（SKILL.md + scripts/）可提交版本库，**不含任何机密**
- ID/Token 只在运行时注入脚本进程环境，不进 LLM 上下文
- 符合安全基线 `Secrets: env-only`

---

## 五、传输加密与存储加密

| 层 | 手段 | 说明 |
|----|------|------|
| 传输层 | 强制 HTTPS | 接口地址必须 `https://`，禁止明文 HTTP |
| 存储层（默认） | **不落盘** | 原始数据只用内存变量，进程结束即销毁 |
| 存储层（进阶） | AES-GCM 加密落盘 | 仅在必须缓存时启用，密钥从环境变量读，用后删除临时文件 |

> 本能力包默认走"内存处理 + 不落盘"，保持零第三方依赖。落盘加密作为进阶手段，
> 需引入 `cryptography` 依赖，仅在确有必要时启用。

---

## 六、禁止事项（红线）

- ❌ 禁止 `print(raw)` 或任何形式输出原始响应
- ❌ 禁止把 Token / 实例 ID 写进 SKILL.md、description、命令行参数
- ❌ 禁止把原始数据写到日志文件、临时文件（除非加密且用后删除）
- ❌ 禁止在 description 中写真实数据（接口地址、字段名、实例 ID）
- ❌ 禁止模型复述、引用脚本返回结论之外的任何原始字段

---

## 七、可接受泄露面（豁免）

- description 中声明"本 skill 涉及数据隔离"（`DATA-GUARD`）—— 只暴露"存在该能力"，不暴露数据本身
- 脚本返回的 `hit_count` / 脱敏标题 / 哈希 digest —— 已脱敏，不可还原
