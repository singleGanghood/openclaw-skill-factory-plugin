# Grader 判定准则（宿主 subagent 版，替代官方 grader.md + claude -p）

动态跑分里，每个 query 需要判定："如果用户发来这句话，模型会不会调用**本 skill**？"
官方用 `claude -p` 起子进程；本插件用**宿主自带 subagent**做同样的判定，零外部 SDK。

## 判定协议

对每个 `(query, candidate_description)`，向宿主 subagent 发起一次判定，提供：

1. **available_skills 列表**：包含被测 skill 的 `name + candidate_description`，
   并混入若干**干扰项**（同插件其它 skill 的真实 description），模拟真实竞争环境。
2. **用户 query**：待判定的问法。
3. **提问**：仅根据 name+description，模型是否会选择调用被测 skill？

要求 subagent 只回结构化结果：

```json
{"query": "...", "triggered": true|false, "chosen_skill": "<name or none>"}
```

把该 query 的 N 次判定各写一行，汇总成 raw_runs.json 交给 `aggregate_eval.py`。

## triggered 的定义

- `chosen_skill == 被测 skill name` → `triggered=true`
- 否则（选了别的 skill 或都不选）→ `triggered=false`

## 判定纪律（避免污染结果）

- **只看 name + description**，不许提前读 SKILL.md 正文（真实触发决策阶段模型也看不到正文）。
- **必须混入干扰 skill**，否则 precision 失真（没有竞争，什么都容易"触发"）。
- 每次判定相互独立，不共享上一次结论。
- 判定 subagent 与"改写 description"的 subagent 应相互隔离，避免自证。

## 与官方 grader 的差异

| | 官方 grader.md | 本插件 |
|---|---|---|
| 执行体 | `claude -p` 子进程 | 宿主自带 subagent |
| 依赖 | `anthropic` SDK / CLI / API key | 无（宿主已具备） |
| 干扰项 | 依赖真实全量 skill 目录 | 主动混入同插件 skill 作干扰，可控 |
| 冷启动 | 每次新进程 | 复用宿主会话，更快 |
