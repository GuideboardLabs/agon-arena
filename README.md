# 🐴 Agon-Bench

**An open benchmark for local LLMs on consumer hardware.**

Named after the Greek *agon* — contest, struggle, gathering. Three events, hidden-test grading, consumer GPUs only. No datacenter. No 8×H100 flex. Just the hardware people actually own: 8GB VRAM cards sitting in gaming PCs and laptops.

> **Current scale:** v2 · 66 points · 19 models · AMD RX 5700 XT (8GB VRAM) · llama.cpp + Vulkan

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
| 🥇 | **Qwen3.6-35B-Q4-ncmoe40** | 21.1G | 21.3 | 21.7 | 16.3 | **59.3** | **89.9%** | 21.7 |
| 🥈 | **Nanbeige4.2-3B** | 2.4G | 23.0 | 15.3 | 15.3 | **53.7** | **81.3%** | 44.9 |
| 🥉 | **Gemma4-26B-A4B** | 16.9G | 23.0 | 14.0 | 16.7 | **53.7** | **81.3%** | 13.5 |
| 4 | **Bonsai-27B-Q1_0** | 3.8G | 22.3 | 15.3 | 15.0 | **52.7** | **79.8%** | 12.5 |
| 5 | **Ornith-1.0-9B** | 5.3G | 19.7 | 16.0 | 16.7 | **52.3** | **79.3%** | 48.0 |
| 6 | **Qwen3.8-27B-Q3-DOWN-XS** | 7.9G | 21.0 | 14.0 | 16.7 | **51.7** | **78.3%** | 24.0 |
| 7 | **Qwen3.8-9B** | 5.8G | 21.7 | 15.0 | 14.7 | **51.3** | **77.8%** | 40.0 |
| 8 | **Heem-9B (Uncensored)** | 5.6G | 19.0 | 14.7 | 16.0 | **49.7** | **75.3%** | 40.0 |
| 9 | **Ornith-1.5-9B** | 5.9G | 19.7 | 11.7 | 16.7 | **48.0** | **72.7%** | 48.0 |
| 10 | **Gemma4-12B** | 6.7G | 18.3 | 12.3 | 15.7 | **46.3** | **70.2%** | 24.0 |
| 11 | **LFM2.5-8B-A1B** | 5.0G | 16.7 | 13.0 | 14.7 | **44.3** | **67.2%** | 91.1 |
| 12 | **Qwopus3.5-9B-Coder** | 4.5G | 13.3 | 12.0 | 16.3 | **41.7** | **63.1%** | 30.0 |
| 13 | **Qwen3.5-9B** | 5.3G | 12.0 | 13.3 | 16.3 | **41.7** | **63.1%** | 60.0 |
| 14 | **MiniCPM5-2B** | 1.6G | 14.0 | 8.7 | 16.7 | **39.3** | **59.6%** | 118.0 |
| 15 | **SuperQwen-35B** | 21.0G | 15.0 | 12.8 | 11.3 | **39.2** | **59.3%** | 10.8 |
| 16 | **Qwythos-9B-v1** | 5.3G | 14.3 | 9.0 | 15.3 | **38.7** | **58.6%** | 30.4 |
| 17 | **Holo-3.1-9B-Coder** | 5.3G | 14.7 | 9.3 | 14.7 | **38.7** | **58.6%** | 40.0 |
| 18 | **Grug-12B** | 6.9G | 13.0 | 5.0 | 14.7 | **32.7** | **49.5%** | 34.0 |
| 19 | **OmniCoder-9B** | 5.4G | 4.3 | 7.7 | 16.7 | **28.7** | **43.4%** | 53.8 |

> **Not shown: Qwen3.8-35B-A3B-Distill** (21.7G, 21.0 / 19.7 / 17.0 = **57.7**,
> **87.4%**). It has a complete 3/3/3 set and would rank #2, but it was absent
> from the 19-model table published on 2026-07 and is left out here so this edit
> changes only the scores and not the roster. Adding it is a separate call.

---

## What the numbers say

- **Qwen3.6-35B-Q4-ncmoe40 takes the crown** at 91.4% — the `-ncmoe 40` recipe turns a 35B MoE into a genuine all-rounder. Best code on the bench (22.7/25).
- **Nanbeige4.2-3B is the story.** A 2.4GB, 3B looped transformer ties a 16.9GB 26B MoE for the top agent score (23.0/24) at 3.3× the speed. The looped architecture gives 3B the reasoning depth of a 6-7B model. The most significant small-model innovation since MoE.
- **Bonsai-27B-Q1_0** — a 3.8GB 1-bit ternary model that shouldn't work but does. Elite agent (22.3/24), 81.3% overall. The dark horse.
- **Speed is a real axis.** LFM2.5-8B (91 tok/s) and MiniCPM5-2B (118 tok/s) are the speed kings, but both trade capability for it. MiniCPM is a razor-sharp reasoner (16.7/17) that can't close agent/code tasks — it reasons beautifully and never ships.
- **The 8GB ceiling is real.** The best model needs 21GB and CPU spill. The best model that *fits* in 8GB is Nanbeige at 83.3%. That gap is the whole point of the bench.

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

---

## Repo layout

```
agon-arena/
├── scripts/
│   ├── run-benchmark.py          # Full 3-event × 3-run matrix runner
│   ├── agent-event.py            # Agent event runner
│   ├── code-event.py             # Code event runner
│   ├── reason-event.py           # Reason event runner
│   ├── dashboard-server.py       # Live dashboard server (serves /api/models)
│   ├── export-static-dashboard.py# Builds self-contained agon-bench.html
│   ├── grade-all.py              # Grade all events against results
│   └── hand-grade.py             # Apply partial-credit corrections
├── references/                   # Benchmark design + methodology docs
├── results/                      # Per-model response files + summaries
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

---

## Roadmap

- [x] 8GB VRAM class (RX 5700 XT, 19 models, v2 66-point scale)
- [x] Static dashboard export for public hosting
- [ ] 12GB VRAM class (RTX 3060/4070)
- [ ] Vision event
- [ ] Tool-use event with real API calls

---

## License

MIT
