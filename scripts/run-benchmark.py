#!/usr/bin/env python3
"""
Agon-Bench v3 Runner — comprehensive benchmark pipeline.
Stable model IDs, per-event tables, per-task real-time DB writes.
"""
import argparse, json, os, sys, time, subprocess, tempfile, re, signal, shutil
from pathlib import Path
from datetime import datetime
import httpx

HERE = Path(__file__).resolve().parent
ARENA = os.environ.get("AGON_HOME", str(HERE.parent))

DB_PATH = os.path.join(ARENA, "agon-bench.db")
SCRIPTS_DIR = os.path.join(ARENA, "scripts")
RESULTS_DIR = os.path.join(ARENA, "results")
SERVER_LOG = os.path.join(ARENA, "server-stderr.log")

# Quants live outside the repo. Point AGON_MODELS_DIR at the directory that
# holds the .gguf files (default ~/models); the registry stores bare filenames.
MODELS_DIR = os.environ.get("AGON_MODELS_DIR", os.path.expanduser("~/models"))

# ── Per-Model Optimal Config ──
MODEL_CONFIG = {
    "omnicoder_9b": {
        "name": "OmniCoder-9B",
        "gguf": "omnicoder-9b-q4_k_m.gguf",
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
        "gguf": "Qwen3.5-9B-Q4_K_M.gguf",
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
        "gguf": "Qwen3.8-9B-Q4_K_M.gguf",
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
        "gguf": "Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
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
        "gguf": "Ornith-1.5-9B-Q4_K_M.gguf",
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
        "gguf": "ornith-1.0-9b-Q4_K_M.gguf",
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
        "gguf": "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf",
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
        "gguf": "Grug-12B.Q4_K_M.gguf",
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
        "gguf": "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
        "draft": "mtp-gemma-4-26B-A4B-it.gguf",
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
        "gguf": "deepreinforce-ai_Ornith-1.0-35B-Q4_K_M.gguf",
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
        "gguf": "ornith-1.0-35b-MTP-graft-Q4_K_M.gguf",
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
        "gguf": "lfm2.5-8b-Q4_K_XL.gguf",
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
        "gguf": "Qwythos-9B-Claude-Mythos-5-1M-Q4_K_M.gguf_DELETED",
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
        "gguf": "Qwopus3.5-9B-Coder-MTP-Q4_K_M.gguf",
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
        "gguf": "Holo-3.1-9B-Coder.Q4_K_M.gguf",
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
        "gguf": "SuperQwen-AgentWorld-35B-A3B-abliterated-Q4_K_M.gguf",
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
        "gguf": "Qwen3.8-27B-Q3-DOWN-XS.gguf",
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
        "gguf": "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 21.1, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 1,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "--threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 -ncmoe 40 --spec-type draft-mtp --reasoning off --reasoning-format none --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 4096, "code_ctx": 16384, "reason_ctx": 4096,
        "timeout_s": 14400, "tok_s": 25.5, "task_timeout_s": 1200,
        "notes": "Qwen3.6-35B Q4_K_M with -ncmoe 40 recipe. 25.5 tok/s with --spec-type draft-mtp (the model's own MTP layer, nextn_predict_layers=1). Paired A/B 2026-10-09 on the test rig, ctx 4096 and 16384, greedy, 1346p/256d: same recipe without the flag measured 19.6/19.9, so MTP is +28 to +30%, output byte-identical, and slightly LESS VRAM (3.51 vs 3.58 GB). The older recorded 21.7 did not reproduce under the A/B harness (got 19.9), so trust the ratio rather than the absolute. Also tried and REJECTED: --spec-type ngram-mod (0% decode, +9% prefill) and --moe-cache-slots-per-layer 16-128 (decode fell to 42-60% and, from 64 slots up, VRAM overflowed past the card and prefill collapsed to 38% then 14%). Needs 28G MemoryMax (20G OOMs).",
        "llama_fork": "moe"
    },
    "qwen38_35b_a3b_distill": {
        "name": "Qwen3.8-35B-A3B-Distill",
        "gguf": "Qwen3.8-35B-A3B-Distill-Q4_K_M.gguf",
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
        "gguf": "Bonsai-27B-Q1_0.gguf",
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
        "gguf": "nanbeige-3b-q4_k_m.gguf",
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
        "gguf": "MiniCPM5-2B-Q4_K_M.gguf",
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
        "gguf": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "draft": None,
        "size_gb": 5.53, "quant": "PTQ1_0", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        # Protocol matched to the PQ2_0 entry so the packing is the only variable: same pinned binary,
        # same uniform 8192 context, same sampling the event scripts can actually honour, same 8192 cap.
        # No --mlock: memlock caps at 4 GB here and these weights are 5.53 GB.
        "server_args": "--gpu-layers 99 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --jinja --reasoning on --reasoning-budget 3072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --parallel 1",
        "agent_ctx": 8192, "code_ctx": 8192, "reason_ctx": 8192,
        "timeout_s": 45000, "tok_s": 10.90,
        "task_timeout_s": 3000,
        # Safety net against a repetition loop eating the whole 10h event budget.
        # Disclosed as a deviation from the sibling Bonsai-27B-Q1_0 run (no cap).
        "max_tokens": 8192,
        "notes": "Ternary PTQ1_0 base-3 codec (1.75 bpw), the slower sibling of the PQ2_0 repack. This entry now runs the SAME protocol as PQ2_0 (pinned prism-b10777-e3de715, ctx 8192 everywhere, the same sampling and cap) so a difference in score is attributable to the packing. Its earlier single-run record at ctx 4096/16384/4096 on our own September build stays in the DB as a separate datapoint and must not be averaged with these runs; filter by ctx_size when ranking. Measured on the pinned runtime at default ctx: 88.09 t/s prefill, 10.90 t/s decode.",
        "llama_fork": "prism_pinned"
    },

    # A SEPARATE identity for the comparison, deliberately. The earlier `bonsai_ternary_ptq1_0`
    # entry carries a September single-run record at ctx 4096/16384/4096 on our own build, and the
    # runner's resume logic would SKIP this entry's run 1 and average today's 8192-context runs with
    # that September one. A new key gives three fresh runs per event under one protocol, which is the
    # only way the packing comparison against PQ2_0 means anything.
    "bonsai_ternary_ptq1_0_pinned": {
        "name": "Ternary-Bonsai-2-27B-PTQ1_0 (pinned, ctx 8192)",
        "gguf": "Ternary-Bonsai-2-27B-PTQ1_0.gguf",
        "draft": None,
        "size_gb": 5.53, "quant": "PTQ1_0", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        # Protocol identical to bonsai2_27b_pq2_0, so the packing is the only variable.
        # No --mlock: memlock caps at 4 GB and these weights are 5.53 GB.
        "server_args": "--gpu-layers 99 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --jinja --reasoning on --reasoning-budget 3072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --parallel 1",
        "agent_ctx": 8192, "code_ctx": 8192, "reason_ctx": 8192,
        "timeout_s": 45000, "tok_s": 10.88,
        "task_timeout_s": 3000,
        # Same loop safety net as PQ2_0, so the two are comparable token for token.
        "max_tokens": 8192,
        "notes": "The comparison arm: PTQ1_0, the higher-fidelity 1.75 bpw packing, run on the pinned prism-b10777-e3de715 binary with the SAME protocol as PQ2_0 (ctx 8192 everywhere, same sampling, same 8192 cap, three runs per event). Measured on the test rig at an 8192-depth decode: 10.61 t/s default, 10.58 with the KV q8_0 the run uses, 11.95 with KV q4_0, 13.60 with ubatch 256. Reference-only on speed: the sustained agentic rate stays under the 10 t/s floor.",
        "llama_fork": "prism_pinned"
    },
    "bonsai2_27b_pq2_0": {
        "name": "Ternary-Bonsai-2-27B-PQ2_0",
        "gguf": "Ternary-Bonsai-2-27B-PQ2_0.gguf",
        "draft": None,
        "size_gb": 7.21, "quant": "PQ2_0", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 99, "gpu_layers_draft": None,
        # Packing, runtime and sampling all follow the 2026-10-16 sweep. PQ2_0 measured 41% faster
        # than PTQ1_0 on this card (15.40 vs 10.90 t/s at default ctx; 11.75 at 8192). The pinned
        # PrismML release carries the no-DP4A Vulkan path written for RDNA1, so no local build is
        # involved. Sampling: the event scripts hard-code temperature 0.3 in every request, so a
        # per-model temperature cannot be set from this entry; top_p 0.95 / top_k 20 / min_p 0.05 do
        # reach the server, which is the vendor's thinking-mode recommendation apart from temperature.
        # --reasoning-budget bounds thinking so the answer is not starved (their known-issues page).
        # No --mlock: memlock caps at 4 GB here and these weights are 7.21 GB.
        "server_args": "--gpu-layers 99 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --jinja --reasoning on --reasoning-budget 3072 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.05 --parallel 1",
        "agent_ctx": 8192, "code_ctx": 8192, "reason_ctx": 8192,
        "timeout_s": 45000, "tok_s": 11.75,
        "task_timeout_s": 3000,
        # Same loop safety net as the PTQ1_0 run, so the two are comparable token-for-token.
        "max_tokens": 8192,
        "notes": "PQ2_0 repack of Ternary-Bonsai-2-27B on PrismML's pinned Vulkan release prism-b10777-e3de715. Measured locally: 124.16 t/s prefill, 15.40 t/s decode at default ctx, 11.75 at 8192. Supersedes the PTQ1_0 reference entry (3.65 t/s on our own September build). Contexts held at 8192 to stay VRAM-resident; 16384 spills to GTT and collapses decode. Sampling: temperature is the shared 0.3 the event scripts send (per-model temperature is not settable), with the vendor's top_p 0.95 / top_k 20 / min_p 0.05 from the server flags plus a 3072 reasoning budget and an 8192 token cap matching the PTQ1_0 run. The DB's per-run temperature and max_tokens columns are hard-coded literals and do NOT reflect the run.",
        "llama_fork": "prism_pinned"
    },
    "mimo_v26_9b_ablit": {
        "name": "MiMo-V2.6-Distill-9B-Ablit",
        "gguf": "MiMo-V2.6-Distill-Qwen-9B-Ablitrated-Q4_K_M.gguf",
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
        "gguf": "xing4_0-29b-IQ4_NL-00001-of-00003.gguf",
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
        "gguf": "Underdog-Saluki-27B-1.0-IQ2-mix.gguf",
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
        "gguf": "MiniCPM-V-4_7-35B-A3B-Q4_K_M.gguf",
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
        "gguf": "LFM2.5-24B-A2B-Q4_K_M.gguf",
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
    "nemotron_74b_a9b": {
        "name": "Nemotron-3.5-Bolt-74B-A9B",
        "gguf": "NVIDIA-Nemotron-3.5-Bolt-74B-A9B-IQ2_XXS.gguf",
        # The dflash drafter is passed through server_args, NOT through the "draft" field:
        # start_server() would add --model-draft + --spec-default, which is the wrong spec
        # type for this pair (dflash, not the model's own MTP head).
        "draft": None,
        "size_gb": 22.02, "quant": "IQ2_XXS", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -ncmoe 38 --fit off --load-mode mmap --spec-type draft-dflash --spec-draft-model dflash-NVIDIA-Nemotron-3.5-Bolt-74B-A9B-NVFP4.gguf --spec-draft-ngl 99 --spec-draft-n-max 7 -c 8192 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --cache-type-k q8_0 --cache-type-v q8_0 --reasoning on --reasoning-format deepseek --reasoning-budget 3072 --flash-attn on --jinja --no-mmproj --temp 0.7 --min-p 0.05 --parallel 1",
        "agent_ctx": 8192, "code_ctx": 8192, "reason_ctx": 8192,
        "timeout_s": 18000, "tok_s": 6.7, "task_timeout_s": 2400,
        "max_tokens": 8192,
        "notes": "NVIDIA Nemotron-3.5-Bolt-74B-A9B, IQ2_XXS (22,018,326,528 B = 22.02 GB, sha256 91d63363e782c8a3d5f4be42 == HF LFS oid). 74B total / 9B active; nemotron_h_moe = 88 blocks, 40 Mamba-2/SSM + 40 MoE + 8 attention (disjoint), 496 experts / 9 active + 1 shared, 1024-dim latent MoE, expert FFN 2048-2560, 2.06 bpw, 262144 native ctx. Needs a llama.cpp build carrying upstream PR #30520; stock builds do not know the architecture. Config is the measured optimum, not inherited: --cpu-moe with no drafter = 1.28/1.67 t/s; -ncmoe 38 + the dflash drafter (--fit off is REQUIRED, auto-fit refuses to fit the draft next to the placed expert layers) = 9.63-10.02 t/s. -t is irrelevant (during generation the CPU used 0.35 of 24 threads). CTX 8192 IS A HARD CEILING, measured: at -c 16384 the card oversubscribes (VRAM 8.47/8.57, GTT 14.95/15.63) and decode collapses to 4.63 t/s, below the 10 t/s floor; at 8192 the attention/KV stays on the card (VRAM 8.45/8.57) and only the experts cross the bus. All three events therefore run at 8192, and max_tokens 8192 is a DISCLOSED deviation - at this ctx a thinking model cannot both think and answer, so the cap is real, not dormant. Thinking is ON (the template emits an open think tag and llama.cpp splits it into message.reasoning_content, verified on a real completion: content='ready' with 137 chars of reasoning, so graded answers are not polluted) with --reasoning-budget 3072 as a DISCLOSED deviation: unbudgeted, a hard task spent a whole 256-token request thinking and returned EMPTY content, and at 8192 ctx there is no room to let it run to 8k. Verified on the real reason task 2 (150 miles in 2.5 h): answered 60 mph / 5 h with thinking bounded. RESULT (2026-10-16, 9 runs): 59.67/66 = agent 22.67/24 (94.4%), code 21.67/25 (86.7%), reason 15.33/17 (90.2%) - the highest raw total on the board. Sustained decode came in at 6.71 t/s aggregate (221,555 tokens over 33,021 s; median 8.92; prefill 35.5), below the 10 t/s admission floor, so the entry is flagged reference-only. 0 of 66 requests hit the ctx wall. The drafter that carried 7.8x on a short warm prompt accepted only 0.36-0.50 much of the time here, which is the whole gap between the 8.5-9.5 estimate and the 6.7 delivered: speculative acceptance is not a constant, it tracks prompt shape.",
        "llama_fork": "nemotron"
    },
    "raon1_mini": {
        "name": "Raon-1 mini preview 28.8B-A4.3B",
        "gguf": "raon-1-mini-preview-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 19.69, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -ncmoe 19 --load-mode none -fa on -c 32768 --threads 6 --threads-batch 6 --prio 2 --jinja --temp 1.0 --top-k 20 --top-p 0.95 --parallel 1",
        "agent_ctx": 32768, "code_ctx": 32768, "reason_ctx": 32768,
        "timeout_s": 21600, "tok_s": 16.2, "task_timeout_s": 2400,
        "max_tokens": 8192,
        "notes": "KRAFTON Raon-1 mini preview, 28.8B total / 4.3B active, Q4_K_M (19,686,434,304 B = 19.69 GB). 25 layers: 18 Raon Delta Attention with fixed state plus 7 MLA layers that carry the KV (~8 KiB/token BF16), 128 routed experts with top-6 plus 1 shared, situ activation, 262144 ctx, thinking on by default. Needs a llama.cpp build with the Raon patch; mainline PR 31107 was closed unmerged. Measured on this card at -c 32768: -ncmoe 19 with --load-mode none = 269-315 t/s prefill, 17.5-17.9 t/s decode, VRAM 7.56 GB with no GTT spill. --load-mode none is worth ~4 t/s and ~120 t/s of prefill over mmap with CPU tensor overrides. -ncmoe 16/17 spilled to 8.3-8.5 GB and cost 4-5 t/s. The 0.73 GB dflash drafter (--spec-type draft-dflash) dropped decode to 10.1 t/s and prefill to 48, so it is NOT used. Sampling: the model card asks temp 1.0 / top_k 20 / top_p 0.95, but call_llm() in the event scripts pins temperature 0.3 - DISCLOSED deviation, only top_k/top_p reach the server. max_tokens 8192 is also a disclosed deviation to bound thinking loops at 17.5 t/s. RESULT (2026-10-26, 9 runs): 53.67/66 = agent 21.0/24 (87.5%), code 16.67/25 (66.7%), reason 16.0/17 (94.1%). Sustained decode 16.22 t/s aggregate (283,562 tokens over 17,480 s); avg_tok_s overwritten from the config estimate to that figure. Code lost on regex engine 0/4, diff tool 1/3, file indexer 1.67/2, LRU 2/3. Agent task 8 (research) 1/3. Reason task 5 lost 0.67 of 3; everything else full.",
        "llama_fork": "raon"
    },
    "groot_19b_a3b": {
        "name": "Groot-19B-A3B-261023",
        "gguf": "Groot-19B-A3B-261023-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 11.66, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -ncmoe 20 -fa on -c 8192 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --jinja --temp 1.0 --top-k 20 --top-p 0.95 --parallel 1",
        "agent_ctx": 16384, "code_ctx": 16384, "reason_ctx": 16384,
        "timeout_s": 21600, "tok_s": 28.5, "task_timeout_s": 2400,
        "max_tokens": 32768,
        "notes": "GrootTeam Groot-19B-A3B-261023, 19B total / 3B active, 128 routed + 1 shared expert (8 active), qwen35moe arch, 40 blocks (30 linear attention + 10 full), 1 MTP layer, native multimodal with an mmproj we do not use. Q4_K_M 11,657,618,561 B. Measured here 2026-10-27 at -c 8192, -ngl 999 -ncmoe 20: 326 t/s prefill on a 2448-token prompt, 28.0-32.2 t/s decode once page cache is warm (first request after load reads cold and shows 16-17). VRAM 6.83 GB used, no GTT spill. --spec-type draft-mtp accepted 133/195 (68%) but decode fell to 22.0 t/s, so it is NOT used. Sampling follows the model card (temp 1.0 / top_k 20 / top_p 0.95) with temperature pinned by the event scripts at 0.3 as usual (disclosed). Thinking left ON: the card evaluates in thinking mode. RESULT (2026-10-27, 9 runs): 58.33/66 = agent 23.0/24 (95.83%), code 19.33/25 (77.33%), reason 16.0/17 (94.12%), rank 5 of 28, no tie. First pass ran code+reason with max_tokens 8192 and was truncated: two of three regex-engine answers stopped mid-file at ~27KB and scored 0/4. Both events were rerun uncapped at 32768 and the capped artifacts kept at /mnt/ssd/agon-archive/groot-capped-8192/. Uncapped code moved 18.67 -> 19.33, so the cap was a real but small defect; the 0/4, 3/4, 0/4 swing on regex engine across identical seeds is the model. Constrained diff tool scored 1/3 in all six runs. Agent never came near a cap (longest answer 2.9KB).",
        "llama_fork": "moe"
    },
    "lfm3_1_7b": {
        "name": "LFM3-1.7B",
        "gguf": "LFM3-1.7B-Q4_K_M.gguf",
        "draft": None,
        "size_gb": 1.10, "quant": "Q4_K_M", "vram_class": "8gb",
        "is_moe": 0, "needs_cpu_moe": 0, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -fa on -c 16384 --threads 6 --threads-batch 6 --cpu-mask 0x3f --prio 2 --jinja --temp 0.1 --top-k 50 --repeat-penalty 1.1 --parallel 1",
        "agent_ctx": 8192, "code_ctx": 16384, "reason_ctx": 8192,
        "timeout_s": 14400, "tok_s": 135.0, "task_timeout_s": 1200,
        "max_tokens": 32768,
        "notes": "Liquid AI LFM3-1.7B text model, official Q4_K_M (1,099,627,808 B = 1.10 GB). NEW tri-hybrid architecture: 2 conv layers, then a repeating conv / full_attention / conv / sliding_attention block stack, hidden 2048, 16 heads at head_dim 128, conv_L_cache 7, 262144 ctx, thinking on by default. Post-trained for agentic harnesses (Hermes Agent, Pi, OpenClaw). Needs ~/llama-lfm3: the arch landed upstream 2026-10-27 in PR 31252, no older build knows it. Sampling follows the card's GENERAL row (temp 0.1, top_k 50, repetition 1.1) rather than its math row; the event scripts still pin temperature 0.3, so only top_k and repeat-penalty reach the server (disclosed). max_tokens 32768 leaves output uncapped in practice: an earlier Groot run showed a cap at 8192 truncating code answers, and this model is fast enough that the cap buys nothing. The card itself says the model is not recommended for agentic coding or complex multi-step reasoning, so a weak code event here is what it predicts of itself. RESULT (2026-10-27, 9 runs): 46.67/66 = agent 18.0/24 (75.0%), code 13.0/25 (52.0%), reason 15.67/17 (92.16%), rank 19 of 29, no tie. Event ranks 20/20/19, so it is uniformly mid-table rather than specialised. It still beats Liquid's own LFM2.5-8B-A1B (67.17%) by 3.5 points at 1.1GB against 5.0GB and 135 t/s against 91, and it matches Gemma4-12B's 70.2% while running 5.6x faster. Code is the ceiling exactly as the card warns (14, 15, 10 of 25); reason is the surprise at 92.16%, within 2 points of Groot-19B at 14x the file size. Loaded in 2 seconds, 1.35GB VRAM including KV.",
        "llama_fork": "lfm3"
    },
    "flint_39b_a3b": {
        "name": "Flint-40B-A3B",
        "gguf": "flint-UD-Q4_K_XL.gguf",
        "draft": None,
        "size_gb": 25.05, "quant": "UD-Q4_K_XL", "vram_class": "8gb",
        "is_moe": 1, "needs_cpu_moe": 1, "needs_reasoning_off": 0,
        "gpu_layers": 999, "gpu_layers_draft": None,
        "server_args": "-ngl 999 -ncmoe 39 -fa on -c 16384 -ctk q8_0 -ctv q8_0 --threads 6 --threads-batch 6 --cpu-mask 0x3f --jinja --top-p 0.95 --top-k 20 --min-p 0.05 --parallel 1",
        "agent_ctx": 16384, "code_ctx": 16384, "reason_ctx": 16384,
        "timeout_s": 21600, "tok_s": 17.1, "task_timeout_s": 3000,
        "max_tokens": 32768,
        "notes": "Recursive SI Flint, 39.8B total / ~2.5B active MoE (49 layers, hidden 2048, 256 routed experts top-6, moe_intermediate_size 512, one shared expert, 262K ctx, 150144 vocab, Apache-2.0). Coding-agent tuned, 'reasoning on demand'. unsloth UD-Q4_K_XL 25.05 GB. Needs a llama.cpp build from a37cc46104 (PR 30928, merged 2026-10-21); the local build is 8ca4060b7 in ~/llama-flint. Measured on the RX 5700 XT with -ncmoe sweep, 520p/256d at ctx 16384: -ncmoe 37 19.02 t/s decode (7.58 GB VRAM, 94% of the card), -ncmoe 40 18.20 t/s (6.22 GB), prefill 160-175 t/s. Runs at 39 for headroom: 7.1 GB and ~18.6 t/s, comfortably over the 10 t/s floor. Sampling: the event scripts hard-code temperature 0.3, so the vendor's temp 1.0 never reaches the server; top_p 0.95 / top_k 20 / min_p 0.05 do. Recorded tok_s is the sustained depth figure: 17.10 t/s measured over 10,671 generated tokens in the code event, against 18.6 on a 256-token probe, so the probe is about 9% optimistic.",
        "llama_fork": "flint"
    }
}

def _resolve_local(cfg):
    """Bare .gguf filenames become absolute paths under MODELS_DIR."""
    for k in ("gguf", "draft"):
        v = cfg.get(k)
        if v and not os.path.isabs(v):
            cfg[k] = os.path.join(MODELS_DIR, v)
    args = cfg.get("server_args") or ""
    if ".gguf" in args:
        args = re.sub(r'(?<![\w/.-])([A-Za-z0-9._+-]+\.gguf)',
                      lambda m: os.path.join(MODELS_DIR, m.group(1)), args)
        cfg["server_args"] = args
    return cfg

MODEL_CONFIG = {k: _resolve_local(v) for k, v in MODEL_CONFIG.items()}

# ── Submitted-model overlay ──
# Models submitted from the command-center panel land in a JSON overlay instead of
# being written into this literal, so the runner keeps ONE reviewed model list and a
# panel-side change can never corrupt it. A missing or unreadable overlay is not an
# error: the bench must still start with every built-in model.
_OVERLAY = os.path.expanduser(
    os.environ.get("AGON_OVERLAY", os.path.join(ARENA, "submitted-models.json"))
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
# The only build with the nemotron_h_moe architecture (upstream PR #30520, commit cd0a5b6a1, build 95).
# A 74B/9B-active hybrid: 88 blocks = 40 Mamba-2/SSM + 40 MoE + 8 attention, IQ2_XXS experts.
LLAMA_SERVER_NEMOTRON = os.path.expanduser("~/llama-nemotron/build-vulkan/bin/llama-server")
# Raon-1 mini: upstream PR 31107 was closed unmerged, only KRAFTON's fork knows
# the raon1_mini arch (hybrid 18 RDA + 7 MLA layers, 128 experts, situ).
LLAMA_SERVER_RAON = os.path.expanduser("~/llama.cpp-raon/build-vulkan/bin/llama-server")
# LFM3 (Liquid, 2026-10-27): tri-hybrid arch, conv + full attention + sliding
# attention mixed per layer. Landed upstream the same day in PR 31252 / 31257, so
# no older build knows it.
LLAMA_SERVER_LFM3 = os.path.expanduser("~/llama-lfm3/build-vulkan/bin/llama-server")
# Flint (Recursive, 2026-10-21): 39.8B MoE, 256 experts top-6, 2.5B active. Upstream
# support landed in llama.cpp a37cc46104 (PR 30928), after the builds above.
LLAMA_SERVER_FLINT = os.path.expanduser("~/llama-flint/build-vulkan/bin/llama-server")

# PrismML's PINNED release binary (prism-b10777-e3de715, 2026-10-14), used as shipped with no build.
# It carries the Vulkan path for GPUs without hardware DP4A that this card needs (#291) plus the
# dedicated PTQ1_0 dequant shader (#252). Measured here 2026-10-16: PQ2_0 124.16 t/s prefill /
# 15.40 t/s decode (11.75 at an 8192 window) against 87.83 / 10.90 for PTQ1_0 on the same build.
LLAMA_SERVER_PRISM_PINNED = os.path.expanduser("~/bonsai2-pinned/llama-prism-b10777-e3de715/llama-server")

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
    elif fork == "nemotron":
        server_bin = LLAMA_SERVER_NEMOTRON
    elif fork == "raon":
        server_bin = LLAMA_SERVER_RAON
    elif fork == "prism_pinned":
        server_bin = LLAMA_SERVER_PRISM_PINNED
    elif fork == "lfm3":
        server_bin = LLAMA_SERVER_LFM3
    elif fork == "flint":
        server_bin = LLAMA_SERVER_FLINT
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
    if cfg.get("llama_fork") in ("vulkan", "moe", "ptq1", "xing", "vulkan-master", "mcpv47",
                                 "nemotron", "lfm3"):
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
    # Task rows are the authority on the score: a run resumed after an
    # interruption only writes summary.json for the tasks it re-ran, so the
    # summary total is a subset of the run. Recompute from the task table so a
    # resumed run cannot record e.g. 13/14 when its eight tasks sum to 23/24.
    task_table = f"{event}_tasks"
    c.execute(
        f"SELECT COALESCE(SUM(score),0), COALESCE(SUM(max_score),0), COUNT(*) "
        f"FROM {task_table} WHERE run_id=? AND status='completed'", (run_id,))
    t_sum, t_max, t_n = c.fetchone()
    if t_n and t_max and abs(t_sum - total_score) > 1e-6:
        log(f"  [DB] run {run_id}: summary said {total_score}/{max_score}, "
            f"task rows say {t_sum}/{t_max} ({t_n} tasks) - using task rows")
        total_score, max_score = t_sum, t_max
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


def run_model_benchmark(model_key, port=8100, max_runs=3, events=None):
    """Run the requested events x max_runs runs for a model (all three by default)."""
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
    all_events = ["agent", "code", "reason"]
    if events is None:
        events = all_events
    unknown = [e for e in events if e not in all_events]
    if unknown:
        log(f"  Unknown event(s): {', '.join(unknown)}")
        return False
    if events != all_events:
        log(f"  Events for this pass: {', '.join(events)}")
    
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
    parser.add_argument("--events", type=str, default=None,
                        help="Comma-separated events to run (agent,code,reason). Default: all")
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
        events = [e.strip() for e in args.events.split(",")] if args.events else None
        run_model_benchmark(key, args.port, args.runs, events)


if __name__ == "__main__":
    import sqlite3
    main()
