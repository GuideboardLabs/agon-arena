---
license: apache-2.0
tags:
- qwen
- qwen3.5
- gguf
- quantization
- amd
- vulkan
- rDNA1
- Radeon
- llama.cpp
- local-llm
base_model:
- Qwen/Qwen3.8-27B
datasets:
- Qwen/Qwen3.8-27B
---

# Qwen3.8-27B — Q3-DOWN-XS GGUF (fully resident on 8 GB RDNA1)

A **7.91 GiB** GGUF of Qwen3.8-27B, quantized so that the **entire model fits in 8 GB VRAM** with **zero CPU spill**, tuned and measured on an **AMD Radeon RX 5700 XT (RDNA1, gfx1010, 8 GB)**.

This is the production recipe that took a 27B model from an unusable **2-3 tok/s** (paging an 11.9 GB blob through PCIe) to a fully-resident **24.48 tok/s at 86.5% of the UD-IQ3_XXS 3-bit control** — the result of measuring every quantization/format/memory lever on the actual GPU.

**It uses only stock llama.cpp quant types.** No custom kernels required. You can run it with any recent stock llama.cpp.

| File | Size | bpw | PPL (wikitext-2, 8x512) | Quality (vs UD-IQ3_XXS 3-bit) | Decode |
|---|---|---|---|---|---|
| **Qwen3.8-27B-Q3-DOWN-XS.gguf** | 7.68 GiB | ~3.2 | **8.2691** | **86.5%** | **24.48 tok/s** |

> **What "86.5%" means — please read:** this is **86.5% of the UD-IQ3_XXS 3-bit control (PPL 7.1553)**, NOT 86.5% of bf16. A bf16 anchor was never built, so true-full-precision intelligence is unmeasured and would be lower. The comparison is apples-to-3-bit: our recipe is 86.5% of the best 3-bit quant that *doesn't even fit* on 8 GB, while running 8x faster than the one that does. Treat it as a 3-bit-relative number, not a full-precision-relative number.

Hardware measured on: RX 5700 XT (8 GB, RDNA1) + Ryzen 5 1600, llama.cpp Vulkan build.

---

## Why "Q3-DOWN-XS" (the recipe)

The model is a **per-tensor-tuned mix** of stock quant types, chosen by testing every combination on the GPU. "DOWN-XS" = the FFN *down* projections use IQ2_XS while the rest uses a higher-quality mix. Full ladder (measured, same frozen PPL protocol):

| Config | PPL | Qual% | Decode |
|---|---|---|---|
| UD-IQ3_XXS (control, 11.9GB) | 7.1553 | 100% | doesn't fit 8GB |
| Q3-DOWN-UP-XS (ceiling) | 8.1278 | 88.0% | doesn't fit all-GPU |
| **Q3-DOWN-XS (THIS)** | **8.2691** | **86.5%** | **24.48 tok/s** |
| Q3-UP-XS | 8.3272 | 85.9% | 24.42 |
| Q3-GATE-PROTECT (old prod) | 8.3561 | 85.6% | 24.19 |

The 88% ceiling needs +340 MiB and overflows 8 GB all-GPU (drops to 13.3 tok/s with spill) — measured and rejected. **86.5% @ 24.48 tok/s fully resident is the practical ceiling on 8 GB.**

---

## How to run it (the recipe)

### 1. Serve it with stock llama.cpp (Vulkan)

```bash
GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1 llama-server \
  -m Qwen3.8-27B-Q3-DOWN-XS.gguf \
  -c 16384 -np 1 -ngl 999 \
  -ctk q8_0 -ctv q8_0 -fa on \
  --jinja --reasoning off --reasoning-format none \
  --port 8101 --host 0.0.0.0
```

### 2. The ONE environment variable that matters

```
GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1
```

This is the single biggest measured win: **+48.6% decode throughput**. Without it, part of the hot working set gets allocated in host-visible (PCIe-accessible) VRAM, and the card thrashes through it at ~13 GB/s instead of the resident ~300 GB/s. The fix forces full residency. **An 8 GB card running this model at 24.5 tok/s instead of 2-3 tok/s is because of this one env var + a model that actually fits.**

### 3. Set the GPU to COMPUTE DPM profile

AMD cards default their power state to the lowest dynamic profile. Set the DPM to the compute profile so the clocks stay up:

```bash
# as root
rocm-smi --setperflevel 5        # COMPUTE
# or via sysfs (RX 5700 XT):
echo COMPUTE | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
```

### 4. Keep it fully resident (`-ngl 999`)

Offload every layer. Do NOT let layers spill to CPU — a single CPU layer's latency lands on top of the GPU's, killing throughput (measured: 24.48 -> 13.34 tok/s with one spilled layer).

---

## Why this is reproducible (no custom kernel)

- **100% stock quant types** (IQ2_XS, IQ4_XS, IQ2_XXS, IQ1_M, IQ3_S, F32...) — verified, zero custom/RDNA tensor types.
- **Stock llama.cpp** — the fork is a superset; upstream runs this file unchanged.
- **Stock env var + stock AMD setting + stock server flags.**

An average user with plain llama.cpp + this file + the env var + COMPUTE DPM gets the same result. That's the point of the recipe.

---

## What's NOT in this model (the custom kernel)

We also built a **custom RDNA1 Vulkan kernel** (`iq2_rdna`, 2.19 bpw) that is the **fastest GEMV structure measured on this card** (333 GB/s vs 226 for stock IQ2_XXS). But at model level the 2-bit format costs ~9 quality points (77.7% vs 86.5%) — systemic to the format, not fixable by the kernel. So **production stays on this Q3-DOWN-XS recipe**. The kernel is published separately as research (GFX1010 ISA falsification, full kernel idea rundown) — see [RDNA1-Kernel-Research].

---

## Build / provenance

- Base: `Qwen/Qwen3.8-27B`
- Quantized with llama.cpp `llama-quantize`, per-tensor IQ types, iMatrix-calibrated.
- Quality protocol: frozen wikitext-2-raw-v1 test set, 8 x 512 chunks, batch 128, `-ngl 999`, same build/GPU for every config. Every number above measured, not estimated.

## License

Apache-2.0. Model: Qwen3.8-27B (Apache-2.0). See original for details.
