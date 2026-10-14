#!/usr/bin/env python3
"""
Agon-Bench Dashboard Server v2 — serves model data from per-event tables.
Replaces the original that was overwritten with a PNG.
"""
import json, os, sqlite3, sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DB_PATH = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")

# ── Model metadata (hardcoded from MODEL_CONFIG + model_profiles) ──
MODEL_META = {
    "underdog_saluki_27b_iq2": {
        "label": "Underdog-Saluki-27B-IQ2", "color": {"bg": "rgba(230,126,34,0.85)", "border": "#e67e22", "light": "rgba(230,126,34,0.15)"},
        "tags": ["Underdog", "Saluki", "IQ2-mix", "2-bit", "Apache-2.0", "7.9 GB"],
        "size_gb": 7.9, "quant": "IQ2-mix",
        "arch": "Qwen3.8-27B dense, 2-bit distill", "params": "27B dense", "ctx": 262144,
        "fc": True, "mm": True, "license": "Apache-2.0", "hf": "ConwayResearch/Underdog-Saluki-27B-1.0",
        "training": "Underdog AI's IQ2-mix (approx 2.3 bpw) quant/distill of Qwen3.8-27B, stock llama.cpp, shipped with mmproj vision projectors",
        "assessment": "Under evaluation. Runs fully VRAM-resident with CPU spill at 23.2 t/s decode / 96 t/s prefill. Tool calling verified by hand: single call correct in 4.1s, parallel 3/3, no-tool case valid. Reasoning is off in this config because the model's own chat template defaults reasoning_effort to xhigh."
    },
    "mimo_v26_9b_ablit": {
        "label": "MiMo-V2.6-Distill-9B-Ablit", "color": {"bg": "rgba(155,89,182,0.85)", "border": "#9b59b6", "light": "rgba(155,89,182,0.15)"},
        "tags": ["MiMo-V2.6", "Qwen-distill", "Apache-2.0", "5.24 GB", "Abliterated"],
        "size_gb": 5.24, "quant": "Q4_K_M",
        "arch": "MiMo-V2.6 distill on Qwen (dense)", "params": "9B dense", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Hikari07jp/MiMo-V2.6-Distill-Qwen-9B-Ablitrated",
        "training": "Distilled from Xiaomi MiMo-V2.6, then community-abliterated (refusal removal)",
        "assessment": "52 t/s decode (measured, fully VRAM-resident) - 4th of 13 in the 9B class and 2nd among dense 9B behind Qwen3.5-9B (60). Hybrid SSM/attention on a Qwen3.5 base. Reasoning is the weak point: 11/17 substantive on the reason event (one recorded point was unearned) and it degenerates into repetition loops on hard tasks. Fast, not competitive."
    },
    "omnicoder_9b": {
        "label": "OmniCoder-9B", "color": {"bg": "rgba(230,126,34,0.85)", "border": "#e67e22", "light": "rgba(230,126,34,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.4 GB", "Thinking"],
        "size_gb": 5.4, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense (Claude Opus distill)", "params": "9B dense", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Tesslate/OmniCoder-9B",
        "training": "Claude Opus reasoning distillation on Qwen3.5-9B",
        "assessment": "Fastest in class at 52.7 tok/s. Exceptional reasoning but highly inconsistent on agent and code tasks."
    },
    "qwen35_9b": {
        "label": "Qwen3.5-9B", "color": {"bg": "rgba(52,152,219,0.85)", "border": "#3498db", "light": "rgba(52,152,219,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.3 GB"],
        "size_gb": 5.3, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Qwen/Qwen3.5-9B",
        "training": "Qwen3.5 base pre-training",
        "assessment": "Solid all-rounder. Strong reasoning, decent agent, average code. Good baseline."
    },
    "ornith_9b": {
        "label": "Ornith-1.0-9B", "color": {"bg": "rgba(155,89,182,0.85)", "border": "#9b59b6", "light": "rgba(155,89,182,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.3 GB", "RL"],
        "size_gb": 5.3, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense RL", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "deepreinforce-ai/Ornith-1.0-9B",
        "training": "Qwen3.5-9B + RL agentic coding",
        "assessment": "Best 9B model. Strong across all events. RL training shows clearly."
    },
    "gemma4_12b": {
        "label": "Gemma4-12B", "color": {"bg": "rgba(46,204,113,0.85)", "border": "#2ecc71", "light": "rgba(46,204,113,0.15)"},
        "tags": ["Gemma4", "Apache-2.0", "6.7 GB", "Multimodal"],
        "size_gb": 6.7, "quant": "Q4_K_XL",
        "arch": "Gemma4 dense", "params": "12B dense", "ctx": 262144,
        "fc": True, "mm": True, "license": "Apache-2.0", "hf": "google/gemma-4-12b-it",
        "training": "Google proprietary + synthetic",
        "assessment": "Strong multimodal contender. 24 tok/s fully in VRAM. Reasoning ON."
    },
    "grug_12b": {
        "label": "Grug-12B", "color": {"bg": "rgba(231,76,60,0.85)", "border": "#e74c3c", "light": "rgba(231,76,60,0.15)"},
        "tags": ["Gemma4", "Apache-2.0", "6.9 GB", "Fine-tune"],
        "size_gb": 6.9, "quant": "Q4_K_M",
        "arch": "Gemma4-12B fine-tune", "params": "12B dense", "ctx": 262144,
        "fc": True, "mm": True, "license": "Apache-2.0", "hf": "mradermacher/Grug-12B-GGUF",
        "training": "Gemma4-12B + RL fine-tune",
        "assessment": "Gemma4-12B fine-tune. 34 tok/s. Weaker than base Gemma4-12B on most tasks."
    },
    "gemma4_26b": {
        "label": "Gemma4-26B-A4B", "color": {"bg": "rgba(39,174,96,0.85)", "border": "#27ae60", "light": "rgba(39,174,96,0.15)"},
        "tags": ["Gemma4", "Apache-2.0", "16.9 GB", "MoE", "Multimodal"],
        "size_gb": 16.9, "quant": "Q4_K_M",
        "arch": "Gemma4 MoE", "params": "26B (4B active)", "ctx": 262144,
        "fc": True, "mm": True, "license": "Apache-2.0", "hf": "google/gemma-4-26b-it",
        "training": "Google proprietary + synthetic",
        "assessment": "Best model overall. 13.5 tok/s with MTP draft. MoE CPU spill required."
    },
    "lfm25_8b": {
        "label": "LFM2.5-8B-A1B", "color": {"bg": "rgba(241,196,15,0.85)", "border": "#f1c40f", "light": "rgba(241,196,15,0.15)"},
        "tags": ["LFM", "Apache-2.0", "5.0 GB", "MoE"],
        "size_gb": 5.0, "quant": "Q4_K_XL",
        "arch": "LFM2.5 MoE", "params": "8B (1B active)", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "lightonai/LFM-2.5-8B-A1B",
        "training": "LightOn AI proprietary",
        "assessment": "Fastest at 91 tok/s. 1B active params. Good value for speed."
    },
    "lfm25_24b_a2b_q4": {
        "label": "LFM2.5-24B-A2B", "color": {"bg": "rgba(22,160,133,0.85)", "border": "#16a085", "light": "rgba(22,160,133,0.15)"},
        "tags": ["LFM", "LFM1.0", "14.5 GB", "MoE", "Agent", "Hermes-tuned"],
        "size_gb": 14.53, "quant": "Q4_K_M",
        "arch": "LFM2.5 MoE hybrid (30 conv + 10 attn)", "params": "24B (2B active)", "ctx": 131072,
        "fc": True, "mm": False, "license": "LFM1.0 (<$10M revenue)", "hf": "LiquidAI/LFM2.5-24B-A2B-GGUF",
        "training": "Liquid AI post-training + agentic RL run inside Hermes Agent (@NousResearch)",
        "assessment": "PENDING - full Agon run in progress. Card claims LFM2.5 wins tool-use/agentic vs Qwen3.6-35B-A3B and loses knowledge/coding; card provenance is llama.cpp Q4_K_M at 4K input ctx."
    },
    "superqwen_35b": {
        "label": "SuperQwen-35B", "color": {"bg": "rgba(52,73,94,0.85)", "border": "#34495e", "light": "rgba(52,73,94,0.15)"},
        "tags": ["Qwen2.5", "Apache-2.0", "21.0 GB", "MoE", "Agent"],
        "size_gb": 21.0, "quant": "Q4_K_M",
        "arch": "Qwen2.5 MoE Agent", "params": "35B (3B active)", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "NovaSky-AI/SuperQwen-AgentWorld-35B-A3B",
        "training": "Qwen2.5-32B + agentic SFT",
        "assessment": "Agent-focused MoE. 10.8 tok/s. Only 1 reason run completed."
    },
    "qwythos_9b_v1": {
        "label": "Qwythos-9B-v1", "color": {"bg": "rgba(230,126,34,0.85)", "border": "#e67e22", "light": "rgba(230,126,34,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.3 GB", "v1"],
        "size_gb": 5.3, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense", "params": "9B dense", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Tesslate/Qwythos-9B-v1",
        "training": "Claude Opus reasoning distillation on Qwen3.5-9B",
        "assessment": "v1 benchmark (57pt scale). Hand-graded. 30.4 tok/s."
    },
    "qwopus_9b": {
        "label": "Qwopus3.5-9B-Coder", "color": {"bg": "rgba(0,188,212,0.85)", "border": "#00bcd4", "light": "rgba(0,188,212,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "4.5 GB", "Coder"],
        "size_gb": 4.5, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Tesslate/Qwopus3.5-9B-Coder",
        "training": "Qwen3.5-9B fine-tune for coding. MTP head ignored (no benefit on 8GB).",
        "assessment": "Coding fine-tune of Qwen3.5-9B. Strong code scores."
    },
    "qwopus_mtp": {
        "label": "Qwopus3.5-9B-Coder-MTP", "color": {"bg": "rgba(0,150,136,0.85)", "border": "#009688", "light": "rgba(0,150,136,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.8 GB", "MTP"],
        "size_gb": 5.8, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense MTP", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Tesslate/Qwopus3.5-9B-Coder",
        "training": "Qwen3.5-9B coder fine-tune with baked-in MTP head. 57.5 tok/s with MTP.",
        "assessment": "MTP variant of Qwopus. Only code run completed."
    },
    "holo_31_9b_coder": {
        "label": "Holo-3.1-9B-Coder", "color": {"bg": "rgba(0,188,212,0.85)", "border": "#00bcd4", "light": "rgba(0,188,212,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.3 GB", "Coder"],
        "size_gb": 5.3, "quant": "Q4_K_M",
        "arch": "Qwen3.5 dense coder", "params": "9B dense", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Tesslate/Holo-3.1-9B-Coder",
        "training": "Qwen3.5-9B fine-tune for coding",
        "assessment": "Coder fine-tune of Qwen3.5-9B. Solid reasoning, inconsistent code. Mid-pack overall."
    },
    "bonsai_27b_q1_0": {
        "label": "Bonsai-27B-Q1_0", "color": {"bg": "rgba(255,87,34,0.85)", "border": "#ff5722", "light": "rgba(255,87,34,0.15)"},
        "tags": ["Bonsai", "Apache-2.0", "3.8 GB", "1-bit", "PrismML"],
        "size_gb": 3.8, "quant": "Q1_0",
        "arch": "Bonsai 27B 1-bit ternary", "params": "27B (1.125 bpw)", "ctx": 32768,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "BonsaiAI/Bonsai-27B",
        "training": "1-bit Bonsai 27B. 1.125 bpw ternary. 90% of FP16. 12.5 tok/s. Uses PrismML llama.cpp fork.",
        "assessment": "3.8GB model that punches way above its weight. #2 overall at 81.3%. Elite agent (93.1%). Slow at 12.5 tok/s."
    },
    "nanbeige_3b": {
        "label": "Nanbeige4.2-3B", "color": {"bg": "rgba(0,150,136,0.85)", "border": "#009688", "light": "rgba(0,150,136,0.15)"},
        "tags": ["Nanbeige", "Apache-2.0", "2.4 GB", "Looped", "3B"],
        "size_gb": 2.4, "quant": "Q4_K_M",
        "arch": "Nanbeige Looped Transformer", "params": "3B (4B total)", "ctx": 262144,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "Nanbeige/Nanbeige4.2-3B",
        "training": "Nanbeige4.2 Looped Transformer. 22 phys layers x2 loops = 44 effective. 3B non-embedding params.",
        "assessment": "3B Looped Transformer. 44.9 tok/s on AMD ROCm. Strong reasoning (86.3%). Mid-pack agent and code."
    },
    "qwen38_9b": {
        "label": "Qwen3.8-9B", "color": {"bg": "rgba(41,128,185,0.85)", "border": "#2980b9", "light": "rgba(41,128,185,0.15)"},
        "tags": ["Qwen3.8", "Apache-2.0", "5.78 GB", "Distill", "Gated DeltaNet"],
        "size_gb": 5.78, "quant": "Q4_K_M",
        "arch": "Qwen3.5-9B (Gated DeltaNet hybrid)", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "empero-ai/Qwen3.8-9B",
        "training": "Full-parameter distillation of Qwen3.8 2.4T A95B into Qwen3.5-9B arch",
        "assessment": "Qwen3.8 2.4T distilled to 9B. mmlu 0.751 vs 0.546 base. New contender in the 9B class."
    },
    "heem_9b": {
        "label": "Heem-9B (Uncensored)", "color": {"bg": "rgba(192,57,43,0.85)", "border": "#c0392b", "light": "rgba(192,57,43,0.15)"},
        "tags": ["Qwen3.5-9B", "Apache-2.0", "5.63 GB", "Abliterated", "Uncensored"],
        "size_gb": 5.63, "quant": "Q4_K_M",
        "arch": "Qwen3.5-9B dense (abliterated)", "params": "9B dense", "ctx": 131072,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "HauhauCS/Qwen3.5-9B-Uncensored",
        "training": "Qwen3.5-9B + abliteration/uncensoring (HauhauCS-Aggressive)",
        "assessment": "Heem Discord bot's production model. Abliterated Qwen3.5-9B. Bench shows whether uncensoring cost capability."
    },
    "qwen38_35b_a3b_distill": {
        "label": "Qwen3.8-35B-A3B-Distill", "color": {"bg": "rgba(41,128,185,0.85)", "border": "#2980b9", "light": "rgba(41,128,185,0.15)"},
        "tags": ["Qwen3.6-35B-A3B", "Apache-2.0", "21.7 GB", "MoE", "Distill"],
        "size_gb": 21.7, "quant": "Q4_K_M",
        "arch": "Qwen3.6-35B-A3B MoE (256 experts, 8/token, Gated DeltaNet hybrid)", "params": "35B total / 3B active", "ctx": 262144,
        "fc": True, "mm": False, "license": "Apache-2.0", "hf": "empero-ai/Qwen3.8-35B-A3B-Distill-GGUF",
        "training": "Off-policy SFT distillation of Qwen3.8 2.4T A95B + Flash Next teacher traces into the Qwen3.6-35B-A3B base",
        "assessment": "Empero's first MoE. Same base weights as Qwen3.6-35B-Q4-ncmoe40 (the current #1) with Qwen3.8 reasoning distilled in, run on the identical -ncmoe 40 recipe so the distillation is the only variable. Vendor evals: ARC-C 0.548->0.591, MMLU flat at 0.834."
    },
}

# ── Task names ──
TASK_NAMES = {
    "agent": ["Tool Calling", "Orchestration", "Error Handling", "Planning", "Parsing", "Decision-Making", "Multi-Step Research Agent", "Memory-Augmented Agent"],
    "code": ["String Cleaner", "Log Parser", "LRU Cache", "File Indexer", "Task Runner CLI", "Constrained Diff Tool", "Regex Engine", "Concurrent Web Scraper"],
    "reason": ["Logical Deduction", "Math Word Problem", "Constraint Satisfaction", "Counterfactual Reasoning", "Analytical Explanation", "Multi-Hop Synthesis"],
}
TASK_MAX = {
    "agent": [3, 3, 4, 2, 3, 3, 3, 3],
    "code": [5, 4, 3, 2, 2, 3, 4, 2],
    "reason": [2, 3, 3, 3, 3, 3],
}
EVENT_MAX = {"agent": 24, "code": 25, "reason": 17}
EVENT_TABLES = {"agent": "agent_runs", "code": "code_runs", "reason": "reason_runs"}
EVENT_TASK_TABLES = {"agent": "agent_tasks", "code": "code_tasks", "reason": "reason_tasks"}


def get_db():
    return sqlite3.connect(DB_PATH)


def ensure_flag_columns():
    """Add flagged/flag_reason columns to models table if missing."""
    db = get_db()
    cur = db.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(models)")]
    if "flagged" not in cols:
        cur.execute("ALTER TABLE models ADD COLUMN flagged INTEGER DEFAULT 0")
    if "flag_reason" not in cols:
        cur.execute("ALTER TABLE models ADD COLUMN flag_reason TEXT")
    db.commit()
    db.close()


def get_model_data():
    """Query per-event tables and build model data dict.

    Auto-populates: includes ANY model with >=3 completed runs in all 3
    events (agent, code, reason), synthesizing default metadata for models
    without a hardcoded MODEL_META entry. Flagged models are included with
    their flag state so the UI can badge them.
    """
    ensure_flag_columns()
    db = get_db()
    cur = db.cursor()
    
    # Get all models
    cur.execute("SELECT id, key, label, size_gb, quant, flagged, flag_reason FROM models ORDER BY id")
    models = cur.fetchall()
    
    result = []
    for mid, key, label, size_gb, quant, flagged, flag_reason in models:
        # Count completed runs per event
        cur.execute("SELECT COUNT(*) FROM agent_runs WHERE model_id=? AND status='completed'", (mid,))
        n_agent = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM code_runs WHERE model_id=? AND status='completed'", (mid,))
        n_code = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM reason_runs WHERE model_id=? AND status='completed'", (mid,))
        n_reason = cur.fetchone()[0]
        
        # Auto-populate: require 3 full runs of all 3 events (unless flagged,
        # in which case keep it visible so the user can see the flag)
        if not (n_agent >= 3 and n_code >= 3 and n_reason >= 3) and not flagged:
            continue
        
        meta = MODEL_META.get(key, {})
        # Synthesize default metadata for models without a hardcoded entry
        if not meta:
            meta = {
                "label": label,
                "color": {"bg": "rgba(128,128,128,0.85)", "border": "#888", "light": "rgba(128,128,128,0.15)"},
                "tags": [quant or "GGUF"],
                "size_gb": size_gb or 0,
                "quant": quant or "",
                "arch": "",
                "params": "",
                "ctx": 0,
                "fc": False, "mm": False, "license": "",
                "hf": "", "training": "",
                "assessment": "",
            }
        
        # Get per-event scores (normalized to standard max)
        agent_scores = []
        code_scores = []
        reason_scores = []
        tok_s_list = []
        
        for event, table in EVENT_TABLES.items():
            cur.execute(f"SELECT total_score, max_score, avg_tok_s FROM {table} WHERE model_id=? AND status='completed' ORDER BY run_number", (mid,))
            rows = cur.fetchall()
            std_max = EVENT_MAX[event]
            for r in rows:
                score, max_s, tok = r
                if max_s and max_s > 0 and max_s != std_max:
                    # Normalize to standard max
                    score = score * std_max / max_s
                if event == "agent":
                    agent_scores.append(score)
                elif event == "code":
                    code_scores.append(score)
                elif event == "reason":
                    reason_scores.append(score)
                if tok:
                    tok_s_list.append(tok)
        
        # Get per-task scores (average across runs)
        task_scores = {"agent": [], "code": [], "reason": []}
        for event, task_table in EVENT_TASK_TABLES.items():
            run_table = EVENT_TABLES[event]
            cur.execute(f"""
                SELECT t.task_id, AVG(t.score) 
                FROM {task_table} t 
                JOIN {run_table} r ON t.run_id = r.id 
                WHERE r.model_id=? AND r.status='completed'
                GROUP BY t.task_id 
                ORDER BY t.task_id
            """, (mid,))
            task_rows = cur.fetchall()
            scores = [0.0] * len(TASK_NAMES[event])
            for tid, avg_score in task_rows:
                if 1 <= tid <= len(scores):
                    scores[tid - 1] = round(avg_score, 1)
            task_scores[event] = scores
        
        # Compute averages (normalize to standard max per event)
        agent_avg = sum(agent_scores) / len(agent_scores) if agent_scores else 0
        code_avg = sum(code_scores) / len(code_scores) if code_scores else 0
        reason_avg = sum(reason_scores) / len(reason_scores) if reason_scores else 0
        tok_s = sum(tok_s_list) / len(tok_s_list) if tok_s_list else 0
        total = agent_avg + code_avg + reason_avg
        max_score = 66
        
        result.append({
            "key": key,
            "label": meta.get("label", label),
            "color": meta.get("color", {"bg": "rgba(128,128,128,0.85)", "border": "#888", "light": "rgba(128,128,128,0.15)"}),
            "tags": meta.get("tags", []),
            "size_gb": size_gb or meta.get("size_gb", 0),
            "quant": quant or meta.get("quant", ""),
            "tok_s": round(tok_s, 1),
            "total": round(total, 1),
            "max": max_score,
            "agent": round(agent_avg, 1),
            "code": round(code_avg, 1),
            "reason": round(reason_avg, 1),
            "tasks": task_scores,
            "taskMax": TASK_MAX,
            "taskNames": TASK_NAMES,
            "arch": meta.get("arch", ""),
            "params": meta.get("params", ""),
            "ctx": meta.get("ctx", 0),
            "fc": meta.get("fc", False),
            "mm": meta.get("mm", False),
            "license": meta.get("license", ""),
            "hf": meta.get("hf", ""),
            "training": meta.get("training", ""),
            "assessment": meta.get("assessment", ""),
            "flagged": bool(flagged),
            "flag_reason": flag_reason or "",
            "runs": {"agent": n_agent, "code": n_code, "reason": n_reason},
        })
    
    db.close()
    return result


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            data = get_model_data()
            self.wfile.write(json.dumps(data).encode())
        elif path in ("/", "/index.html", "/agon-dashboard.html"):
            # RETIRED: the Agon-Bench UI now lives in the Jacquard command center,
            # which reads this same database directly. A pointer rather than a 404,
            # so an old bookmark reads as "it moved" instead of "it is broken".
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                b"<!doctype html><meta charset=utf-8><title>Agon-Bench moved</title>"
                b"<body style=\"font:14px system-ui;background:#111318;color:#e8eaed;"
                b"padding:40px;line-height:1.6\">"
                b"<h1 style=\"font-size:17px\">Agon-Bench moved</h1>"
                b"<p>The dashboard is now a panel in the Jacquard command center:</p>"
                b"<p><a style=\"color:#5eead4\" href=\"http://127.0.0.1:8195/?tab=agon\">"
                b"http://127.0.0.1:8195/?tab=agon</a></p>"
                b"<p style=\"color:#9aa0a6\">This process's /api/models and /api/flag still "
                b"work; only the UI moved. The panel reads agon-bench.db directly.</p>")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/flag":
            # Toggle the flagged state of a model. Body: {"key": "...", "flagged": true, "reason": "..."}
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode() or "{}")
                key = body.get("key")
                flagged = body.get("flagged", True)
                reason = body.get("reason", "")
                if not key:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing key")
                    return
                ensure_flag_columns()
                db = get_db()
                cur = db.cursor()
                cur.execute("UPDATE models SET flagged=?, flag_reason=? WHERE key=?", (1 if flagged else 0, reason if flagged else None, key))
                db.commit()
                db.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "key": key, "flagged": flagged}).encode())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
    
    def log_message(self, format, *args):
        pass  # suppress default logging


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"Agon-Bench Dashboard v2 on http://0.0.0.0:{port}")
    server.serve_forever()
