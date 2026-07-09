# Agon-Bench Results (v2 — July 2026)

## 8GB VRAM Class (8 models)

| Rank | Model | Size | Agent (24) | Reason (8) | Code (25) | Total (57) | % | tok/s |
|------|-------|:----:|:----------:|:----------:|:---------:|:----------:|:-:|:----:|
| 🥇 | **Gemma4-12B** | 6.3GB | 20.7 | 5.7 | 20.3 | **46.7** | 82% | 24 |
| 🥈 | **Grug-12B** | 6.9GB | 20.0 | 5.0 | 20.0 | **45.0** | 79% | 34 |
| 🥉 | **OmniCoder-9B** | 5.3GB | 20.3 | 5.0 | 18.0 | **43.3** | 76% | 52 |
| 4 | **Qwen3.5-9B** | 6.3GB | 18.7 | 5.3 | 19.0 | **43.0** | 75% | 47 |
| 5 | **Qwythos-9B** | 5.3GB | 18.7 | 4.3 | 19.7 | **42.7** | 75% | 48 |
| 6 | **Ornith-1.0-9B** | 5.3GB | 17.7 | 5.7 | 16.7 | **40.0** | 70% | 48 |
| 7 | **Holo-3.1-9B-Coder** | 5.3GB | 15.7 | 3.0 | 16.3 | **35.0** | 61% | 45 |
| 8 | **LFM2.5-8B** | 5.0GB | 14.7 | 2.3 | 17.0 | **34.0** | 60% | 52 |

## Grug-12B — Detailed Results

Grug-12B is a fine-tune of Gemma4-12B. Same architecture, same tokenizer, same `<|channel>thought` thinking format. The Q4_K_M is 6.9GB vs Gemma4's 6.3GB — 600MB larger for the same quantization level.

### Agent Event (24 pts) — Run 2 (clean VRAM)

| Task | Difficulty | Score | Time |
|------|-----------|:-----:|:----:|
| Tool Calling | Easy | **3/3** | 2.6s |
| Orchestration | Easy-Medium | **3/3** | 4.3s |
| Error Handling | Medium | **4/4** | 4.7s |
| Planning | Medium-Hard | **2/2** | 9.1s |
| Parsing | Medium | 2/3 | 9.4s |
| Decision-Making | Hard | 2/3 | 3.9s |
| Multi-Step Research | Hard | 2/3 | 22.4s |
| Memory-Augmented Agent | Very Hard | 2/3 | 22.5s |
| **Total** | | **20/24 (83%)** | **1.2 min** |

### Reason Event (8 pts) — Run 1

| Task | Difficulty | Score | Time |
|------|-----------|:-----:|:----:|
| Logical Deduction | Easy | 0/1 | 1276s* |
| Math Word Problem | Easy-Medium | **1/1** | 16.1s |
| Constraint Satisfaction | Medium | **1/1** | 22.7s |
| Counterfactual Reasoning | Medium-Hard | **1/1** | 8.5s |
| Analytical Explanation | Hard | **1/1** | 9.4s |
| Multi-Hop Synthesis | Very Hard | 0/1 | 5.9s |
| Graph Path Optimization | Hard | 0/1 | 20.8s |
| Probabilistic Diagnosis | Very Hard | **1/1** | 19.0s |
| **Total** | | **5/8 (63%)** | **22 min** |

*\*Task 1 triggered a 92K-char thinking chain (native `<|channel>thought` tokens not suppressed by `--reasoning off`). The other 7 tasks completed in seconds.*

### Code Event (25 pts) — Run 1

| Task | Difficulty | Score | Time |
|------|-----------|:-----:|:----:|
| String Cleaner | Easy | **5/5** | 9.0s |
| Log Parser | Easy-Medium | **4/4** | 11.9s |
| LRU Cache | Medium | **3/3** | 7.0s |
| File Indexer | Medium-Hard | 1/2 | 33.4s |
| Task Runner CLI | Hard | 1/2 | 52.8s |
| Constrained Diff Tool | Very Hard | 2/3 | 1278s* |
| Regex Engine | Hard | 0/4 | 77.5s |
| Concurrent Web Scraper | Very Hard | **2/2** | 32.2s |
| **Total** | | **20/25 (80%)** | **25 min** |

*\*Task 6 triggered a 118K-char thinking chain. Other 7 tasks completed in seconds.*

### vs Gemma4-12B

| Metric | Gemma4-12B | Grug-12B | Delta |
|--------|:----------:|:--------:|:-----:|
| **Total (57)** | **46.7** | **45.0** | **-1.7** |
| Agent (24) | 20.7 | 20.0 | -0.7 |
| Reason (8) | 5.7 | 5.0 | -0.7 |
| Code (25) | 20.3 | 20.0 | -0.3 |
| **tok/s** | **24** | **34** | **+10 (+42%)** |

### Key Observations

- **Speed**: Grug runs 42% faster than Gemma4 on clean VRAM (34 vs 24 tok/s). The 600MB larger file size doesn't matter when you have the full 8GB to yourself.
- **Quality**: Within 1.7 points of Gemma4 overall. Grug is better at parsing (2.0 vs 1.7) and web scraping (2.0 vs 1.0), worse at planning (2.0 vs 3.0) and graph path optimization (0.0 vs 1.0).
- **Regex Engine**: Complete miss (0/4). This is the biggest single-task gap vs Gemma4 (3.3/4).
- **Thinking Tokens**: Grug retains Gemma4's native `<|channel>thought` format. `--reasoning off` doesn't suppress it. Complex tasks trigger long reasoning chains (92K-118K chars) that waste tokens. The benchmark scripts strip them, but the model still burns time generating them.
- **VRAM Contention**: Critical finding. Running multiple models simultaneously drops TPS from ~34 to ~2.4. Always run one model at a time on 8GB hardware.

## Methodology

- All models: Q4_K_M quantization
- Hardware: AMD RX 5700 XT (8GB VRAM)
- Backend: llama.cpp + Vulkan (AMD radv/mesa)
- One model at a time (VRAM contention degrades performance severely)
- Hidden test grading (no model sees test cases)
- v2 benchmark: 8 tasks per event, 57 points total
- Hand-graded with hidden test verification
