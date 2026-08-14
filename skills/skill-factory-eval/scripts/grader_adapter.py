#!/usr/bin/env python3
"""
grader_adapter.py — 触发判定适配层（把"宿主 subagent 判定"标准化为可插拔、可回放的进程协议）。

背景 / 为什么需要它
====================
官方 skill-creator 用 `import anthropic` + `claude -p` 直接把"这个 query 会不会触发本 skill"
判定跑通，因此它的 eval 是"全自动"的——代价是硬依赖 SDK/CLI/API key。

本插件坚持零第三方依赖，但过去把"真实触发判定"完全交给自然语言约定（references/grader-rubric.md），
导致动态 eval 无法一键自动跑。本模块用一个**统一的判定协议**补齐这一环：

    run_eval_loop.py  ──(每个 query 一行 JSON)──►  grader（一个"命令"）  ──(判定结果 JSON)──►  聚合

grader 有三种后端（backend），全部零第三方依赖：

  1. host-cmd  ：把判定委托给"宿主提供的命令"（如 OpenClaw/CodeBuddy 暴露的 subagent CLI）。
                 协议：命令从 stdin 读一行 JSON 请求，向 stdout 写一行 JSON 结果。
                 这才是生产用法——真正复用宿主自带的模型能力，无需任何外部 SDK。
  2. replay    ：从一个 JSONL 回放文件里读取历史判定结果（用于 CI / 回归 / 离线复现，完全确定）。
  3. mock      ：内置启发式判定器（关键词重合 + 排除边界），零模型、零依赖，用于自测闭环连通性。

请求 / 响应协议（一行一个 JSON）
================================
请求（run_eval_loop → grader）：
    {"query": "...", "skill_name": "foo", "candidate_description": "...",
     "distractors": [{"name":"bar","description":"..."}], "run_index": 0}

响应（grader → run_eval_loop）：
    {"query": "...", "triggered": true|false, "chosen_skill": "<name|none>"}

用法
====
    # 生产：委托宿主命令做判定
    python3 grader_adapter.py --backend host-cmd --cmd "openclaw subagent grade" < requests.jsonl

    # 回放：CI 里确定性复现
    python3 grader_adapter.py --backend replay --replay-file runs.jsonl < requests.jsonl

    # 自测：内置启发式
    python3 grader_adapter.py --backend mock < requests.jsonl

通常你不需要手动调它——`run_eval_loop.py --grader ...` 会在内部按同样协议调用本模块。
"""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# mock 后端：零模型的启发式判定器（仅用于自测闭环连通性，不代表真实触发力）
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]")
_EXCLUSION_HINTS = ["do not use", "don't use", "not for", "不适用", "不要用", "禁止用于", "而不是"]


def _tokens(text: str):
    return set(_WORD_RE.findall((text or "").lower()))


def _quoted_keywords(desc: str):
    q = re.findall(r"'([^']+)'", desc) + re.findall(r'"([^"]+)"', desc)
    kws = [x for x in q if 1 <= len(x) <= 40]
    toks = set()
    for k in kws:
        toks |= _tokens(k)
    return toks


def mock_grade(req: dict) -> dict:
    """启发式：query 与被测 skill 触发词的重合度 vs 与干扰项的重合度，取最高者。"""
    query = req["query"]
    q_tok = _tokens(query)
    target_desc = req.get("candidate_description", "")

    def overlap(desc: str) -> float:
        kw = _quoted_keywords(desc) or _tokens(desc)
        if not kw:
            return 0.0
        return len(q_tok & kw) / (len(kw) ** 0.5 + 1e-9)

    target_score = overlap(target_desc)
    best_other = 0.0
    best_other_name = "none"
    for d in req.get("distractors", []):
        s = overlap(d.get("description", ""))
        if s > best_other:
            best_other, best_other_name = s, d.get("name", "none")

    # 若 query 命中被测 skill 的排除边界词，压制其触发
    low_q = query.lower()
    for d in req.get("distractors", []):
        pass
    exclusion_penalty = 0.0
    # 极简：如果 query 明显是"评估/安装/拆分"等相邻意图词，降低 target
    for adj in ["评估", "assess", "安装", "install", "拆", "split", "排序", "算法", "sort"]:
        if adj in low_q:
            exclusion_penalty = 0.5

    target_final = target_score - exclusion_penalty
    triggered = target_final > 0.15 and target_final >= best_other
    return {
        "query": query,
        "triggered": bool(triggered),
        "chosen_skill": req.get("skill_name") if triggered else (best_other_name if best_other > target_final else "none"),
        "_backend": "mock",
    }


# ---------------------------------------------------------------------------
# replay 后端：从历史 JSONL 精确回放（CI / 回归 / 离线复现）
# ---------------------------------------------------------------------------
def load_replay(path: Path):
    """key = (query, run_index) -> result；run_index 缺失时按 query 顺序取。"""
    table = {}
    seq = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        q = rec["query"]
        ri = rec.get("run_index")
        if ri is None:
            ri = seq.get(q, 0)
            seq[q] = ri + 1
        table[(q, ri)] = rec
    return table


def replay_grade(req: dict, table: dict, seq: dict) -> dict:
    q = req["query"]
    ri = req.get("run_index")
    if ri is None:
        ri = seq.get(q, 0)
        seq[q] = ri + 1
    rec = table.get((q, ri)) or table.get((q, 0))
    if rec is None:
        raise KeyError(f"replay file has no record for query={q!r} run_index={ri}")
    return {
        "query": q,
        "triggered": bool(rec.get("triggered")),
        "chosen_skill": rec.get("chosen_skill", "none"),
        "_backend": "replay",
    }


# ---------------------------------------------------------------------------
# host-cmd 后端：委托宿主命令（真正复用宿主 subagent，零 SDK 依赖）
# ---------------------------------------------------------------------------
def host_cmd_grade(req: dict, cmd: str, timeout: int) -> dict:
    """把请求 JSON 从 stdin 喂给宿主命令，读取其 stdout 的一行 JSON 结果。"""
    proc = subprocess.run(
        shlex.split(cmd),
        input=json.dumps(req, ensure_ascii=False),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"host grader cmd failed (rc={proc.returncode}): {proc.stderr.strip()}")
    out = proc.stdout.strip().splitlines()
    if not out:
        raise RuntimeError("host grader cmd produced no output")
    rec = json.loads(out[-1])
    return {
        "query": req["query"],
        "triggered": bool(rec.get("triggered")),
        "chosen_skill": rec.get("chosen_skill", "none"),
        "_backend": "host-cmd",
    }


def grade_stream(requests, backend: str, cmd: str = "", replay_file: str = "", timeout: int = 60):
    """对一批请求逐条判定，产出结果列表。供 run_eval_loop 直接 import 调用。"""
    results = []
    replay_table, replay_seq = {}, {}
    if backend == "replay":
        if not replay_file:
            raise ValueError("--replay-file is required for replay backend")
        replay_table = load_replay(Path(replay_file))
    for req in requests:
        if backend == "mock":
            res = mock_grade(req)
        elif backend == "replay":
            res = replay_grade(req, replay_table, replay_seq)
        elif backend == "host-cmd":
            if not cmd:
                raise ValueError("--cmd is required for host-cmd backend")
            res = host_cmd_grade(req, cmd, timeout)
        else:
            raise ValueError(f"unknown backend: {backend}")
        res["should_trigger"] = req.get("should_trigger")
        results.append(res)
    return results


def main():
    ap = argparse.ArgumentParser(description="Trigger-grading adapter (host-cmd / replay / mock).")
    ap.add_argument("--backend", choices=["host-cmd", "replay", "mock"], default="mock")
    ap.add_argument("--cmd", default="", help="host grader command (for --backend host-cmd)")
    ap.add_argument("--replay-file", default="", help="JSONL of historical results (for --backend replay)")
    ap.add_argument("--timeout", type=int, default=60)
    args = ap.parse_args()

    requests = []
    for line in sys.stdin.read().splitlines():
        line = line.strip()
        if line:
            requests.append(json.loads(line))

    results = grade_stream(requests, args.backend, args.cmd, args.replay_file, args.timeout)
    for r in results:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
