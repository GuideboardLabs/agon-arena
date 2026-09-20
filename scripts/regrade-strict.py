#!/usr/bin/env python3
"""Re-grade a stored Agon model output against current task assertions.

Reports BOTH the lenient (historical) and strict (corrected) result so a
correction is visible rather than silently applied.

Usage:
    python3 regrade-strict.py <model_dir_under_sprint-results> [--task N]
"""

import argparse
import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assertions import match_assertion  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

TASK_ASSERTIONS = {
    "task1": [("Identifies fish owner", "CONTAINS:dave")],
    "task2": [("Correct meeting time", "CONTAINS:2.5"),
              ("Correct distance from A", "CONTAINS:150"),
              ("Shows equations", "CONTAINS:60")],
    "task3": [("Sprint Planning in Room B", "CONTAINS:Room B"),
              ("Standup before 10:00", "CONTAINS:9:"),
              ("Design Review after Standup", "CONTAINS:Design")],
    "task4": [("Revenue would be lower", "CONTAINS:9%"),
              ("Tickets would not increase", "CONTAINS:not"),
              ("Demographic similarity causes irrelevant recs", "CONTAINS:irrelevant")],
    "task5": [("Identifies mobile issue", "CONTAINS:mobile"),
              ("Mention conversion rate drop", "CONTAINS:55%"),
              ("Recommends action", "CONTAINS:recommend")],
    "task6": [("Identifies threat code expired", "CONTAINS:expired"),
              ("Mentions Emergency Override", "CONTAINS:Emergency"),
              ("drone", "CONTAINS:drone")],
}


def grade_file(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if text.startswith("[ERROR]"):
        return None
    task = Path(path).parent.name
    asserts = TASK_ASSERTIONS.get(task)
    if not asserts:
        return None
    len_pass = sum(1 for _, exp in asserts if match_assertion(text, exp, strict=False)[0])
    str_pass = sum(1 for _, exp in asserts if match_assertion(text, exp, strict=True)[0])
    detail = []
    for label, exp in asserts:
        l_ok = match_assertion(text, exp, strict=False)[0]
        s_ok, why = match_assertion(text, exp, strict=True)
        if l_ok != s_ok:
            detail.append((label, exp, l_ok, s_ok, why))
    return task, len_pass, str_pass, len(asserts), detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model_dir")
    ap.add_argument("--root", default=str(REPO / "sprint-results"))
    args = ap.parse_args()

    pattern = os.path.join(args.root, args.model_dir, "**", "task*", "response.txt")
    files = sorted(glob.glob(pattern, recursive=True))
    if not files:
        print(f"no responses under {pattern}")
        return 1

    print(f"RE-GRADE: {args.model_dir}  ({len(files)} response files)")
    print("=" * 78)
    tot_l = tot_s = tot_n = 0
    corrections = []
    for f in files:
        res = grade_file(f)
        if not res:
            continue
        task, lp, sp, n, detail = res
        tot_l += lp; tot_s += sp; tot_n += n
        flag = "  <-- CORRECTED" if lp > sp else ""
        print(f"  {task:8} lenient {lp}/{n}   strict {sp}/{n}{flag}")
        for label, exp, l_ok, s_ok, why in detail:
            corrections.append((task, label, exp, why))
    print("=" * 78)
    print(f"  TOTAL  lenient {tot_l}/{tot_n}  ({tot_l/max(tot_n,1)*100:.0f}%)"
          f"   strict {tot_s}/{tot_n}  ({tot_s/max(tot_n,1)*100:.0f}%)")
    print(f"  correction: -{tot_l - tot_s} checks ({(tot_l-tot_s)/max(tot_n,1)*100:.0f}% of the task set)")
    if corrections:
        print("\n  false credits the old matcher granted:")
        for task, label, exp, why in corrections:
            print(f"    {task} / {label}: expected {exp} -> {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
