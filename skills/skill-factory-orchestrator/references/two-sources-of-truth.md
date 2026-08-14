# 两个事实源：eligible vs 治理注册表

这是整条流水线最容易踩坑的地方，也是可行性调研第五点约束 4 的核心。**二者不能混为一谈。**

## 对照表

| 维度 | 运行时 eligible | 治理注册表 |
|------|-----------------|------------|
| 回答的问题 | 现在这个 agent **能不能用**这个 skill？ | 哪个**版本**通过过**什么验证**？ |
| 事实来源 | per-agent skills 白名单 + `metadata.openclaw`（os/requires/env）实时判定 | `.openclaw/skill-factory/registry.json`（历史追加） |
| 决定因素 | OS 匹配、bin 在 PATH、env/config 满足、在白名单内 | 人为/自动登记的验证结论 |
| 变化时机 | 环境变化即变（换机器、装了 bin、改白名单） | 只在通过验证后追加 |
| 谁来改 | 配置层（`agents.*.skills`）+ 环境 | 编排器 Step07 |
| 能否互相替代 | ❌ 注册表登记了 ≠ 现在能用 | ❌ 现在能用 ≠ 已通过治理验证 |

## 两层 eligible 过滤（OpenClaw 实际逻辑）

1. **第一层 · per-agent allowlist（配置层）**
   - `agents.<id>.skills`（显式列表**替换**而非合并）；省略则继承 `agents.defaults.skills`
   - 未知 agent id 回退默认，避免越权放宽
2. **第二层 · runtime eligibility（运行时门控）**
   - `os` 列表须含当前平台
   - `always: true` 直接放行
   - `requires.bins` 扫 PATH、`requires.env`、`requires.config` 是否满足
   - 支持 remote/paired node 的 bin/platform 检查

> 本插件里：`skill-splitter` 因声明 `requires.bins:["python3"]`，在无 python3 的环境第二层会判不可用；
> `skill-factory-screenshot` 不声明 bin，任何平台都能被发现，但其后端各自受门控（peekaboo 后端受 `os:darwin`+`peekaboo` 约束）。

## 铁律

- **登记（Step07）只写注册表**，绝不修改 `agents.*.skills` 或任何 `metadata.openclaw`。
- **判定（Step05）只读 eligible**，不写注册表。
- 用户报"装了却用不了" → 查 **eligible**（白名单 + 门控），不是查注册表。
- 审计"这个 skill 什么时候验过、能不能回滚" → 查 **注册表**，不是查运行状态。
