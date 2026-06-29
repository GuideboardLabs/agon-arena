# Agon Arena

**An open benchmark for local language models on consumer hardware.**

Named after the Greek word for contest (agon). Three events. Hidden test grading. Consumer GPUs only.

Most LLM benchmarks test on datacenter hardware. Agon Arena tests on the hardware people actually own. 8GB VRAM. 4GB VRAM. The GPUs sitting in gaming PCs and laptops around the world.

## Events

| Event | Points | What it measures |
|-------|--------|-----------------|
| Agent | 18 | Tool calling, orchestration, planning, parsing, error handling, decision-making |
| Reason | 17 | Logical deduction, math, constraint satisfaction, counterfactuals, analysis, synthesis |
| Code | 19 | String processing, parsing, data structures, file I/O, CLI tools, diff algorithms |

Every task uses hidden test cases. Models never see the grading criteria. No partial credit. No human judgment. Just pass or fail.

## Results (June 2026)

### 8GB VRAM Class (7 models)

Hardware: AMD RX 5700 XT via llama.cpp + Vulkan. All models Q4_K_M.

| Model | Size | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|------|:----------:|:-----------:|:---------:|:----------:|:-:|:----:|
| **Holo-3.1-9B-Coder** | 5.3GB | 15.7 | 14.7 | 12.7 | **43.1** | **80%** | 36.6 |
| **Gemma4-12B** | 6.3GB | 15.0 | 16.7 | 10.3 | **42.0** | **78%** | 21.6 |
| **Qwen3.5-9B** | 6.3GB | 14.0 | 16.0 | 10.3 | **40.3** | **75%** | 41.9 |
| **Ornith-1.0-9B** | 5.3GB | 11.7 | 16.3 | 12.0 | **40.0** | **74%** | 45.4 |
| **VibeThinker-3B** | 1.8GB | 15.3 | 17.0 | 7.0 | **39.0** | **72%** | 82.7 |
| **LFM2.5-8B** | 5.0GB | 10.7 | 16.7 | 8.8 | **36.2** | **67%** | 91.1 |
| **Holo-3.1-9B** | 5.3GB | 5.3 | 15.0 | 7.0 | **27.3** | **51%** | 36.6 |

### 4GB VRAM Class (1 model)

| Model | Size | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|------|:----------:|:-----------:|:---------:|:----------:|:-:|:----:|
| **VibeThinker-3B** | 1.8GB | 15.3 | 17.0 | 7.0 | **39.0** | **72%** | 82.7 |

### 24GB VRAM Class (VRAM split: 6-7GB GPU, rest system RAM)

| Model | Size | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|------|:----------:|:-----------:|:---------:|:----------:|:-:|:----:|
| **SuperQwen-35B-A3B** | 19.7GB | 18.0 | 12.0 | 18.3 | **48.3** | **89%** | 10.1 |

### Interactive Dashboard

Open `agon-dashboard.html` in a browser for interactive charts with class-switching tabs.

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

Replace `agent-event.py` with `reason-event.py` or `code-event.py` for other events.

### Grade results

```bash
python3 scripts/grade-all.py
```

By default reads from `./results/`. Override with `AGON_RESULTS_DIR` env var.

### Full matrix run

```bash
bash scripts/run-agon-full.sh
```

Edit the `MODELS` array in the script to match your model names and ports.

## Structure

```
agon-arena/
├── scripts/
│   ├── agent-event.py      # Agent event runner
│   ├── reason-event.py     # Reason event runner
│   ├── code-event.py       # Code event runner
│   ├── grade-all.py        # Grade all events against results
│   ├── rerun-tests.py      # Re-grade with fixed harness
│   └── run-agon-full.sh    # Full 3-run matrix runner
├── references/             # Benchmark design docs
├── results/                # Generated output (gitignored)
│   ├── agon-bench-results.json
│   └── AGON-BENCH-RESULTS.md
├── agon-dashboard.html     # Interactive results dashboard
├── LICENSE                 # MIT
└── README.md
```

## Roadmap

- [x] 8GB VRAM class (RX 5700 XT, 7 models)
- [x] 4GB VRAM class (VibeThinker-3B)
- [x] 24GB VRAM class (SuperQwen-35B-A3B, VRAM split)
- [ ] 12GB VRAM class (RTX 3060/4070)
- [ ] Vision event
- [ ] Tool-use event with real API calls

## License

MIT
