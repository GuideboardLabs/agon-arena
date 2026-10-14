#!/usr/bin/env python3
"""Recompute Agon run totals from the per-task rows.

Why this exists: the leaderboard aggregates `total_score` / `max_score` off the RUN
row (dashboard-server.py selects them WHERE status='completed'), and the runner
derives those totals from only the tasks present in THAT invocation. That is fine for
an uninterrupted run, but it silently breaks for a partial re-run: delete one bad task
row, let the runner re-run just that task, and the run row is rewritten to the score of
the single task it just ran.

A repaired run then reports something like 2/3 where its eight tasks actually sum to
22/24, and the composite reads ~67% instead of ~92% for that event. The task rows stay
correct, so the repair is to re-derive the totals from them.

Usage:  agon-fix-run-totals.py [model_key ...]     (default: every model)
        agon-fix-run-totals.py --check             (report only, change nothing)
"""
import os
import sqlite3
import sys

DB = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
EVENTS = (("agent", "agent_runs", "agent_tasks"),
          ("code", "code_runs", "code_tasks"),
          ("reason", "reason_runs", "reason_tasks"))

# Tasks per event, verified against completed runs in the DB: agent 8 (max 24),
# code 8 (max 25), reason 6 (max 17). That is 22 tasks and a max of 66 per run,
# which is the number dashboard-server.py assumes. Reason is NOT 8 - assuming it is
# makes every healthy reason run look 2 tasks short.
EXPECTED_TASKS = {"agent": 8, "code": 8, "reason": 6}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    check = "--check" in sys.argv

    c = sqlite3.connect(f"file:{DB}?mode={'ro' if check else 'rw'}", uri=True)
    if args:
        rows = c.execute(
            f"select id,key,name from models where key in ({','.join('?' * len(args))})",
            args).fetchall()
    else:
        rows = c.execute("select id,key,name from models order by id").fetchall()

    changed = 0
    for mid, key, name in rows:
        for ev, rtab, ttab in EVENTS:
            for rid, rn, tscore, tmax in c.execute(
                    f"select id,run_number,total_score,max_score from {rtab} "
                    f"where model_id=? order by run_number", (mid,)):
                q = c.execute(
                    f"select count(*),sum(score),sum(max_score),sum(elapsed_s) "
                    f"from {ttab} where run_id=?", (rid,)).fetchone()
                n, sscore, smax, sel = q
                sscore = sscore or 0.0
                smax = smax or 0.0
                sel = sel or 0.0
                if n == 0:
                    continue
                # Only a run holding every task has a meaningful total.
                if n < EXPECTED_TASKS[ev]:
                    print(f"  {key} {ev} run{rn}: {n}/8 tasks yet, row={tscore}/{tmax} "
                          f"(incomplete, left alone)")
                    continue
                old = (tscore, tmax)
                if old == (sscore, smax):
                    continue
                changed += 1
                print(f"  {key} {ev} run{rn}: row {old[0]}/{old[1]}  ->  "
                      f"tasks {sscore}/{smax}  (8 tasks)   <== FIXED")
                if not check:
                    c.execute(f"""update {rtab} set total_score=?, max_score=?,
                                  total_elapsed_s=?, status='completed'
                                  where id=?""", (sscore, smax, sel, rid))
    if not check:
        c.commit()
    print(f"\n  {'would change' if check else 'changed'}: {changed} run(s)")
    c.close()


if __name__ == "__main__":
    main()
