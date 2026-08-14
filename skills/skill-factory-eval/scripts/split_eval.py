#!/usr/bin/env python3
"""
split_eval.py — train/test 分层分割（对齐官方 run_loop.split_eval_set 语义）。

按 should_trigger 分层洗牌后切分，保证 train/test 里正反例比例一致，防止 description
优化过拟合到具体问法。零第三方依赖。

用法：
    python3 split_eval.py eval_set.json [--holdout 0.4] [--seed 42]
输入既可是 gen_eval_set.py 的完整输出（含 eval_set 键），也可是纯数组。
"""
import argparse
import json
import random
import sys
from pathlib import Path


def load_eval_set(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "eval_set" in data:
        return data["eval_set"]
    if isinstance(data, list):
        return data
    raise ValueError("输入必须是数组，或含 'eval_set' 键的对象")


def split_eval_set(eval_set, holdout: float, seed: int = 42):
    random.seed(seed)
    trigger = [e for e in eval_set if e.get("should_trigger")]
    no_trigger = [e for e in eval_set if not e.get("should_trigger")]
    random.shuffle(trigger)
    random.shuffle(no_trigger)
    n_t = max(1, int(len(trigger) * holdout)) if trigger else 0
    n_n = max(1, int(len(no_trigger) * holdout)) if no_trigger else 0
    test = trigger[:n_t] + no_trigger[:n_n]
    train = trigger[n_t:] + no_trigger[n_n:]
    return train, test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_set")
    ap.add_argument("--holdout", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    eval_set = load_eval_set(Path(args.eval_set))
    if len(eval_set) < 2:
        print("Error: eval set 至少需要 2 条", file=sys.stderr)
        sys.exit(2)

    train, test = split_eval_set(eval_set, args.holdout, args.seed)
    out = {
        "holdout": args.holdout,
        "seed": args.seed,
        "train": train,
        "test": test,
        "counts": {
            "train": len(train),
            "test": len(test),
            "train_pos": sum(1 for e in train if e.get("should_trigger")),
            "train_neg": sum(1 for e in train if not e.get("should_trigger")),
            "test_pos": sum(1 for e in test if e.get("should_trigger")),
            "test_neg": sum(1 for e in test if not e.get("should_trigger")),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
