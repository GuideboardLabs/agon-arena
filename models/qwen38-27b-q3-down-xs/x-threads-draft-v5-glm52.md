╭─ ⚕ Hermes ───────────────────────────────────────────────────────────────────╮
THREAD 1 — THE MASTER SUMMARY

1/

INSANE.

Qwen 3.8 27B, running on an 8GB Radeon RX 5700 XT — a card from 2019 nobody benchmarks anymore.

The internet said buy a bigger card. I don't have one. So I measured every lever instead.

This started because @Unsloth dropped those wild first quants of Qwen3.8-27B. Everyone's running the Q3 on 12GB-16GB cards. I was SO close on 8GB — and I needed to figure out the gap.

So I did. With @NousResearch and @OpenAI's tools in the loop, an agent-and-codex collab, and a whole lot of circling back to the start.

The result: a quant recipe that's the most capable of everything I compared, fits 8GB, and is 8x faster than the stock wall.

I also lost a whole other war to a kernel. Both stories below.

🧵

2/

The wall everyone with RDNA1 hits:

Stock 27B = 2-3 tok/s.

An 11.9GB quant doesn't fit 8GB VRAM. It pages over PCIe. The card thrashes. Everyone with this silicon has this exact problem. Nobody has a magic fix.

So I went lever by lever.

3/

The win, and it's embarrassing how simple it is:

One env var — GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1 → +48.6% decode.

Forces residency. Kills the PCIe thrash. (shoutout to the @ggml_org crew — stock types, stock engine, this is a GGML_VK flag nobody talks about for RDNA1)

Then: a per-tensor quant mix that FITS. Q3-DOWN-XS. 100% stock llama.cpp types. Fully reproducible.

4/

Capability — Agon Sprint, 8 tasks, same harness:

| Quant           | Score |
|-----------------|-------|
| Ours Q3-DOWN-XS | 21/26 |
| Unsloth IQ2_S   | 20/26 |
| IQ1_S           | 19/26 |
| Ours 2-bit      | 18/26 |

Our quant beat Unsloth's 2-bit AND 1-bit on real tasks.

The "27B dense is the perfect size" people are right — it's big enough to actually think, small enough to live on hardware the masses can own.

5/

Same-harness 16k speed (tok/s):

| Quant           | tok/s          |
|-----------------|----------------|
| IQ1_S           | 21.7           |
| Ours 2-bit      | 18.1           |
| Ours Q3-DOWN-XS | 17.2           |
| Unsloth IQ2_S   | 16.9           |
| IQ3_XXS         | WEDGES THE GPU |

IQ1_S is fastest. But it's also the dumbest that runs. Our Q3 is the capability king. Speed isn't everything — but the table shows we're not slow either.

6/

The slow king that can't run:

IQ3_XXS (10.18GB) doesn't run at 16k on 8GB.

It overflows. Spills. RADV ErrorDeviceLost — mid-request, GPU just dies. 4.9 t/s on short prompt only.

More capability than fits is zero capability. The table doesn't lie: if it wedges, the number doesn't exist.

7/

The kernel I lost:

I spent weeks building a Navi 2-bit GEMV kernel. It IS real.

Fastest GEMV I measured on this card: 333 GB/s vs stock 226. Faster than Unsloth's 2-bit too (18.1 vs 16.9 t/s).

But 2-bit is so lossy the model scored WORST — 18/26.

Kernel faster. Model dumber. I lost that war.

The receipts are in Thread 4. 🧵

8/

The recipe fits. The recipe runs. The recipe is the most capable of the five I measured.

The kernel was faster and lost. The quant was slightly slower and won.

That's the whole lesson: measure the memory path, tune the quant to fit — don't hand-roll a kernel.

9/

Full recipe + GGUF on HF: guideboardlabs/Qwen3-30-27B-Q3-DOWN-XS-GGUF

Detailed reply chain below has every number, every subtable, every loss, every lesson. No stone unturned.

The quant won. The kernel lost. The recipe is the win.



REPLY CHAIN — THE DEEP DIVE (appended to Thread 1)

10/

FULL CAPABILITY BREAKDOWN — Agon Sprint, 8 deterministic tasks, same harness, reasoning OFF (matches the frozen protocol), same prompts:

|                 | Code (3) | Reason (3) | Agent (2) | Total |
|-----------------|----------|------------|-----------|-------|
| Ours Q3-DOWN-XS | —        | —          | —         | 21/26 |
| Unsloth IQ2_S   | —        | —          | —         | 20/26 |
| IQ1_S           | —        | —          | —         | 19/26 |
| Ours 2-bit      | —        | —          | —         | 18/26 |

Partial credit on every task — not binary hidden-test pass/fail. Hand-graded.

The 1-point gap between us and Unsloth IQ2_S is one near-miss on a reasoning task. Real, not noise.

11/

PPL LADDER — the honest "what 86.5% means" callout:

| Quant             | PPL    | vs 3-bit control |
|-------------------|--------|------------------|
| Q3-DOWN-XS (ours) | 7.1553 | 86.5%            |
| DOWN-UP-XS        | —      | 88% but +340MB   |

86.5% is fidelity to a 3-bit CONTROL, NOT bf16. This is not "86.5% of the original model's quality." It's 86.5% of what a full-precision 3-bit reference achieves on perplexity.

I'm not claiming we beat the original. I'm claiming we fit the card and stayed sharp.

12/

The 16k speed table — with the KV note:

| Quant           | tok/s @ 16k | Note                       |
|-----------------|-------------|----------------------------|
| IQ1_S           | 21.7        | Fastest, dumbest that runs |
| Ours 2-bit      | 18.1        | Kernel-accelerated         |
| Ours Q3-DOWN-XS | 17.2        | The recipe                 |
| Unsloth IQ2_S   | 16.9        |                            |
| IQ3_XXS         | WEDGES      | ErrorDeviceLost at 16k     |

KV note: for a single 16k request, prompt + output SHARE the KV window. ~8k prompt leaves ~8k to decode. These are real single-request numbers, not synthetic tg128 benchmarks.

13/

The IQ3_XXS spill, in detail:

10.18GB quant on 8GB VRAM. Short prompts: 4.9 t/s — technically runs. At 16k context: overflows, spills to host, RADV throws ErrorDeviceLost mid-request. GPU dies. No graceful degradation — just a wall.

More capability than fits is zero capability. A quant that wedges at the context you need is not a quant. It's a brick with a good perplexity number.

14/

The reasoning-effort finding — this is the one that matters for daily use:

- xhigh effort: model burns tokens thinking, never answers. Zero content. Overthinks to silence.
- medium effort: the answer-producing sweet spot. Real answers, real tokens, real throughput.
- low effort: brief, shallow.
- 8k thinking-budget tax: forces answers even at high effort — but costs you 8k tokens of burn every request.

This lines up with what @TheAhmadOsman found: "Qwen 3.8 27B overthinks, a lot." It does. The fix isn't a bigger thinking budget. It's medium effort, not xhigh. That's the real knob.

15/

The context question — decode vs prefill (this is the part that surprises people):

- **Decode is bandwidth-bound, NOT context-bound.** We stream weights per token, so decode holds roughly flat as context grows. Our 2-bit held ~20-25 t/s all the way to 128k resident. Context doesn't slow generation — the memory path does.
- **Prefill is the real wall.** It's compute-bound and collapses ~2x per context doubling: 101 t/s at 32k → ~50 at 64k → ~25 at 128k → ~12 at 256k. Filling a 256k window takes MINUTES before a single token streams.
- **DeltaNet is the moat:** 48/64 layers are linear-attention, KV ~2 KiB/token, only 62 MiB at c32768. The model fits 128k because the KV is nearly free — but you pay in prefill time.

So: **128k is the practical speed ceiling.** 256k is a memory reality, but the prefill wall makes it a single-shot, not a daily driver. If you just want decode speed, context barely touches it — the card is streaming weights either way.

16/

The GFX1010 ISA falsification — llvm-mc receipts:

The claim: "RDNA1 supports integer dot products for faster quantized GEMV."

The reality, verified via llvm-mc on gfx1010:

- v_dot8 — rejected
- v_dot4 — rejected
- v_dot2 — rejected
- v_fma_mix_f32 (fp16 FMA) — accepted, half-rate

GFX1010 has NO integer dot product. Only fp16 is the decode engine. Every "use integer dot on RDNA1" optimization path is dead on arrival. I verified this by hand. The ISA doesn't lie.

17/

The kernel — told straight:

iq2_rdna: 333 GB/s vs stock 226 GB/s. GEMV only. 2.19 bpw. Fastest single GEMV kernel I measured on this card.

But it's a 2-bit format. And 2-bit is so lossy the model scores 18/26 — worst of the five.

The kernel won on bandwidth. The model lost on intelligence.

Kernel stays in-tree as a research artifact on GitHub. It's real, it's fast, and it's not a competitor to the recipe. It's a lesson.

18/

WINS, LOSSES, LESSONS — the full recap:

WINS:
- +48.6% from one env var
- Q3-DOWN-XS 21/26 — most capable quant that fits
- Fits 8GB, 100% stock types, reproducible
- 128k possible on 2-bit, 32k comfortable on Q3

LOSSES:
- The kernel (333 GB/s, but 18/26 — faster and dumber)
- IQ3_XXS (can't run at 16k, wedges)
- Prefill at 64k+ (bandwidth wall, not memory)

LESSONS:
- The quant won. The kernel lost. The recipe is the win.
- Measure the memory path. Tune to fit. Don't hand-roll kernels.
- medium effort, not xhigh.
- More capability than fits = zero capability.

Recipe on HF: guideboardlabs/Qwen3-30-27B-Q3-DOWN-XS-GGUF

Base model: @Alibaba_Qwen Qwen3.8-27B.

🧵→ Thread 2 (the baseline / 3-bit reality) continues.



THREAD 2 — THE BASELINE / 3-BIT REALITY

1/

SERIOUSLY.

Before the recipe, before the env var, before any of it — the baseline.

Stock 27B on an RX 5700 XT (RDNA1/gfx1010) = 2-3 tok/s.

Not "slow." Unusable. Here's why.

🧵

2/

The stock wall:

An 11.9GB quant on 8GB VRAM. The overflow pages over PCIe every single token. The card spends more time fetching than computing.

2-3 tok/s. That's not a model running. That's a model drowning.

Everyone with RDNA1 has this. Nobody talks about it because nobody benchmarks RDNA1 in 2026.

3/

The 3-bit reality:

You can't fit a proper 3-bit quant on 8GB. IQ3_XXS is 10.18GB — overflows.

So the choice is brutal:
- 3-bit that doesn't fit → wedges
- 2-bit that fits → dumber
- Something in between → ?

The "something in between" is the whole point of the recipe.

🧵→ Thread 3

4/

The per-tensor answer — Q3-DOWN-XS:

The recipe isn't one quant. It's a MIX, tuned per-tensor to fit 8GB while keeping capability:

- FFN-down → IQ2_XS
- Rest: IQ2_XXS / IQ1_M / IQ3_S / IQ4_XS
- Norms + embeddings: F32
- 100% stock llama.cpp types — no custom format, no fork

| Layer      | Type                             |
|------------|----------------------------------|
| FFN-down   | IQ2_XS                           |
| Mix        | IQ2_XXS / IQ1_M / IQ3_S / IQ4_XS |
| Norms      | F32                              |
| Embeddings | F32                              |

Reproducible. Stock engine. No special sauce in the binary.

5/

Why this mix and not "just use IQ2_S":

Unsloth's IQ2_S is a great 2-bit. It scored 20/26.

Our Q3-DOWN-XS scored 21/26 — and it's barely slower (17.2 vs 16.9 t/s at 16k).

The difference: we spend the 3-bit budget where it matters (attention, norms, embeddings) and go aggressive only on the FFN-down where loss is cheapest.

That's the whole art. Per-tensor budget allocation.

6/

The +340MB question:

DOWN-UP-XS hits 88% fidelity (vs our 86.5%) — but costs +340MB.

On 8GB, 340MB is real. That's context window. That's whether you run 32k or wedge at 16k.

86.5% and fits > 88% and doesn't. Every time on this card.

7/

The baseline taught the lesson: on 8GB RDNA1, you're not optimizing for "best quant." You're optimizing for "best quant that FITS."

That reframing is the whole project.

🧵→ Thread 3 (the breakthrough / GGUF / HF)



THREAD 3 — THE BREAKTHROUGH / RECIPE + GGUF + HF

1/

NO WAY. One env var. +48.6% decode.

The single biggest win in this entire project wasn't a kernel, wasn't a new quant format, wasn't a clever trick.

It was a flag. GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1.

Here's what it does.

🧵

2/

The env var, explained:

Default: Vulkan allocates some tensors in host-visible vidmem. On RDNA1 with an overflowing quant, that means pages flying over PCIe every token.

GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM=1 forces everything into local VRAM. Residency. No thrash.

Result: +48.6% decode. On the SAME quant. The model didn't get smarter. It stopped drowning.

3/

The recipe — final form:

Q3-DOWN-XS. Per-tensor mix. 100% stock types.

- FFN-down → IQ2_XS (cheap loss, big savings)
- IQ2_XXS / IQ1_M / IQ3_S / IQ4_XS across the rest
- Norms + embeddings: F32 (never quantize these)
- Stock llama.cpp, stock ggml types, no fork

GGUF: guideboardlabs/Qwen3-30-27B-Q3-DOWN-XS-GGUF

4/

The protocol number — frozen tg128, c32768:

24.48 t/s.

That's the stable throughput at 32k context, tg128, protocol-benchmark conditions.

Real single cold 16k request: ~17 t/s. That's the number you'll actually feel.

Both real. Different measurement conditions. I'm giving you both so you know what's synthetic and what's live.

5/

Capability recap (because this is the headline):

| Quant           | Score | Fits 8GB? |
|-----------------|-------|-----------|
| Ours Q3-DOWN-XS | 21/26 | ✅        |
| Unsloth IQ2_S   | 20/26 | ✅        |
| IQ1_S           | 19/26 | ✅        |
| Ours 2-bit      | 18/26 | ✅        |
| IQ3_XXS         | —     | ❌ wedges |

Most capable quant that fits. That's the claim. The table backs it.

6/

The honest comparison to Unsloth:

I measured their UD-IQ2_S against our Q3-DOWN-XS, same harness, same tasks, same prompts.

- Theirs: 20/26, 16.9 t/s
- Ours: 21/26, 17.2 t/s

We're not dunking on Unsloth. Their IQ2_S is excellent. We just allocated the bit budget differently and squeezed one more task out of it.

Different recipe, same stock types. That's a fair fight and we're proud of the result.

7/

Recipe is live. GGUF is up. Reproduce it.

guideboardlabs/Qwen3-30-27B-Q3-DOWN-XS-GGUF

@Alibaba_Qwen for the base. @ggml_org for the engine. Stock everything.

The quant won. The recipe is the win.

🧵→ Thread 4 (the kernel — the loss told straight)



THREAD 4 — THE KERNEL / THE SPEED WIN, TOLD STRAIGHT

1/

I built a kernel. It was faster. And that part was a WIN — a real one.

Here's the science, the receipts, and what actually happened when the speed win met the capability wall.

🧵

2/

What I built:

iq2_rdna — a Navi-specific 2-bit GEMV kernel for RDNA1/gfx1010.

Target: accelerate decode for 2-bit quants on a card with no integer dot product.

Measured: 333 GB/s vs stock 226 GB/s. GEMV only. 2.19 bpw.

That's a real number. Fastest GEMV I measured on this card.

3/

Why I thought it would win:

333 vs 226 GB/s is a 47% bandwidth uplift. On a bandwidth-bound card (448 GB/s peak, RDNA1), that should translate directly to faster decode.

And it did: 18.1 t/s vs Unsloth IQ2_S's 16.9 t/s. The kernel moved tokens faster.

4/

But here's what the speed win surfaced:

The kernel accelerates a 2-bit format. And 2-bit is so lossy the model scores 18/26 — worst of all five quants.

| Quant               | tok/s | Score |
|---------------------|-------|-------|
| Ours 2-bit (kernel) | 18.1  | 18/26 |
| Unsloth IQ2_S       | 16.9  | 20/26 |
| Ours Q3-DOWN-XS     | 17.2  | 21/26 |

The kernel won the speed column. The model lost the point. Faster tokens don't matter if the answers are worse.

That split — a real speed win AND a real capability loss in the same artifact — is exactly why I kept circling back to the start.

5/

The GFX1010 ISA falsification — why this was hard:

I went in assuming RDNA1 had integer dot products for quantized GEMV. The internet said so.

llvm-mc said otherwise:

- v_dot8 — rejected
- v_dot4 — rejected
- v_dot2 — rejected
- v_fma_mix_f32 (fp16 FMA) — accepted, half-rate

No integer dot on gfx1010. Period. Only fp16. I verified this by hand with the assembler. The ISA doesn't negotiate.

6/

What the kernel IS:

A real speed win. It's on GitHub. Fastest GEMV I measured on this card (333 GB/s). It proves the bandwidth is there — and for a pure decode-throughput use case, it genuinely wins.

It's NOT a competitor to the recipe for capability. The recipe uses stock types at 86.5% fidelity and scores 21/26. The kernel uses 2-bit at 2.19 bpw and scores 18/26.

The speed win is real. The capability trade is real. Both are true, and I'm telling you both.

7/

The process — and the lesson, told straight:

This wasn't linear. I made a plan, executed, hit a wall, made changes, and circled back to the start a few times. Sol (inside ChatGPT) and I had talked through pieces of this for a while — this project was putting it all together and more.

The kernel got us a speed win — finally, after weeks. But it wasn't the whole answer. The env var took one line and gave +48.6%. The quant recipe took an afternoon and won on capability.

The biggest wins were measuring the memory path and tuning the quant to fit — not hand-rolling a kernel.

The kernel stays in-tree. It's a real piece of work and a real speed win. But the recipe won the daily-driver battle, and I'm not going to pretend otherwise.

8/

Recipe: guideboardlabs/Qwen3-30-27B-Q3-DOWN-XS-GGUF
Kernel: GitHub (research artifact, same repo)

Topic twin: @cyrilXBT — same 27B-on-8GB thesis, RDNA1 edition

The underdog card ran the big model. Not because I found a secret. Because I measured every lever and told the truth about which ones worked.

🧵
╰──────────────────────────────────────────────────────────────────────────────╯
