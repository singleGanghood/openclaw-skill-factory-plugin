# 拆解后验证清单 — 功能等价与质量验收

> 拆解完成后必须逐项验证，全部通过才算成功；任何一项失败需回滚或修复。

---

## 一、独立可运行验证

对每个子 Skill：

- [ ] 目录结构符合规范（`SKILL.md` + `scripts/`/`references/`/`assets/`）
- [ ] `SKILL.md` 的 frontmatter 可解析（`name` + `description`）
- [ ] 有独立触发词，能单独被 Agent 触发
- [ ] 入口脚本可直接运行：`python3 scripts/<entry>.py --help` 无报错
- [ ] 用一个最小输入样例跑通 输入 → 输出

## 二、功能等价验证

- [ ] 拆解前后对同一输入，全链路最终输出一致
- [ ] 原 Skill 的回归测试全部通过（若有）
- [ ] 中间阶段输出与拆分前逐一对比（可对比日志/JSON）
- [ ] 边界情况（空输入、超时、部分失败）行为一致

**等价性对比方法**：
```bash
# 拆解前基线
cd {SKILL_DIR} && python3 modules/pipeline/precompute_daily.py > baseline.json

# 拆解后全链路（编排器串联）
cd {ORCHESTRATOR_DIR} && python3 run_all.py > after_split.json

# diff 对比
diff <(jq -S . baseline.json) <(jq -S . after_split.json)
```

## 三、性能达标验证

- [ ] 每个子 Skill 预估耗时 ≤ 10 分钟
- [ ] 总耗时（关键路径求和）比拆分前下降 ≥ 50%
- [ ] 长耗时子 Skill 支持异步执行（`sessions_spawn`）不被阻塞

**耗时统计**：在子 Skill SKILL.md 的 Overview 中标注预估耗时。

## 四、结构合规验证

对每个子 Skill 运行结构检查：

```bash
bash {SKILL_DIR}/tools/skill-assessor/scripts/check_structure.sh {SUB_SKILL_DIR}
```

- [ ] 0 错误
- [ ] 0 警告（或警告可接受并有说明）
- [ ] 根目录无散落文件（`common.py` 等运行时必需文件除外，需在 SKILL.md 说明）

## 五、依赖完整性验证

- [ ] 共享依赖（`common.py`、`_path_setup.py` 等）路径引用正确，无复制
- [ ] 跨模块 import 全部修复，无 `ModuleNotFoundError`
- [ ] 无循环依赖（`dependency graph` 为 DAG）
- [ ] 数据契约字段与代码实际输入/输出一致

**循环依赖检测**：
```bash
python3 -c "
import ast, sys, glob
from collections import defaultdict
graph = defaultdict(set)
for f in glob.glob('**/*.py', recursive=True):
    try:
        tree = ast.parse(open(f).read())
    except Exception:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            graph[f].add(node.module)
print('检查 import 图，确认无环')
"
```

## 六、收尾验证

- [ ] 编排器 SKILL.md 列出全部子 Skill、调用顺序、数据流
- [ ] 迁移后残留文件、`__pycache__`、临时 JSON 已清理
- [ ] 原大 Skill 已降级为薄编排器（无业务逻辑残留）
- [ ] 已向用户汇报：子 Skill 清单、耗时对比、验证结果

---

## 失败处理协议

| 失败项 | 处置 |
|--------|------|
| 任一子 Skill 无法独立运行 | 修复该子 Skill 的 import/入口，不得带病交付 |
| 功能不等价 | 用 git 回滚到拆分前，重新规划边界 |
| 性能未达标 | 将最耗时子 Skill 再拆分或改异步 |
| 循环依赖 | 抽取公共逻辑到共享模块，重新划分边界 |

> 原则：**宁可回滚重新规划，不可带病交付。**
