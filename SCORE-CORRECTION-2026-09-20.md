# Agon-Bench Score Correction — 2026-09-20

## Summary

Two checks in the **Code** event could not fail. Every run that completed them
banked their points, regardless of what the model actually produced. This note
records the correction.

| Task (Code event) | Recorded | Corrected | Free points |
|---|---|---|---|
| File Indexer | 111/140 (79.3%) | 78/140 (55.7%) | 33 |
| Task Runner CLI | 77/140 (55.0%) | 11/140 (7.9%) | 66 |
| **Code event total** | **971/1742 (55.7%)** | **872/1742 (50.1%)** | **99 (5.7 pp)** |

**This data is not a re-run.** Every corrected score was recomputed from
evidence already on disk. The models were not re-benchmarked, and no model's
output changed — only the scoring of it. Agent and Reason events are unaffected:
they were re-graded against the corrected matcher and produced zero corrections.

## Defect 1 — File Indexer: an assertion both outputs satisfy

The check script for task 4 printed exactly one of two strings:

```python
print('BROKEN' if 'note3' in output else 'NO_BROKEN')
```

and the assertion was `CONTAINS:BROKEN`. **Both branches contain `BROKEN`.** The
check passed whether or not the model's indexer found the broken link. It could
not fail, and it ran green 69 times without ever reporting a miss.

Ground truth was recoverable from two sources, because the harness had recorded
the real value in `details`:

- **49 rows** — `details` records `actual`, which is the genuine `BROKEN` /
  `NO_BROKEN` output. Exact.
- **19 rows** — recorded before the harness stored `details`. The model's stored
  response was re-run through the harness's own check script. Exact.
- **2 rows** (run_id 23, 79) — no `details` and no stored response. Counted as
  not-earned, so the published figure is a **conservative lower bound**.

## Defect 2 — Task Runner CLI: the answer was computed and discarded

The setup block for task 5 computed exactly the right thing:

```python
files = ['taskrunner/__init__.py', 'taskrunner/runner.py',
         'taskrunner/cli.py', 'taskrunner/models.py']
missing = [f for f in files if not (tmpdir / f).exists()]
```

and then the check was a bare `print('OK')` with `expected: OK`. `missing` was
never read. Any run whose test script executed at all collected the point.

This one is **exact for every row**, no inference needed: the task had two
checks, and only the second (a real `from taskrunner.models import Task, Result`)
could fail. So the recorded score fully determines the outcome — 2.0 means the
import check passed, 1.0 means it did not, 0.0 means the script errored.

Corrected score = `1.0 if recorded == 2.0 else 0.0`.

Note that two of the three copies of this check (`grade-all.py`,
`rerun-tests.py`) already carried the corrected form
`print('OK' if not missing else f'MISSING: {missing}')`. `code-event.py` — the
script the runner actually invokes — did not. The fix existed in the codebase
and was never live.

## Why the numbers are trustworthy

- The correction script is `scripts/apply-assertion-correction.py`; run it with
  no arguments for a dry run.
- **Every original value is preserved.** All 99 changes are recorded in the
  `score_corrections` table (old score, new score, original `details`, reason,
  and the specific evidence used per row) before the score was updated. A
  pre-correction copy of the database is at `agon-bench.db.bak-20260920`.
- 67 run totals were recalculated from their per-task sums and tagged
  `2026-09-20 assertion-defect recompute` in `code_runs.notes`.

## Impact on the leaderboard

This shifts Code scores down by roughly 5.7pp across the board. Because the free
points were nearly uniform, **relative code ranking moves less than the absolute
numbers do** — the fix mostly lowers the ceiling rather than reordering models.

Measured against per-task sums (the documented source of truth), **all 23
affected models move down, by 1.0 to 2.0 Code points**:

| Model | Code before | Code after | Δ |
|---|---|---|---|
| Grug-12B | 7.0 | 5.0 | −2.0 |
| LFM2.5-8B-A1B | 15.0 | 13.0 | −2.0 |
| SuperQwen-35B | 14.8 | 12.8 | −2.0 |
| Qwythos-9B-v1 | 11.0 | 9.0 | −2.0 |
| Qwopus3.5-9B-Coder-MTP | 11.0 | 9.0 | −2.0 |
| MiniCPM5-2B | 10.3 | 8.7 | −1.7 |
| Holo-3.1-9B-Coder | 11.0 | 9.3 | −1.7 |
| Qwopus3.5-9B-Coder | 13.7 | 12.0 | −1.7 |
| Qwen3.8-27B-Q3-DOWN-XS | 15.7 | 14.0 | −1.7 |
| Nanbeige4.2-3B | 16.7 | 15.3 | −1.3 |
| Heem-9B (Uncensored) | 16.0 | 14.7 | −1.3 |
| Ornith-1.5-9B | 13.0 | 11.7 | −1.3 |
| OmniCoder-9B | 9.0 | 7.7 | −1.3 |
| Qwen3.5-9B | 14.3 | 13.3 | −1.0 |
| Ornith-1.0-9B | 17.0 | 16.0 | −1.0 |
| Gemma4-12B | 13.3 | 12.3 | −1.0 |
| Gemma4-26B-A4B | 15.0 | 14.0 | −1.0 |
| Ornith-1.0-35B-MTP | 12.5 | 11.5 | −1.0 |
| Qwen3.8-9B | 16.0 | 15.0 | −1.0 |
| Qwen3.6-35B-Q4-ncmoe40 | 22.7 | 21.7 | −1.0 |
| Qwen3.8-35B-A3B-Distill | 20.7 | 19.7 | −1.0 |
| Ternary-Bonsai-2-27B-PTQ1_0 | 22.0 | 21.0 | −1.0 |
| Bonsai-27B-Q1_0 | 16.3 | 15.3 | −1.0 |

The spread (−1.0 to −2.0) is the real signal: models that had genuinely
functional indexers and TaskRunner projects lose only the free structural point,
while models that produced broken output lose both. The corrected column
therefore separates them, which the original could not.

### A separate corruption found and repaired in passing

Recomputing run totals surfaced one **pre-existing** inconsistency unrelated to
the assertion defects: `code_runs` id 123 (Ornith-1.5-9B, run 1) had a stored
`total_score` of **1.0** while its per-task rows summed to **13.0**. The
published README leaderboard was generated while that stale total was live, so
its Ornith-1.5-9B Code figure (9.0) was depressed by 4 points for a reason that
had nothing to do with this model's actual performance.

After the recompute, **every run total in all three events reconciles with its
per-task sum**, and no task row scores above its `max_score`. The table above
isolates the assertion correction from that repair by comparing per-task sums on
both sides.

Two caveats for anyone reading the table:

1. **Do not mix corrected and uncorrected Code numbers.** The Code column here
   is corrected; a table published before 2026-09-20 is not.
2. **The corrected Code column is now harder than the original by construction.**
   Task Runner CLI in particular goes from a near-free 55% to a genuine 7.9%,
   which is the real discrimination signal that was previously hidden.

## What changed in the harness

- `scripts/assertions.py` — one shared matcher for all three runners, with
  word-boundary rules that differ for numeric (`150` ≠ `1500`), alphabetic
  (`not` ≠ `cannot`), and punctuation-terminated tokens (`9:` matches `9:00`).
- `scripts/test_assertions.py` — 29 regression checks covering both defects.
- Both assertions promoted from `CONTAINS:` to `EXACT:` in all 5 sites.
- `scripts/audit-checks.py` — scans every check for the provable
  "cannot fail" shape so the next one is caught by machine, not by accident.
  It reports REVIEW findings separately, because a check can also fail via a
  non-zero exit code, which no static analysis of stdout can rule out.

## Honest limits

The two unresolved File Indexer rows (23, 79) could not be resolved from disk.
They are counted as not-earned, which makes the published File Indexer figure
the lowest defensible one rather than the highest. If their responses resurface,
the number can only move up, by at most 2 points out of 140.

`audit-checks.py` cannot prove the scripts are sound. It proves only that no
check's stdout is provably constant-and-accepted. A check that always raises
would pass the audit and still be broken.
