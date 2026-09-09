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

| # | Model | Size | Agent | Code | Reason | **Total** | **%** | tok/s |
|---|-------|:----:|:-----:|:----:|:------:|:---------:|:-----:|:-----:|
| 🥇 | **Qwen3.6-35B-Q4-ncmoe40** | 21.1G | 21.3 | 22.7 | 16.3 | **60.3** | **91.4%** | 21.7 |
| 🥈 | **Nanbeige4.2-3B** | 2.4G | 23.0 | 16.7 | 15.3 | **55.0** | **83.3%** | 44.9 |
| 🥉 | **Gemma4-26B-A4B** | 16.9G | 23.0 | 15.0 | 16.7 | **54.7** | **82.8%** | 13.5 |
| 4 | **Bonsai-27B-Q1_0** | 3.8G | 22.3 | 16.3 | 15.0 | **53.7** | **81.3%** | 12.5 |
| 5 | **Ornith-1.0-9B** | 5.3G | 19.7 | 17.0 | 16.7 | **53.3** | **80.8%** | 48.0 |
| 6 | **Qwen3.8-27B-Q3-DOWN-XS** | 7.9G | 21.0 | 15.7 | 16.7 | **53.3** | **80.8%** | 24.0 |
| 7 | **Qwen3.8-9B** | 5.8G | 21.7 | 16.0 | 14.7 | **52.3** | **79.3%** | 40.0 |
| 8 | **Heem-9B (Uncensored)** | 5.6G | 19.0 | 16.0 | 16.0 | **51.0** | **77.3%** | 40.0 |
| 9 | **Gemma4-12B** | 6.7G | 18.3 | 13.3 | 15.7 | **47.3** | **71.7%** | 24.0 |
| 10 | **LFM2.5-8B-A1B** | 5.0G | 16.7 | 15.0 | 14.7 | **46.3** | **70.2%** | 91.1 |
| 11 | **Ornith-1.5-9B** | 5.9G | 19.7 | 9.0 | 16.7 | **45.3** | **68.7%** | 48.0 |
| 12 | **Qwopus3.5-9B-Coder** | 4.5G | 13.3 | 13.7 | 16.3 | **43.3** | **65.7%** | 30.0 |
| 13 | **Qwen3.5-9B** | 5.3G | 12.0 | 14.3 | 16.3 | **42.7** | **64.6%** | 60.0 |
| 14 | **SuperQwen-35B** | 21.0G | 15.0 | 14.8 | 11.3 | **41.2** | **62.4%** | 10.8 |
| 15 | **MiniCPM5-2B** | 1.6G | 14.0 | 10.3 | 16.7 | **41.0** | **62.1%** | 118.0 |
| 16 | **Qwythos-9B-v1** | 5.3G | 14.3 | 11.0 | 15.3 | **40.7** | **61.6%** | 30.4 |
| 17 | **Holo-3.1-9B-Coder** | 5.3G | 14.7 | 11.0 | 14.7 | **40.3** | **61.1%** | 40.0 |
| 18 | **Grug-12B** | 6.9G | 13.0 | 7.0 | 14.7 | **34.7** | **52.5%** | 34.0 |
| 19 | **OmniCoder-9B** | 5.4G | 4.3 | 9.0 | 16.7 | **30.0** | **45.5%** | 53.8 |

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
