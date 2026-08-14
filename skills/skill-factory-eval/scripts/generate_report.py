#!/usr/bin/env python3
"""
generate_report.py — 把 run_eval_loop.py 的 eval_results.json 渲染成单文件 HTML 报告
（补齐"无 eval 可视化"短板，对标官方 eval-viewer，但零第三方依赖、单文件、可离线打开）。

特性：
- 纯标准库 + 内联 CSS/JS，产出**单个 .html**，双击即可在任意浏览器打开，无需服务器/网络。
- 顶部总览：verdict、按 test 选出的最优轮、precision/recall/accuracy 仪表。
- 迭代曲线：每轮 train/test 的 precision/recall（纯 CSS 柱状，无图表库依赖）。
- 明细表：每个 query 的 should_trigger / trigger_rate / pass，红绿高亮，失败项置顶。
- 最优 description 全文展示，便于人工复核 / 回写 SKILL.md。

用法：
    python3 generate_report.py eval_results.json -o eval_report.html
"""
import argparse
import html
import json
import sys
from pathlib import Path


def esc(s):
    return html.escape(str(s), quote=True)


def pct(x):
    try:
        return f"{float(x) * 100:.0f}%"
    except Exception:
        return "-"


def bar(value, color):
    w = max(0.0, min(1.0, float(value))) * 100
    return f'<div class="bar"><div class="fill" style="width:{w:.1f}%;background:{color}"></div></div>'


def results_table(results):
    rows = sorted(results, key=lambda r: (r.get("pass", False), not r.get("should_trigger")))
    out = ['<table class="rt"><thead><tr>'
           '<th>query</th><th>should</th><th>rate</th><th>runs</th><th>result</th>'
           '</tr></thead><tbody>']
    for r in rows:
        ok = r.get("pass")
        cls = "ok" if ok else "bad"
        should = "触发" if r.get("should_trigger") else "不触发"
        rate = r.get("trigger_rate", 0)
        out.append(
            f'<tr class="{cls}"><td class="q">{esc(r.get("query",""))}</td>'
            f'<td>{should}</td>'
            f'<td>{pct(rate)}<br>{bar(rate, "#3b82f6")}</td>'
            f'<td>{r.get("triggers",0)}/{r.get("runs",0)}</td>'
            f'<td class="v">{"✓ PASS" if ok else "✗ FAIL"}</td></tr>'
        )
    out.append("</tbody></table>")
    return "".join(out)


def iterations_chart(iterations):
    cells = []
    for it in iterations:
        tr, te = it["train"], it["test"]
        cells.append(f"""
        <div class="iter">
          <div class="itag">iter {it['iteration']}</div>
          <div class="mrow"><span>train P</span>{bar(tr['precision'], '#22c55e')}<b>{pct(tr['precision'])}</b></div>
          <div class="mrow"><span>train R</span>{bar(tr['recall'], '#16a34a')}<b>{pct(tr['recall'])}</b></div>
          <div class="mrow"><span>test&nbsp; P</span>{bar(te['precision'], '#f59e0b')}<b>{pct(te['precision'])}</b></div>
          <div class="mrow"><span>test&nbsp; R</span>{bar(te['recall'], '#d97706')}<b>{pct(te['recall'])}</b></div>
        </div>""")
    return '<div class="iters">' + "".join(cells) + "</div>"


HTML_TMPL = """<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Skill Eval Report — {skill}</title>
<style>
:root{{--bg:#0b1020;--card:#141b2e;--fg:#e6edf7;--mut:#8aa0c0;--ok:#22c55e;--bad:#ef4444;--line:#243049}}
*{{box-sizing:border-box}}
body{{margin:0;font:14px/1.5 -apple-system,Segoe UI,Roboto,'PingFang SC','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--fg)}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 20px 60px}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:var(--mut);margin-bottom:20px}}
.verdict{{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;letter-spacing:.5px}}
.PASS{{background:rgba(34,197,94,.15);color:var(--ok);border:1px solid var(--ok)}}
.FAIL{{background:rgba(239,68,68,.15);color:var(--bad);border:1px solid var(--bad)}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:18px 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}
.card .k{{color:var(--mut);font-size:12px}} .card .val{{font-size:26px;font-weight:700;margin-top:4px}}
.bar{{height:6px;border-radius:6px;background:#22304a;overflow:hidden;margin-top:4px}}
.bar .fill{{height:100%}}
h2{{font-size:15px;margin:26px 0 10px;color:#cdd9ee}}
.iters{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}}
.iter{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}}
.iter.best{{border-color:var(--ok);box-shadow:0 0 0 1px var(--ok) inset}}
.itag{{font-weight:700;margin-bottom:8px}}
.mrow{{display:grid;grid-template-columns:56px 1fr 42px;align-items:center;gap:8px;margin:3px 0;font-size:12px;color:var(--mut)}}
.mrow b{{color:var(--fg);text-align:right}}
table.rt{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}}
.rt th,.rt td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}}
.rt th{{background:#101728;color:var(--mut);font-weight:600}}
.rt td.q{{max-width:360px;word-break:break-word}}
.rt tr.ok td.v{{color:var(--ok)}} .rt tr.bad td.v{{color:var(--bad);font-weight:700}}
.rt tr.bad{{background:rgba(239,68,68,.06)}}
pre.desc{{background:#0d1424;border:1px solid var(--line);border-radius:10px;padding:14px;white-space:pre-wrap;word-break:break-word;color:#d6e2f5}}
.foot{{color:var(--mut);font-size:12px;margin-top:30px;text-align:center}}
.cfg{{color:var(--mut);font-size:12px}}
</style></head>
<body><div class="wrap">
  <h1>Skill Eval Report — {skill}</h1>
  <div class="sub">
    <span class="verdict {verdict}">{verdict}</span>
    &nbsp; 按 test 集选出的最优：iter {best_iter} ·
    <span class="cfg">grader={grader} · rewriter={rewriter} · target≥{target} · runs/query={rpq} · holdout={holdout}</span>
  </div>

  <div class="grid">
    <div class="card"><div class="k">Test Precision（越高越不误触发）</div><div class="val">{best_p}</div>{bar_p}</div>
    <div class="card"><div class="k">Test Recall（越高越不漏触发）</div><div class="val">{best_r}</div>{bar_r}</div>
    <div class="card"><div class="k">Test Accuracy</div><div class="val">{best_a}</div>{bar_a}</div>
  </div>

  <h2>迭代过程（train 优化 / test 选最优，blinded history）</h2>
  {iters}

  <h2>最优 description（可回写 SKILL.md）</h2>
  <pre class="desc">{best_desc}</pre>

  <h2>最优轮 · 测试集明细（失败项置顶）</h2>
  {test_table}

  <h2>最优轮 · 训练集明细</h2>
  {train_table}

  <div class="foot">Generated by skill-factory-eval · generate_report.py · zero-dependency single-file report</div>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="eval_results.json from run_eval_loop.py")
    ap.add_argument("-o", "--out", default="eval_report.html")
    args = ap.parse_args()

    data = json.loads(Path(args.results).read_text(encoding="utf-8"))
    best = data.get("best", {})
    iters = data.get("iterations", [])
    cfg = data.get("config", {})
    best_iter_idx = best.get("iter", 0)
    best_rec = next((it for it in iters if it["iteration"] == best_iter_idx), iters[-1] if iters else {})

    # 标记最优迭代卡片
    iters_html = iterations_chart(iters)
    iters_html = iters_html.replace(
        f'<div class="itag">iter {best_iter_idx}</div>',
        f'<div class="itag">iter {best_iter_idx} ★best</div>')
    # 给最优卡片加 best 类
    iters_html = iters_html.replace(
        f'<div class="iter">\n          <div class="itag">iter {best_iter_idx} ★best</div>',
        f'<div class="iter best">\n          <div class="itag">iter {best_iter_idx} ★best</div>')

    p = best.get("test_precision", 0)
    r = best.get("test_recall", 0)
    a = best.get("test_accuracy", 0)

    doc = HTML_TMPL.format(
        skill=esc(data.get("skill", "")),
        verdict=esc(data.get("verdict", "FAIL")),
        best_iter=best_iter_idx,
        grader=esc(cfg.get("grader_backend", "-")),
        rewriter=esc(cfg.get("rewriter_backend", "-")),
        target=esc(cfg.get("target", 0.8)),
        rpq=esc(cfg.get("runs_per_query", 3)),
        holdout=esc(cfg.get("holdout", 0.4)),
        best_p=pct(p), best_r=pct(r), best_a=pct(a),
        bar_p=bar(p, "#f59e0b"), bar_r=bar(r, "#d97706"), bar_a=bar(a, "#3b82f6"),
        iters=iters_html,
        best_desc=esc(data.get("best_description", "")),
        test_table=results_table(best_rec.get("test_results", [])),
        train_table=results_table(best_rec.get("train_results", [])),
    )
    Path(args.out).write_text(doc, encoding="utf-8")
    print(f"OK: wrote {args.out} ({len(doc)} bytes)")


if __name__ == "__main__":
    main()
