#!/usr/bin/env python3
"""
run_eval_loop.py — 一键全自动 eval-driven 优化闭环（补齐"动态 eval 非全自动"短板）。

它把此前分散在文档约定里的步骤，串成**一条真正可一键跑的闭环**，对齐官方
`run_loop.py` 的语义（train/test 分层、按 test 选最优、blinded history、precision/recall），
但**零第三方依赖**：判定与改写都通过可插拔适配器完成，不 import anthropic、不调 claude -p。

闭环：
    eval_set ──split──► (train, test)
        │
        └─ 每轮迭代：
             1) 对 train+test 的每个 query 构造判定请求（含干扰项），发给 grader（grader_adapter）
             2) aggregate → train/test 的 precision/recall/accuracy
             3) train 未全过 且 未达 max_iterations：把 failed/false triggers + blinded 历史
                交给 rewriter（改写适配器）产出新 description → 回到 1)
             4) 记录每轮 test 分，最终**按 test 分选最优 description**
        │
        └─ 产出 eval_results.json（含每轮历史、最优 description、verdict、可视化所需数据）

判定后端（--grader-backend）：host-cmd（生产，委托宿主 subagent） / replay（CI 复现） / mock（自测）
改写后端（--rewriter-backend）：host-cmd（生产，委托宿主 subagent 改写） / none（不改写，仅评测当前）

用法示例：
    # 生产：宿主命令做判定 + 宿主命令做改写，全自动跑满 5 轮
    python3 run_eval_loop.py \
        --skill <skill-dir>/SKILL.md \
        --eval-set eval_set.json \
        --grader-backend host-cmd --grader-cmd "openclaw subagent grade" \
        --rewriter-backend host-cmd --rewriter-cmd "openclaw subagent rewrite-desc" \
        --out eval_results.json

    # 自测 / CI：mock 判定，不改写，验证闭环连通与聚合口径
    python3 run_eval_loop.py --skill <skill-dir>/SKILL.md --eval-set eval_set.json \
        --grader-backend mock --rewriter-backend none --out eval_results.json
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

# 复用同目录脚本（纯标准库，import 同级模块）
sys.path.insert(0, str(Path(__file__).resolve().parent))
import grader_adapter  # noqa: E402
from split_eval import load_eval_set, split_eval_set  # noqa: E402
from aggregate_eval import aggregate  # noqa: E402


HARD_CHAR_LIMIT = 1024


def read_current_description(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""
    import re
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return ""
    fm = m.group(1)
    blk = re.search(r"^description:\s*[|>]-?\s*\n((?:[ \t]+.*\n?)+)", fm, re.MULTILINE)
    ln = re.search(r"^description:\s*(?![|>-])(.+)$", fm, re.MULTILINE)
    if blk:
        return " ".join(l.strip() for l in blk.group(1).splitlines() if l.strip())
    if ln:
        return ln.group(1).strip().strip('"').strip("'")
    return ""


def build_requests(items, skill_name, candidate_desc, distractors, runs_per_query):
    """为一组 eval item 构造判定请求（每 item 重复 runs_per_query 次）。"""
    reqs = []
    for it in items:
        for i in range(runs_per_query):
            reqs.append({
                "query": it["query"],
                "should_trigger": bool(it.get("should_trigger")),
                "skill_name": skill_name,
                "candidate_description": candidate_desc,
                "distractors": distractors,
                "run_index": i,
            })
    return reqs


def grade(items, skill_name, candidate_desc, distractors, runs_per_query,
          backend, cmd, replay_file, timeout):
    reqs = build_requests(items, skill_name, candidate_desc, distractors, runs_per_query)
    results = grader_adapter.grade_stream(reqs, backend, cmd, replay_file, timeout)
    # 转成 aggregate_eval 期望的 raw_runs 形态
    raw = [{"query": r["query"], "should_trigger": r["should_trigger"], "triggered": r["triggered"]}
           for r in results]
    return raw


def rewrite_description(skill_name, current_desc, train_agg, history,
                        backend, cmd, timeout):
    """通过改写适配器产出新 description。backend=none 时返回 None（不改写）。"""
    if backend == "none":
        return None
    failed = [r["query"] for r in train_agg["results"] if r["should_trigger"] and not r["pass"]]
    false_trig = [r["query"] for r in train_agg["results"] if not r["should_trigger"] and not r["pass"]]
    # blinded：只给 train 信号 + 历史尝试（不给 test 分，防过拟合）
    payload = {
        "task": "rewrite_skill_description",
        "skill_name": skill_name,
        "current_description": current_desc,
        "failed_triggers": failed,      # 应触发却没触发 → 需补触发词/强化意图
        "false_triggers": false_trig,   # 不该触发却触发 → 需强化 Do NOT use for 边界
        "previous_attempts": history,   # 提示不要重复
        "constraints": {
            "max_chars": HARD_CHAR_LIMIT,
            "no_angle_brackets": True,
            "style": "imperative, intent-oriented, generalize to intent categories (do NOT paste raw queries)",
            "words": "100-200",
        },
    }
    if backend != "host-cmd":
        raise ValueError(f"unknown rewriter backend: {backend}")
    if not cmd:
        raise ValueError("--rewriter-cmd is required for host-cmd rewriter")
    proc = subprocess.run(shlex.split(cmd), input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"rewriter cmd failed (rc={proc.returncode}): {proc.stderr.strip()}")
    out = proc.stdout.strip().splitlines()
    if not out:
        raise RuntimeError("rewriter cmd produced no output")
    rec = json.loads(out[-1])
    new_desc = (rec.get("description") or "").strip()
    if not new_desc:
        return None
    if len(new_desc) > HARD_CHAR_LIMIT:
        new_desc = new_desc[:HARD_CHAR_LIMIT]
    return new_desc


def main():
    ap = argparse.ArgumentParser(description="One-command automated eval-driven optimization loop.")
    ap.add_argument("--skill", required=True, help="path to SKILL.md (or its dir)")
    ap.add_argument("--eval-set", required=True, help="eval_set.json (array or {eval_set:[...]})")
    ap.add_argument("--distractors", default="", help="optional JSON file: [{name,description}] competing skills")
    ap.add_argument("--holdout", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--runs-per-query", type=int, default=3)
    ap.add_argument("--trigger-threshold", type=float, default=0.5)
    ap.add_argument("--target", type=float, default=0.8)
    ap.add_argument("--max-iterations", type=int, default=5)
    # grader
    ap.add_argument("--grader-backend", choices=["host-cmd", "replay", "mock"], default="mock")
    ap.add_argument("--grader-cmd", default="")
    ap.add_argument("--grader-replay-file", default="")
    ap.add_argument("--timeout", type=int, default=60)
    # rewriter
    ap.add_argument("--rewriter-backend", choices=["host-cmd", "none"], default="none")
    ap.add_argument("--rewriter-cmd", default="")
    ap.add_argument("--out", default="eval_results.json")
    args = ap.parse_args()

    skill_md = Path(args.skill)
    if skill_md.is_dir():
        skill_md = skill_md / "SKILL.md"
    if not skill_md.exists():
        print(f"Error: {skill_md} not found", file=sys.stderr)
        sys.exit(2)

    import re
    text = skill_md.read_text(encoding="utf-8")
    nm = re.search(r"^name:\s*(.+)$", text, re.MULTILINE)
    skill_name = (nm.group(1).strip().strip('"').strip("'") if nm else skill_md.parent.name)

    eval_set = load_eval_set(Path(args.eval_set))
    if len(eval_set) < 2:
        print("Error: eval set needs >= 2 items", file=sys.stderr)
        sys.exit(2)

    distractors = []
    if args.distractors:
        distractors = json.loads(Path(args.distractors).read_text(encoding="utf-8"))

    train, test = split_eval_set(eval_set, args.holdout, args.seed)
    current_desc = read_current_description(skill_md)

    history = []          # blinded：仅记录 description + train 分，不含 test
    iterations = []       # 完整记录（含 test 分，供报告/选最优）
    best = None           # {"iter","description","test_precision","test_recall","test_accuracy"}

    for it in range(args.max_iterations):
        # 1) 判定 train + test
        train_raw = grade(train, skill_name, current_desc, distractors, args.runs_per_query,
                          args.grader_backend, args.grader_cmd, args.grader_replay_file, args.timeout)
        test_raw = grade(test, skill_name, current_desc, distractors, args.runs_per_query,
                         args.grader_backend, args.grader_cmd, args.grader_replay_file, args.timeout)
        train_agg = aggregate(train_raw, args.trigger_threshold)
        test_agg = aggregate(test_raw, args.trigger_threshold)
        ts, trs = test_agg["summary"], train_agg["summary"]

        rec = {
            "iteration": it,
            "description": current_desc,
            "train": trs,
            "test": ts,
            "train_results": train_agg["results"],
            "test_results": test_agg["results"],
        }
        iterations.append(rec)
        history.append({"description": current_desc,
                        "train_passed": trs["passed"], "train_total": trs["total"]})

        # 按 test 选最优（test 相同则取更早/更短）
        cand = {"iter": it, "description": current_desc,
                "test_precision": ts["precision"], "test_recall": ts["recall"],
                "test_accuracy": ts["accuracy"],
                "test_score": ts["precision"] + ts["recall"]}
        if best is None or cand["test_score"] > best["test_score"]:
            best = cand

        train_all_pass = trs["failed"] == 0
        # 2) 停止条件：train 全过 或 到达上限 或 无改写器
        if train_all_pass or it == args.max_iterations - 1 or args.rewriter_backend == "none":
            break

        # 3) 改写 description（blinded：不传 test 分）
        new_desc = rewrite_description(skill_name, current_desc, train_agg, history,
                                       args.rewriter_backend, args.rewriter_cmd, args.timeout)
        if not new_desc or new_desc == current_desc:
            break  # 改写器没给出新方案，提前停止
        current_desc = new_desc

    best_prec = best["test_precision"]
    best_rec = best["test_recall"]
    verdict = "PASS" if (best_prec >= args.target and best_rec >= args.target) else "FAIL"

    out = {
        "skill": skill_name,
        "config": {
            "holdout": args.holdout, "seed": args.seed,
            "runs_per_query": args.runs_per_query,
            "trigger_threshold": args.trigger_threshold,
            "target": args.target, "max_iterations": args.max_iterations,
            "grader_backend": args.grader_backend,
            "rewriter_backend": args.rewriter_backend,
        },
        "split_counts": {
            "train": len(train), "test": len(test),
        },
        "iterations": iterations,
        "best": best,
        "best_description": best["description"],
        "verdict": verdict,
        "target": args.target,
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "skill": skill_name, "verdict": verdict,
        "best_iter": best["iter"],
        "test_precision": best_prec, "test_recall": best_rec,
        "iterations_run": len(iterations),
        "out": args.out,
    }, indent=2, ensure_ascii=False))
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
