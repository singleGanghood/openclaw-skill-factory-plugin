#!/usr/bin/env python3
"""
aggregate_eval.py — 把宿主 subagent 的原始跑分结果聚合成 precision/recall/accuracy。

对齐官方 run_loop 里的判分口径，但输入来源是"宿主 subagent 的判定结果"，
而非官方的 `claude -p` 子进程——因此零外部 SDK 依赖。

输入（raw_runs.json）：数组，每条是对某个 query 的一次判定：
  {"query": "...", "should_trigger": true, "triggered": true}
同一 query 出现多次即为多次 run（用于统计触发率）。

用法：
    python3 aggregate_eval.py raw_runs.json [--trigger-threshold 0.5] [--target 0.8]
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def aggregate(raw, trigger_threshold: float):
    by_query = defaultdict(lambda: {"should_trigger": None, "runs": 0, "triggers": 0})
    for r in raw:
        q = r["query"]
        by_query[q]["should_trigger"] = bool(r["should_trigger"])
        by_query[q]["runs"] += 1
        if r.get("triggered"):
            by_query[q]["triggers"] += 1

    results = []
    for q, agg in by_query.items():
        rate = agg["triggers"] / agg["runs"] if agg["runs"] else 0.0
        did_trigger = rate >= trigger_threshold
        passed = did_trigger == agg["should_trigger"]
        results.append({
            "query": q,
            "should_trigger": agg["should_trigger"],
            "runs": agg["runs"],
            "triggers": agg["triggers"],
            "trigger_rate": round(rate, 3),
            "pass": passed,
        })

    # 混淆矩阵（按 run 计，和官方一致）
    tp = sum(r["triggers"] for r in results if r["should_trigger"])
    pos_runs = sum(r["runs"] for r in results if r["should_trigger"])
    fn = pos_runs - tp
    fp = sum(r["triggers"] for r in results if not r["should_trigger"])
    neg_runs = sum(r["runs"] for r in results if not r["should_trigger"])
    tn = neg_runs - fp
    total = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    accuracy = (tp + tn) / total if total > 0 else 0.0

    passed_q = sum(1 for r in results if r["pass"])
    return {
        "results": results,
        "summary": {
            "passed": passed_q,
            "failed": len(results) - passed_q,
            "total": len(results),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "accuracy": round(accuracy, 3),
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw_runs")
    ap.add_argument("--trigger-threshold", type=float, default=0.5)
    ap.add_argument("--target", type=float, default=0.8,
                    help="precision/recall 达标目标，用于给出 verdict")
    args = ap.parse_args()

    raw = json.loads(Path(args.raw_runs).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "runs" in raw:
        raw = raw["runs"]
    out = aggregate(raw, args.trigger_threshold)
    s = out["summary"]
    out["verdict"] = "PASS" if (s["precision"] >= args.target and s["recall"] >= args.target) else "FAIL"
    out["target"] = args.target
    print(json.dumps(out, indent=2, ensure_ascii=False))
    sys.exit(0 if out["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
