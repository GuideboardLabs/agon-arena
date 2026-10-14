#!/usr/bin/env python3
"""Generate an ER diagram of the Agon-Bench database schema as PNG."""
import sqlite3, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

DB = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
OUT = os.path.expanduser("~/Documents/agon-arena/agon-bench-schema.png")

# ── Table definitions ──
TABLES = {
    "models": {
        "pk": "id",
        "fks": {},
        "cols": [
            ("id", "INTEGER PK"),
            ("key", "TEXT UNIQUE"),
            ("label", "TEXT"),
            ("name", "TEXT"),
            ("size_gb", "REAL"),
            ("quant", "TEXT"),
            ("vram_class", "TEXT"),
            ("gguf_path", "TEXT"),
            ("draft_path", "TEXT"),
            ("is_moe", "INT"),
            ("needs_cpu_moe", "INT"),
            ("needs_reasoning_off", "INT"),
            ("gpu_layers", "INT"),
            ("gpu_layers_draft", "INT"),
            ("notes", "TEXT"),
            ("created_at", "TEXT"),
            ("updated_at", "TEXT"),
        ],
    },
    "model_config": {
        "pk": "model_id",
        "fks": {"model_id": "models.id"},
        "cols": [
            ("model_id", "INTEGER PK/FK"),
            ("server_args", "TEXT"),
            ("agent_ctx", "INT"),
            ("code_ctx", "INT"),
            ("reason_ctx", "INT"),
            ("timeout_s", "INT"),
            ("tok_s", "REAL"),
            ("notes", "TEXT"),
        ],
    },
    "model_profiles": {
        "pk": "model_id",
        "fks": {"model_id": "models.id"},
        "cols": [
            ("model_id", "INTEGER PK/FK"),
            ("architecture", "TEXT"),
            ("total_params_b", "REAL"),
            ("active_params_b", "REAL"),
            ("num_experts", "INT"),
            ("active_experts", "INT"),
            ("context_window", "INT"),
            ("native_multimodal", "INT"),
            ("native_function_calling", "INT"),
            ("training_data", "TEXT"),
            ("license", "TEXT"),
            ("hf_repo", "TEXT"),
        ],
    },
    "agent_runs": {
        "pk": "id",
        "fks": {"model_id": "models.id"},
        "cols": [
            ("id", "INTEGER PK"),
            ("model_id", "INT FK"),
            ("run_number", "INT"),
            ("seed", "INT"),
            ("ctx_size", "INT"),
            ("temperature", "REAL"),
            ("max_tokens", "INT"),
            ("total_elapsed_s", "REAL"),
            ("total_prompt_tokens", "INT"),
            ("total_generated_tokens", "INT"),
            ("avg_tok_s", "REAL"),
            ("total_score", "REAL"),
            ("max_score", "INT"),
            ("vram_used_mb", "INT"),
            ("vram_total_mb", "INT"),
            ("thinking_off", "INT"),
            ("draft_model_used", "INT"),
            ("cpu_spill_pct", "REAL"),
            ("spec_type", "TEXT"),
            ("started_at", "TEXT"),
            ("completed_at", "TEXT"),
            ("status", "TEXT"),
            ("notes", "TEXT"),
        ],
    },
    "agent_tasks": {
        "pk": "id",
        "fks": {"run_id": "agent_runs.id"},
        "cols": [
            ("id", "INTEGER PK"),
            ("run_id", "INT FK"),
            ("task_id", "INT"),
            ("task_name", "TEXT"),
            ("difficulty", "TEXT"),
            ("score", "REAL"),
            ("max_score", "REAL"),
            ("elapsed_s", "REAL"),
            ("response_chars", "INT"),
            ("prompt_tokens", "INT"),
            ("generated_tokens", "INT"),
            ("tok_s", "REAL"),
            ("thinking_chars", "INT"),
            ("response_chars_total", "INT"),
            ("details", "TEXT"),
            ("started_at", "TEXT"),
            ("completed_at", "TEXT"),
            ("status", "TEXT"),
        ],
    },
    "code_runs": {
        "pk": "id",
        "fks": {"model_id": "models.id"},
        "cols": [],
    },
    "code_tasks": {
        "pk": "id",
        "fks": {"run_id": "code_runs.id"},
        "cols": [],
    },
    "reason_runs": {
        "pk": "id",
        "fks": {"model_id": "models.id"},
        "cols": [],
    },
    "reason_tasks": {
        "pk": "id",
        "fks": {"run_id": "reason_runs.id"},
        "cols": [],
    },
    "benchmark_runs": {
        "pk": "id",
        "fks": {"model_id": "models.id"},
        "cols": [
            ("id", "INTEGER PK"),
            ("model_id", "INT FK"),
            ("event", "TEXT"),
            ("run_number", "INT"),
            ("seed", "INT"),
            ("timestamp", "TEXT"),
            ("ctx_size", "INT"),
            ("temperature", "REAL"),
            ("max_tokens", "INT"),
            ("total_elapsed_s", "REAL"),
            ("total_prompt_tokens", "INT"),
            ("total_generated_tokens", "INT"),
            ("avg_tok_s", "REAL"),
            ("total_score", "REAL"),
            ("max_score", "INT"),
            ("notes", "TEXT"),
            ("vram_used_mb", "INT"),
            ("vram_total_mb", "INT"),
            ("thinking_off", "INT"),
            ("draft_model_used", "INT"),
            ("cpu_spill_pct", "REAL"),
            ("spec_type", "TEXT"),
        ],
    },
    "task_scores": {
        "pk": "id",
        "fks": {"run_id": "benchmark_runs.id"},
        "cols": [
            ("id", "INTEGER PK"),
            ("run_id", "INT FK"),
            ("task_id", "INT"),
            ("task_name", "TEXT"),
            ("max_score", "REAL"),
            ("score", "REAL"),
            ("elapsed_s", "REAL"),
            ("response_chars", "INT"),
            ("prompt_tokens", "INT"),
            ("generated_tokens", "INT"),
            ("tok_s", "REAL"),
            ("thinking_chars", "INT"),
            ("response_chars_total", "INT"),
            ("details", "TEXT"),
        ],
    },
    "gpu_log": {
        "pk": "id",
        "fks": {"model_id": "models.id"},
        "cols": [
            ("id", "INTEGER PK"),
            ("timestamp", "TEXT"),
            ("model_id", "INT FK"),
            ("vram_total_mb", "INT"),
            ("vram_used_mb", "INT"),
            ("vram_free_mb", "INT"),
            ("gpu_util_pct", "REAL"),
            ("notes", "TEXT"),
        ],
    },
}

# Fix the copy-paste issue: code_runs, reason_runs need their own col lists
TABLES["code_runs"]["cols"] = [
    ("id", "INTEGER PK"),
    ("model_id", "INT FK"),
    ("run_number", "INT"),
    ("seed", "INT"),
    ("ctx_size", "INT"),
    ("temperature", "REAL"),
    ("max_tokens", "INT"),
    ("total_elapsed_s", "REAL"),
    ("total_prompt_tokens", "INT"),
    ("total_generated_tokens", "INT"),
    ("avg_tok_s", "REAL"),
    ("total_score", "REAL"),
    ("max_score", "INT"),
    ("vram_used_mb", "INT"),
    ("vram_total_mb", "INT"),
    ("thinking_off", "INT"),
    ("draft_model_used", "INT"),
    ("cpu_spill_pct", "REAL"),
    ("spec_type", "TEXT"),
    ("started_at", "TEXT"),
    ("completed_at", "TEXT"),
    ("status", "TEXT"),
    ("notes", "TEXT"),
]
TABLES["reason_runs"]["cols"] = TABLES["code_runs"]["cols"][:]
TABLES["code_tasks"]["cols"] = [
    ("id", "INTEGER PK"),
    ("run_id", "INT FK"),
    ("task_id", "INT"),
    ("task_name", "TEXT"),
    ("difficulty", "TEXT"),
    ("score", "REAL"),
    ("max_score", "REAL"),
    ("elapsed_s", "REAL"),
    ("response_chars", "INT"),
    ("prompt_tokens", "INT"),
    ("generated_tokens", "INT"),
    ("tok_s", "REAL"),
    ("thinking_chars", "INT"),
    ("response_chars_total", "INT"),
    ("details", "TEXT"),
    ("started_at", "TEXT"),
    ("completed_at", "TEXT"),
    ("status", "TEXT"),
]
TABLES["reason_tasks"]["cols"] = TABLES["code_tasks"]["cols"][:]

# ── Layout ──
# Position tables in a grid
LAYOUT = {
    "models": (0, 0),
    "model_config": (0, 1),
    "model_profiles": (0, 2),
    "agent_runs": (1, 0),
    "agent_tasks": (1, 1),
    "code_runs": (2, 0),
    "code_tasks": (2, 1),
    "reason_runs": (3, 0),
    "reason_tasks": (3, 1),
    "benchmark_runs": (4, 0),
    "task_scores": (4, 1),
    "gpu_log": (5, 0),
}

# ── Drawing ──
COL_W = 2.8   # table width in inches
ROW_H = 0.28  # row height
HEADER_H = 0.35
PAD_X = 0.8
PAD_Y = 0.6

# Calculate figure size
max_row = max(r for r, c in LAYOUT.values())
max_col = max(c for r, c in LAYOUT.values())
fig_w = (max_col + 1) * (COL_W + PAD_X) + 1
fig_h = (max_row + 1) * (len(TABLES["models"]["cols"]) * ROW_H + HEADER_H + PAD_Y) + 1

fig, ax = plt.subplots(1, 1, figsize=(fig_w, fig_h))
ax.set_xlim(0, fig_w)
ax.set_ylim(0, fig_h)
ax.axis("off")
ax.set_facecolor("#1a1a2e")
fig.patch.set_facecolor("#1a1a2e")

# Colors
PK_COLOR = "#e8d44d"
FK_COLOR = "#6ab0f3"
COL_COLOR = "#c8d6e5"
HEADER_BG = "#0f3460"
TABLE_BG = "#16213e"
BORDER_COLOR = "#0f3460"
FK_LINE_COLOR = "#6ab0f3"

def draw_table(ax, name, cols, pk, fks, row, col):
    x = col * (COL_W + PAD_X) + 0.5
    y = fig_h - (row * (len(cols) * ROW_H + HEADER_H + PAD_Y) + 1.5)
    w = COL_W
    h = HEADER_H + len(cols) * ROW_H + 0.1

    # Table background
    rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                          facecolor=TABLE_BG, edgecolor=BORDER_COLOR, linewidth=1.5, zorder=1)
    ax.add_patch(rect)

    # Header
    header = FancyBboxPatch((x, y + h - HEADER_H), w, HEADER_H,
                            boxstyle="round,pad=0.02",
                            facecolor=HEADER_BG, edgecolor=BORDER_COLOR, linewidth=1.5, zorder=2)
    ax.add_patch(header)
    ax.text(x + w/2, y + h - HEADER_H/2, name, ha="center", va="center",
            fontsize=9, fontweight="bold", color="#e8d44d", zorder=3)

    # Columns
    for i, (cname, ctype) in enumerate(cols):
        cy = y + h - HEADER_H - (i + 1) * ROW_H + 0.05
        is_pk = cname == pk
        is_fk = cname in fks

        if is_pk and is_fk:
            color = "#f0a030"  # PK+FK
            marker = "PK+FK"
        elif is_pk:
            color = PK_COLOR
            marker = "PK"
        elif is_fk:
            color = FK_COLOR
            marker = "FK"
        else:
            color = COL_COLOR
            marker = "  "

        # Column bg
        if i % 2 == 0:
            bg = mpatches.Rectangle((x + 0.05, cy), w - 0.1, ROW_H - 0.02,
                                    facecolor="#1e2a4a", edgecolor="none", zorder=1)
            ax.add_patch(bg)

        # Type badge
        type_short = ctype.split()[0] if ctype else ""
        ax.text(x + 0.1, cy + ROW_H/2 - 0.02, marker, fontsize=7, va="center", color=color, zorder=3)
        ax.text(x + 0.35, cy + ROW_H/2 - 0.02, cname, fontsize=7, va="center",
                fontweight="bold" if is_pk else "normal", color=color, zorder=3)
        ax.text(x + w - 0.1, cy + ROW_H/2 - 0.02, type_short, fontsize=5.5, va="center",
                ha="right", color="#7f8fa6", zorder=3)

    return x, y, w, h

# Draw all tables
positions = {}
for tname, tinfo in TABLES.items():
    r, c = LAYOUT.get(tname, (0, 0))
    x, y, w, h = draw_table(ax, tname, tinfo["cols"], tinfo["pk"], tinfo["fks"], r, c)
    positions[tname] = (x, y, w, h)

# Draw FK relationships
for tname, tinfo in TABLES.items():
    for fk_col, ref in tinfo["fks"].items():
        ref_table = ref.split(".")[0]
        if ref_table not in positions or tname not in positions:
            continue
        src_x, src_y, src_w, src_h = positions[tname]
        dst_x, dst_y, dst_w, dst_h = positions[ref_table]

        # Find the FK column's y position
        cols = tinfo["cols"]
        fk_idx = next((i for i, (c, _) in enumerate(cols) if c == fk_col), None)
        if fk_idx is None:
            continue
        fk_y = src_y + src_h - HEADER_H - (fk_idx + 1) * ROW_H + ROW_H/2

        # Find the PK column's y position in the ref table
        ref_info = TABLES[ref_table]
        pk_idx = next((i for i, (c, _) in enumerate(ref_info["cols"]) if c == ref_info["pk"]), None)
        if pk_idx is None:
            pk_y = dst_y + dst_h - HEADER_H/2
        else:
            pk_y = dst_y + dst_h - HEADER_H - (pk_idx + 1) * ROW_H + ROW_H/2

        # Draw FK line
        start = (src_x + src_w, fk_y)
        end = (dst_x, pk_y)
        mid_x = (start[0] + end[0]) / 2

        ax.plot([start[0], mid_x, mid_x, end[0]],
                [start[1], start[1], end[1], end[1]],
                color=FK_LINE_COLOR, linewidth=0.8, alpha=0.5,
                linestyle="--", zorder=0)

        # Arrow at the end
        ax.annotate("", xy=(end[0] - 0.05, end[1]), xytext=(end[0] + 0.1, end[1]),
                    arrowprops=dict(arrowstyle="->", color=FK_LINE_COLOR, lw=0.8, alpha=0.5),
                    zorder=0)

# Legend
legend_y = 0.5
ax.text(0.3, legend_y + 0.3, "Legend", fontsize=10, fontweight="bold", color="#e8d44d", zorder=5)
ax.text(0.3, legend_y, "PK  Primary Key", fontsize=8, color=PK_COLOR, zorder=5)
ax.text(0.3, legend_y - 0.3, "FK  Foreign Key", fontsize=8, color=FK_COLOR, zorder=5)
ax.text(0.3, legend_y - 0.6, "PK+FK  Composite PK/FK", fontsize=8, color="#f0a030", zorder=5)
ax.text(0.3, legend_y - 0.9, "- - →  FK Relationship", fontsize=8, color=FK_LINE_COLOR, zorder=5)

# Title
ax.text(fig_w/2, fig_h - 0.3, "Agon-Bench Database Schema (v3 + MTP)",
        fontsize=14, fontweight="bold", ha="center", color="#e8d44d", zorder=5)

plt.tight_layout(pad=0)
plt.savefig(OUT, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Schema diagram saved to {OUT}")
print(f"Size: {os.path.getsize(OUT)} bytes")
