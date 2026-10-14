# 🐴 Agon-Bench

**An open benchmark for local LLMs on consumer hardware.**

Named after the Greek *agon* — contest, struggle, gathering. Three events, hidden-test grading, consumer GPUs only. No datacenter. No 8×H100 flex. Just the hardware people actually own: 8GB VRAM cards sitting in gaming PCs and laptops.

> **Current scale:** v2 · 66 points · 23 models · AMD RX 5700 XT (8GB VRAM) · llama.cpp + Vulkan

---

## The three events

| Event | Points | Tasks | What it measures |
|-------|:------:|:-----:|------------------|
| **Agent** | 24 | 8 | Tool calling, orchestration, error handling, planning, parsing, decision-making, multi-step research, memory-augmented agent |
| **Code** | 25 | 8 | String cleaner, log parser, LRU cache, file indexer, task-runner CLI, constrained diff tool, regex engine, concurrent web scraper |
| **Reason** | 17 | 6 | Logical deduction, math word problems, constraint satisfaction, counterfactual reasoning, analytical explanation, multi-hop synthesis |

Every task runs against **hidden test cases**. Models never see the grading criteria. No partial credit, no human judgment, no vibes. Pass or fail.

---

## Leaderboard (66-point scale, 3-run averages)

Hardware: AMD RX 5700 XT (8GB VRAM, RDNA 1), Ryzen 5 1600, 64GB RAM. All models Q4_K_M unless noted. One model at a time (8GB can't fit multiple). Models over 8GB use CPU offloading.

> **Code column corrected 2026-09-20.** Two Code-event checks could not fail, so
> every completed run banked their points. Code scores here are corrected; Agent
> and Reason are unchanged. Totals are therefore **not comparable** to any table
> published before this date. Details: [SCORE-CORRECTION-2026-09-20.md](SCORE-CORRECTION-2026-09-20.md).

| # | Model | Size | Agent | Code | Reason | **Total** | **%** | tok/s |
|---|-------|:----:|:-----:|:----:|:------:|:---------:|:-----:|:-----:|
| 🥇 | **LFM2.5-24B-A2B** † | 14.5G | 22.0 | 23.3 | 16.3 | **61.7** | **93.43%** | 25.8 |
| 🥈 | **Qwen3.6-35B-Q4-ncmoe40** | 21.1G | 21.3 | 21.7 | 16.3 | **59.3** | **89.90%** | 21.7 |
| 🥉 | **Qwen3.8-35B-A3B-Distill** | 21.7G | 21.0 | 19.7 | 17.0 | **57.7** | **87.37%** | 21.0 |
| 4 | **MiniCPM-V-4.7-35B-A3B** | 19.7G | 21.3 | 19.0 | 15.7 | **56.0** | **84.85%** | 19.2 |
| 5 | **Underdog-Saluki-27B-IQ2** | 7.9G | 20.3 | 18.3 | 16.0 | **54.7** | **82.83%** | 23.2 |
| 6= | **Nanbeige4.2-3B** | 2.4G | 23.0 | 15.3 | 15.3 | **53.7** | **81.31%** | 44.9 |
| 6= | **Gemma4-26B-A4B** | 16.9G | 23.0 | 14.0 | 16.7 | **53.7** | **81.31%** | 13.5 |
| 8 | **Bonsai-27B-Q1_0** | 3.8G | 22.3 | 15.3 | 15.0 | **52.7** | **79.80%** | 12.5 |
| 9 | **Ornith-1.0-9B** | 5.3G | 19.7 | 16.0 | 16.7 | **52.3** | **79.29%** | 48.0 |
| 10 | **Qwen3.8-27B-Q3-DOWN-XS** | 7.9G | 21.0 | 14.0 | 16.7 | **51.7** | **78.28%** | 24.0 |
| 11 | **Qwen3.8-9B** | 5.8G | 21.7 | 15.0 | 14.7 | **51.3** | **77.78%** | 40.0 |
| 12 | **Heem-9B (Uncensored)** | 5.6G | 19.0 | 14.7 | 16.0 | **49.7** | **75.25%** | 40.0 |
| 13 | **Ornith-1.5-9B** | 5.9G | 19.7 | 11.7 | 16.7 | **48.0** | **72.73%** | 48.0 |
| 14 | **Gemma4-12B** | 6.7G | 18.3 | 12.3 | 15.7 | **46.3** | **70.20%** | 24.0 |
| 15 | **LFM2.5-8B-A1B** | 5.0G | 16.7 | 13.0 | 14.7 | **44.3** | **67.17%** | 91.1 |
| 16= | **Qwopus3.5-9B-Coder** | 4.5G | 13.3 | 12.0 | 16.3 | **41.7** | **63.13%** | 30.0 |
| 16= | **Qwen3.5-9B** | 5.3G | 12.0 | 13.3 | 16.3 | **41.7** | **63.13%** | 60.0 |
| 18 | **MiniCPM5-2B** | 1.6G | 14.0 | 8.7 | 16.7 | **39.3** | **59.60%** | 118.0 |
| 19 | **SuperQwen-35B** | 21.0G | 15.0 | 12.8 | 11.3 | **39.2** | **59.34%** | 10.8 |
| 20= | **Qwythos-9B-v1** | 5.3G | 14.3 | 9.0 | 15.3 | **38.7** | **58.59%** | 30.4 |
| 20= | **Holo-3.1-9B-Coder** | 5.3G | 14.7 | 9.3 | 14.7 | **38.7** | **58.59%** | 40.0 |
| 22 | **Grug-12B** | 6.9G | 13.0 | 5.0 | 14.7 | **32.7** | **49.49%** | 34.0 |
| 23 | **OmniCoder-9B** | 5.4G | 4.3 | 7.7 | 16.7 | **28.7** | **43.43%** | 53.1 |

Ties are real and are labelled rather than broken: Nanbeige4.2-3B and Gemma4-26B-A4B both
compute to 81.313131%, and the two 63.13% and two 58.59% pairs are likewise identical to six
decimals.

**† LFM2.5-24B-A2B's row was re-cut at a 32,768-token window.** The Code and Reason events run
at 16,384 tokens, thinking shares that window with the answer, and this model's reasoning on one
Code task and one Reason task runs longer than the window, so those six task-runs were originally
recorded as truncated reasoning and scored zero. Re-running only those six at 32,768 recovers 14
of the 15 points those tasks were worth. Every other row ran at the standard window, and **118
task-runs across 19 other models carry the same artefact unfixed**, so this row is not yet
protocol-identical to the rest of the table. That work is next on the list. Full mechanism and
evidence: [references/context-window-truncation.md](references/context-window-truncation.md).

Every row carries a complete 3/3/3 set of completed runs. Models with an incomplete set are
excluded from the ranking entirely rather than ranked on partial data.

---

## What the numbers say

- **LFM2.5-24B-A2B takes the board at 93.43%**, on an architecture that is not a finetune of anything else here: 24B total with 2B active per token, 64 experts routed top-4, and **30 of its 40 layers are gated short convolutions** with only every fourth layer running full attention. It holds the best code score on the bench (23.3/25) and is the fastest model in the top five at 25.8 tok/s. The dagger under the table covers what changed.
- **Qwen3.6-35B-Q4-ncmoe40 is the model that held the crown** at 89.90%, and it held it cleanly: it runs with reasoning suppressed, so the context-window artefact cannot touch it. The `-ncmoe 40` recipe turns a 35B MoE into a genuine all-rounder.
- **Nanbeige4.2-3B is still the story at the small end.** A 2.4GB, 3B looped transformer ties for the best agent score on the bench (23.0/24) at 3.3× the speed of the 26B it ties with. The looped architecture gives 3B the reasoning depth of a 6-7B model.
- **Bonsai-27B-Q1_0 is the dark horse**: a 3.8GB 1-bit ternary model that shouldn't work but does. Elite agent (22.3/24), 79.80% overall.
- **Speed is a real axis.** LFM2.5-8B (91.1 tok/s) and MiniCPM5-2B (118.0 tok/s) are the speed kings, but both trade capability for it. MiniCPM is a razor-sharp reasoner (16.7/17) that can't close agent or code tasks. It reasons beautifully and never ships.
- **The 8GB ceiling is real.** The top of the board needs 21GB with CPU spill, and the best model under 5GB is Nanbeige4.2-3B at 81.31% on 2.4GB. That gap is the whole point of the bench.

### A harness artefact worth knowing about

The Code and Reason events run at a 16,384-token context, and thinking shares that window with
the answer. A model whose reasoning on one task runs longer than the window never finishes the
thought, so the harness records the truncated reasoning stream as the answer and the task scores
zero. LFM2.5-24B-A2B lost 12 Code points and 3 Reason points to this and nothing else, and those
six task-runs were re-cut at 32,768 to recover 14 of the 15 points. That is where the 93.43% at
the top of the table comes from, and it is disclosed rather than hidden.

The same artefact is still sitting in **118 task-runs across 19 other models**, from Gemma4-12B
and Grug-12B in the middle of the board up to Gemma4-26B and Underdog-Saluki in the top six.
Those models are scored low for the same reason this one was. Re-cutting them is roughly a day of
GPU time, one model at a time, and it is the honest way to make the whole table
protocol-identical. The mechanism, the replay method, and the reproducibility gap in the seeding
are in [references/context-window-truncation.md](references/context-window-truncation.md).

---

## Interactive dashboard

Two ways to view the results:

- **`agon-dashboard.html`** — the live dashboard. Needs the local server:
  ```bash
  python3 scripts/dashboard-server.py 8765
  # then open http://localhost:8765
  ```
- **`agon-bench.html`** — a **self-contained static export** with the data baked in. Drop it on any static host (IONOS, GitHub Pages, S3) and it just works. No server, no API. Regenerate after a new run:
  ```bash
  python3 scripts/export-static-dashboard.py agon-bench.html
  ```

Both show composite scores, per-event breakdowns, per-task heatmaps, speed comparison, and a head-to-head VS mode.

---

## Running the benchmark

### Prerequisites

- Python 3.10+
- A running llama.cpp server (or any OpenAI-compatible endpoint)
- `httpx` (`pip install httpx`)

### Full matrix run

```bash
python3 scripts/run-benchmark.py --models <model_key> --port 8100
```

The runner starts the llama.cpp server, runs all 3 events × 3 runs (seeds 42/137/256), writes per-task results to the SQLite DB in real time, and supports resume (a timed-out run picks up where it left off).

### Single event

```bash
python3 scripts/agent-event.py \
  --model-url http://127.0.0.1:8080 \
  --model my-model \
  --output results/my-model/agent/run1 \
  --run 1 --seed 1
```

Swap `agent-event.py` for `code-event.py` or `reason-event.py` for the other events.

### Grade results

```bash
python3 scripts/grade-all.py
```

Reads from `./results/` by default. Override with `AGON_RESULTS_DIR`.

### Re-running a truncated task

```bash
python3 scripts/agon-winback-rerun.py --port 8174
```

Re-cuts task-runs whose response was cut off by the context window at a larger window, with a
pre-flight assertion that the server on that port is really the one you intended. Runs outside the
database unless `--db-path` and `--run-id` are passed, so an official run row cannot be modified.

---

## Repo layout

```
agon-arena/
├── scripts/
│   ├── run-benchmark.py          # Full 3-event × 3-run matrix runner
│   ├── agent-event.py            # Agent event runner
│   ├── code-event.py             # Code event runner
│   ├── reason-event.py           # Reason event runner
│   ├── assertions.py             # Hidden-test assertions + matcher
│   ├── grade-all.py              # Grade all events against results
│   ├── hand-grade.py             # Apply partial-credit corrections
│   ├── dashboard-server.py       # Live dashboard server (serves /api/models)
│   ├── export-static-dashboard.py# Builds self-contained agon-bench.html
│   ├── create_db.py              # Schema creation
│   ├── audit-checks.py           # Find checks that cannot fail
│   ├── verify-scores.py          # Recompute every score from per-task rows
│   ├── agon-grade-audit.py       # Audit grading across a run
│   ├── agon-fix-run-totals.py    # Reconciliation: recompute run totals
│   ├── agon-sweep-ncmoe.py       # MoE offload-depth sweep
│   ├── agon-code-reasoning-ab.py # Reasoning-config A/B (see the truncation note)
│   ├── agon-t7-room-test.py      # Single-task window test, pre-flight asserted
│   ├── agon-winback-rerun.py     # Replay truncated task-runs at a larger window
│   ├── agon-suspend.sh           # Suspend other GPU services before a bench
│   ├── agon-restore.sh           # Restore them afterwards
│   ├── retry-task.py             # Re-run one failed task
│   ├── find-ceilings.py          # Find the context ceiling per model
│   ├── real-ctx-test.py          # Measure usable context
│   ├── speed-test.py             # Decode/prefill throughput probe
│   ├── sprint-bench.py           # Fast partial sweep
│   └── ...                       # Model-specific probes and regrades
├── references/                   # Design, methodology, and findings docs
├── results/                      # Published result summaries
├── models/                       # Per-model notes and write-ups
├── artshow/                      # Prompt sets for the board's art panels
├── agon-bench.db                 # SQLite source of truth (scores, runs, tasks)
├── agon-dashboard.html           # Live interactive dashboard
├── agon-bench.html               # Static dashboard export (for hosting)
├── LICENSE                       # MIT
└── README.md
```

---

## Methodology notes

- **Hidden tests, no partial credit.** Models never see grading criteria. The harness runs their code against unseen test cases.
- **3 runs per event** (seeds 42/137/256) to smooth variance. Reported scores are the mean.
- **Hand-grading for termination failures.** Some models (MiniCPM5-2B, SuperQwen) reason correctly but loop instead of emitting a final answer. Where the in-thought logic is clearly correct, partial credit is applied via `hand-grade.py` — the DB is the source of truth.
- **tok/s is the mean across completed runs**, not a burst test.
- **One model at a time.** The GPU cannot hold two, so other services are suspended for the duration of a bench and restored afterwards (`agon-suspend.sh` / `agon-restore.sh`).
- **Known gap: the seed argument is accepted and never sent.** The event payloads carry no seed key, so recorded seeds are misleading and every completion is an uncontrolled sample at temperature 0.3. Per-task spread is documented in `references/context-window-truncation.md`; treat any one or two point composite gap as inside the noise until this is fixed.

---

## Roadmap

- [x] 8GB VRAM class (RX 5700 XT, 23 models, v2 66-point scale)
- [x] Static dashboard export for public hosting
- [ ] Send the seed in every event payload (reproducibility)
- [ ] 12GB VRAM class (RTX 3060/4070)
- [ ] Vision event
- [ ] Tool-use event with real API calls

---

## License

MIT
