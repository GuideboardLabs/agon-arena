# Baseline Fleet — June 2026

## Hardware Declaration

```
CPU: AMD Ryzen 5 5600X (6C/12T)
RAM: 32GB DDR4
GPU: AMD Radeon RX 5700 XT (8GB VRAM, Navi 10)
Backend: llama.cpp (Vulkan via RADV/Mesa)
Quantization: UD-Q4_K_XL (Gemma4, LFM2.5) / Q4_K_M (Ornith, Jackrong)
Context length: 32K
Threads: 8 inference, 12 batch
KV cache: q8_0
Temperature: 0.3
Max tokens: 4096 (Code, Agent) / 8192 (Reason)
```

## Full Results (3-run average, 180 max)

| Model | Quant | Code (60) | Agent (60) | Reason (60) | **Total (180)** |
|-------|:-----:|:---------:|:----------:|:-----------:|:---------------:|
| **Gemma4-12B** | Q4_K_M | **47.3** | **56.7** | **50.7** | **154.6** 🥇 |
| **Ornith-1.0-9B** | Q4_K_M | 36.3 | 50.0 | **55.7** | **142.0** 🥈 |
| **LFM2.5-8B-A1B** | UD-Q4_K_XL | 29.0 | 40.3 | 37.3 | **106.6** 🥉 |
| **Jackrong Qwen3.5-9B** | Q4_K_M | 23.0 | 40.3 | 17.7 | **81.0** |

*\\*Jackrong scores corrected after re-grading — original subagent graded thinking traces instead of final code blocks. Agent jumped from 26.0→40.3 after extracting actual code from 30-50KB thinking traces.*

## Per-Event Breakdown

### Code Event (60 pts)

| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| 1. String Cleaner | 8.0 | 8.0 | 5.7 | 2.3 |
| 2. Log Parser | 7.3 | 3.3 | 5.7 | 6.0 |
| 3. LRU Cache | 9.0 | 8.0 | 6.0 | 4.7 |
| 4. File Indexer | 8.0 | 7.0 | 3.7 | 4.0 |
| 5. Task Runner CLI | 10.0 | 6.7 | 4.7 | 6.0 |
| 6. Constrained Diff Tool | 5.0 | 3.3 | 3.3 | 0.0 |
| **Total** | **47.3** | **36.3** | **29.0** | **23.0** |

### Agent Event (60 pts)

| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| 1. Tool Calling | 9.7 | 9.7 | 10.0 | 7.7 |
| 2. Orchestration | 10.0 | 9.0 | 9.0 | 5.3 |
| 3. Error Handling | 10.0 | 9.0 | 6.3 | 8.0 |
| 4. Planning | 7.7 | 7.3 | 3.7 | 7.0 |
| 5. Parsing | 9.3 | 6.3 | 2.0 | 5.0 |
| 6. Decision-Making | 10.0 | 8.7 | 9.3 | 7.3 |
| **Total** | **56.7** | **50.0** | **40.3** | **40.3** |

### Reason Event (60 pts)

| Task | Gemma4 | Ornith | LFM2.5 | Jackrong |
|------|:------:|:------:|:------:|:--------:|
| 1. Logical Deduction | 2.7 | 8.3 | 0.0 | 2.0 |
| 2. Math Word Problem | 10.0 | 10.0 | 6.7 | 3.0 |
| 3. Constraint Satisfaction | 8.0 | 8.0 | 8.7 | 3.0 |
| 4. Counterfactual Reasoning | 10.0 | 10.0 | 8.0 | 3.0 |
| 5. Analytical Explanation | 10.0 | 10.0 | 8.7 | 4.0 |
| 6. Multi-Hop Synthesis | 10.0 | 9.3 | 5.3 | 2.7 |
| **Total** | **50.7** | **55.7** | **37.3** | **17.7** |

## Measured Throughput

| Model | tok/s | Notes |
|-------|:-----:|-------|
| Gemma4-12B QAT (UD-Q4_K_XL) | ~22 | q8_0 KV cache, 32K ctx |
| Ornith-1.0-9B (Q4_K_M) | ~47 | Fastest in the 8-9B tier |
| LFM2.5-8B-A1B (UD-Q4_K_XL) | ~105 | Verbose thinking traces inflate char count |
| Jackrong Qwen3.5-9B (Q4_K_M) | ~33 | Comparable to Qwen3.5 baseline |

## Key Observations

1. **Gemma4-12B is the overall winner** — dominates Agent (56.7/60) with near-perfect tool calling, orchestration, parsing, and decision-making. Strong across all events. Silver tier (154.6/180).

2. **Ornith-1.0-9B leads on Reasoning** (55.7/60) — strongest logical deduction and counterfactual reasoning. Code is its weakness (36.3) due to regex bugs and broken diff implementations. Silver tier (142.0/180).

3. **LFM2.5-8B is fastest but weakest** — 105 tok/s is 2-5x faster than competitors, but thinking traces contaminate code extraction and reasoning output. Bronze tier (106.6/180).

4. **Jackrong suffers from severe thinking-trace contamination** — 30-50KB of reasoning before any answer. Agent is its strongest event (40.3, Bronze). Reason is its weakest (17.7 — gets stuck in infinite thinking loops on logic puzzles). Needs work tier (81.0/180).

5. **Reason event is the strongest differentiator** — Gemma4 and Ornith both score 50+ while LFM2.5 scores 37.3 and Jackrong scores 17.7. The multi-hop synthesis task (Task 6) is the single best discriminator.

6. **All models struggle with Constrained Diff Tool** (Task 6 of Code) — none scored above 5/10. Myers diff algorithm implementations are consistently buggy.

7. **Gemma4 struggles with Logical Deduction** (Task 1 of Reason) — scored 2.7/10. Gets stuck in circular reasoning on the logic puzzle, unable to resolve the Bob/Dave ambiguity.

8. **LFM2.5 thinking traces** — the model outputs verbose thinking text (30K+ chars per task) even with `--reasoning off --reasoning-format none`. This contaminates code extraction and makes hidden tests fail. The actual code is correct but buried in thinking noise.

9. **Jackrong thinking traces are even worse** — the model outputs 30-50KB of thinking text per task, and in many cases the thinking never terminates with an actual answer. This is a DeepSeek-style architecture issue. The model iterates through dozens of draft code blocks before settling on a final version. Subagents MUST extract the LAST code block, not the first one, and not the thinking text itself.

10. **Grading subagents can be fooled by thinking traces** — the original Jackrong grading scored Agent at 26.0/60 because the subagent read the thinking trace and concluded "no function produced." The actual code was at the end of the file, buried under 30KB of reasoning. Re-grading by extracting the final code block raised Agent to 40.3/60. Always check the tail of the response file for the final code block before scoring 0.

## Grading Methodology

All grading was done by subagent delegation — reading prompt.txt and response.txt for each task across all 3 runs, scoring against the Agon-Bench rubric. Scores are 3-run averages. Hidden test results were noted but not used as the primary scoring mechanism (LRU Cache hidden tests are broken for all models).
