# Eval Harness 协议（触发判定 / description 改写的可插拔适配层）

本文件定义 `run_eval_loop.py` 与外部"判定/改写能力"之间的**进程级协议**，
用来把过去"靠自然语言约定"的动态 eval，升级为**一键可跑、可插拔、可回放**的自动闭环——
同时**坚持零第三方依赖**（不 import `anthropic`、不调 `claude -p`）。

核心思想：`run_eval_loop.py` 不关心"谁来做判定/改写"，只按下面的 JSON 协议与一个**命令**通信。
这样：
- **生产**：命令 = 宿主（OpenClaw / CodeBuddy）暴露的 subagent CLI → 真实复用宿主模型能力；
- **CI / 回归**：命令 = 回放历史结果 → 完全确定、可复现；
- **自测**：命令 = 内置启发式 mock → 验证闭环连通性，无需任何模型。

---

## 一、触发判定协议（grader）

由 `grader_adapter.py` 实现三种后端：`host-cmd` / `replay` / `mock`。

### 请求（run_eval_loop → grader），一行一个 JSON
```json
{"query": "帮我创建一个skill", "should_trigger": true, "skill_name": "skill-generator",
 "candidate_description": "ALWAYS invoke ... 'create skill' ...",
 "distractors": [{"name": "skill-assessor", "description": "..."}],
 "run_index": 0}
```

### 响应（grader → run_eval_loop），一行一个 JSON
```json
{"query": "帮我创建一个skill", "triggered": true, "chosen_skill": "skill-generator"}
```

### `triggered` 判定语义
- `chosen_skill == skill_name` → `triggered=true`
- 否则（选了干扰项或都不选）→ `triggered=false`

### host-cmd 后端：宿主命令契约
宿主命令必须：**从 stdin 读一行请求 JSON，向 stdout 写一行结果 JSON，退出码 0**。
判定纪律（与 `grader-rubric.md` 一致）：
- 只看 `skill_name + candidate_description + distractors`，**不读 SKILL.md 正文**；
- **必须**把 `distractors` 作为竞争项一起给模型，否则 precision 失真；
- 每次判定独立，不共享上一次结论；判定 subagent 与改写 subagent 相互隔离。

示例：
```bash
python3 run_eval_loop.py ... \
  --grader-backend host-cmd --grader-cmd "openclaw subagent grade"
```

### replay 后端：确定性复现
把某次真实跑分的逐条结果存成 JSONL（每行含 `query / triggered / chosen_skill`，可选 `run_index`），
CI 里用它复现，不再起模型：
```bash
python3 grader_adapter.py --backend replay --replay-file runs.jsonl < requests.jsonl
```

### mock 后端：零模型自测
内置启发式（query 与触发词 token 重合度 vs 干扰项，叠加相邻意图词惩罚）。
**仅用于验证闭环连通性**，不代表真实触发力。

---

## 二、description 改写协议（rewriter）

`run_eval_loop.py --rewriter-backend host-cmd --rewriter-cmd "<命令>"`。
命令契约：**stdin 读一个改写请求 JSON，stdout 写 `{"description": "..."}`**。

### 改写请求（blinded：不含 test 分数，防过拟合）
```json
{"task": "rewrite_skill_description",
 "skill_name": "skill-generator",
 "current_description": "...",
 "failed_triggers": ["应触发却没触发的 query ..."],
 "false_triggers": ["不该触发却触发的 query ..."],
 "previous_attempts": [{"description": "...", "train_passed": 4, "train_total": 6}],
 "constraints": {"max_chars": 1024, "no_angle_brackets": true,
                 "style": "imperative, intent-oriented, generalize to intent categories",
                 "words": "100-200"}}
```

### 改写响应
```json
{"description": "ALWAYS invoke this skill when ... 'create skill', '创建skill' ... Do NOT use for ..."}
```

改写方**必须**遵守 constraints：≤1024 字符、无尖括号、泛化到意图类别（**不要**逐字塞入 query）。
`run_eval_loop.py` 会对超长结果二次截断兜底。

`--rewriter-backend none`：不改写，仅对当前 description 评测一轮（用于纯基准测量）。

---

## 三、为什么这仍是"零依赖"

- 所有脚本只用 Python 标准库（`json/subprocess/shlex/argparse/pathlib/random/re/collections`）。
- host-cmd 通过**子进程 + stdin/stdout** 与宿主通信，宿主命令是什么由用户配置——
  插件不绑定任何特定 SDK/CLI/API key。
- 因此：**在任何宿主上，闭环脚本本身都能一键跑起来**；接上宿主 grader/rewriter 命令即变为生产级全自动。

---

## 四、与官方 run_loop.py 的对应关系

| 官方 run_loop.py | 本插件 | 说明 |
|---|---|---|
| `import anthropic` 直接调模型判定 | `grader_adapter host-cmd`（委托宿主命令） | 去 SDK，改进程协议 |
| `improve_description` 内联调模型改写 | `rewriter host-cmd`（委托宿主命令） | 去 SDK，改进程协议 |
| `split_eval_set` | `split_eval.py` / 内部复用 | 语义一致（seed=42, stratified） |
| 混淆矩阵按 run 计 + best-by-test + blinded | `aggregate_eval.py` + `run_eval_loop.py` | 口径一致 |
| eval-viewer（HTML） | `generate_report.py`（单文件 HTML） | 零依赖、可离线 |

**结论**：把官方"内联 SDK 调用"的两处（判定、改写）抽象成**可插拔进程协议**，
从而在保持零依赖的同时，获得与官方等价的"一键全自动闭环"。
