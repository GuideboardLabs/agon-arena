#!/usr/bin/env python3
"""
Agon-Bench v3 Runner — comprehensive benchmark pipeline.
Stable model IDs, per-event tables, per-task real-time DB writes.
"""
import argparse, json, os, sys, time, subprocess, tempfile, re, signal, shutil
from pathlib import Path
from datetime import datetime
import httpx

DB_PATH = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
SCRIPTS_DIR = os.path.expanduser("~/Documents/agon-arena/scripts")
RESULTS_DIR = os.path.expanduser("~/Documents/agon-arena/results")
SERVER_LOG = os.path.expanduser("~/Documents/agon-arena/server-stderr.log")

# ── Per-Model Optimal Config ──
MODEL_CONFIG = {
    "omnicoder_9b": {
        "name": "OmniCoder-9B",
        "gguf": "/mnt/blue/LLMbackups/omnicoder-9b-q4_k_m.gguf",
        "draft": None,
        "size_gb": 5.4, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 53.8,
        "notes": "Best Agent score in class. 52 tok/s."
    },
    "qwen35_9b": {
        "name": "Qwen3.5-9B",
        "gguf": "/mnt/blue/LLMbackups/Qwen3.5-9B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.3, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 47.0,
        "notes": "Base Qwen3.5-9B. 47 tok/s."
    },
    "qwen38_9b": {
        "name": "Qwen3.8-9B",
        "gguf": "/home/sc/models/Qwen3.8-9B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.78, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1 --reasoning off --reasoning-format none",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 40.0,
        "notes": "Qwen3.8 2.4T A95B distilled into Qwen3.5-9B arch (Gated DeltaNet hybrid). mmlu 0.751 vs 0.546 base. Thinking model - needs --reasoning off --reasoning-format none."
    },
    "heem_9b": {
        "name": "Heem-9B (Uncensored)",
        "gguf": "/home/sc/models/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.63, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1 --reasoning off --reasoning-format none",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 40.0,
        "notes": "Qwen3.5-9B abliterated/uncensored (HauhauCS-Aggressive). Heem Discord bot's production model. Thinking model - needs --reasoning off --reasoning-format none."
    },
    "ornith_15_9b": {
        "name": "Ornith-1.5-9B",
        "gguf": "/mnt/blue/Ornith-1.5-9B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.9, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 999 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.6 --top-p 0.95 --top-k 20 --min-p 0.0 --parallel 1 --jinja --reasoning on",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 48.0,
        "notes": "Ornith-1.5-9B dense, fully VRAM-resident (5.9GB in 8GB, no spill). Q4_K_M. Model card: reasoning model, temp=0.6/top_p=0.95/top_k=20 for coding, --jinja --reasoning on. No speculative decoding."
    },
    "ornith_9b": {
        "name": "Ornith-1.0-9B",
        "gguf": "/home/sc/models/ornith-1.0-9b-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.3, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 48.0,
        "notes": "Ornith MoE distilled to 9B. 48 tok/s."
    },
    "gemma4_12b": {
        "name": "Gemma4-12B",
        "gguf": "/mnt/blue/LLMbackups/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
        "draft": None,
        "size_gb": 6.7, "quant": "Q4_K_XL", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 24.0,
        "notes": "Fully fits in VRAM. 24 tok/s. Reasoning ON (realistic usage)."
    },
    "grug_12b": {
        "name": "Grug-12B",
        "gguf": "/home/sc/models/Grug-12B.Q4_K_M.gguf",
        "draft": None,
        "size_gb": 6.9, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 34.0,
        "notes": "Gemma4-12B fine-tune. 34 tok/s. Reasoning ON (realistic usage)."
    },
    "gemma4_26b": {
        "name": "Gemma4-26B-A4B",
        "gguf": "/home/sc/models/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
        "draft": "/home/sc/models/mtp-gemma-4-26B-A4B-it.gguf",
        "size_gb": 16.9, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 30, "gpu_layers_draft": 99,
        "server_args": "--gpu-layers 30 --cpu-moe --flash-attn on --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1 --reasoning-format none",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 13.5,
        "task_timeout_s": 1800,
        "notes": "Best model. Needs MTP draft for 13.5 tok/s. MoE CPU spill required. Reasoning ON (realistic usage)."
    },
    "ornith_35b": {
        "name": "Ornith-1.0-35B",
        "gguf": "/home/sc/models/deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 20.0, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 20, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 20 --cpu-moe --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 9.2,
        "notes": "RL-trained for agentic coding. 9.2 tok/s. MoE CPU spill."
    },
    "ornith_35b_mtp": {
        "name": "Ornith-1.0-35B-MTP",
        "gguf": "/mnt/blue/LLMbackups/ornith-1.0-35b-MTP-graft-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 21.7, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 20, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 20 --cpu-moe --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 9.2,
        "notes": "MTP-graft variant. Same model with MTP head for speculative decoding. MoE CPU spill."
    },
    "lfm25_8b": {
        "name": "LFM2.5-8B-A1B",
        "gguf": "/mnt/blue/LLMbackups/lfm2.5-8b-Q4_K_XL.gguf",
        "draft": None,
        "size_gb": 5.0, "quant": "Q4_K_XL", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 91.1,
        "notes": "LFM2.5-8B-A1B MoE. 1B active. 91 tok/s."
    },
    "qwythos_9b_v1": {
        "name": "Qwythos-9B-v1",
        "gguf": "/home/sc/models/Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M.gguf_DELETED",
        "draft": None,
        "size_gb": 5.3, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 30.4,
        "notes": "v1 benchmark (57pt scale). Hand-graded. 30.4 tok/s."
    },
    "qwopus_9b": {
        "name": "Qwopus3.5-9B-Coder",
        "gguf": "/mnt/blue/LLMbackups/Qwopus3.5-9B-Coder-MTP-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 4.5, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 30.0,
        "notes": "Qwen3.5-9B fine-tune for coding. MTP head ignored (no benefit on 8GB)."
    },
    "holo_31_9b_coder": {
        "name": "Holo-3.1-9B-Coder",
        "gguf": "/mnt/blue/LLMbackups/Holo-3.1-9B-Coder.Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.3, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 40.0,
        "notes": "Holo-3.1-9B-Coder. ~40 tok/s expected."
    },
    "superqwen_35b": {
        "name": "SuperQwen-35B",
        "gguf": "/mnt/blue/LLMbackups/SuperQwen-AgentWorld-35B-A3B-abliterated-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 21.0, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 12, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 12 --cpu-moe --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1 --no-kv-offload",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 3600, "tok_s": 10.8,
        "notes": "VRAM split: 12 GPU layers. 10.8 tok/s. Needs longer timeout."
    },
    "qwen38_27b_q3downxs": {
        "name": "Qwen3.8-27B-Q3-DOWN-XS",
        "gguf": "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf",
        "draft": None,
        "size_gb": 7.91, "quant": "IQ3_XXS", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "--threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --reasoning off --reasoning-format none --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 24.0, "task_timeout_s": 1200,
        "notes": "Our IQ3 king. Qwen3.8-27B dense, custom iq2_rdna kernel, 24 t/s. CPU spill (27B doesn't fit 8GB).",
        "llama_fork": "vulkan"
    },
    "qwen36_35b_q4_ncmoe40": {
        "name": "Qwen3.6-35B-Q4-ncmoe40",
        "gguf": "/mnt/blue/qwen36/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 21.1, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "--threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 -ncmoe 40 --spec-type draft-mtp --reasoning off --reasoning-format none --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 25.5, "task_timeout_s": 1200,
        "notes": "Qwen3.6-35B Q4_K_M with -ncmoe 40 recipe. 25.5 tok/s with --spec-type draft-mtp (the model's own MTP layer, nextn_predict_layers=1). Paired A/B 2026-10-09 on this box, ctx 4096 and 16384, greedy, 1346p/256d: same recipe without the flag measured 19.6/19.9, so MTP is +28 to +30%, output byte-identical, and slightly LESS VRAM (3.51 vs 3.58 GB). The older recorded 21.7 did not reproduce under the A/B harness (got 19.9), so trust the ratio rather than the absolute. Also tried and REJECTED: --spec-type ngram-mod (0% decode, +9% prefill) and --moe-cache-slots-per-layer 16-128 (decode fell to 42-60% and, from 64 slots up, VRAM overflowed past the card and prefill collapsed to 38% then 14%). Needs 28G MemoryMax (20G OOMs).",
        "llama_fork": "moe"
    },
    "qwen38_35b_a3b_distill": {
        "name": "Qwen3.8-35B-A3B-Distill",
        "gguf": "/home/sc/models/Qwen3.8-35B-A3B-Distill-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 21.7, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "--threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 -ncmoe 40 --spec-type draft-mtp --reasoning off --reasoning-format none --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 21.0, "task_timeout_s": 1200,
        # The card warns the student was trained on 8,192-token examples and that
        # greedy/low-temp decoding on long generations is "a known repetition-loop
        # failure mode for reasoning models in this class". Observed on agent run 3
        # (seed 256): task 5 ran unbounded past 20,000 decoded tokens and hit the
        # task timeout, scoring 0/3 on a task it scored 3/3 on in the other two runs
        # (1334s for the run vs ~150s). Cap output so a loop costs one task at worst
        # instead of the whole run's wall clock.
        "max_tokens": 8192,
        "notes": "Empero Qwen3.8-35B-A3B-Distill: Qwen3.8 teacher traces distilled into the SAME Qwen3.6-35B-A3B base as qwen36_35b_q4_ncmoe40. Matched-recipe head-to-head (identical -ncmoe 40 + reasoning off) so the distillation is the only variable. Empero reports ARC-Challenge 0.548->0.591, MMLU flat 0.834 vs base. --spec-type draft-mtp added 2026-10-09 to keep the pair matched: verified the file is the same arch (qwen35moe, 41 blocks, 256 experts, nextn_predict_layers=1) so the flag applies, but its gain was NOT separately measured here (tok_s left at the old 21.0).",
        "llama_fork": "moe"
    },
    "bonsai_27b_q1_0": {
        "name": "Bonsai-27B-Q1_0",
        "gguf": "/home/sc/models/Bonsai-27B-Q1_0.gguf",
        "draft": None,
        "size_gb": 3.8, "quant": "Q1_0", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 28800, "tok_s": 12.5,
        "task_timeout_s": 1200,
        "notes": "1-bit Bonsai 27B. 1.125 bpw ternary. 90% of FP16. 12.5 tok/s. Uses PrismML llama.cpp fork.",
        "llama_fork": "prism"
    },
    "nanbeige_3b": {
        "name": "Nanbeige4.2-3B",
        "gguf": "/mnt/blue/LLMbackups/Nanbeige4.2-3B/nanbeige-3b-q4_k_m.gguf",
        "draft": None,
        "size_gb": 2.4, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 44.9,
        "notes": "Nanbeige4.2-3B Looped Transformer. 22 phys layers x2 loops = 44 effective. 44.9 tok/s on AMD ROCm."
    },
    "minicpm5_2b": {
        "name": "MiniCPM5-2B",
        "gguf": "/home/sc/models/MiniCPM5-2B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 1.56, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.3 --min-p 0.05 --parallel 1 --jinja --reasoning on",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 118.0, "max_tokens": 4096,
        "notes": "MiniCPM5-2B dense 2B LlamaForCausalLM (42 layers, 131K ctx, ChatML). OpenBMB 2B-class SOTA. Reasoning model (thinking/response tags) - --jinja --reasoning on. Fully VRAM-resident (1.56GB in 8GB). Needs build-vulkan fork (minicpm5 tokenizer not in ROCmFPX).",
        "llama_fork": "vulkan"
    },
    "bonsai_ternary_ptq1_0": {
        "name": "Ternary-Bonsai-2-27B-PTQ1_0",
        "gguf": "/mnt/blue/LLMbackups/Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "draft": None,
        "size_gb": 5.53, "quant": "PTQ1_0", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        "server_args": "--gpu-layers 99 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 45000, "tok_s": 4.23,
        "task_timeout_s": 3000,
        # Safety net against a repetition loop eating the whole 10h event budget.
        # Disclosed as a deviation from the sibling Bonsai-27B-Q1_0 run (no cap).
        "max_tokens": 8192,
        "notes": "REFERENCE ONLY - single run per event, NOT part of the ranked pack. Ternary PTQ1_0 base-3 codec (1.75 bpw). Runs on our RDNA1 build llama.cpp-bonsai2: 4.23 t/s decode vs 2.93 for the vendor prebuilt.",
        "llama_fork": "ptq1"
    },
    "mimo_v26_9b_ablit": {
        "name": "MiMo-V2.6-Distill-9B-Ablit",
        "gguf": "/home/sc/models/MiMo-V2.6-Distill-Qwen-9B-Ablitrated-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 5.24, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        # --reasoning off --reasoning-format none: MiMo routes everything to
        # message.reasoning_content and leaves content EMPTY without both flags.
        # Verified: 4000-token completion with zero characters of content.
        "server_args": "--gpu-layers 999 --mlock --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --reasoning off --reasoning-format none --temp 0.3 --min-p 0.05 --parallel 1 --jinja",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 52.0,
        "task_timeout_s": 900,
        # Loop safety net: MiMo degenerated into a 1573-repeat loop on reason task 1
        # and hit 8192 tokens on 2 more. 8192 @ 52 t/s is ~2.6 min, inside task_timeout_s.
        "max_tokens": 8192,
        "notes": "Xiaomi MiMo-V2.6-Distill-Qwen-9B, community abliteration (Hikari07jp). 9B dense, Q4_K_M, 5.24 GiB, fully VRAM-resident, no spill/draft. Measured 52 t/s decode / 127 t/s prefill. NOT a thinking-off model by choice: needs --reasoning off + --reasoning-format none or it returns empty content. Reason event 12/17 but 1 point was unearned (task 1 graded 2/2 on a response never mentioning the fish - the CONTAINS:dave check is satisfied by echoing the prompt's own constraint 8). Substantive 11/17 = bottom of the fleet. Degenerate repetition loops on hard tasks.",
        "llama_fork": "vulkan"
    },

    "xing4_0_29b_a4b": {
        "name": "Xing4.0-29B-A4B",
        "gguf": "/mnt/blue/LLMbackups/xing/xing4_0-29b-IQ4_NL-00001-of-00003.gguf",
        "draft": None,
        "size_gb": 18.72, "quant": "IQ4_NL", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        # No --mlock and no --no-mmap: an 18.72 GiB model on a 31 GiB box that lives on
        # a spinning HDD must be allowed to page. --mlock here would pin the whole file
        # and invite the OOM killer; --no-mmap would need ~43GB during load.
        "server_args": "--gpu-layers 999 -c 16384 -ctk q8_0 -ctv q8_0 -fa on --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --temp 0.7 --min-p 0.05 --parallel 1 --jinja",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 45000, "tok_s": 4.38,
        "task_timeout_s": 3000,
        # Loop safety net: 8192 tokens at 4.38 t/s is ~31 min, inside task_timeout_s.
        # Disclosed as a deviation from the uncapped sibling runs.
        "max_tokens": 8192,
        "notes": "REFERENCE ONLY - single run per event, NOT part of the ranked pack. China Telecom (ex-TeleChat) Xing4.0, DeepSeek-V3 lineage: MLA + MoE (64 routed experts, 4 active) + an mHC block. 29B total / 4B active, 256K native ctx, Apache-2.0, trained on Ascend NPU. Needs the shuxiaoqiong/llama.cpp xing4_0-port fork; Vulkan lacks the fused XING4_0_HC kernels so resolve_fused_ops() disables them and the decomposed generic-op path runs. 5.37 t/s bench / 4.38 t/s live.",
        "llama_fork": "xing"
    },

    # Underdog AI's 2-bit (IQ2-mix) distill of Qwen3.8-27B. Ships its own mmproj.
    # Recipe is MIRRORED from qwen38_27b_q3downxs on purpose: same base family, same
    # 8GB-resident-with-CPU-spill class, so the quant is the only variable between them.
    # Reasoning is turned OFF for the same reason it is there: this template carries
    # `reasoning_effort|default('xhigh')`, so an unspecified request injects
    # "think carefully, validate key assumptions, consider alternatives" into EVERY prompt
    # and, with the harness's 32768-token allowance, burns the budget inside thinking.
    # Do not drop --reasoning off without reading the template out of the GGUF first.
    "underdog_saluki_27b_iq2": {
        "name": "Underdog-Saluki-27B-IQ2",
        "gguf": "/home/sc/models/Underdog-Saluki-27B-1.0-IQ2-mix.gguf",
        "draft": None,
        "size_gb": 7.9, "quant": "IQ2-mix", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        # -ngl 999 -fa on are NOT optional here. Without them this fork keeps every layer
        # on CPU: measured 1.77 t/s decode / 1.90 prefill, vs 24.03 / 66.42 with them
        # (13.6x, same binary and model). The runner's cmd assembly never appends -ngl
        # from the gpu_layers field, so server_args is the only place it can live.
        "server_args": "-ngl 999 -fa on --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --reasoning off --reasoning-format none --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 23.2, "task_timeout_s": 1200,
        "notes": "Underdog AI Saluki 27B, IQ2-mix ~2.3 bpw quant of Qwen3.8-27B dense. Apache-2.0. Measured 23.2 t/s decode / 96 t/s prefill on this card, fully VRAM-resident with CPU spill. Tool calling verified locally: single call correct in 4.1s, parallel 3/3, no-tool case valid JSON. Vision works via the shipped mmproj but was validated on the eggbench task, not Agon (which is text-only). Recipe mirrors qwen38_27b_q3downxs so the 2-bit quant is the isolated variable. NOTE: an earlier session wrongly reported this model dying after ~20 requests; that was a 4GB cgroup in the calling harness OOM-killing the server, not the quant - a systemd scope fixed it and it then survived 100/100.",
        "llama_fork": "vulkan"
    },

    # OpenBMB MiniCPM-V 4.7 35B-A3B. Arch is qwen35moe - 41 blocks, 256 experts / 8 active,
    # expert FFN 512, nextn_predict_layers 1 - identical geometry to our Qwen3.6-35B-A3B, so
    # it is an apples-to-apples sibling rather than a new architecture. Hybrid stack: 30
    # gated-deltanet/SSM layers + 10 full-attention layers. Apache-2.0.
    #
    # -ncmoe 30 is the SWEPT optimum for THIS quant, and it is not inherited from the Qwen
    # recipe. Measured on this card, steady state: ncmoe 40 = 15.8, 30 = 21.4/21.8, 25 = 15.0/14.4,
    # 20 = 13.7/12.7, 15 = 5.5/10.1, 10 = 6.4/10.4 t/s. The rule: the best N is the largest N
    # whose REMAINING expert weight still fits in VRAM. Verified in-run at 30: VRAM 8.23GB
    # (card full), GTT 0.54GB. Every layer past that spills into GTT and GTT is where the
    # performance dies. Carrying the Qwen3.6 recipe's -ncmoe 40 cost 37%.
    #
    # --jinja is MANDATORY: the GGUF carries its own 7,250-char ChatML template. Without it
    # llama.cpp applies a default and the model emits an empty  thinking block and stops -
    # a blank answer at a plausible-looking 10.7 t/s. --reasoning off is then required too,
    # or it writes a "[Start thinking] Thinking Process:" block and burns the budget.
    # (--chat-template-kwargs '{"enable_thinking": false}' still works but is deprecated in
    # this build in favour of --reasoning off.)
    #
    # No --mlock (19.71GB on a 31GB box must stay free to page) and no --no-mmap (known
    # immediate GPU OOM on this card). No draft model: neither official quant ships an MTP
    # block despite declaring nextn_predict_layers = 1, so --spec-type draft-mtp aborts with
    # GGML_ASSERT(layer.nextn.eh_proj && "MTP block missing nextn.eh_proj").
    # One server serves all three events, so -c must cover the widest (code = 16384).
    # The vision projector is deliberately NOT loaded: all three Agon events are text-only.
    "minicpm_v47_35b_a3b_q4": {
        "name": "MiniCPM-V-4.7-35B-A3B",
        "gguf": "/mnt/ssd/models/minicpm-v47/MiniCPM-V-4_7-35B-A3B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 19.71, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 0, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -fa on -ncmoe 30 -c 16384 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --jinja --reasoning off --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 19.7, "task_timeout_s": 1200,
        "max_tokens": 8192,
        "notes": "OpenBMB MiniCPM-V 4.7 35B-A3B, official Q4_K_M (19.71 GiB, 21,166,255,040 B). Architecture qwen35moe: 41 blocks, 256 experts / 8 active, expert FFN 512, nextn_predict_layers 1 - geometry line-for-line identical to our Qwen3.6-35B-A3B, so this is a same-architecture A/B rather than a new design. Its HF text_config is identical to Qwen3.6's field-for-field except vocab_size (248144 vs 248320), all 733 of its tensors match Qwen3.6 by name AND shape, and its F32 weights correlate r=0.996-1.000 against a random baseline of 0.003 - so the language backbone IS lightly-modified Qwen3.6-35B-A3B weights, not a new design (OpenBMB credits 'Qwen3.6 for providing the language backbone'). Retracted earlier claims that the RoPE base differed and that it added 3D RoPE; neither is true. Hybrid: 30 SSM/delta-net layers + 10 full-attention. Expert bytes: routed _exps are 18.16 GiB at 4.844 bpw (Q4_K 14.1 + Q6_K 4.1), whole file 4.883 bpw. Needs the post-PR-29416 build (~/llama-mcpv47, merged 2026-10-10) which adds the minicpmv4_7 projector and the 3D RoPE; the pinned build has no section_order handling. Measured 21.4/21.8 t/s decode at -c 8192 and 19.7 t/s at -c 16384 on a 251-token generation, VRAM 8082MB peak / GTT 472MB. Vision and VIDEO both verified independently (image descriptions and a directional-motion claim on a 4s clip that held up frame-by-frame), but neither is exercised here because Agon is text-only. max_tokens 8192 was disclosed as a deviation from the uncapped qwen36_35b_q4_ncmoe40 sibling, and it DID fire: exactly one of the 66 requests was cut at 8192 (reason run 1 task 1, 418s), with three more reaching 7384/7182/6380. Verified harmless - that task still scored 2/2 - but it is a real truncation, not a dormant safety net.",
        "llama_fork": "mcpv47"
    },

    # Liquid AI LFM2.5-24B-A2B. Arch is lfm2moe: 40 blocks = 2 leading dense + 38 MoE,
    # 64 experts / 4 active, expert FFN 1536, hidden 2048. Hybrid stack: 30 gated
    # shortconv layers (head_count_kv = 0) + 10 full-attention layers (GQA 32/8).
    # Tied embeddings, 428 tensors, 131072 ctx, vocab 128000.
    #
    # Expert bulk is ~22.9B params = ~13.8 GB = ~0.364 GB per MoE layer. That is what
    # sets the -ncmoe optimum: the best N is the largest N whose REMAINING expert weight
    # still fits in VRAM. Same rule as the MiniCPM-V 4.7 entry, re-swept for THIS quant
    # rather than inherited from a sibling.
    #
    # --jinja is MANDATORY. The GGUF carries its own 5,443-char ChatML template whose
    # add_generation_prompt opens the assistant turn with an OPEN " thinking" tag (the
    # model always reasons). needs_reasoning_off is 0 to match the fleet - 58 of 58
    # stored benchmark_runs ran with thinking_off=0.
    "lfm25_24b_a2b_q4": {
        "name": "LFM2.5-24B-A2B",
        "gguf": "/mnt/blue/LLMbackups/LFM2.5-24B-A2B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 14.53, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -fa on -ncmoe 21 -c 16384 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --jinja --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 25.8, "task_timeout_s": 1200,
        "notes": "Liquid AI LFM2.5-24B-A2B, official Q4_K_M (14,526,258,464 B = 14.53 GB, sha256 d3334405b96228eb9908cdebb5c6194908f2da64282bda852afc3a3910c64e7d == HF LFS oid). First release post-trained against Hermes Agent itself. lfm2moe, 40 blocks (2 dense lead + 38 MoE), 64 experts / 4 active, expert FFN 1536, hidden 2048, 30 shortconv + 10 attention layers, tied embeddings, 131072 ctx. -ncmoe 21 is a swept optimum, not an inherited recipe: measured on this card at -c 16384, ncmoe 38/30/25/21/18/14/10 = 16.93/19.12/21.36/25.76/24.48/19.31/16.87 t/s with GTT 0.25/0.25/0.25/0.25/1.11/2.35/3.75 GiB, so 21 is the largest N whose remaining expert weight still fits in VRAM. Reasoning verification: the GGUF template's add_generation_prompt emits an OPEN think tag, and llama.cpp logs 'chat template supports preserving reasoning, it is enabled by default'; checked on a real completion - content='ready' (5 chars) with reasoning_content=441 chars, so thinking is split out and does NOT pollute graded answers. max_tokens 8192 is a DISCLOSED deviation from the uncapped qwen36_35b_q4_ncmoe40 sibling, set because this model reasons on every request (a 236-char agent answer cost 1326 generated tokens; a trivial 'reply ready' cost 105 tokens for 5 chars). Watch for it actually firing: if any request is cut at 8192 the affected task's score is not comparable.",
        "llama_fork": "mcpv47"
    },
}

# ── Submitted-model overlay ──
# Models submitted from the command-center panel land in a JSON overlay instead of
# being written into this literal, so the runner keeps ONE reviewed model list and a
# panel-side change can never corrupt it. A missing or unreadable overlay is not an
# error: the bench must still start with every built-in model.
_OVERLAY = os.path.expanduser(
    os.environ.get("AGON_OVERLAY", "~/.local/state/agon-submitted-models.json")
)
if os.path.exists(_OVERLAY):
    try:
        with open(_OVERLAY) as _f:
            _submitted = json.load(_f)
        if isinstance(_submitted, dict):
            MODEL_CONFIG.update(_submitted)
            print(f"Loaded {len(_submitted)} submitted model(s) from {_OVERLAY}")
    except Exception as _e:
        print(f"WARNING: could not read submitted-model overlay {_OVERLAY}: {_e}")

# ── Event Scripts ──
EVENT_SCRIPTS = {
    "agent": os.path.join(SCRIPTS_DIR, "agent-event.py"),
    "code": os.path.join(SCRIPTS_DIR, "code-event.py"),
    "reason": os.path.join(SCRIPTS_DIR, "reason-event.py"),
}

EVENT_MAX_SCORES = {"agent": 24, "code": 25, "reason": 17}
EVENT_CTX = {"agent": "agent_ctx", "code": "code_ctx", "reason": "reason_ctx"}
EVENT_TABLES = {"agent": "agent_runs", "code": "code_runs", "reason": "reason_runs"}

LLAMA_SERVER = os.path.expanduser("~/ROCmFPX/build-rdna1/bin/llama-server")
LLAMA_SERVER_PRISM = os.path.expanduser("~/llama.cpp-prism/build-vulkan/bin/llama-server")
LLAMA_SERVER_ESCHA = os.path.expanduser("~/ROCmFPX-escha/build-rdna1/bin/llama-server")
LLAMA_SERVER_VULKAN = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
LLAMA_SERVER_MOE = os.path.expanduser("~/llama.cpp-moe-cache/build-vulkan/bin/llama-server")

# Newer upstream worktree (build ~11483), kept separate from the pinned build-vulkan
# fork so a mainline GGUF can be A/B'd across llama.cpp versions without disturbing
# the build every other model on this bench was measured with.
LLAMA_SERVER_MASTER = os.path.expanduser("~/llama-master-wt/build-vulkan/bin/llama-server")

# shuxiaoqiong/llama.cpp branch xing4_0-port (HEAD 63c16fb) - adds the xing4_0 arch
# and the mHC (manifold-constrained hyper-connection) ops. Vulkan has no fused
# XING4_0_HC kernels, so resolve_fused_ops() auto-disables them and the graph falls
# back to a decomposed path built from generic ops. That fallback is why this runs
# on RDNA1 at all; the "not supported, set to disabled" lines are expected.
LLAMA_SERVER_XING = os.path.expanduser("~/llama.cpp-xing/build-vulkan/bin/llama-server")

# Our RDNA1 R&D build: PrismML-Eng/llama.cpp fork carrying the PTQ1_0 group-accessor
# decode (+14%, bit-exact). The historical ~/llama.cpp-prism symlink points at
# /mnt/ssd which is not always mounted, so PTQ1_0 resolves to this explicit path.
LLAMA_SERVER_PTQ1 = os.path.expanduser("~/llama.cpp-bonsai2/build-vulkan/bin/llama-server")

# Post-PR-29416 master worktree (8bb3cf0d2): carries the minicpmv4_7 vision projector and
# the model's "3D RoPE" (rope.section_order = zyxt). The pinned build-vulkan fork has no
# section_order handling at all, so MiniCPM-V 4.7 cannot run on it.
LLAMA_SERVER_MCPV47 = os.path.expanduser("~/llama-mcpv47/build-vulkan/bin/llama-server")

# Launch llama-server in its own systemd scope instead of inheriting the caller's
# cgroup. The Hermes gateway runs with memory.high = 12GiB; a >12GB model launched
# inside that cgroup is continuously reclaimed by the kernel and falls back to
# re-reading weights from disk every token (measured 0.15-0.27 tok/s vs 11.4-13.9
# tok/s scoped). Set AGON_NO_SCOPE=1 to disable if systemd-run is unavailable.
USE_SCOPED_LAUNCH = os.environ.get("AGON_NO_SCOPE") != "1" and shutil.which("systemd-run") is not None

LLAMA_BENCH = os.path.expanduser("~/ROCmFPX/build-rdna1/bin/llama-bench")


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def check_gpu():
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for gpu_id, info in data.items():
                if isinstance(info, dict) and "vram_total_mb" in info:
                    total = int(info["vram_total_mb"])
                    used = int(info.get("vram_used_mb", 0))
                    free = total - used
                    return total, used, free, None
    except:
        pass
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
    except:
        pass
    try:
        with open("/sys/class/drm/card0/device/mem_info_vram_total") as f:
            total = int(f.read().strip()) // (1024*1024)
        with open("/sys/class/drm/card0/device/mem_info_vram_used") as f:
            used = int(f.read().strip()) // (1024*1024)
        return total, used, total - used, None
    except:
        pass
    return None, None, None, None


def log_gpu_state(model_key=None):
    total, used, free, util = check_gpu()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO gpu_log (timestamp, model_id, vram_total_mb, vram_used_mb, vram_free_mb, gpu_util_pct) "
        "VALUES (?, (SELECT id FROM models WHERE key=?), ?, ?, ?, ?)",
        (datetime.now().isoformat(), model_key, total, used, free, util)
    )
    conn.commit()
    conn.close()
    return total, used, free


def kill_llama_servers():
    subprocess.run(["pkill", "-f", "llama-server"], capture_output=True, timeout=5)
    time.sleep(2)
    result = subprocess.run(["pgrep", "-f", "llama-server"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        log("  WARNING: llama-server still running, trying SIGKILL")
        subprocess.run(["pkill", "-9", "-f", "llama-server"], capture_output=True, timeout=5)
        time.sleep(2)


def start_server(model_key, port=8100):
    cfg = MODEL_CONFIG[model_key]
    gguf = cfg["gguf"]
    
    if not os.path.exists(gguf):
        log(f"  ERROR: Model file not found: {gguf}")
        return None
    
    # Use PrismML fork for Bonsai ternary/1-bit models; Escha fork for Q2_0_ROCMFPX (ROCmFP2); Vulkan fork for iq2_rdna/RDNA1-K custom types
    fork = cfg.get("llama_fork")
    if fork == "prism":
        server_bin = LLAMA_SERVER_PRISM
    elif fork == "escha":
        server_bin = LLAMA_SERVER_ESCHA
    elif fork == "vulkan":
        server_bin = LLAMA_SERVER_VULKAN
    elif fork == "moe":
        server_bin = LLAMA_SERVER_MOE
    elif fork == "ptq1":
        server_bin = LLAMA_SERVER_PTQ1
    elif fork == "xing":
        server_bin = LLAMA_SERVER_XING
    elif fork == "vulkan-master":
        server_bin = LLAMA_SERVER_MASTER
    elif fork == "mcpv47":
        server_bin = LLAMA_SERVER_MCPV47
    else:
        server_bin = LLAMA_SERVER
    
    cmd = [
        server_bin,
        "--model", gguf,
        "--port", str(port),
        "--host", "0.0.0.0",
        "--no-warmup",
    ]
    if cfg.get("draft"):
        cmd.extend(["--model-draft", cfg["draft"]])
        if cfg.get("gpu_layers_draft"):
            cmd.extend(["--gpu-layers-draft", str(cfg["gpu_layers_draft"])])
        cmd.extend(["--spec-default"])
    
    server_args = cfg["server_args"].split()
    cmd.extend(server_args)
    
    log(f"  Starting server on port {port}...")
    log(f"  Command: {' '.join(cmd[:6])} ...")
    
    env = os.environ.copy()
    # RDNA1: disable host-visible vidmem (broken; hangs without it) for custom Vulkan/MoE forks
    if cfg.get("llama_fork") in ("vulkan", "moe", "ptq1", "xing", "vulkan-master", "mcpv47"):
        env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    if cfg.get("llama_fork") == "prism":
        prism_bin_dir = os.path.dirname(LLAMA_SERVER_PRISM)
        env["LD_LIBRARY_PATH"] = f"{prism_bin_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    elif cfg.get("llama_fork") == "escha":
        escha_bin_dir = os.path.dirname(LLAMA_SERVER_ESCHA)
        env["LD_LIBRARY_PATH"] = f"{escha_bin_dir}:{env.get('LD_LIBRARY_PATH', '')}"
    
    # Launch OUTSIDE the Hermes gateway's cgroup.
    #
    # The gateway's systemd unit sets memory.high = 12GiB. A 21.7GB MoE launched
    # inside it gets continuously reclaimed by the kernel, which re-reads expert
    # weights from disk on every token. Measured: 0.15-0.27 tok/s inside the
    # gateway cgroup vs 11.4-13.9 tok/s in its own scope, on identical args.
    # The bug is invisible in the logs (the server loads and answers /v1/models)
    # and it silently corrupts benchmark scores by causing task timeouts.
    #
    # `systemd-run --user --scope` places the server under user.slice where the
    # only limit is physical RAM.
    wrapped = cmd
    if USE_SCOPED_LAUNCH:
        unit = f"agon-llama-{port}"
        wrapped = [
            "systemd-run", "--user", "--scope", f"--unit={unit}",
            "--property=MemoryAccounting=yes",
            "--collect",
        ] + cmd
        log(f"  Launching in own cgroup via systemd-run --scope (unit {unit})")

    proc = subprocess.Popen(
        wrapped,
        stdout=subprocess.DEVNULL,
        stderr=open(SERVER_LOG, "a"),
        preexec_fn=os.setsid,
        env=env
    )
    
    for attempt in range(200):
        time.sleep(2)
        try:
            resp = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if resp.status_code == 200:
                log(f"  Server ready on port {port}")
                return proc
            elif resp.status_code == 503:
                if attempt % 5 == 0:
                    log(f"  Server loading... (attempt {attempt+1}/200)")
        except:
            pass
    
    log(f"  ERROR: Server failed to start on port {port}")
    kill_llama_servers()
    return None


def get_or_create_model_id(key, cfg):
    """Get stable model ID, creating if needed."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO models (key, name, label) VALUES (?, ?, ?)",
              (key, cfg["name"], cfg["name"]))
    c.execute("""
        UPDATE models SET
            name=?, label=?, size_gb=?, quant=?, vram_class=?,
            gguf_path=?, draft_path=?, is_moe=?, needs_cpu_moe=?,
            needs_reasoning_off=?, gpu_layers=?, gpu_layers_draft=?, notes=?,
            updated_at=datetime('now')
        WHERE key=?
    """, (cfg["name"], cfg["name"], cfg["size_gb"], cfg["quant"], cfg["vram_class"],
          cfg["gguf"], cfg.get("draft"), cfg["is_moe"], cfg["needs_cpu_moe"],
          cfg["needs_reasoning_off"], cfg["gpu_layers"], cfg.get("gpu_layers_draft"),
          cfg["notes"], key))
    c.execute("SELECT id FROM models WHERE key=?", (key,))
    model_id = c.fetchone()[0]
    
    # Also update model_config
    c.execute("INSERT OR IGNORE INTO model_config (model_id) VALUES (?)", (model_id,))
    c.execute("""
        UPDATE model_config SET
            server_args=?, agent_ctx=?, code_ctx=?, reason_ctx=?, timeout_s=?, notes=?
        WHERE model_id=?
    """, (cfg["server_args"], cfg["agent_ctx"], cfg["code_ctx"],
          cfg["reason_ctx"], cfg["timeout_s"], cfg["notes"], model_id))
    
    conn.commit()
    conn.close()
    return model_id


def create_run_in_db(event, model_id, run_number, seed, ctx_size):
    """Create a run entry and return its ID."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    table = EVENT_TABLES[event]
    c.execute(f"""
        INSERT OR IGNORE INTO {table}
        (model_id, run_number, seed, ctx_size, temperature, max_tokens, started_at, status)
        VALUES (?, ?, ?, ?, 0.3, 32768, datetime('now'), 'running')
    """, (model_id, run_number, seed, ctx_size))
    c.execute(f"SELECT id FROM {table} WHERE model_id=? AND run_number=?",
              (model_id, run_number))
    run_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return run_id


def get_completed_tasks(event, run_id):
    """Get set of completed task IDs for a run."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    task_table = f"{event}_tasks"
    c.execute(f"SELECT task_id FROM {task_table} WHERE run_id=? AND status='completed'", (run_id,))
    tasks = {row[0] for row in c.fetchall()}
    conn.close()
    return tasks


def run_event(model_key, event, run_number, port=8100, seed=None, run_id=None):
    """Run a single event for a model. Writes per-task results to DB in real-time."""
    cfg = MODEL_CONFIG[model_key]
    script = EVENT_SCRIPTS[event]
    ctx_key = EVENT_CTX[event]
    ctx_size = cfg[ctx_key]
    
    output_dir = os.path.join(RESULTS_DIR, model_key, event, f"run{run_number}")
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = [
        sys.executable, script,
        "--model-url", f"http://127.0.0.1:{port}",
        "--model", model_key,
        "--output", output_dir,
        "--run", str(run_number),
    ]
    if seed is not None:
        cmd.extend(["--seed", str(seed)])
    if run_id:
        cmd.extend(["--db-path", DB_PATH, "--run-id", str(run_id)])
    
    # Per-task timeout: bump for slow models
    task_timeout = cfg.get("task_timeout_s", 600)
    cmd.extend(["--task-timeout", str(task_timeout)])

    # Per-model max_tokens cap: fail-fast for verbose/looping models.
    # Event scripts default to 32768 (agent/code) / 8192 (reason), which lets
    # deep-thinking models burn 15-30K tokens looping. A cap makes them fail
    # fast instead of timing out. Only set when the model config specifies it.
    if cfg.get("max_tokens"):
        cmd.extend(["--max-tokens", str(cfg["max_tokens"])])
    
    # Check which tasks already have results in DB
    completed_tasks = set()
    if run_id:
        completed_tasks = get_completed_tasks(event, run_id)
    
    if completed_tasks:
        all_task_ids = set(range(1, 9))
        remaining = sorted(all_task_ids - completed_tasks)
        if remaining:
            cmd.extend(["--tasks", ",".join(str(t) for t in remaining)])
            log(f"  {len(completed_tasks)}/{len(all_task_ids)} tasks already done, running remaining: {remaining}")
        else:
            log(f"  All tasks already completed for {event} run {run_number}, skipping")
            return 0, 0, output_dir, 0, None
    
    log(f"  Running {event} run {run_number} (ctx={ctx_size})...")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=cfg["timeout_s"])
    elapsed = time.time() - start
    
    summary_path = os.path.join(output_dir, "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path) as f:
            summary = json.load(f)
        total_score = sum(t.get("hidden_tests_passed", 0) for t in summary.get("tasks", []))
        total_max = sum(t.get("hidden_tests_total", 0) for t in summary.get("tasks", []))
        log(f"  {event} run {run_number}: {total_score}/{total_max} in {elapsed:.0f}s")
        return total_score, total_max, summary_path, elapsed, summary
    else:
        log(f"  ERROR: No summary.json produced for {event} run {run_number}")
        log(f"  stdout: {result.stdout[-500:]}")
        log(f"  stderr: {result.stderr[-500:]}")
        return 0, EVENT_MAX_SCORES[event], None, elapsed, None


def complete_run_in_db(event, run_id, elapsed, total_score, max_score, tok_s, vram_used=None, vram_total=None, cfg=None):
    """Mark a run as completed with final stats."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    table = EVENT_TABLES[event]
    c.execute(f"""
        UPDATE {table} SET
            total_elapsed_s=?, total_score=?, max_score=?,
            avg_tok_s=?, vram_used_mb=?, vram_total_mb=?,
            thinking_off=?, draft_model_used=?,
            completed_at=datetime('now'), status='completed'
        WHERE id=?
    """, (round(elapsed, 1), total_score, max_score,
          round(tok_s, 1) if tok_s else None,
          vram_used, vram_total,
          1 if (cfg or {}).get("needs_reasoning_off") else 0,
          1 if (cfg or {}).get("draft") else 0,
          run_id))
    conn.commit()
    conn.close()
    log(f"  [DB] Run {run_id} completed in database")


def server_alive(port):
    """Check if the llama-server on `port` is responding."""
    try:
        resp = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def ensure_server(model_key, port):
    """Restart the server if it died. Returns the live proc (or None)."""
    if server_alive(port):
        return True
    log(f"  WARNING: server on port {port} is DOWN — restarting...")
    kill_llama_servers()
    proc = start_server(model_key, port)
    if not proc:
        log(f"  FAILED: could not restart server for {model_key}")
        return False
    log(f"  Server restarted on port {port}")
    return True


def run_model_benchmark(model_key, port=8100, max_runs=3):
    """Run all 3 events x max_runs runs for a model."""
    cfg = MODEL_CONFIG[model_key]
    log(f"\n{'='*60}")
    log(f"Starting {cfg['name']} ({model_key})")
    log(f"{'='*60}")
    
    # Get stable model ID
    model_id = get_or_create_model_id(model_key, cfg)
    log(f"  Model ID: {model_id} (stable)")
    
    # Check GPU state
    total, used, free = log_gpu_state(model_key)
    if total:
        log(f"  GPU VRAM: {used}MB used / {total}MB total ({free}MB free)")
        if free is not None and free < 1000:
            log(f"  WARNING: Less than 1GB VRAM free.")
    
    # Kill any existing servers
    kill_llama_servers()
    
    tok_s = cfg.get("tok_s")
    if tok_s:
        log(f"  Using pre-measured tok/s: {tok_s}")
    
    # Start server
    proc = start_server(model_key, port)
    if not proc:
        log(f"  FAILED: Could not start server for {model_key}")
        return False
    
    log_gpu_state(model_key)
    
    # Run each event 3 times with different seeds
    seeds = [42, 137, 256]
    events = ["agent", "code", "reason"]
    
    for event in events:
        ctx_key = EVENT_CTX[event]
        ctx_size = cfg[ctx_key]
        
        for run_num in range(1, max_runs + 1):
            seed = seeds[run_num - 1]
            
            # Create run in DB (idempotent)
            run_id = create_run_in_db(event, model_id, run_num, seed, ctx_size)
            
            # Check if already completed
            completed_tasks = get_completed_tasks(event, run_id)
            all_task_ids = set(range(1, 9))
            if completed_tasks == all_task_ids:
                log(f"  {event} run {run_num} already fully completed, skipping")
                continue

            # Ensure the server is still alive before each run; restart if it died
            if not ensure_server(model_key, port):
                log(f"  FAILED: server unavailable for {event} run {run_num}")
                return False

            log_gpu_state(model_key)
            
            score, max_score, summary_path, elapsed, summary = run_event(
                model_key, event, run_num, port, seed, run_id=run_id
            )
            
            if summary:
                complete_run_in_db(event, run_id, elapsed, score, max_score, tok_s, cfg=cfg)
            else:
                log(f"  FAILED: {event} run {run_num} produced no results")
    
    # Cleanup
    kill_llama_servers()
    log(f"  Completed {cfg['name']}")
    return True


def init_database():
    """Initialize database with schema and model entries."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("create_db", os.path.join(SCRIPTS_DIR, "create_db.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    init_schema = mod.init_database
    init_schema()
    
    # Upsert all models
    for key, cfg in MODEL_CONFIG.items():
        get_or_create_model_id(key, cfg)
    
    log("Database initialized with model entries")


def main():
    parser = argparse.ArgumentParser(description="Agon-Bench v3 Runner")
    parser.add_argument("--init-db", action="store_true", help="Initialize database only")
    parser.add_argument("--models", type=str, default=None,
                        help="Comma-separated model keys to run. Default: all")
    parser.add_argument("--port", type=int, default=8100, help="Server port")
    parser.add_argument("--runs", type=int, default=3, help="Runs per event (default: 3)")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    args = parser.parse_args()
    
    if args.list_models:
        print("Available models:")
        for key, cfg in sorted(MODEL_CONFIG.items()):
            path_ok = "✓" if os.path.exists(cfg["gguf"]) else "✗"
            print(f"  {key:20s} {path_ok} {cfg['name']:25s} {cfg['gguf']}")
        return
    
    if args.init_db:
        init_database()
        return
    
    # Initialize DB
    init_database()
    
    # Determine which models to run
    if args.models:
        model_keys = [m.strip() for m in args.models.split(",")]
    else:
        model_keys = list(MODEL_CONFIG.keys())
    
    for key in model_keys:
        if key not in MODEL_CONFIG:
            log(f"Unknown model: {key}")
            continue
        cfg = MODEL_CONFIG[key]
        if not os.path.exists(cfg["gguf"]):
            log(f"Model file not found: {cfg['gguf']}")
            log(f"  Skipping {key}")
            continue
        run_model_benchmark(key, args.port, args.runs)


if __name__ == "__main__":
    import sqlite3
    main()
