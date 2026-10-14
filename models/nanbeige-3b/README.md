---
license: apache-2.0
tags:
- nanbeige
- gguf
- quantization
- amd
- rocm
- llama.cpp
base_model:
- Nanbeige/Nanbeige4.2-3B
datasets:
- Nanbeige/Nanbeige4.2-3B
---

# Nanbeige4.2-3B — Looped Transformer GGUF

**2.4GB Q4_K_M GGUF for AMD ROCm / llama.cpp**

A 3B parameter model using a looped transformer architecture (22 physical layers × 2 loops = 44 effective layers). Built and benchmarked on an AMD RX 5700 XT (8GB VRAM) via the ROCmFPX fork of llama.cpp.

## Download

| File | Size | Quant | Link |
|------|------|-------|------|
| `nanbeige-3b-q4_k_m.gguf` | 2.4 GB | Q4_K_M | [Download](nanbeige-3b-q4_k_m.gguf) |

## Hardware Requirements

- **Minimum:** 8GB VRAM GPU (fits entirely at Q4_K_M with `-ngl 99`)
- **Recommended:** Any AMD GPU with ROCm support, or any Vulkan-capable GPU
- **RAM:** 4GB+ system RAM
- **Storage:** 2.4GB for the GGUF file

## Build (ROCmFPX fork)

This GGUF was built and tested with a custom fork of llama.cpp that adds Nanbeige architecture support. The fork is at [GuideboardLabs/ROCmFPX](https://github.com/GuideboardLabs/ROCmFPX).

```bash
git clone https://github.com/GuideboardLabs/ROCmFPX.git
cd ROCmFPX
mkdir build && cd build

# For AMD ROCm (tested on ROCm 5.7 with RX 5700 XT)
cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_HIPBLAS=ON

# For Vulkan (any GPU)
cmake .. -DCMAKE_BUILD_TYPE=Release -DLLAMA_VULKAN=ON

# For CPU-only
cmake .. -DCMAKE_BUILD_TYPE=Release

make -j$(nproc)
```

## Server Command

```bash
./bin/llama-server \
  --model /path/to/nanbeige-3b-q4_k_m.gguf \
  --port 8100 \
  --host 0.0.0.0 \
  --gpu-layers 99 \
  --mlock \
  --threads 6 \
  --threads-batch 6 \
  --cache-type-k q8_0 \
  --cache-type-v q8_0 \
  --temp 0.7 \
  --min-p 0.05 \
  --parallel 1
```

### Key flags explained

| Flag | Why |
|------|-----|
| `--gpu-layers 99` | Offload all layers to GPU. Model is 2.4GB, fits entirely in 8GB VRAM. |
| `--mlock` | Lock memory to prevent swapping. Critical for consistent inference speed. |
| `--cache-type-k q8_0` | KV cache in Q8_0 to save VRAM. The model has 262K context — this matters. |
| `--cache-type-v q8_0` | Same for value cache. |
| `--threads 6` | Match your CPU core count (6 physical cores on this test system). |
| `--temp 0.7` | Standard sampling temperature for agent/code tasks. |
| `--min-p 0.05` | Min-p sampling to filter low-probability tokens. |

## Performance (AMD RX 5700 XT, 8GB VRAM)

| Metric | Value |
|--------|-------|
| Prompt processing | 169.25 tok/s |
| Text generation | 44.88 tok/s |
| VRAM usage | 2.39 GB (fits entirely) |
| Context window | 262,144 tokens |

## Agon-Bench Results

Full benchmark: 3 events × 3 runs each on AMD RX 5700 XT via llama.cpp + Vulkan.

| Event | Run 1 | Run 2 | Run 3 | Avg | Pct |
|-------|-------|-------|-------|-----|-----|
| Agent | 23/24 | 22/24 | 24/24 | 23.0 | **95.8%** |
| Code | 18/25 | 16/25 | 16/25 | 16.7 | **66.7%** |
| Reasoning | 15/17 | 15/17 | 16/17 | 15.3 | **90.2%** |
| **Composite** | | | | | **84.2%** |

### Leaderboard position

| Rank | Model | Size | Composite | tok/s |
|------|-------|------|-----------|-------|
| 1 | Gemma4-26B-A4B | 16.9 GB | 84.6% | 13.5 |
| **2** | **Nanbeige4.2-3B** | **2.4 GB** | **84.2%** | **44.9** |
| 3 | Ornith-1.0-9B | 5.3 GB | 82.7% | 48.0 |
| 4 | Bonsai-27B-Q1_0 | 3.8 GB | 82.2% | 12.5 |

### Per-task breakdown

**Agent (95.8%)** — Near-perfect across the board. Tool Calling, Error Handling, Planning, Parsing, Decision-Making, and Multi-Step Research all at 100%. Only Orchestration (78%) and Memory-Augmented Agent (89%) show minor weakness.

**Code (66.7%)** — Inconsistent. Log Parser and LRU Cache at 100%. Regex Engine (33%) and String Cleaner (53%) are the weak points — the 3B training corpus limits breadth of coding knowledge.

**Reasoning (90.2%)** — Strong. Math Word Problems, Constraint Satisfaction, Counterfactual Reasoning, and Multi-Hop Synthesis all at 100%. Logical Deduction (67%) and Analytical Explanation (67%) are the only gaps.

## Architecture Notes

Nanbeige uses a **looped transformer** design:

- 22 physical transformer layers
- Each layer processes the hidden state twice (2 loops)
- Effective depth: 44 layers
- Total parameters: ~3B (non-embedding)
- Context window: 262,144 tokens
- Rope theta: 70,000,000 (supports the long context)

This gives a 3B model the reasoning depth of a 6-7B model, which is why it competes with models 5-7x its size on agent and reasoning tasks. The tradeoff is that code tasks benefit more from training corpus breadth than architectural depth.

## Conversion Notes

The GGUF was converted from the original safetensors using the ROCmFPX fork's converter:

```bash
python3 convert_hf_to_gguf.py /path/to/Nanbeige4.2-3B/ --outfile nanbeige-3b-f16.gguf --model nanbeige
./bin/llama-quantize nanbeige-3b-f16.gguf nanbeige-3b-q4_k_m.gguf Q4_K_M
```

The converter handles the looped architecture metadata automatically:
- `num_loops=2`
- `skip_loop_final_norm=false`
- Rope theta scaled for 262K context

## License

Apache-2.0 (same as the original Nanbeige4.2-3B model)

## Links

- [Original model on Hugging Face](https://huggingface.co/Nanbeige/Nanbeige4.2-3B)
- [ROCmFPX fork (llama.cpp with Nanbeige support)](https://github.com/GuideboardLabs/ROCmFPX)
- [Agon-Bench benchmark suite](https://github.com/GuideboardLabs/agon-arena)
- [Full dashboard](http://100.94.216.2:8765)
