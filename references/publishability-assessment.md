# Publishability Assessment — June 2026

## Current State

**Code event (19 hidden tests, 6 tasks):** Fully instrumented. Harness is clean after 3 rounds of fixes (seed variations removed, thinking-trace stripping fixed, Task 2/5/6 test bugs fixed).

**Agent and Reason events:** No hidden tests. Responses exist but no automated scoring. The `hidden_tests_passed` and `hidden_tests_total` fields are always 0/0.

## What We Can Publish Right Now

A **Code-only benchmark** with clear caveats:

| Model | Size | Mean Score | Avg Time (6 tasks) | Consistency |
|-------|------|-----------|-------------------|-------------|
| **Gemma4-12B** | 6.3GB | **13.3/19 (70%)** | ~220s | 13, 13, 14 |
| **Ornith-1.0-9B** | 5.3GB | **12.0/19 (63%)** | ~207s | 12, 12, 12 |
| **LFM2.5-8B** | 5.0GB | **~9.5/19 (50%)** | ~260s | 6/16, 11, 12, 9 |
| **Jackrong** | 5.3GB | **~2.7/19 (14%)** | ~750s | 4/6, 4/6, 0/9 |

## What's Missing Before a Full "King in the Field" Article

1. **Agent and Reason hidden tests** — Without them, you're publishing a 1/3 benchmark. The Code event is the most objective, but the full picture needs all three.
2. **Jackrong is an unfair comparison** — The thinking loop is a llama.cpp config issue, not a model quality issue. In Pi (official API), Jackrong works fine. Publishing a 14% score for it would be misleading unless caveated heavily.
3. **Only 3 runs per model** — Good for a preview, but for a "king in the field" claim you'd want 5+ runs for statistical confidence.

## The Ornith Story

**What's good:**
- Ornith is **1GB smaller** than Gemma4 (5.3 vs 6.3) and slightly faster
- It's **within 1 point** of Gemma4 on Code (12.0 vs 13.3) — that's ~6% behind a model 2.7B parameters larger
- It's **consistent** — all 3 runs scored exactly 12/19 (no variance)
- It handily beats LFM2.5-8B and Jackrong

**What's not good:**
- It **can't parse logs at all** (Task 2: 0/4 every run — returns all zeros). Gemma4 gets 2/4 on the same task.
- It's **not a "king"** — it's a solid mid-range model that punches slightly above its weight class, but Gemma4-12B clearly outperforms it
- The "king" framing would need to be about **efficiency per parameter** or **value for size**, not raw performance

## Recommended Approach

**For a publishable article right now:** Publish a **Code-only benchmark** with clear caveats about Agent/Reason being in development. Frame it as "Agon-Bench Code Results: First Look" rather than a definitive ranking.

**For a "king in the field" article about Ornith:** You need:
1. Agent and Reason tests implemented (so you have all 3 events)
2. A more competitive comparison — maybe add Qwen2.5-7B or Llama-3.1-8B as baselines
3. A clear thesis: "Ornith-1.0-9B: 70% of Gemma4-12B's code ability at 84% of the size" is honest and compelling

**Next step:** Implement the Agent and Reason hidden tests (they're just rubric-based grading, not code execution), then run all 3 events for all models. That gives you a complete 3-event score to publish with confidence.
