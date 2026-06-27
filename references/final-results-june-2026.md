# Final Results — June 2026 Baseline

## Hardware

- **CPU:** AMD Ryzen 5 5600X (6C/12T)
- **RAM:** 64GB DDR4
- **GPU:** AMD Radeon RX 5700 XT (8GB VRAM)
- **Backend:** llama.cpp (Vulkan via radv/mesa)
- **Quantization:** Q4_K_M (all models)
- **Context length:** 32768
- **Temperature:** 0.3
- **Max tokens:** 32768

## Models Tested

| Model | Size | File Size | Quant | Source |
|-------|:----:|:---------:|:-----:|--------|
| Gemma4-12B | 12B | 6.3 GB | Q4_K_M | unsloth |
| Ornith-1.0-9B | 9B | 5.3 GB | Q4_K_M | unsloth |
| LFM2.5-8B | 8B | 5.0 GB | UD-Q4_K_XL | unsloth |
| Qwen3.5-9B | 9B | 5.3 GB | Q4_K_M | unsloth |
| Jackrong (Qwen3.5-9B-DeepSeek-V4-Flash) | 9B | 5.3 GB | Q4_K_M | unsloth |

## Overall Scores (54 max)

| Model | Agent (18) | Reason (17) | Code (19) | **Total** | **%** |
|-------|:----------:|:-----------:|:---------:|:---------:|:-----:|
| **Gemma4-12B** | 15.0 ±1.5 | 16.7 ±0.5 | 10.3 ±0.5 | **42.0** | **78%** |
| **Qwen3.5-9B** | 14.0 ±1.0 | 16.0 ±0.0 | 10.3 ±2.5 | **40.3** | **75%** |
| **Ornith-1.0-9B** | 11.7 ±1.0 | 16.3 ±0.5 | 12.0 ±0.0 | **40.0** | **74%** |
| **LFM2.5-8B** | 10.7 ±3.5 | 16.7 ±0.5 | 8.8 ±2.5 | **36.2** | **67%** |
| Jackrong* | 9.0 ±2.5 | 16.0 ±1.0 | 2.7 ±2.0 | **27.7** | **51%** |

*\*Jackrong scores are unreliable — DeepSeek-V4-Flash thinking loop causes "EMPTY after cleaning" on many Code tasks. Replaced by Qwen3.5-9B in the baseline fleet.*

## Efficiency Metrics

| Model | tok/s | Total Tokens | Runtime | Benchmark % | Composite % |
|-------|:----:|:-----------:|:-------:|:-----------:|:-----------:|
| Gemma4-12B | 21.6 | 47.6k | 36.8m | 78% | 72.4% |
| Qwen3.5-9B | 41.9 | 142.5k | 56.7m | 75% | 71.7% |
| Ornith-1.0-9B | 45.4 | 77.5k | 28.5m | 74% | 71.7% |
| LFM2.5-8B | 91.1 | 200.4k | 36.7m | 67% | 70.3% |

**Composite formula:** `benchmark_pct * 0.9 + efficiency_pct * 0.1` where `efficiency_pct = model_tok_s / max_tok_s * 100`.

Efficiency weight is 10% — intentionally modest so it doesn't distort the benchmark ranking. On 8GB VRAM, larger models (12B) are VRAM-constrained, reducing throughput. On 16GB+, all models would fit more comfortably and the speed gap would narrow, but relative ordering (smaller = faster) persists.

## Per-Event Breakdown

### Agent Event (18 pts)

| Task | Gemma4 | Qwen3.5 | Ornith | LFM2.5 |
|------|:------:|:-------:|:------:|:------:|
| 1. Tool Calling (3) | 2.0 | 2.0 | 2.0 | 2.0 |
| 2. Orchestration (3) | 3.0 | 2.0 | 2.3 | 2.0 |
| 3. Error Handling (4) | 4.0 | 4.0 | 4.0 | 2.3 |
| 4. Planning (2) | 1.3 | 2.0 | 0.7 | 0.7 |
| 5. Parsing (3) | 1.7 | 1.0 | 0.0 | 1.0 |
| 6. Decision-Making (3) | 3.0 | 3.0 | 2.7 | 2.7 |

### Reason Event (17 pts)

| Task | Gemma4 | Qwen3.5 | Ornith | LFM2.5 |
|------|:------:|:-------:|:------:|:------:|
| 1. Logical Deduction (2) | 2.0 | 2.0 | 2.0 | 2.0 |
| 2. Math Word Problem (3) | 3.0 | 3.0 | 3.0 | 2.7 |
| 3. Constraint Satisfaction (3) | 3.0 | 3.0 | 3.0 | 3.0 |
| 4. Counterfactual Reasoning (3) | 2.7 | 3.0 | 3.0 | 3.0 |
| 5. Analytical Explanation (3) | 3.0 | 2.0 | 2.3 | 3.0 |
| 6. Multi-Hop Synthesis (3) | 3.0 | 3.0 | 3.0 | 3.0 |

### Code Event (19 pts)

| Task | Gemma4 | Qwen3.5 | Ornith | LFM2.5 |
|------|:------:|:-------:|:------:|:------:|
| 1. String Cleaner (5) | 5.0 | 2.0 | 5.0 | 3.2 |
| 2. Log Parser (4) | 2.0 | 1.0 | 0.0 | 1.5 |
| 3. LRU Cache (3) | 0.0 | 3.0 | 3.0 | 0.8 |
| 4. File Indexer (2) | 2.0 | 2.0 | 2.0 | 1.8 |
| 5. Task Runner CLI (2) | 0.0 | 0.3 | 0.0 | 0.0 |
| 6. Constrained Diff Tool (3) | 1.3 | 2.0 | 2.0 | 1.5 |

## Key Observations

### Gemma4-12B — Overall Leader (78%)

- **Agent (83%):** Best in class. Perfect on Error Handling, Decision-Making, and Orchestration. Only weakness: Planning (1.3/2 — one run had a syntax error in a lambda).
- **Reason (98%):** Near-perfect. Only one missed keyword check across all 3 runs.
- **Code (54%):** Tied with Qwen3.5-9B for lowest code score. LRU Cache is 0/3 — the model outputs a note about OrderedDict instead of actual code. Task Runner CLI is 0/2. Diff Tool is 1.3/3.
- **Efficiency:** Slowest at 21.6 tok/s. VRAM-constrained — the GPU swaps layers in and out of 8GB VRAM.

### Qwen3.5-9B — New Baseline (75%)

Replaces Jackrong (which has a DeepSeek-V4-Flash thinking loop that cannot be suppressed in llama.cpp). Vanilla model with no thinking architecture.

**Strengths:**
- Agent event (78%): 2nd place behind Gemma4. Perfect on Error Handling (4/4), Planning (2/2), Decision-Making (3/3).
- Reason event (94%): Near-perfect. Consistent 16/17 across all 3 runs.
- LRU Cache (3/3): Perfect — tied with Ornith.
- File Indexer (2/2): Perfect — tied with all models.
- Diff Tool (2/3): Strong — tied with Ornith and LFM2.5.

**Weaknesses:**
- String Cleaner (2/5): High variance — sometimes forgets `import re`.
- Log Parser (1/4): Consistently 1/4. Hardcodes `rest.startswith('LEVEL:')` instead of parsing actual log levels.
- Task Runner CLI (0.3/2): Uses `from tabulate import tabulate` (not stdlib).

### Ornith-1.0-9B — Code Leader (74%)

- **Code (63%):** Best code score. Perfect on String Cleaner (5/5), LRU Cache (3/3), File Indexer (2/2). Consistent 12/19 every run — zero variance.
- **Reason (96%):** Near-perfect.
- **Agent (65%):** Weakest agent score. Planning is 0.7/2. Parsing is 0/3 (returns empty dicts).
- **Efficiency:** 45.4 tok/s. Fast, small (5.3GB), consistent.

### LFM2.5-8B — Most Variable (67%)

- **Reason (98%):** Tied with Gemma4 for best reasoning.
- **Agent (59%):** High variance (10.7 ± 3.5). Error Handling ranges from 1/4 to 4/4.
- **Code (55%):** Some runs produce syntax errors, others produce working code.
- **Efficiency:** 91.1 tok/s — fastest model by far. Fits entirely in 8GB VRAM with room to spare.

### Jackrong — Config-Limited (51%)

Jackrong's Code score (2.7/19) is not a fair measure. The DeepSeek-V4-Flash thinking loop cannot be suppressed by `--reasoning off --reasoning-format none` in llama.cpp. The model opens ` thinking` and never closes it, generating 130KB+ of circular reasoning with zero code output. In Pi (official API with `reasoning_content`/`content` split), Jackrong works fine.

**Excluded from the baseline fleet.** Use Qwen3.5-9B for fair comparison.

## Scoring Tiers

| Tier | Score | Models |
|:----:|:-----:|--------|
| Gold | 45-54 | — |
| Silver | 36-44 | Gemma4-12B (42.0), Qwen3.5-9B (40.3), Ornith-1.0-9B (40.0) |
| Bronze | 27-35 | LFM2.5-8B (36.2) |
| Needs work | 18-26 | — |
| Not suitable | 0-17 | — |
