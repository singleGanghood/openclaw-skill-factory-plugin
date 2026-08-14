# 治理注册表（Governance Registry）

> 治理注册表回答的是「**哪个版本的 skill 通过过什么验证**」，用于审计与回滚。
> 它**不**决定「现在这个 agent 能不能用这个 skill」——那是运行时 eligible 的职责。

## 存储位置

```
.skill-factory/registry.json
```

首次登记时若不存在则创建。

## Schema

```json
{
  "version": 1,
  "records": [
    {
      "name": "expense-filler",
      "version": "1.0.0",
      "contentHash": "sha256:...",       // SKILL.md + 资源文件内容哈希，作为不可变快照证据
      "assessorScore": 88,                // skill-assessor 给出的百分制分数
      "assessorReportRef": ".skill-factory/reports/expense-filler-1.0.0.md",
      "verifiedAt": "2026-08-14T10:00:00+08:00",
      "verifiedBy": "orchestrator",       // 或具体 agent / 用户 id
      "sessionTest": { "positive": true, "negativeNoMisfire": true },
      "rollbackRef": "expense-filler@0.9.0", // 上一个已验证版本，供回滚
      "notes": "..."
    }
  ]
}
```

## 登记规则

1. **只追加，不覆盖**：每次通过验证的版本追加一条 record，保留历史用于回滚。
2. **contentHash 必填**：对 skill 目录内容计算哈希，作为「这次登记的到底是哪份内容」的不可变证据：
   ```bash
   find <skill-dir> -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256
   ```
3. **rollbackRef**：指向上一个已登记且验证通过的版本，回滚时直接取该版本内容。
4. **登记不改运行状态**：写 registry.json **绝不**触碰 `agents.*.skills`、`agents.defaults.skills`，也不改任何 SKILL.md 的 `metadata.openclaw`。

## 回滚流程

1. 从 registry.json 找到目标 `rollbackRef` 对应的 record 及其 `contentHash`
2. 恢复该版本的 skill 内容
3. 重新走 Step05 eligible 判定 + Step06 会话测试
4. 追加一条新的登记记录（记录「回滚到 X 版本」）
