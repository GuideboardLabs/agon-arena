# Grading Protocol — Subagent-Based Approach

## Why subagents

Reading 162 response files (27 runs × 6 tasks) manually is impractical. The subagent delegation pattern lets you grade all runs for one model-event combination in parallel while the pipeline continues.

## Delegation pattern

```python
delegate_task(
    goal="Grade all [Event] tasks for [Model] across all 3 runs.",
    context="""[Full rubric with per-task criteria, point breakdowns, and what to look for]
Results at ~/Documents/agon-results/[model]/[event]/run{1,2,3}/
Each run has task1-task6/ with prompt.txt and response.txt.
""",
    toolsets=["terminal", "file"]
)
```

## Rubric format

Each task gets a 10-point rubric broken into 3-5 criteria. Example:

```
Task N — Name (Difficulty):
- Criterion 1 (what to check) = 3
- Criterion 2 (what to check) = 3
- Criterion 3 (edge cases, quality) = 2
- Criterion 4 (code quality, format) = 2
```

## Output format

Subagents return a JSON array:

```json
[
  {"task": 1, "name": "String Cleaner", "score": 8, "notes": "..."},
  {"task": 2, "name": "Log Parser", "score": 5, "notes": "..."}
]
```

## Score file format

Subagents should save scores to a file in the model/event directory (e.g. `scores.json` or `grades.json`) so the main agent can compile results without re-reading all responses. Two formats are used:

**Array format (per-task, all runs — preferred):**
```json
[
  {"run": 1, "task": 1, "name": "String Cleaner", "score": 8, "notes": "..."},
  {"run": 1, "task": 2, "name": "Log Parser", "score": 7, "notes": "..."}
]
```

**Dict format (per-run, all tasks — compact):**
```json
{
  "run1": [8, 7, 9, 8, 10, 5],
  "run2": [8, 8, 9, 8, 10, 5],
  "run3": [8, 7, 9, 8, 10, 5]
}
```

The array format is preferred because it includes per-task notes explaining deductions. The dict format is acceptable for simple tasks where notes aren't needed.

## Compiling results

After all subagents finish, compile the scores from the saved files:

```python
# Read scores.json or grades.json from each model/event directory
# Compute per-task averages across 3 runs
# Compute event totals and overall totals
# Report as mean ± range
```

See `references/baseline-fleet-june-2026.md` for the compiled results format.

## Per-run vs per-model scoring

Grade each run independently (3 scores per task per model). Report as **mean ± range** for each event.

## What to read

Always read both `prompt.txt` and `response.txt` for each task. The prompt defines the exact requirements; the response is what the model actually produced. Don't score based on summary.json metadata alone.

## Known grading pitfalls

- **LRU Cache (Task 3):** Hidden tests were broken for all models (test harness bug — lambda expressions in `-c` mode hit `Argument list too long`). **Fixed June 2026:** Converted to script-based tests using temp files. Rerun affected models to get valid hidden test results.
- **DeepSeek-style models:** Responses contain raw thinking tags (` thinking... response`) in `content` when using `--reasoning-format none`. The code is extractable but mixed with thinking text. Grade the code content, not the thinking noise.
- **LFM2.5 thinking traces:** Extremely verbose (30K+ chars per task). The actual code is buried in the middle. Read carefully — the thinking text is not the answer.
- **CRITICAL: DeepSeek-style models bury code in thinking traces.** Jackrong (Qwen3.5-9B-DeepSeek-V4-Flash) outputs 30-50KB of thinking text before any answer. The thinking trace contains dozens of draft code blocks that the model iterates through before settling on a final version. **The subagent MUST extract the LAST code block from the response, not the first one, and not the thinking text itself.** A subagent that grades the thinking trace as "no function produced" is wrong — the function is at the end of the file, buried under 30KB of reasoning. Always check the tail of the response file for the final code block before scoring 0.
- **Code event harness now strips thinking traces automatically (June 2026):** The `run_hidden_tests()` function in `code-event.py` now calls `strip_thinking()` before code extraction, removing `...` and `...` blocks. This means hidden test results for Code tasks are now valid even for thinking-trace models. However, **manual grading of Code responses** should still be aware of thinking traces — the response file still contains the raw output, and the grader needs to find the final code block.
- **Truncation detection:** After grading, spot-check responses that scored 0. Read the last 200 characters. If it ends mid-sentence (e.g., "before index 200, and if there is no space, we need to..."), the response was truncated (hit max_tokens), not empty. Re-run with higher max_tokens and re-grade. This affected 37/216 responses across all 4 models in the June 2026 baseline run at max_tokens=8192. **Fixed:** All event scripts now use max_tokens=32768.
- **Run-to-run variance:** At temperature=0.3, simple tasks (String Cleaner, Tool Calling) may produce identical outputs across runs. This is expected — the seed mechanism forces variation on harder tasks.
