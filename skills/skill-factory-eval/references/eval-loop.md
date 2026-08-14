# Eval-Driven Description 优化闭环（对齐并反超官方 skill-creator）

本文件定义 description 自动优化的**判分口径、改写规则与停止条件**，
逻辑对齐 Anthropic 官方 `run_loop.py` / `improve_description.py`，但用**宿主 subagent**执行，
不依赖 `anthropic` SDK。

## 一、判分口径（与官方一致）

对每个 query 跑 N 次（`runs_per_query`，默认 3），统计触发率 `triggers/runs`：

- `did_trigger = trigger_rate >= trigger_threshold`（默认 0.5）
- `pass = (did_trigger == should_trigger)`

混淆矩阵按 **run** 计（非按 query）：

| | 预测触发 | 预测不触发 |
|---|---|---|
| 应触发(should_trigger=true) | TP | FN |
| 不应触发(should_trigger=false) | FP | TN |

- `precision = TP / (TP + FP)` —— 越高越不误触发
- `recall = TP / (TP + FN)` —— 越高越不漏触发
- `accuracy = (TP + TN) / total`

## 二、优化循环（train 优化 / test 选优）

1. 只对 **train 集** 收集失败：
   - `failed_triggers`：should_trigger=true 但没触发（补触发词、强化意图）
   - `false_triggers`：should_trigger=false 却触发（强化 `Do NOT use for` 边界）
2. 把 failed/false + **历史尝试（提示"不要重复，换结构"）** 交给宿主 subagent 改写 description。
   - **必须对改写者隐藏 test 分数**（blinded history），防止过拟合到 test。
3. 改写约束：
   - 祈使、意图导向（"Use this skill when..."），不写实现细节
   - **≤ 100–200 词**，硬上限 **1024 字符**（超限二次压缩）
   - 泛化到"用户意图类别"，**不要**堆砌具体 query（防过拟合、省注入空间）
   - 无尖括号 `< >`
4. 回到动态跑分重测。

## 三、停止条件

- train 全过（`failed == 0`），或
- 达到 `max_iterations`（默认 5）

## 四、选最优（防过拟合的关键）

- 有 test 集：按 **test_passed** 最高的迭代选最优 description。
- 无 test 集：按 train_passed 选。

## 五、达标门槛（verdict）

- 目标默认 `precision >= 0.8 且 recall >= 0.8` → `PASS`。
- 未达标 → 产出最优候选 + 结构化优化指令，交 orchestrator 决策。

## 六、相对官方的提速点 + 全自动闭环

1. **快路径短路**：先跑 `static_trigger_score.py`（0 模型调用），<70 分直接回喂 generator，
   根本不进入昂贵的动态循环。官方无此层，任何候选都要真实跑模型。
2. **一键全自动闭环**：`run_eval_loop.py` 把 split→判定→聚合→改写→按 test 选最优串成**一条命令**，
   对齐官方 `run_loop.py` 的口径，但判定/改写通过 [eval-harness-protocol.md](eval-harness-protocol.md)
   的**进程协议**委托宿主命令——不新拉 `claude -p` 子进程、不初始化 `anthropic` client。
3. **可插拔 + 可回放**：判定后端 `host-cmd`（生产）/ `replay`（CI 确定性复现）/ `mock`（自测），
   同一套编排在生产与 CI 复用；`replay` 让 eval 结果可离线回归，官方无此能力。
4. **可选降低 runs_per_query**：静态分很高的候选，动态可只跑 1–2 次抽检而非 3 次。

## 七、可视化（补齐官方 eval-viewer 的等价物）

跑完后用 `generate_report.py eval_results.json -o eval_report.html` 产出**零依赖单文件 HTML**：
verdict、按 test 选出的最优轮、每轮 train/test 的 precision/recall 柱状、失败项置顶的明细表、
最优 description 全文。双击即在浏览器打开，无需服务器/网络。
