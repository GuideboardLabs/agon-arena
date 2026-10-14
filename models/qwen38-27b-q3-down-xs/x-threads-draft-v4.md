# X Thread Drafts — RDNA1 8GB: the quant won, the kernel lost. (v2, with real capability + speed data)

All numbers measured on: AMD RX 5700 XT (8 GB, RDNA1/gfx1010) + Ryzen 5 1600, llama.cpp Vulkan fork,
GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1, COMPUTE DPM profile. One model at a time, no contention.

Capability = Agon Sprint (8 deterministic code/reason/agent tasks, hidden tests, same seed).
Speed = same harness, ~5600-token prompt, 200-token out (prompt+output share the 16k KV).

HF quant + full recipe: https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

---

## THREAD 1 — The Big Summary (master post)

**1 (hook)**
"Weeks ago I set out to run a 27B LLM on an 8 GB Radeon RX 5700 XT (RDNA1). The internet said: buy a bigger card. I don't have one. So I measured every lever instead. The result: a quant recipe that's the *best capability* of everything I compared, fits 8GB, and 8x faster than the stock wall. And I lost a whole other battle to a kernel. Here's both. 🧵

**2 (the wall)**
Stock 27B on this card = 2-3 tok/s, because an 11.9GB quant doesn't fit 8GB and pages over PCIe. Basically unusable.

Everyone with RDNA1 has this problem. Nobody has a magic fix. Yet.

**3 (the recipe, the real win)**
The win wasn't a kernel. It was:
- ONE env var: GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1  → +48.6% decode (forces residency, kills PCIe thrash)
- a per-tensor quant mix that FITS (Q3-DOWN-XS: FFN-down gets IQ2_XS, the rest a tuned mix)

100% stock quant types. Anyone can reproduce it.

**4 (the honest capability numbers — Agon Sprint, 8 deterministic tasks)**
| Quant | Score |
|---|---|
| Ours Q3-DOWN-XS | **21/26** |
| Unsloth UD-IQ2_S | 20/26 |
| Unsloth UD-IQ1_S | 19/26 |
| Ours 2-bit custom kernel | 18/26 |

Our quant beat Unsloth's 2-bit AND 1-bit on real tasks. That's the win.

**5 (same-harness 16k speed)**
| Quant | decode t/s |
|---|---|
| Unsloth IQ1_S (5.77GB) | 21.7 |
| Ours 2-bit kernel (7.79GB) | 18.1 |
| Unsloth IQ2_S (7.80GB) | 16.9 |
| Ours Q3-DOWN-XS (7.91GB) | 17.2 |
| Unsloth IQ3_XXS (10.18GB) | WEDGES THE GPU |

**6 (the slow king moment)**
The quant everyone praises — Unsloth IQ3_XXS — **does not run at 16k on 8GB.** It overflows VRAM, spills to CPU, and my GPU hit a hard recovery (RADV ErrorDeviceLost) mid-request. On a short prompt it crawled at 4.9 tok/s. The "slow king" isn't slow — it's a no-show on this card.

**7 (the kernel battle I lost — the honest part)**
I spent weeks building a Navi-specific 2-bit GEMV kernel. It IS real — faster than Unsloth's 2-bit (18.1 vs 16.9 t/s), fastest GEMV structure I measured (333 GB/s). But the 2-bit format itself is so lossy that my kernel model scored WORST on capability (18/26). The kernel was faster; the model was dumber. I lost that war, and I'll show the receipts in thread 4.

**8 (why the quant won)**
The recipe fits, the recipe runs, the recipe is *the most capable of the five I measured.* 86.5% of the 3-bit control that doesn't fit — but on real tasks it beat everything that DOES fit. That's not a PPL trick, that's a capability sweep.

**9 (link + humility)**
Full recipe, all numbers, the exact server command, the tensor mix — on the model card.
https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

Moral: on old AMD hardware, the biggest win is measuring the memory path and tuning the quant to fit — not hand-rolling a kernel. I learned that the expensive way. 🧵

---

## THREAD 2 — The Baseline (3-bit reality on this card)

**1** "Before the recipe, the baseline reality of 3-bit 27B on an 8GB RDNA1 card: it doesn't fit, so it crawls. I measured the whole ladder so you don't have to. 🧵

**2** The 100% control is UD-IQ3_XXS. PPL 7.16, but 11.9GB — needs ~2GB CPU spill on this card. On a 16k real task it WEDGED my GPU. PPL is meaningless if the model can't generate.

**3** The ladder (all measured):
- Q3-DOWN-UP-XS: 88.0%, doesn't fit
- Q3-DOWN-XS: 86.5%, 24 t/s ✓
- Q3-UP-XS: 85.9%, 24 t/s
- Q3-GATE-PROTECT: 85.6%, 24 t/s

**4** The key insight: the FFN-down projection matters most. Put IQ2_XS there, not the up paths. That's the "DOWN-XS" name. Small placement choice, real capability gain.

**5** The spill trap is real: DOWN-UP-XS is +1.5 pts but +340MB → halves your speed. A model that spills is not a model that works. Fit first, quality second.

**6 (close)** So the realistic 3-bit on 8GB RDNA1 = Q3-DOWN-XS. It fits, it's the most capable thing I could fit, and it beats the quant that everyone praises but that can't actually run here.

---

## THREAD 3 — The Breakthrough (recipe + GGUF + HF link)

**1 (hook)** "The breakthrough wasn't a kernel. It was realizing that 8GB RDNA1 could run a 27B at good speed with the RIGHT quant + ONE env var. I published the GGUF + recipe. Here's how. 🧵

**2 (the env var)** GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1 → +48.6% decode. The card was thrashing PCIe, not computing. Forcing residency was worth more than any kernel I built.

**3 (the recipe)** Per-tensor mix, 100% stock types:
- FFN-down → IQ2_XS (the key)
- rest → IQ2_XXS / IQ1_M / IQ3_S / IQ4_XS
- norms/embd → F32
- 0 custom types, 0 custom kernels, 0 custom GPU needs.

**4 (capability, real)** Agon Sprint: 21/26. Beats Unsloth's IQ2_S (20) and IQ1_S (19) on the same card, same harness.

**5 (speed, real)** 24 t/s sustained (frozen tg128 protocol), ~17 t/s on a single cold 16k request. Both measured. It runs.

**6 (reproducible)** Stock types, stock flags, one env var, one COMPUTE profile. If you have an 8GB Radeon and this GGUF + 2 lines, you get this. No fork, no kernel, no black box.

**7 (link)** GGUF + full instructions + the honest table on the model card:
https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

Go run a 27B on 8GB.

---

## THREAD 4 — The Kernel (the loss, told straight with science)

**1 (hook)** "I built a custom Navi/RDNA1 2-bit GEMV kernel for llama.cpp. It was faster. And it lost. Here's what I learned the hard way — the full kernel story. 🧵

**2 (the win, genuinely)** For a single matrix-vector layer, my kernel (iq2_rdna, 2.19 bpw) hit 333 GB/s vs 226 for stock IQ2_XXS. A measured ~47% faster GEMV on this card. Real. And end-to-end, my 2-bit model decoded faster than Unsloth's 2-bit (18.1 vs 16.9 t/s).

**3 (the loss)** But the 2-bit FORMAT is dumb. On Agon Sprint (8 tasks), my kernel 2-bit model scored 18/26 — worse than Unsloth's 1-bit (19) and 2-bit (20). The kernel was faster but the model was dumber. You cannot kernel your way out of a 2-bit quality wall.

**4 (the science — GFX1010)** I verified gfx1010 (RDNA1) has NO integer dot-product. No v_dot8, no v_dot4. A lot of the "miracle 2-bit" kernel design assumes an ISA that isn't on this chip. I documented this with llvm-mc. It falsified a core claim driving this whole thread of work.

**5 (what I'd do differently)** I put weeks into a custom kernel to squeeze speed, and the real 8x speedup was already sitting in an env var + a fit-minded quant. The kernel was solving the wrong problem. Humility: I should have measured the memory path first.

**6 (the science wins)** I don't regret it — I characterized the GPU, falsified an ISA claim, and the GEMV win is real and published. But the RECIPE won. The quant won. The kernel is a research artifact, not a competitor.

**7 (links)** Kernel write-up: GitHub. Quant + recipe: https://huggingface.co/guideboardlabs/Qwen3.8-27B-Q3-DOWN-XS-GGUF

Buy the card. Or measure the memory path. I chose the second, eventually. 🧵

---
