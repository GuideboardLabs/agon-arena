#!/usr/bin/env python3
"""Apply the assertion-defect correction to recorded Agon scores.

Two checks in the code event could not fail, so every completed run banked
their points. Rather than re-running 23 models (~6h GPU), this recomputes the
affected tasks from evidence already on disk:

  Task 4 (File Indexer) -- the wikilinks check was `CONTAINS:BROKEN` against a
    script that prints 'BROKEN' or 'NO_BROKEN'. BOTH contain BROKEN, so it
    passed unconditionally. Ground truth is recoverable because the harness
    recorded the real `actual` value ('BROKEN'/'NO_BROKEN') in `details`; for
    rows predating `details`, the model's stored response is re-run through the
    harness's own check.

  Task 5 (Task Runner CLI) -- the 'creates project structure' check was a bare
    `print('OK')` with expected OK. Score is fully determined: 2.0 meant the
    genuine import check also passed, 1.0 meant it did not, 0.0 meant the script
    errored. So corrected score = 1 if recorded==2.0 else 0. Exact for all rows.

Originals are never destroyed: every change is written to `score_corrections`
before the score is updated, and the reason is appended to `code_runs.notes`.

Usage:
    python3 apply-assertion-correction.py            # dry run, prints the diff
    python3 apply-assertion-correction.py --apply    # write changes
"""

import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "agon-bench.db")
CODE_EVENT = os.path.join(HERE, "code-event.py")

CORRECTION_TAG = "2026-09-20 assertion-defect recompute"


def load_check(label):
    src = open(CODE_EVENT, errors="replace").read()
    i = src.find(f'"label": "{label}"')
    if i < 0:
        raise SystemExit(f"check not found in code-event.py: {label}")
    seg = src[i:i + 6000]
    out = {}
    for k in ("setup", "check", "expected"):
        m = re.search(rf'"{k}":\s*("(?:[^"\\]|\\.)*")', seg)
        if m is None:
            raise SystemExit(f"{label}: field {k!r} not found")
        out[k] = ast.literal_eval(m.group(1))
    return out


def extract_code(text):
    blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return blocks[-1] if blocks else text


def run_indexer_check(cfg, code):
    """Return the harness's own stdout for this submission."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        model_path = f.name
    open(model_path, "w").write(code)
    script = (cfg["setup"] + "\n\n" + cfg["check"]).replace("MODEL_CODE_PATH", repr(model_path))
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        test_path = f.name
        f.write(script)
    try:
        r = subprocess.run([sys.executable, test_path], capture_output=True,
                           text=True, timeout=30)
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def ensure_audit_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS score_corrections (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      INTEGER NOT NULL,
            task_id     INTEGER NOT NULL,
            old_score   REAL,
            new_score   REAL,
            old_details TEXT,
            reason      TEXT,
            evidence    TEXT,
            applied_at  TEXT DEFAULT (datetime('now'))
        )""")


def main():
    apply = "--apply" in sys.argv
    con = sqlite3.connect(DB)
    cur = con.cursor()
    ensure_audit_table(cur)
    if apply:
        con.commit()

    cfg_idx = load_check("Indexer finds wikilinks")

    cur.execute("select id, model_id, run_number from code_runs")
    runs = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    cur.execute("select id, key from models")
    mkey = dict(cur.fetchall())

    changes = []

    # ---------- Task 4: File Indexer ----------
    cur.execute("select run_id, score, details from code_tasks where task_id=4 order by run_id")
    t4_rows = cur.fetchall()
    t4_recorded = sum(r[1] for r in t4_rows)
    t4_new = 0.0
    t4_evidence = {"details": 0, "response_file": 0, "unresolved": 0}
    t4_unresolved = []

    for run_id, score, det in t4_rows:
        check_struct = 1.0 if score == 2.0 else 0.0   # 'skips hidden dirs' was sound
        wiki_broken = None
        ev = None

        if det:
            d = json.loads(det)
            w = [x for x in d if len(x) >= 4 and "wikilinks" in str(x[0])]
            if w:
                wiki_broken = (str(w[0][2]) == "BROKEN")
                ev = f"details actual={w[0][2]!r}"
                t4_evidence["details"] += 1

        if wiki_broken is None:
            mid, rn = runs.get(run_id, (None, None))
            key = mkey.get(mid)
            path = f"{ROOT}/results/{key}/code/run{rn}/task4/response.txt" if key else None
            if path and os.path.exists(path):
                out = run_indexer_check(cfg_idx, extract_code(open(path, errors="replace").read()))
                wiki_broken = (out == "BROKEN")
                ev = f"re-ran stored response -> {out!r}"
                t4_evidence["response_file"] += 1
            else:
                t4_evidence["unresolved"] += 1
                t4_unresolved.append(run_id)
                wiki_broken = False   # conservative: assume the point was not earned
                ev = "UNRESOLVED - no details and no stored response; assumed not earned"

        new = (1.0 if wiki_broken else 0.0) + check_struct
        t4_new += new
        if abs(new - score) > 1e-9:
            changes.append((run_id, 4, score, new,
                            "Indexer wikilinks check was CONTAINS:BROKEN against "
                            "BROKEN/NO_BROKEN output; both matched", ev))
        _ = score

    # ---------- Task 5: Task Runner CLI ----------
    cur.execute("select run_id, score from code_tasks where task_id=5 order by run_id")
    t5_rows = cur.fetchall()
    t5_recorded = sum(r[1] for r in t5_rows)
    t5_new = 0.0
    for run_id, score in t5_rows:
        new = 1.0 if score == 2.0 else 0.0
        t5_new += new
        if abs(new - score) > 1e-9:
            changes.append((run_id, 5, score, new,
                            "TaskRunner structure check was a bare print('OK') with "
                            "expected OK; only the import check could fail",
                            "recorded score determines outcome (2.0=import passed)"))

    # ---------- report ----------
    cur.execute("select sum(score), sum(max_score) from code_tasks")
    before, maxs = cur.fetchone()
    free = (t4_recorded - t4_new) + (t5_recorded - t5_new)
    after = before - free

    print("=" * 74)
    print("ASSERTION-DEFECT CORRECTION" + ("" if apply else "   [DRY RUN]"))
    print("=" * 74)
    print(f"\nTask 4 File Indexer : {t4_recorded:.0f}/140 ({t4_recorded/140*100:.1f}%)"
          f" -> {t4_new:.0f}/140 ({t4_new/140*100:.1f}%)"
          f"   evidence={t4_evidence}")
    if t4_unresolved:
        print(f"   unresolved rows (conservative lower bound): {t4_unresolved}")
    print(f"Task 5 Task Runner  : {t5_recorded:.0f}/140 ({t5_recorded/140*100:.1f}%)"
          f" -> {t5_new:.0f}/140 ({t5_new/140*100:.1f}%)"
          f"   evidence=exact from recorded score")
    print(f"\nCODE EVENT          : {before:.0f}/{maxs:.0f} ({before/maxs*100:.1f}%)"
          f" -> {after:.0f}/{maxs:.0f} ({after/maxs*100:.1f}%)")
    print(f"FREE POINTS         : {free:.0f}  ({free/maxs*100:.1f} pp)")
    print(f"\n{len(changes)} task rows to change")

    if not apply:
        print("\nDRY RUN - nothing written. Re-run with --apply")
        con.close()
        return 0

    for run_id, task_id, old, new, reason, ev in changes:
        cur.execute("""insert into score_corrections
                       (run_id, task_id, old_score, new_score, reason, evidence)
                       values (?,?,?,?,?,?)""", (run_id, task_id, old, new, reason, ev))
        cur.execute("update code_tasks set score=? where run_id=? and task_id=?",
                    (new, run_id, task_id))

    # recalculate affected run totals
    affected = sorted({c[0] for c in changes})
    for rid in affected:
        cur.execute("""select coalesce(sum(score),0), coalesce(sum(max_score),0)
                       from code_tasks where run_id=?""", (rid,))
        s, m = cur.fetchone()
        cur.execute("""update code_runs set total_score=?, max_score=?,
                       notes = coalesce(notes,'') || ? where id=?""",
                    (s, m, f" | {CORRECTION_TAG}", rid))

    con.commit()
    print(f"\nAPPLIED: {len(changes)} rows corrected, {len(affected)} run totals recalculated")
    print("originals preserved in score_corrections")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
