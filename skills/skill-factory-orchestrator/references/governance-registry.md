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

1. **幂等追加（只追加新内容，不覆盖、不重复）**：以 **`(name, version, contentHash)` 为幂等键**。
   - 登记前先查重：若注册表已存在**完全相同**的 `(name, version, contentHash)` record → **不追加**（NOOP）。
   - 未命中才追加一条新 record，保留历史用于回滚。
   - 这样「同一版本内容登记多少次，记录都只有一条」——重复执行结果收敛，天然幂等。
2. **contentHash 必填**：对 skill 目录内容计算哈希，作为「这次登记的到底是哪份内容」的不可变证据。
   `install_skill.py` 用等价的纯 Python 实现（把相对路径 + 文件字节逐一喂入 sha256），
   语义与下述 shell 口径一致，但跨平台、无需 shell/xargs：
   ```bash
   find <skill-dir> -type f -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256
   ```
   > 计算时统一忽略 `__pycache__` / `*.pyc` / `.git` / `.DS_Store` 等噪声，保证「同内容永远同 hash」。
3. **rollbackRef**：指向上一个已登记且验证通过的版本，回滚时直接取该版本内容。
   升级安装（UPGRADE）时由 `install_skill.py` 自动填入上一条同名 record 的 `name@version`。
4. **CONFLICT 是错误，不是新记录**：同 `(name, version)` 但 `contentHash` 不同（即「同版本内容漂移」）
   或试图**降级**，视为冲突 → **拒绝登记与安装**，必须 bump 版本号后重试（或显式 `--force`）。
5. **登记不改运行状态**：写 registry.json **绝不**触碰 `agents.*.skills`、`agents.defaults.skills`，也不改任何 SKILL.md 的 `metadata.openclaw`。

## 幂等安装（Idempotent Install）

「安装」同时触碰**磁盘转正**与**治理登记**两层，二者都必须幂等。由
[scripts/install_skill.py](../scripts/install_skill.py) 统一承担——**以 contentHash 为幂等键，
做内容寻址的原子转正 + 查重式登记**，四态收敛：

```
候选 (name, version, hash_new)   目标现状                    → action（幂等结果）
──────────────────────────────────────────────────────────────────────
目标不存在                                                   → install   （原子转正 + 登记）
目标存在, hash 相同                                          → noop      （已到目标态，跳过，退出码 0）
目标存在, hash 不同, version 相同                            → conflict  （同版本漂移，拒绝，退出码 2）
目标存在, hash 不同, version 更高                            → upgrade   （替换 + 记 rollbackRef + 登记）
目标存在, hash 不同, version 更低                            → conflict  （防降级覆盖，除非 --force）
```

**幂等保障要点**：
- **内容寻址**：靠 contentHash 判断「是否已到目标态」，而非时间戳/文件是否存在 → 真幂等。
- **原子转正**：先写临时目录再 `os.replace()` 整目录替换，杜绝半写/边读边覆盖。
- **并发安全**：对生效目录加文件锁（`fcntl.flock`，退化为 `O_EXCL` lockfile），加锁后二次决策防 TOCTOU。
- **两事实源分离**：安装只作用于**磁盘 + registry**，**永不**改 eligible / per-agent skills（见 two-sources-of-truth.md）。
- **可预测**：`--dry-run` 只输出四态决策、零副作用，便于 CI 反复跑。

用法：
```bash
python3 scripts/install_skill.py \
  --staging .skill-factory/staging/<name> \
  --dest <skills 生效根，如 .codebuddy/skills> \
  --registry .skill-factory/registry.json \
  --assessor-score 85 --eval-precision 1.0 --eval-recall 0.9 \
  [--dry-run] [--force]
# 退出码：0=install/noop/upgrade  2=conflict  3=用法/输入错误
```

## 回滚流程

1. 从 registry.json 找到目标 `rollbackRef` 对应的 record 及其 `contentHash`
2. 恢复该版本的 skill 内容
3. 重新走 Step05 eligible 判定 + Step06 会话测试
4. 追加一条新的登记记录（记录「回滚到 X 版本」）
