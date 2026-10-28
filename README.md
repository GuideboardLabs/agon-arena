# Agon-Bench

An open benchmark for local LLMs on consumer hardware.

Three events, hidden-test grading, one 8GB GPU. Named after the Greek *agon*: contest, struggle, gathering. No datacenter, no 8xH100 cluster, just the card in a gaming PC and the memory it does not have.

**Current scale:** v2 · 66 points · 29 models · AMD RX 5700 XT (8GB VRAM, RDNA 1) · Ryzen 5 1600 · 32GB RAM · llama.cpp with the Vulkan backend

---

## The three events

| Event | Points | Tasks | What it measures |
|-------|:------:|:-----:|------------------|
| **Agent** | 24 | 8 | Tool calling, orchestration, error handling, planning, parsing, decision making, multi-step research, memory-augmented agent |
| **Code** | 25 | 8 | String cleaner, log parser, LRU cache, file indexer, task-runner CLI, constrained diff tool, regex engine, concurrent web scraper |
| **Reason** | 17 | 6 | Logical deduction, math word problems, constraint satisfaction, counterfactual reasoning, analytical explanation, multi-hop synthesis |

Every task is graded against **hidden test cases**. Models never see the criteria. No partial credit, no human judgment, no vibes: the harness runs their code against tests they have not read.

---

## Leaderboard

Three runs per event, mean reported. All models Q4_K_M or better unless the name says otherwise. One model at a time, because 8GB cannot hold two. Models over 8GB keep their expert or attention layers on the CPU.

| # | Model | Size | Agent /24 | Code /25 | Reason /17 | **Total /66** | **%** | tok/s |
|---|-------|:----:|:---------:|:--------:|:----------:|:-------------:|:-----:|:-----:|
| 1 | **LFM2.5-24B-A2B** | 14.5G | 22.00 | 23.33 | 16.33 | **61.66** | **93.42%** | 25.8 |
| 2 | **Nemotron-3.5-Bolt-74B-A9B** | 22.0G | 22.67 | 21.67 | 15.33 | **59.67** | **90.41%** | 6.7 ⟡ |
| 3 | **Qwen3.6-35B-Q4-ncmoe40** | 21.1G | 21.33 | 21.67 | 16.33 | **59.33** | **89.89%** | 21.7 |
| 4 | **Ternary-Bonsai-2-27B-PTQ1** ⟡ | 5.5G | 22.00 | 20.00 | 17.00 | **59.00** | **89.39%** | 10.9 |
| 5 | **Groot-19B-A3B** | 11.7G | 23.00 | 19.33 | 16.00 | **58.33** | **88.38%** | 28.5 |
| 6 | **Qwen3.8-35B-A3B-Distill** | 21.7G | 21.00 | 19.67 | 17.00 | **57.67** | **87.38%** | 21.0 |
| 7 | **MiniCPM-V-4.7-35B-A3B** | 19.7G | 21.33 | 19.00 | 15.67 | **56.00** | **84.85%** | 19.2 |
| 8 | **Ternary-Bonsai-2-27B-PQ2** ⟡ | 7.2G | 21.67 | 17.00 | 16.33 | **55.00** | **83.33%** | 11.8 |
| 9 | **Underdog-Saluki-27B-IQ2** | 7.9G | 20.33 | 18.33 | 16.00 | **54.66** | **82.82%** | 23.2 |
| 10 | **Gemma4-26B-A4B** | 16.9G | 23.00 | 14.00 | 16.67 | **53.67** | **81.32%** | 13.5 |
| 11 | **Raon-1 mini preview 28.8B-A4.3B** ⟡ | 19.7G | 21.00 | 16.67 | 16.00 | **53.67** | **81.32%** | 16.2 |
| 12 | **Nanbeige4.2-3B** | 2.4G | 23.00 | 15.33 | 15.33 | **53.66** | **81.30%** | 44.9 |
| 13 | **Bonsai-27B-Q1_0** | 3.8G | 22.33 | 15.33 | 15.00 | **52.66** | **79.79%** | 12.5 |
| 14 | **Ornith-1.0-9B** | 5.3G | 19.67 | 16.00 | 16.67 | **52.34** | **79.30%** | 48.0 |
| 15 | **Qwen3.8-27B-Q3-DOWN-XS** | 7.9G | 21.00 | 14.00 | 16.67 | **51.67** | **78.29%** | 24.0 |
| 16 | **Qwen3.8-9B** | 5.8G | 21.67 | 15.00 | 14.67 | **51.34** | **77.79%** | 40.0 |
| 17 | **Heem-9B (Uncensored)** | 5.6G | 19.00 | 14.67 | 16.00 | **49.67** | **75.26%** | 40.0 |
| 18 | **Ornith-1.5-9B** | 5.9G | 19.67 | 11.67 | 16.67 | **48.01** | **72.74%** | 48.0 |
| 19 | **LFM3-1.7B** | 1.1G | 18.00 | 13.00 | 15.67 | **46.67** | **70.71%** | 135.0 |
| 20 | **Gemma4-12B** | 6.7G | 18.33 | 12.33 | 15.67 | **46.33** | **70.20%** | 24.0 |
| 21 | **LFM2.5-8B-A1B** | 5.0G | 16.67 | 13.00 | 14.67 | **44.34** | **67.18%** | 91.1 |
| 22 | **Qwen3.5-9B** | 5.3G | 12.00 | 13.33 | 16.33 | **41.66** | **63.12%** | 60.0 |
| 23 | **Qwopus3.5-9B-Coder** | 4.5G | 13.33 | 12.00 | 16.33 | **41.66** | **63.12%** | 30.0 |
| 24 | **MiniCPM5-2B** | 1.6G | 14.00 | 8.67 | 16.67 | **39.34** | **59.61%** | 118.0 |
| 25 | **SuperQwen-35B** | 21.0G | 15.00 | 12.83 | 11.33 | **39.16** | **59.33%** | 10.8 |
| 26 | **Holo-3.1-9B-Coder** | 5.3G | 14.67 | 9.33 | 14.67 | **38.67** | **58.59%** | 40.0 |
| 27 | **Qwythos-9B-v1** | 5.3G | 14.33 | 9.00 | 15.33 | **38.66** | **58.58%** | 30.4 |
| 28 | **Grug-12B** | 6.9G | 13.00 | 5.00 | 14.67 | **32.67** | **49.50%** | 34.0 |
| 29 | **OmniCoder-9B** | 5.4G | 4.33 | 7.67 | 16.67 | **28.67** | **43.44%** | 53.1 |

Ties are labelled rather than broken: Gemma4-26B-A4B and Raon both compute to 81.32%, and Qwen3.5-9B and Qwopus3.5-9B-Coder are identical at 63.12% to two decimals.

**† Nemotron-3.5-Bolt-74B-A9B is reference only.** It produces the second-highest raw score on the board, but sustained decode came in at 6.7 tok/s, under the 10 tok/s admission floor, so it is not ranked as a contender.

**⟡ Non-standard context window.** Unless noted, rows run the standard windows: 4096 for Agent and Reason, 16384 for Code. The marked rows need more room on an 8GB card and are disclosed rather than silently normalised: Nemotron at 8192 for all three events, both Ternary-Bonsai PTQ1 and PQ2 plus the pinned PTQ1 at 8192, Groot at 8192 for Agent and Reason, Raon at 32768 for all three. Larger windows cost throughput on this hardware, so they cut against the model, not for it.

Every row carries a complete 3/3/3 set of completed runs. A model with a partial set is excluded from the table rather than ranked on half a result.

---

## What the numbers say

- **LFM2.5-24B-A2B holds the board at 93.42%.** 24B total, 2B active, 64 experts routed top-4, and 30 of its 40 layers are gated short convolutions with full attention only every fourth layer. It takes the best Code score here (23.33) and still runs at 25.8 tok/s. Its six truncated task-runs were re-cut at a 32768 window, which is disclosed below.
- **The best agent score is a three-way tie at 23.00:** Groot-19B-A3B, Gemma4-26B-A4B and Nanbeige4.2-3B. The spread in size between them is 16.9G to 2.4G, and Nanbeige is 3.3x faster than the 26B it ties with.
- **Ternary-Bonsai-2-27B-PTQ1 is the efficiency answer.** 89.39% at 5.5GB and 10.9 tok/s, second only to LFM2.5-24B on score while fitting comfortably inside the card. A 1.75 bit-per-weight packing that stays coherent is the most surprising result on this bench.
- **Code is where models fall over.** The median Code score is 15 out of 25 while the median Reason score is 15.67 out of 17. Reasoning is nearly solved at this scale; writing code that passes unseen tests is not. Every model below 80% loses most of its ground in Code.
- **Size buys less than people think.** The 29 rows span 1.1G to 22G, and the top and bottom are 50 points apart, but six of the top ten are under 12GB. The 8GB ceiling is real for speed and context, not for capability.

### A harness artefact worth knowing about

Agent and Reason run at 4096 tokens and Code at 16384, and a thinking model shares that window with its answer. A model whose reasoning on one task exceeds the window never finishes the thought, so the harness records truncated reasoning as the answer and the task scores zero.

LFM2.5-24B-A2B lost 12 Code points and 3 Reason points to this and nothing else; those six task-runs were re-cut at 32768 and recovered 14 of the 15. That is where the top row comes from, and it is disclosed rather than hidden. `scripts/agon-winback-rerun.py` is the replay tool, with a pre-flight check that the server on the port is the one you meant. The mechanism is documented in [references/context-window-truncation.md](references/context-window-truncation.md).

---

## Viewing the results

- **`agon-bench.html`** is a self-contained static export with the published data baked in. No server, no API, no database: open the file or drop it on any static host. Regenerate it after a new run:
  ```bash
  python3 scripts/export-static-dashboard.py agon-bench.html
  ```
- **`agon-dashboard.html`** is the live version and reads the SQLite database through a small server:
  ```bash
  python3 scripts/dashboard-server.py 8765
  # then open http://localhost:8765
  ```

Both show composite scores, per-event breakdowns, per-task heatmaps, speed, and a head-to-head view.

---

## Running the benchmark

### Prerequisites

- Python 3.10+ and `httpx` (`pip install httpx`)
- A llama.cpp build with the Vulkan backend, or any OpenAI-compatible endpoint
- Your GGUF files on disk

### Point it at your weights

The model registry in `scripts/run-benchmark.py` stores bare filenames. Set one variable and it resolves:

```bash
export AGON_MODELS_DIR=~/models      # default
```

Anything not under one directory works too: `AGON_HOME` relocates the database, `AGON_DB` overrides the DB path, and `LLAMA_SERVER` points at the server binary for the replay tool.

### Full matrix run

```bash
python3 scripts/run-benchmark.py --models <model_key> --port 8100
```

The runner starts llama-server, runs 3 events x 3 runs, writes every task result to SQLite as it lands, and resumes rather than restarting if a run times out.

### Single event

```bash
python3 scripts/agent-event.py \
  --model-url http://127.0.0.1:8080 \
  --model my-model \
  --output results/my-model/agent/run1 \
  --run 1 --seed 1
```

Swap in `code-event.py` or `reason-event.py` for the other two.

### Grade, verify, audit

```bash
python3 scripts/grade-all.py        # grade saved responses
python3 scripts/verify-scores.py    # re-run hidden tests against saved files
python3 scripts/audit-checks.py     # find checks that cannot fail
python3 scripts/test_assertions.py  # regression tests for the matcher
```

---

## Repo layout

```
agon-arena/
├── scripts/
│   ├── run-benchmark.py            # full 3-event x 3-run runner
│   ├── agent-event.py              # Agent event harness
│   ├── code-event.py               # Code event harness
│   ├── reason-event.py             # Reason event harness
│   ├── assertions.py               # hidden-test matching shared by all events
│   ├── test_assertions.py          # regression tests for that matcher
│   ├── grade-all.py                # grade saved responses
│   ├── hand-grade.py               # apply partial-credit corrections
│   ├── verify-scores.py            # re-run tests against saved responses
│   ├── audit-checks.py             # find assertions that cannot fail
│   ├── create_db.py                # schema
│   ├── dashboard-server.py         # live dashboard + JSON API
│   ├── export-static-dashboard.py  # builds agon-bench.html
│   ├── agon-winback-rerun.py       # replay runs cut off by the context window
│   ├── regrade-strict.py           # re-grade one saved output
│   └── speed-test.py               # quick decode/prefill probe
├── references/
│   ├── grading-protocol.md
│   ├── context-window-truncation.md
│   └── throughput-measurement.md
├── results/agon-bench-results.json # published board, machine readable
├── agon-dashboard.html             # live dashboard
├── agon-bench.html                 # static export with data baked in
├── LICENSE
└── README.md
```

---

## Methodology notes

- **Hidden tests.** Models never see the criteria; the harness runs their code against unseen cases.
- **3 runs per event**, reported as the mean.
- **Hand grading for termination failures.** Some models reason correctly and then loop instead of answering. Where the in-thought logic is unambiguous, partial credit is applied by `hand-grade.py`. The database is the source of truth.
- **tok/s is the mean across completed runs**, not a burst measurement, and includes prefill time in the event totals.
- **One model at a time.** The card cannot hold two.
- **Known gap: the seed argument is accepted and never sent.** Event payloads carry no seed key, so recorded seeds are misleading and every completion is an uncontrolled sample at temperature 0.3. Treat a one or two point composite gap as inside the noise until this is fixed.

---

## License

MIT
