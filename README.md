# Agon Arena

**An open benchmark for local language models on consumer hardware.**

Named after the Greek word for contest (agon). Three events. Hidden test grading. Consumer GPUs only.

Most LLM benchmarks test on datacenter hardware. Agon Arena tests on the hardware people actually own. 8GB VRAM. 4GB VRAM. The GPUs sitting in gaming PCs and laptops around the world.

## Events (v2 — July 2026)

| Event | Points | Tasks | What it measures |
|-------|--------|-------|-----------------|
| Agent | 24 | 8 | Tool calling, orchestration, error handling, planning, parsing, decision-making, multi-step research, memory-augmented agent |
| Reason | 8 | 8 | Logical deduction, math word problems, constraint satisfaction, counterfactual reasoning, analytical explanation, multi-hop synthesis, graph path optimization, probabilistic diagnosis |
| Code | 25 | 8 | String cleaner, log parser, LRU cache, file indexer, task runner CLI, constrained diff tool, regex engine, concurrent web scraper |

Every task uses hidden test cases. Models never see the grading criteria. No partial credit. No human judgment. Just pass or fail.

## Results (July 2026)

### 8GB VRAM Class (8 models)

Hardware: AMD RX 5700 XT via llama.cpp + Vulkan. All models Q4_K_M. One model at a time (8GB VRAM cannot fit multiple models).

| Rank | Model | Size | Agent (24) | Reason (8) | Code (25) | Total (57) | % | tok/s |
|------|-------|:----:|:----------:|:----------:|:---------:|:----------:|:-:|:----:|
| 🥇 | **Gemma4-12B** | 6.3GB | 20.7 | 5.7 | 20.3 | **46.7** | **82%** | 24 |
| 🥈 | **Grug-12B** | 6.9GB | 20.0 | 5.0 | 20.0 | **45.0** | **79%** | 34 |
| 🥉 | **OmniCoder-9B** | 5.3GB | 20.3 | 5.0 | 18.0 | **43.3** | **76%** | 52 |
| 4 | **Qwen3.5-9B** | 6.3GB | 18.7 | 5.3 | 19.0 | **43.0** | **75%** | 47 |
| 5 | **Qwythos-9B** | 5.3GB | 18.7 | 4.3 | 19.7 | **42.7** | **75%** | 48 |
| 6 | **Ornith-1.0-9B** | 5.3GB | 17.7 | 5.7 | 16.7 | **40.0** | **70%** | 48 |
| 7 | **Holo-3.1-9B-Coder** | 5.3GB | 15.7 | 3.0 | 16.3 | **35.0** | **61%** | 45 |
| 8 | **LFM2.5-8B** | 5.0GB | 14.7 | 2.3 | 17.0 | **34.0** | **60%** | 52 |

### Key Takeaways

- **Gemma4-12B** remains the most capable model for 8GB VRAM, but **Grug-12B** (a Gemma4 fine-tune) is only 1.7 points behind at 40% faster generation (34 vs 24 tok/s).
- **Grug-12B** excels at tool calling, error handling, parsing, and web scraping. Weak on regex engine (0/4) and graph path optimization.
- **OmniCoder-9B** leads the 9B class with strong agent performance (20.3/24).
- **Qwythos-9B** is the best code model in the 9B class (19.7/25).
- **VRAM contention** is critical: running multiple models simultaneously drops TPS from ~34 to ~2.4 on 8GB hardware. Always run one model at a time.

### Interactive Dashboard

Open `agon-dashboard.html` in a browser for interactive charts with per-task breakdowns and model comparison tabs.

## Usage

### Prerequisites

- Python 3.10+
- A running llama.cpp server (or any OpenAI-compatible API endpoint)
- `httpx` (`pip install httpx`)

### Run a single event

```bash
python3 scripts/agent-event.py \
  --model-url http://127.0.0.1:8080 \
  --model my-model \
  --output results/my-model/agent/run1 \
  --run 1 --seed 1
```

Replace `agent-event.py` with `reason-event-v2.py` or `code-event.py` for other events.

### Grade results

```bash
python3 scripts/grade-all.py
```

By default reads from `./results/`. Override with `AGON_RESULTS_DIR` env var.

### Full matrix run

```bash
bash scripts/run-agon-v2.sh
```

Edit the `MODELS` array in the script to match your model names and ports.

## Structure

```
agon-arena/
├── scripts/
│   ├── agent-event.py        # Agent event runner (v2)
│   ├── reason-event-v2.py    # Reason event runner (v2)
│   ├── code-event.py         # Code event runner
│   ├── grade-all.py          # Grade all events against results
│   ├── rerun-tests.py        # Re-grade with fixed harness
│   └── run-agon-v2.sh        # Full 3-run matrix runner (v2)
├── references/               # Benchmark design docs
├── results/                  # Generated output (gitignored)
│   ├── agon-bench-results.json
│   └── AGON-BENCH-RESULTS.md
├── agon-dashboard.html       # Interactive results dashboard
├── LICENSE                   # MIT
└── README.md
```

## Roadmap

- [x] 8GB VRAM class (RX 5700 XT, 8 models, v2)
- [x] Grug-12B (Gemma4 fine-tune) benchmarked
- [ ] 12GB VRAM class (RTX 3060/4070)
- [ ] Vision event
- [ ] Tool-use event with real API calls

## License

MIT
