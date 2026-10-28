#!/usr/bin/env python3
"""Export the per-model, per-task breakdown from the Agon database.

Writes two artefacts next to the results file:
  results/agon-bench-tasks.csv  long format, one row per model x task
  results/agon-bench-tasks.md   three matrices, one per event

Means are taken over the completed runs of each model (3 per event). A task's
max score is the maximum recorded for that task, so the cells are directly
comparable across models.

Usage:
    python3 scripts/export-task-matrix.py [--db path] [--out-dir results]
"""
import argparse
import csv
import os
import sqlite3
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARENA = os.environ.get("AGON_HOME", os.path.dirname(HERE))
DB_DEFAULT = os.environ.get("AGON_DB", os.path.join(ARENA, "agon-bench.db"))

SHORT = {
    "Tool Calling": "Tool Calling", "Orchestration": "Orchestration",
    "Error Handling": "Error Handling", "Planning": "Planning", "Parsing": "Parsing",
    "Decision-Making": "Decision-Making", "Multi-Step Research Agent": "Research Agent",
    "Memory-Augmented Agent": "Memory Agent",
    "String Cleaner": "String Cleaner", "Log Parser": "Log Parser", "LRU Cache": "LRU Cache",
    "File Indexer": "File Indexer", "Task Runner CLI": "Runner CLI",
    "Constrained Diff Tool": "Diff Tool", "Regex Engine": "Regex Engine",
    "Concurrent Web Scraper": "Web Scraper",
    "Logical Deduction": "Logic Deduction", "Math Word Problem": "Math Word Prob",
    "Constraint Satisfaction": "Constraint Sat.", "Counterfactual Reasoning": "Counterfactual",
    "Analytical Explanation": "Analytical Expl.", "Multi-Hop Synthesis": "Multi-Hop",
}

EVENTS = [
    ("agent", "agent_tasks", "agent_runs"),
    ("code", "code_tasks", "code_runs"),
    ("reason", "reason_tasks", "reason_runs"),
]


def collect(db_path):
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    models = {
        r["id"]: (r["label"], r["flagged"])
        for r in db.execute("SELECT id, label, flagged FROM models")
    }

    # task_id -> (name, max_score), taken per event
    task_meta = {}
    cell = defaultdict(list)   # (model_id, event, task_id) -> [scores]
    runs = defaultdict(int)    # (model_id, event) -> completed runs

    for event, task_table, run_table in EVENTS:
        # Canonical max per task = the value most runs recorded. A couple of
        # early runs wrote Regex Engine at /8 instead of /4; MAX() would promote
        # that outlier and inflate the column, so take the mode.
        for r in db.execute(
            f"""SELECT task_id,
                       (SELECT x.task_name FROM {task_table} x
                         WHERE x.task_id = t.task_id LIMIT 1) name,
                       t.max_score mx, COUNT(*) n
                FROM {task_table} t JOIN {run_table} RUN ON t.run_id = RUN.id
                WHERE RUN.status='completed'
                GROUP BY t.task_id, t.max_score ORDER BY t.task_id, n DESC"""
        ):
            key = (event, r["task_id"])
            if key not in task_meta:            # first row per task is the mode
                task_meta[key] = (r["name"] or "", float(r["mx"]))

        for r in db.execute(
            f"""SELECT RUN.model_id mid, t.task_id tid, t.score, t.max_score rec
                FROM {task_table} t JOIN {run_table} RUN ON t.run_id = RUN.id
                WHERE RUN.status='completed'"""
        ):
            canon = task_meta[(event, r["tid"])][1]
            rec = float(r["rec"] or canon)
            # normalise a run recorded against a different maximum
            score = r["score"] * canon / rec if rec else r["score"]
            cell[(r["mid"], event, r["tid"])].append(score)

        for r in db.execute(
            f"SELECT model_id mid, COUNT(*) n FROM {run_table} WHERE status='completed' GROUP BY model_id"
        ):
            runs[(r["mid"], event)] = r["n"]

    expected = {"agent": 24, "code": 25, "reason": 17}
    for event in expected:
        got = sum(mx for (e, _), (_, mx) in task_meta.items() if e == event)
        if abs(got - expected[event]) > 1e-6:
            raise SystemExit(
                f"{event} task maxima sum to {got:g}, expected {expected[event]:g}. "
                "A run recorded a task against the wrong maximum."
            )

    # only models with a complete 3/3/3 set appear
    board = [
        mid for mid, (label, flagged) in models.items()
        if all(runs.get((mid, e), 0) >= 3 for e, _, _ in EVENTS)
    ]
    return models, task_meta, cell, runs, board


def event_means(db_path):
    """Mean of run totals per model/event, the same figures the board prints."""
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    out = {}
    for event, _, run_table in EVENTS:
        for r in db.execute(
            f"""SELECT model_id, AVG(total_score) a FROM {run_table}
                WHERE status='completed' GROUP BY model_id"""
        ):
            out[(r["model_id"], event)] = round(r["a"], 2)
    return out


def build_rows(models, task_meta, cell):
    rows = []
    for mid, (label, flagged) in models.items():
        for event, _, _ in EVENTS:
            for tid in sorted(t for (e, t) in task_meta if e == event):
                scores = cell.get((mid, event, tid), [])
                if not scores:
                    continue
                _, mx = task_meta[(event, tid)]
                rows.append({
                    "model": label,
                    "event": event,
                    "task_id": tid,
                    "task": task_meta[(event, tid)][0],
                    "max_score": mx,
                    "mean_score": round(sum(scores) / len(scores), 3),
                    "pct": round(100 * sum(scores) / len(scores) / mx, 1) if mx else 0,
                    "min_run": min(scores),
                    "max_run": max(scores),
                    "runs": len(scores),
                    "reference_only": 1 if flagged else 0,
                })
    return rows


def write_csv(rows, path):
    cols = ["model", "event", "task_id", "task", "max_score", "mean_score",
            "pct", "min_run", "max_run", "runs", "reference_only"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def write_markdown(rows, models, task_meta, order, path):
    by = defaultdict(dict)
    for r in rows:
        by[r["model"]][(r["event"], r["task_id"])] = r

    out = ["# Agon-Bench per-task breakdown", "",
           "Mean of each model's completed runs, per task. Cell format is "
           "`mean/max`. Rows are in board order. A dash means no completed run "
           "for that task.", ""]

    for event, _, _ in EVENTS:
        tids = sorted(t for (e, t) in task_meta if e == event)
        total = sum(task_meta[(event, t)][1] for t in tids)
        out.append(f"## {event.title()} ({total} points, {len(tids)} tasks)")
        out.append("")
        head = "| # | Model | " + " | ".join(
            f"{task_meta[(event, t)][0]}<br>/{task_meta[(event, t)][1]:g}" for t in tids
        ) + f" | **{event.title()}** |"
        out.append(head)
        out.append("|---|-------|" + "|".join([":---:"] * len(tids)) + "|:---:|")
        for i, label in enumerate(order, 1):
            cells, acc, accmax = [], 0.0, 0
            for t in tids:
                r = by[label].get((event, t))
                if not r:
                    cells.append("-")
                    continue
                acc += r["mean_score"]
                accmax += r["max_score"]
                cells.append(f"{r['mean_score']:g}/{r['max_score']:g}")
            star = " †" if by[label] and next(iter(by[label].values()))["reference_only"] else ""
            out.append(f"| {i} | {label}{star} | " + " | ".join(cells) +
                       f" | **{acc:.2f}/{accmax:g}** |")
        out.append("")

    out += ["† Reference only: below the 10 tok/s admission floor.", ""]
    open(path, "w").write("\n".join(out))


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agon-Bench · task matrix</title>
<style>
  :root { --bg:#08120f; --ink:#e8f4ef; --muted:#7fa79b; --line:#1d3b33; --accent:#2fe6c8; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:13px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace; }
  header { padding:26px 28px 14px; border-bottom:1px solid var(--line); }
  h1 { margin:0; font-size:22px; letter-spacing:-.2px; }
  .sub { color:var(--muted); margin-top:6px; font-size:12px; }
  .wrap { overflow:auto; max-height:calc(100vh - 96px); }
  table { border-collapse:separate; border-spacing:0; }
  th,td { padding:5px 6px; text-align:center; white-space:nowrap; }
  thead th { position:sticky; top:0; background:var(--bg); z-index:3;
             border-bottom:1px solid var(--line); font-weight:600; cursor:pointer; }
  thead th.task { width:88px; vertical-align:top; padding:8px 5px 6px;
                  font-weight:500; font-size:11px; color:#cfe6de; line-height:1.2; }
  thead th.task .lbl { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
                       overflow:hidden; height:27px; }
  thead th.task .mx { margin-top:3px; }
  thead th .mx { color:#7fa79b; font-size:10px; }
  .sticky { position:sticky; left:0; background:var(--bg); z-index:2; text-align:left; }
  thead .sticky { z-index:4; }
tbody td.sticky { box-shadow:1px 0 0 var(--line); }
  tbody tr:hover td { filter:brightness(1.25); }
  td.cell { width:56px;  font-variant-numeric:tabular-nums; color:#08120f; font-weight:600; }
  td.rank { color:var(--muted); width:34px; }
  td.model { font-weight:600; max-width:300px; font-size:12.5px; overflow:hidden; text-overflow:ellipsis; }
  td.sub { font-weight:700; border-left:1px solid var(--line); }
  td.tot { font-weight:700; border-left:1px solid var(--line); }
  .legend { display:flex; gap:16px; align-items:center; padding:12px 28px; color:var(--muted); font-size:11px; }
  .bar { width:220px; height:10px; border-radius:2px;
         background:linear-gradient(90deg,#5a1f1f,#7a4a1f,#2a3a22,#1d6b52,#2fe6c8); }
  .note { padding:0 28px 22px; color:#5f8a7d; font-size:11px; }
</style></head><body>
<header>
  <h1>Agon-Bench · per-task matrix</h1>
  <div class="sub">__SUB__</div>
</header>
<div class="wrap"><table id="t"><thead></thead><tbody></tbody></table></div>
<div class="legend"><span>0%</span><div class="bar"></div><span>100%</span>
  <span>· click a task header to sort · hover a cell for run spread</span></div>
<div class="note">Scores are the mean over each model's completed runs. Colour is a cell's score divided by that task's maximum. Subtotals and the total come
from the run totals, the same figures the leaderboard prints, so a row reconciles exactly.
A dash means no completed run for that task.</div>
<script>
const DATA = __DATA__;
const SHORT = {
    "Tool Calling": "Tool Calling", "Orchestration": "Orchestration",
    "Error Handling": "Error Handling", "Planning": "Planning", "Parsing": "Parsing",
    "Decision-Making": "Decision-Making", "Multi-Step Research Agent": "Research Agent",
    "Memory-Augmented Agent": "Memory Agent",
    "String Cleaner": "String Cleaner", "Log Parser": "Log Parser", "LRU Cache": "LRU Cache",
    "File Indexer": "File Indexer", "Task Runner CLI": "Runner CLI",
    "Constrained Diff Tool": "Diff Tool", "Regex Engine": "Regex Engine",
    "Concurrent Web Scraper": "Web Scraper",
    "Logical Deduction": "Logic Deduction", "Math Word Problem": "Math Word Prob",
    "Constraint Satisfaction": "Constraint Sat.", "Counterfactual Reasoning": "Counterfactual",
    "Analytical Explanation": "Analytical Expl.", "Multi-Hop Synthesis": "Multi-Hop",
}

EVENTS = ['agent','code','reason'];
const order = ['rank','model', ...DATA.tasks.map(t => t.event + ':' + t.id), 'sub_agent','sub_code','sub_reason','total'];
let sortKey = null, sortDir = -1;

function ink(rgb) {
  const [r, g, b] = rgb.match(/[0-9]+/g).map(Number);
  const lum = (0.2126*r + 0.7152*g + 0.0722*b) / 255;
  return lum > 0.55 ? '#08120f' : '#eafbf5';
}

function colorRgb(pct) {
  const p = Math.max(0, Math.min(100, pct)) / 100;
  const stops = [[0,[90,31,31]],[30,[122,74,31]],[55,[42,58,34]],[75,[29,107,82]],[100,[47,230,200]]];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i], [b, cb] = stops[i+1];
    if (p >= a/100 && p <= b/100) {
      const t = (p - a/100) / ((b - a)/100 || 1);
      const c = ca.map((v, j) => Math.round(v + (cb[j] - v) * t));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return 'rgb(47,230,200)';
}

function color(pct) {
  const p = Math.max(0, Math.min(100, pct)) / 100;
  const stops = [[0,[90,31,31]],[30,[122,74,31]],[55,[42,58,34]],[75,[29,107,82]],[100,[47,230,200]]];
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i], [b, cb] = stops[i+1];
    if (p >= a/100 && p <= b/100) {
      const t = (p - a/100) / ((b - a)/100 || 1);
      const c = ca.map((v, j) => Math.round(v + (cb[j] - v) * t));
      return `rgb(${c[0]},${c[1]},${c[2]})`;
    }
  }
  return '#2fe6c8';
}

function rows() {
  let r = DATA.models.map(m => {
    const cells = {};
    const subtotals = { agent: m.ev.agent || 0, code: m.ev.code || 0, reason: m.ev.reason || 0 };
    DATA.tasks.forEach(t => { cells[t.event + ':' + t.id] = m.cells[t.event + ':' + t.id] || null; });
    return { m, cells, subtotals, total: subtotals.agent + subtotals.code + subtotals.reason };
  });
  if (sortKey) {
    r.sort((a, b) => {
      const val = x => {
        if (sortKey === 'total') return x.total;
        if (sortKey === 'model') return x.m.label;
        if (sortKey.startsWith('sub_')) return x.subtotals[sortKey.slice(4)];
        const c = x.cells[sortKey];
        return c ? c.mean / c.max : -1;
      };
      const va = val(a), vb = val(b);
      if (typeof va === 'string') return sortDir * va.localeCompare(vb);
      return sortDir * (va - vb);
    });
  } else {
    r.sort((a, b) => a.m.rank - b.m.rank);
  }
  return r;
}

function render() {
  const thead = document.querySelector('#t thead');
  const tbody = document.querySelector('#t tbody');
  let h = '<tr><th class="sticky">#</th><th class="sticky" style="left:34px">Model</th>';
  DATA.tasks.forEach(t => {
    h += `<th class="task" data-key="${t.event}:${t.id}" title="${t.name} (${t.max} pts)"><span class="lbl">${t.short}</span><div class="mx">/${t.max}</div></th>`;
  });
  EVENTS.forEach(e => h += `<th class="task" data-key="sub_${e}"><span class="lbl">${e}</span><div class="mx">/__MAX__</div></th>`);
  h += '<th class="task" data-key="total"><span class="lbl">total</span><div class="mx">/66</div></th></tr>';
  thead.innerHTML = h;

  tbody.innerHTML = rows().map((r, i) => {
    let cells = '';
    DATA.tasks.forEach(t => {
      const c = r.cells[t.event + ':' + t.id];
      if (!c) { cells += '<td class="cell" style="background:#14201c;color:#46615a">–</td>'; return; }
      const pct = 100 * c.mean / c.max;
      const shown = c.mean % 1 ? c.mean.toFixed(2) : String(c.mean);
      const bg = colorRgb(pct);
      cells += `<td class="cell" style="background:${bg};color:${ink(bg)}" title="${c.mean}/${c.max} · run range ${c.min}–${c.max_run} · n=${c.n}">${shown}</td>`;
    });
    const evMax = { agent: 24, code: 25, reason: 17 };
    const subs = EVENTS.map(e => {
      const pct = 100 * r.subtotals[e] / evMax[e];
      const bg = colorRgb(pct);
      return `<td class="sub" style="background:${bg};color:${ink(bg)}" title="${r.subtotals[e].toFixed(2)}/${evMax[e]}">${r.subtotals[e].toFixed(2)}</td>`;
    }).join('');
    const tb = colorRgb(100 * r.total / 66);
    return `<tr><td class="sticky rank">${r.m.rank}</td>
      <td class="sticky model" style="left:34px" title="${r.m.label}">${r.m.label}${r.m.reference ? ' †' : ''}</td>
      ${cells}${subs}<td class="tot" style="background:${tb};color:${ink(tb)}">${r.total.toFixed(2)}</td></tr>`;
  }).join('');

  document.querySelectorAll('th[data-key]').forEach(th => {
    th.onclick = () => {
      const k = th.dataset.key;
      if (sortKey === k) sortDir *= -1; else { sortKey = k; sortDir = -1; }
      render();
    };
  });
}
render();
</script></body></html>"""


def write_html(rows, order, task_meta, ev_by_name, path):
    tasks = []
    maxes = {}
    for event, _, _ in EVENTS:
        for tid in sorted(t for (e, t) in task_meta if e == event):
            name, mx = task_meta[(event, tid)]
            tasks.append({"event": event, "id": tid, "name": name,
                          "short": SHORT.get(name, name), "max": mx})
            maxes[event] = maxes.get(event, 0) + mx

    models_by_name = defaultdict(lambda: {"cells": {}})
    for r in rows:
        m = models_by_name[r["model"]]
        m["label"] = r["model"]
        m["reference"] = bool(r["reference_only"])
        m["cells"][f"{r['event']}:{r['task_id']}"] = {
            "mean": r["mean_score"], "max": r["max_score"],
            "min": r["min_run"], "max_run": r["max_run"], "n": r["runs"],
        }

    payload = {
        "tasks": tasks,
        "models": [
            {"rank": i, "label": name,
             "reference": models_by_name[name]["reference"],
             "ev": ev_by_name.get(name, {}),
             "cells": models_by_name[name]["cells"]}
            for i, name in enumerate(order, 1)
        ],
    }
    sub = f"{len(order)} models · {len(tasks)} tasks · mean of completed runs · board order unless a column is clicked"
    html = (HTML.replace("__DATA__", __import__("json").dumps(payload, separators=(",", ":")))
                .replace("__SUB__", sub))
    for event, _, _ in EVENTS:
        html = html.replace("__MAX__", f"{maxes[event]:g}", 1)
    open(path, "w").write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--out-dir", default=os.path.join(ARENA, "results"))
    args = ap.parse_args()

    models, task_meta, cell, runs, board = collect(args.db)
    rows = build_rows(models, task_meta, cell)
    ev_means = event_means(args.db)

    keep = set(board)
    name_of = {models[m][0] for m in keep}
    rows = [r for r in rows if r["model"] in name_of]

    # board order: by total of task means, descending
    totals = defaultdict(float)
    for r in rows:
        totals[r["model"]] += r["mean_score"]
    order = sorted({r["model"] for r in rows}, key=lambda m: -totals[m])

    os.makedirs(args.out_dir, exist_ok=True)
    ev_by_name = {}
    for mid in board:
        ev_by_name[models[mid][0]] = {e: ev_means.get((mid, e), 0.0) for e, _, _ in EVENTS}

    write_csv(rows, os.path.join(args.out_dir, "agon-bench-tasks.csv"))
    write_markdown(rows, models, task_meta, order,
                   os.path.join(args.out_dir, "agon-bench-tasks.md"))
    write_html(rows, order, task_meta, ev_by_name,
               os.path.join(ARENA, "agon-bench-tasks.html"))

    print(f"{len(order)} models x {len(task_meta)} tasks -> {len(rows)} cells")
    print(os.path.join(args.out_dir, "agon-bench-tasks.csv"))
    print(os.path.join(args.out_dir, "agon-bench-tasks.md"))
    print(os.path.join(ARENA, "agon-bench-tasks.html"))


if __name__ == "__main__":
    main()
