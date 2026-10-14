# Context-window truncation on the Code and Reason events

**Status:** finding, recorded 2026-10-13 during the LFM2.5-24B-A2B bench.
The official leaderboard is **unchanged** by this. It explains a class of zero scores and
documents a replay that recovers them.

## The symptom

LFM2.5-24B-A2B scored **0/4 on code task 7 in all three runs**. The stored responses were
66,191, 68,646 and 68,941 characters long, contained **zero code fences**, opened on prose
("We need to produce a complete script `regex_engine.py`…") and ended mid-sentence.

Every one of them ended at roughly 16.1k tokens, which is the event's context ceiling, not a
model decision to stop.

## The mechanism

The event scripts run at `-c 16384` (the reason event at `-c 8192` plus `--max-tokens 8192`).
Thinking and answer share that window, and llama.cpp splits a `think` block out of the response
only once the block **closes**.

Task 7 costs this model about **27,000 tokens of thinking** before it reaches an answer. At
16,384 the window closes while the thinking is still open, so nothing ever splits, and the
harness records the raw truncated reasoning stream as the completion. That is why the saved
"answer" is 66 KB of derivation with no code in it. The task is lost to the window rather than
to the model.

A model that finishes its thinking inside 16,384 is unaffected. Several top entries avoid the
trap entirely by running with `--reasoning off`. LFM2.5-24B-A2B runs with reasoning on.

## The replay

Same weights, same tasks, same seeds, larger window. Only the truncated task-runs were re-cut.

| task-run | official (16384) | re-run (32768) | delta |
|---|---|---|---|
| code t7 r1 | 0/4 | 4/4 | +4 |
| code t7 r2 | 0/4 | 3/4 | +3 |
| code t7 r3 | 0/4 | 4/4 | +4 |
| reason t1 r1 | 1/2 | 2/2 | +1 |
| reason t1 r2 | 1/2 | 2/2 | +1 |
| reason t1 r3 | 1/2 | 2/2 | +1 |

The two affected tasks were worth **15 points** above their official score and **14 came back**.
The recovered answers are 5,234 to 6,396 bytes with two code fences each, and they end cleanly.

Reason task 1 has the same defect at 8,192: it produced 31,545 to 32,371 characters of thinking
containing the word "step" zero times, where the check it failed is `CONTAINS:step`. At 32,768
it answers in about 2,200 bytes containing "step" twice.

## What the two numbers mean

- **Re-cut: 61.7/66 = 93.43%**, first on the 23-model board. This is the number the leaderboard
  now carries, marked with a dagger in the table and disclosed in the note beneath it.
- **Original 16,384 run: 57.0/66 = 86.36%**, third. This is what the model scored under the
  standard window, and it is retained here because the gap between the two is the finding.

Both numbers exist on purpose. Quoting only the original would hide a real harness artefact that
applies to any model that thinks for longer than the window. Quoting only the re-cut without
saying so would misrepresent the protocol.

## The artefact is not specific to this model

A scan of the whole database for the same signature (a zero-scored task whose stored response is
far larger than any real answer) finds **118 task-runs across 20 models**. The largest
concentrations are Qwythos-9B-v1 (19), Qwen3.5-9B (17), Qwopus3.5-9B-Coder (16), Mimo-v2.6-9B
(11), Grug-12B (11) and Gemma4-12B (10). Within the top six of the board, Gemma4-26B-A4B and
Underdog-Saluki each carry affected runs.

Qwen3.6-35B-Q4-ncmoe40, the model that held first place, carries none: it runs with reasoning
suppressed, so its thinking never consumes the window. Every model that runs with reasoning on is
a candidate.

Re-cutting the rest is roughly 24 hours of GPU time, one model at a time with the other services
suspended, and until that is done the table mixes two effective protocols.

## Replay hygiene

- A **pre-flight assertion** reads the command line of whichever pid owns the port and refuses to
  run unless it carries the intended marker (`-c 32768`). A replay that silently scores against
  the original server produces numbers that look real and are not.
- Replays run **outside the database** unless `--db-path` and `--run-id` are passed, so the
  official run row cannot be touched. The harness is idempotent: a task-run that already has a
  score is skipped, so a retry after a transient failure redoes only what failed.
- A `systemd-run --user --scope` stop can return **without** terminating the process. Confirm the
  pid is gone and re-read VRAM before starting anything else, or the next server fails to bind
  and the harness quietly scores the previous one.

## Open reproducibility gap

**The event scripts accept `--seed` and never send it.** The payload is
`{model, messages, max_tokens, temperature, chat_template_kwargs}` with no seed key, so the DB's
recorded seed is misleading: every completion is an uncontrolled sample at temperature 0.3.

Observed spread on the standard recipe, seven samples of code task 7: `0,0,0,0,0,0,2`.
Seven samples of code task 5: `0,0,2,2,2,0,0`. Repeated agent runs of one competitor landed
23, 22 and 19. Any composite gap of one or two points sits inside that spread and cannot be read
as a real difference until the seed is actually sent.
