# Agon-Bench Results

## 8GB VRAM Class (7 models)

| Model | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|-----------|------------|----------|-----------|----|-------|
| **Holo-3.1-9B-Coder** | 15.7 | 14.7 | 12.7 | **43.1** | 80% | 36.6 |
| **Gemma4-12B** | 15.0 | 16.7 | 10.3 | **42.0** | 78% | 21.6 |
| **Qwen3.5-9B** | 14.0 | 16.0 | 10.3 | **40.3** | 75% | 41.9 |
| **Ornith-1.0-9B** | 11.7 | 16.3 | 12.0 | **40.0** | 74% | 45.4 |
| **VibeThinker-3B** | 15.3 | 17.0 | 7.0 | **39.0** | 72% | 82.7 |
| **LFM2.5-8B** | 10.7 | 16.7 | 8.8 | **36.2** | 67% | 91.1 |
| **Holo-3.1-9B** | 5.3 | 15.0 | 7.0 | **27.3** | 51% | 36.6 |

## 4GB VRAM Class (1 model)

| Model | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|-----------|------------|----------|-----------|----|-------|
| **VibeThinker-3B** | 15.3 | 17.0 | 7.0 | **39.0** | 72% | 82.7 |

## 24GB VRAM Class (VRAM split: 6-7GB GPU, rest system RAM)

| Model | Agent (18) | Reason (17) | Code (19) | Total (54) | % | tok/s |
|-------|-----------|------------|----------|-----------|----|-------|
| **SuperQwen-35B-A3B** | 18.0 | 12.0 | 18.3 | **48.3** | 89% | 10.1 |

## Holo-3.1-9B-Coder — Detailed Results

### Code Event (19 pts)
- Run 1: **14/19** (74%) — String Cleaner 4/5, Log Parser 1/4, LRU Cache 3/3, File Indexer 2/2, Task Runner 1/2, Diff Tool 3/3
- Run 2: **13/19** (68%) — String Cleaner 4/5, Log Parser 2/4, LRU Cache 3/3, File Indexer 1/2, Task Runner 1/2, Diff Tool 2/3
- Run 3 (solo): **11/19** (58%) — String Cleaner 0/5, Log Parser 2/4, LRU Cache 3/3, File Indexer 2/2, Task Runner 1/2, Diff Tool 3/3
- **Mean: 12.7/19 (67%)**

### Agent Event (18 pts)
- Run 1: **15/18** (83%) — Tool Calling 3/3, Orchestration 2/3, Error Handling 4/4, Planning 2/2, Parsing 1/3, Decision-Making 3/3
- Run 2: **17/18** (94%) — Tool Calling 3/3, Orchestration 2/3, Error Handling 4/4, Planning 2/2, Parsing 3/3, Decision-Making 3/3
- Run 3 (solo): **15/18** (83%) — Tool Calling 3/3, Orchestration 2/3, Error Handling 4/4, Planning 2/2, Parsing 1/3, Decision-Making 3/3
- **Mean: 15.7/18 (87%)**

### Reason Event (17 pts)
- Run 1: **14/17** (82%) — Logical Deduction 2/2, Math Word 3/3, Constraint Sat. 3/3, Counterfactual 3/3, Analytical Expl. 2/3, Multi-Hop 2/3
- Run 2: **15/17** (88%) — Logical Deduction 2/2, Math Word 3/3, Constraint Sat. 3/3, Counterfactual 3/3, Analytical Expl. 1/3, Multi-Hop 3/3
- Run 3 (solo): **15/17** (88%) — Logical Deduction 2/2, Math Word 3/3, Constraint Sat. 3/3, Counterfactual 3/3, Analytical Expl. 2/3, Multi-Hop 3/3
- **Mean: 14.7/17 (86%)**

### vs Base Holo-3.1-9B
| Metric | Base | Coder | Delta |
|--------|------|-------|-------|
| **Code** | 7.0 (37%) | **12.7 (67%)** | **+5.7 pts (+30%)** |
| **Agent** | 5.3 (30%) | **15.7 (87%)** | **+10.4 pts (+57%)** |
| **Reason** | 15.0 (88%) | 14.7 (86%) | -0.3 pts (-2%) |
| **Total** | 27.3 (51%) | **43.1 (80%)** | **+15.8 pts (+29%)** |

### Key Observations
- **Code**: Massive improvement. LRU Cache went from 0→3 (perfect), Diff Tool from 1.7→2.7, Task Runner from 0→1.0. String Cleaner still inconsistent (varies 0-4/5).
- **Agent**: Huge improvement. Error Handling went from 0→4 (perfect), Decision-Making from 1→3, Orchestration from 0→2. Parsing still weak (1.7/3).
- **Reason**: Slight regression. Multi-Hop Synthesis dropped from 3→2.7. Otherwise identical to base.
- **Efficiency**: Same as base (~36.6 tok/s) — same architecture, same size.
- **Architecture**: Qwen3.5-based, code-specialized LoRA (r=8, alpha=16). Claims 63.4% HumanEval+ vs 52.4% base.

## Holo-3.1-9B (Base) — Detailed Results

### Code Event (19 pts)
- Run 1: **10/19** (53%) — String Cleaner 4/5, Log Parser 2/4, LRU Cache 0/3 (syntax error), File Indexer 2/2, Task Runner 0/2, Diff Tool 2/3
- Run 2: **5/19** (26%) — String Cleaner 0/5 (runtime error), Log Parser 2/4, LRU Cache 0/3, File Indexer 2/2, Task Runner 0/2, Diff Tool 1/3
- Run 3: **6/19** (32%) — String Cleaner 0/5 (syntax error), Log Parser 2/4, LRU Cache 0/3, File Indexer 2/2, Task Runner 0/2, Diff Tool 2/3
- **Mean: 7.0/19 (37%)**

### Agent Event (18 pts)
- Run 1: **7/18** (39%) — Tool Calling 2/3, Orchestration 0/3, Error Handling 0/4, Planning 2/2, Parsing 0/3, Decision-Making 3/3
- Run 2: **4/18** (22%) — Tool Calling 2/3, Orchestration 0/3, Error Handling 0/4, Planning 2/2, Parsing 0/3, Decision-Making 0/3
- Run 3: **5/18** (28%) — Tool Calling 3/3, Orchestration 0/3, Error Handling 0/4, Planning 2/2, Parsing 0/3, Decision-Making 0/3
- **Mean: 5.3/18 (30%)**

### Reason Event (17 pts)
- Run 1: **15/17** (88%) — Logical Deduction 2/2, Math Word 3/3, Constraint Sat. 3/3, Counterfactual 3/3, Analytical Expl. 1/3, Multi-Hop 3/3
- Run 2: **15/17** (88%) — same pattern
- Run 3: **15/17** (88%) — same pattern
- **Mean: 15.0/17 (88%)**

## SuperQwen-35B-A3B — Detailed Results

### Code Event (19 pts)
- Run 1: **19/19** (100%)
- Run 2: **17/19** (89%) — Task 1 truncation edge case, Task 6 diff broken
- Run 3: **19/19** (100%)
- **Mean: 18.3/19 (96.5%)**

### Agent Event (18 pts)
- Run 1: **18/18** (100%)
- Run 2: **18/18** (100%)
- Run 3: **18/18** (100%)
- **Mean: 18.0/18 (100%)**

### Reason Event (17 pts)
- Run 1: **11/17** (65%) — Math word problem 0/3, Counterfactual 2/3, Analytical Expl. 1/3
- Run 2: **13/17** (76%) — Math word problem 0/3, Analytical Expl. 2/3
- Run 3: **12/17** (71%) — Logical Deduction 1/2, Math word problem 0/3, Analytical Expl. 2/3
- **Mean: 12.0/17 (70.6%)**

## Methodology
- All models: Q4_K_M quantization
- Hardware: AMD RX 5700 XT (8GB VRAM)
- Backend: llama.cpp + Vulkan (AMD radv/mesa)
- 3 runs per model per event, reported as mean
- Hidden test grading (no model sees test cases)
- 24GB class models use VRAM split: 6-7GB GPU, rest system RAM
- **Harness fix (2026-06-29)**: Fixed code fence extraction regex that was eating code when responses started with ```. All Holo-3.1-9B scores are regraded with the fixed harness.
- **Solo runs**: Run 3 of each event for Holo-3.1-9B-Coder was run solo (no concurrent model load) to ensure full model attention.
