# X Thread Drafts — RDNA1 8GB recipe + kernel research

All numbers measured on: AMD RX 5700 XT (8 GB, RDNA1/gfx1010) + Ryzen 5 1600, llama.cpp Vulkan.
Frozen PPL protocol: wikitext-2-raw-v1 test, 8x512 chunks, batch 128, `-ngl 999`.

HF model + full recipe: https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

---

## THREAD 1 — The Big Summary (the master post)

---
**Tweet 1 (hook)**
"I spent weeks trying to run a 27B LLM on an 8 GB Radeon RX 5700 XT (RDNA1). The stock answer is: you can't, or you crawl at 2-3 tok/s. I got it to 24.5 tok/s at 86.5% of the best 3-bit quant (vs bf16 it's lower — see below). Fully resident, no custom kernel. Here's the whole story. 🧵

**Tweet 2 (the wall)**
An 11.9GB UD-IQ3_XXS quant of Qwen3.8-27B doesn't fit 8GB. So it pages through PCIe at ~13 GB/s. Decode: ~2-3 tok/s. Basically unusable for real work.

Everyone says: buy more VRAM. I don't have that option. So I measured everything.

**Tweet 3 (the first ceiling break — residency)**
The single biggest win was NOT a model change. It was ONE environment variable:

GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1

Without it, part of the hot working set lands in host-visible VRAM and the card thrashes PCIe. With it: +48.6% decode. This is free for everyone.

**Tweet 4 (the recipe)**
Then I tuned the quantization per-tensor — not one blob, but a mix chosen by measuring every combination on the GPU.

The winner: Q3-DOWN-XS. 7.91 GB, fully resident, zero CPU spill.

**Tweet 5 (the numbers)**
Result vs the stock wall:
- 2-3 tok/s -> 24.48 tok/s  (8x)
- 86.5% of the UD-IQ3_XXS 3-bit control (the 100% reference) — NOTE: that's vs 3-bit, NOT bf16. A bf16 anchor was never measured, so vs true full precision we're below 86.5%. But the 3-bit control doesn't even fit on 8GB.
- zero spill, zero custom kernel

PPL 8.2691 vs 7.1553 (the 3-bit control).

**Tweet 6 (why it's reproducible)**
100% stock quant types. Stock llama.cpp. Stock env var. Stock AMD COMPUTE profile.

No fork. No custom kernel. Anyone with an 8GB Radeon and this GGUF + 2 lines gets the same result.

**Tweet 7 (the honest ceiling)**
The theoretical ceiling on 8GB is ~88% (Q3-DOWN-UP-XS) but it's +340 MiB -> spills -> drops to 13.3 tok/s. Measured and rejected.

86.5% @ 24.5 tok/s fully resident IS the practical ceiling on 8GB RDNA1. That's the recipe.

**Tweet 8 (link + close)**
Full recipe, all the numbers, the exact server command, and the model:
https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

The moral: the biggest win on old AMD hardware is measuring the memory path and tuning the quant to fit — not buying a bigger card. 🧵 end

---

## THREAD 2 — Baseline (typical 3-bit performance on this card)

**Tweet 1 (hook)**
Baseline reality check: what does a typical 3-bit 27B actually do on an 8GB RDNA1 card? Short answer: it doesn't fit, so it crawls. I measured the whole ladder. Here's the honest baseline. 🧵

**Tweet 2 (control)**
The 100% control is UD-IQ3_XXS. 11.9GB. PPL 7.155. But on 8GB it needs ~4GB of CPU spill, so decode collapses.

PPL is meaningless if the model can't generate.

**Tweet 3 (the ladder — real numbers)**
I measured every Q3-family config on the GPU:
- Q3-DOWN-UP-XS: 88.0%, PPL 8.128, doesn't fit
- Q3-DOWN-XS: 86.5%, PPL 8.269, 24.48 t/s ✓
- Q3-UP-XS: 85.9%, PPL 8.327, 24.42 t/s
- Q3-GATE-PROTECT: 85.6%, PPL 8.356, 24.19 t/s

**Tweet 4 (the finding)**
The FFN-down projection matters more than the rest. Putting IQ2_XS on the down paths (not the up) is the single best placement.

That's the "DOWN-XS" recipe.

**Tweet 5 (the spill trap)**
Big trap: adding quality so the model barely overflows = disaster. DOWN-UP-XS (88%) is +1.5 quality pts but +340MB -> 13.3 tok/s. That's -46% speed for +1.5 pts. Measured reject.

A model that spills is not a model that works.

**Tweet 6 (the baseline conclusion)**
So "3-bit on 8GB RDNA1" = Q3-DOWN-XS at 24.5 tok/s is the realistic baseline. Anything more spills and halves your speed. Anything less is leaving quality on the table.

That's the honest baseline for this card class.

---

## THREAD 3 — The Breakthrough (recipe + custom GGUF + link)

**Tweet 1 (hook)**
"The 'breakthrough' wasn't a kernel. It was finding that 8GB RDNA1 could run a 27B at 24.5 tok/s with the RIGHT quantization recipe and ONE env var. I published the GGUF + full recipe. Here it is. 🧵

**Tweet 2 (the env var — the real story)**
The single biggest measured win on this card:
GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1  -> +48.6% decode.

The card was spending most of its time shuffling state over PCIe, not computing. Forcing residency was worth more than any kernel change.

**Tweet 3 (the recipe)**
The recipe is a per-tensor quant mix:
- FFN down -> IQ2_XS (the key)
- rest -> IQ2_XXS / IQ1_M / IQ3_S / IQ4_XS mix
- norms / embd -> F32
- 0 custom types, 0 custom kernels

**Tweet 4 (the numbers)**
7.91 GiB. Fully resident. Zero spill.
Decode: 24.48 tok/s (stock: 2-3)
Quality: 86.5% of the UD-IQ3_XXS 3-bit control (NOT bf16 — that's unmeasured and lower)
PPL: 8.269 vs 7.155 (the 3-bit control that doesn't fit)

**Tweet 5 (reproducible)**
Because it's stock types + stock flags, ANYONE can reproduce it. No fork. No kernel. Just:
- llama.cpp Vulkan
- this GGUF
- GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1
- COMPUTE DPM profile

**Tweet 6 (link)**
GGUF + full instructions on the model card:
https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

Go run a 27B on 8GB.

---

## THREAD 4 — The Kernel (research-only, no head-to-head)

**Tweet 1 (hook)**
"I built a custom RDNA1 Vulkan GEMV kernel for llama.cpp. It's the fastest GEMV structure I measured on this card. But it does NOT win end-to-end, and I'm going to tell you why. This is a research thread, not a victory lap. 🧵

**Tweet 2 (the win)**
For a single GEMMV (matrix-vector) layer, my kernel (iq2_rdna, 2.19 bpw) hit 333 GB/s vs 226 for stock IQ2_XXS. A real, measured ~47% faster kernel on this card.

**Tweet 3 (the catch)**
But at the model level, the 2-bit format costs ~9 points vs our 86.5% 3-bit recipe (77.7% vs 86.5% — both measured relative to the 3-bit control, not bf16). That's SYSTEMIC to the format — not fixable by the kernel. The kernel is faster but the model is dumber.

**Tweet 4 (the reason — honest)**
This is the honest part: I verified gfx1010 (RDNA1) has NO integer dot-product. No v_dot8, no v_dot4. The ISA a lot of the "miracle" 2-bit kernels assume just isn't on this chip. So the whole 2-bit race on RDNA1 is a quality problem, not a kernel problem.

**Tweet 5 (the falsification)**
I documented this properly — including that the integer-dot claim driving a lot of RDNA 1 kernel work is falsified on gfx1010. We tested it on the actual GPU with llvm-mc.

**Tweet 6 (the conclusion)**
So: custom kernel = fastest GEMV on the card, but production STAYS on stock recipe (Q3-DOWN-XS at 24.5 tok/s, 86.5%).

The kernel is a real research artifact. The recipe is the actual win.

**Tweet 7 (link)**
Kernel writeup + GFX1010 ISA falsification is coming to GitHub. Recipe + GGUF live here:
https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF
```
