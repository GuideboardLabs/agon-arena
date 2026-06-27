# Agon-Bench Results — June 2026

## Overview
3-event benchmark (Agent + Reason + Code) for local LLMs on AMD RX 5700 XT (8GB VRAM, Vulkan).

## Final Scores

| Model | Size | Agent (18) | Reason (17) | Code (19) | **Total (54)** | **%** |
|-------|------|:----------:|:-----------:|:---------:|:--------------:|:-----:|
| **Gemma4-12B** | 6.3GB | **15.0** | **16.7** | **13.3** | **45.0** | **83%** |
| **Ornith-1.0-9B** | 5.3GB | **11.7** | **16.3** | **12.0** | **40.0** | **74%** |
| **LFM2.5-8B** | 5.0GB | **10.7** | **16.7** | **9.5** | **36.9** | **68%** |
| **Jackrong** | 5.3GB | **9.0** | **16.3** | **2.7** | **28.0** | **52%** |

## Per-Task Breakdown

### Agent Event (max 18)
| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| Tool Calling (3) | 2.0 | 2.0 | 2.0 | 1.3 |
| Orchestration (3) | 3.0 | 2.3 | 2.0 | 1.0 |
| Error Handling (4) | 4.0 | 4.0 | 2.3 | 4.0 |
| Planning (2) | 1.3 | 0.7 | 0.7 | 0.7 |
| Parsing (3) | 1.7 | 0.0 | 1.0 | 0.0 |
| Decision-Making (3) | 3.0 | 2.7 | 2.7 | 2.0 |

### Reason Event (max 17)
| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| Logical Deduction (2) | 2.0 | 2.0 | 2.0 | 1.7 |
| Math Word Problem (3) | 3.0 | 3.0 | 2.7 | 3.0 |
| Constraint Satisfaction (3) | 3.0 | 3.0 | 3.0 | 3.0 |
| Counterfactual Reasoning (3) | 2.7 | 3.0 | 3.0 | 2.7 |
| Analytical Explanation (3) | 3.0 | 2.3 | 3.0 | 3.0 |
| Multi-Hop Synthesis (3) | 3.0 | 3.0 | 3.0 | 3.0 |

### Code Event (max 19)
| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| String Cleaner (5) | 5.0 | 5.0 | 3.3 | 0.0 |
| Log Parser (4) | 2.0 | 0.0 | 1.0 | 1.3 |
| LRU Cache (3) | 3.0 | 3.0 | 0.8 | 0.0 |
| File Indexer (2) | 2.0 | 2.0 | 1.8 | 0.7 |
| Task Runner CLI (2) | 0.0 | 0.0 | 0.5 | 0.0 |
| Constrained Diff Tool (3) | 1.3 | 2.0 | 1.3 | 0.0 |

## Key Takeaways

### Ornith-1.0-9B: The Efficiency King
- **90% of Gemma4's code ability** at 84% of the size (12.0 vs 13.3)
- **Near-perfect reasoning** (16.3/17, 96%)
- **Consistent** — zero variance on Code (12/19 every run)
- **1GB smaller, faster** — 5.3GB vs 6.3GB, ~207s vs ~221s
- **Weakness**: Agent tasks (11.7/18 vs Gemma4's 15.0) — struggles with Planning and Parsing

### Gemma4-12B: The Overall Leader
- **Best total score** (45.0/54, 83%)
- **Dominates Agent** (15.0/18) — especially Planning and Parsing
- **Solid Code** (13.3/19) — only model to pass Log Parser tests
- **Largest model** (6.3GB) — requires the most VRAM

### LFM2.5-8B: The Dark Horse
- **Ties Gemma4 on Reasoning** (16.7/17)
- **Most variable** — Code scores range from 6 to 12 across runs
- **Smallest model** (5.0GB) — best for low-VRAM setups

### Jackrong: Config-Dependent
- **Reasoning is strong** (16.3/17) when it works
- **Code is crippled** by llama.cpp thinking loop issue
- **Not a fair comparison** — scores reflect config limitation, not model ability

## Caveats
1. Jackrong scores are deflated by a llama.cpp config issue with DeepSeek-V4-Flash thinking traces
2. No model passed Task 5 (Task Runner CLI) — multi-file project output is genuinely hard
3. No model passed Task 6 "detects changes" — real diff algorithms are hard
4. Agent/Reason grading was applied to existing response files (not re-run)
5. All results on single RX 5700 XT with Vulkan — YMMV on different hardware

## Data
Full JSON: `agon-bench-results.json`
