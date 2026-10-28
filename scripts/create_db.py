#!/usr/bin/env python3
"""
Agon-Bench v3 Database Schema — stable model IDs, per-event tables, per-task real-time tracking.
"""
import sqlite3, os
from pathlib import Path

DB_PATH = os.environ.get("AGON_DB", str(Path(__file__).resolve().parent.parent / "agon-bench.db"))

SCHEMA_SQL = """
-- Models: stable IDs via INSERT OR IGNORE + UPDATE pattern
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    label TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    size_gb REAL,
    quant TEXT,
    vram_class TEXT,
    gguf_path TEXT,
    draft_path TEXT,
    is_moe INTEGER DEFAULT 0,
    needs_cpu_moe INTEGER DEFAULT 0,
    needs_reasoning_off INTEGER DEFAULT 0,
    gpu_layers INTEGER,
    gpu_layers_draft INTEGER,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS model_config (
    model_id INTEGER PRIMARY KEY,
    server_args TEXT,
    agent_ctx INTEGER DEFAULT 4096,
    code_ctx INTEGER DEFAULT 16384,
    reason_ctx INTEGER DEFAULT 4096,
    timeout_s INTEGER DEFAULT 3600,
    tok_s REAL,
    notes TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id)
);

CREATE TABLE IF NOT EXISTS model_profiles (
    model_id INTEGER PRIMARY KEY,
    architecture TEXT,
    total_params_b REAL,
    active_params_b REAL,
    num_experts INTEGER,
    active_experts INTEGER,
    context_window INTEGER,
    native_multimodal INTEGER DEFAULT 0,
    native_function_calling INTEGER DEFAULT 0,
    training_data TEXT,
    license TEXT,
    hf_repo TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id)
);

-- Agent event
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,
    seed INTEGER,
    ctx_size INTEGER DEFAULT 4096,
    temperature REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 32768,
    total_elapsed_s REAL,
    total_prompt_tokens INTEGER,
    total_generated_tokens INTEGER,
    avg_tok_s REAL,
    total_score REAL,
    max_score INTEGER,
    vram_used_mb INTEGER,
    vram_total_mb INTEGER,
    thinking_off INTEGER DEFAULT 0,
    draft_model_used INTEGER DEFAULT 0,
    cpu_spill_pct REAL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    notes TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id),
    UNIQUE(model_id, run_number)
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    difficulty TEXT,
    score REAL DEFAULT 0,
    max_score REAL DEFAULT 0,
    elapsed_s REAL,
    response_chars INTEGER,
    prompt_tokens INTEGER,
    generated_tokens INTEGER,
    tok_s REAL,
    thinking_chars INTEGER,
    response_chars_total INTEGER,
    details TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    FOREIGN KEY (run_id) REFERENCES agent_runs(id),
    UNIQUE(run_id, task_id)
);

-- Code event
CREATE TABLE IF NOT EXISTS code_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,
    seed INTEGER,
    ctx_size INTEGER DEFAULT 16384,
    temperature REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 32768,
    total_elapsed_s REAL,
    total_prompt_tokens INTEGER,
    total_generated_tokens INTEGER,
    avg_tok_s REAL,
    total_score REAL,
    max_score INTEGER,
    vram_used_mb INTEGER,
    vram_total_mb INTEGER,
    thinking_off INTEGER DEFAULT 0,
    draft_model_used INTEGER DEFAULT 0,
    cpu_spill_pct REAL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    notes TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id),
    UNIQUE(model_id, run_number)
);

CREATE TABLE IF NOT EXISTS code_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    difficulty TEXT,
    score REAL DEFAULT 0,
    max_score REAL DEFAULT 0,
    elapsed_s REAL,
    response_chars INTEGER,
    prompt_tokens INTEGER,
    generated_tokens INTEGER,
    tok_s REAL,
    details TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    FOREIGN KEY (run_id) REFERENCES code_runs(id),
    UNIQUE(run_id, task_id)
);

-- Reason event
CREATE TABLE IF NOT EXISTS reason_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL,
    run_number INTEGER NOT NULL,
    seed INTEGER,
    ctx_size INTEGER DEFAULT 4096,
    temperature REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 32768,
    total_elapsed_s REAL,
    total_prompt_tokens INTEGER,
    total_generated_tokens INTEGER,
    avg_tok_s REAL,
    total_score REAL,
    max_score INTEGER,
    vram_used_mb INTEGER,
    vram_total_mb INTEGER,
    thinking_off INTEGER DEFAULT 0,
    draft_model_used INTEGER DEFAULT 0,
    cpu_spill_pct REAL,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    notes TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id),
    UNIQUE(model_id, run_number)
);

CREATE TABLE IF NOT EXISTS reason_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    difficulty TEXT,
    score REAL DEFAULT 0,
    max_score REAL DEFAULT 0,
    elapsed_s REAL,
    response_chars INTEGER,
    prompt_tokens INTEGER,
    generated_tokens INTEGER,
    tok_s REAL,
    details TEXT,
    started_at TEXT,
    completed_at TEXT,
    status TEXT DEFAULT 'running',
    FOREIGN KEY (run_id) REFERENCES reason_runs(id),
    UNIQUE(run_id, task_id)
);

-- GPU log
CREATE TABLE IF NOT EXISTS gpu_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    model_id INTEGER,
    vram_total_mb INTEGER,
    vram_used_mb INTEGER,
    vram_free_mb INTEGER,
    gpu_util_pct REAL,
    notes TEXT,
    FOREIGN KEY (model_id) REFERENCES models(id)
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def upsert_model(key, name, label, **kwargs):
    """Insert or update a model, returning its stable ID."""
    conn = get_db()
    c = conn.cursor()
    # Try to insert, ignore if exists
    c.execute("INSERT OR IGNORE INTO models (key, name, label) VALUES (?, ?, ?)",
              (key, name, label))
    # Update fields
    fields = []
    values = []
    for k, v in kwargs.items():
        if v is not None:
            fields.append(f"{k}=?")
            values.append(v)
    if fields:
        fields.append("updated_at=datetime('now')")
        c.execute(f"UPDATE models SET {', '.join(fields)} WHERE key=?",
                  values + [key])
    # Get stable ID
    c.execute("SELECT id FROM models WHERE key=?", (key,))
    model_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return model_id


def create_run(event, model_id, run_number, seed, ctx_size, temperature=0.3, max_tokens=32768):
    """Create a run entry and return its ID."""
    conn = get_db()
    c = conn.cursor()
    table = f"{event}_runs"
    c.execute(f"""
        INSERT OR IGNORE INTO {table}
        (model_id, run_number, seed, ctx_size, temperature, max_tokens, started_at, status)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'), 'running')
    """, (model_id, run_number, seed, ctx_size, temperature, max_tokens))
    c.execute(f"SELECT id FROM {table} WHERE model_id=? AND run_number=?",
              (model_id, run_number))
    run_id = c.fetchone()[0]
    conn.commit()
    conn.close()
    return run_id


def complete_run(event, run_id, total_elapsed_s, total_score, max_score,
                 total_prompt_tokens=0, total_generated_tokens=0, avg_tok_s=None,
                 vram_used_mb=None, vram_total_mb=None, status='completed', notes=None):
    """Mark a run as completed with final stats."""
    conn = get_db()
    c = conn.cursor()
    table = f"{event}_runs"
    c.execute(f"""
        UPDATE {table} SET
            total_elapsed_s=?,
            total_prompt_tokens=?,
            total_generated_tokens=?,
            avg_tok_s=?,
            total_score=?,
            max_score=?,
            vram_used_mb=?,
            vram_total_mb=?,
            completed_at=datetime('now'),
            status=?,
            notes=COALESCE(?, notes)
        WHERE id=?
    """, (total_elapsed_s, total_prompt_tokens, total_generated_tokens,
          avg_tok_s, total_score, max_score,
          vram_used_mb, vram_total_mb, status, notes, run_id))
    conn.commit()
    conn.close()


def save_task_result(event, run_id, task_id, task_name, difficulty,
                     score, max_score, elapsed_s, response_chars,
                     prompt_tokens, generated_tokens, tok_s,
                     details=None, thinking_chars=None, response_chars_total=None):
    """Write per-task result to DB immediately."""
    conn = get_db()
    c = conn.cursor()
    task_table = f"{event}_tasks"
    c.execute(f"""
        INSERT OR REPLACE INTO {task_table}
        (run_id, task_id, task_name, difficulty, score, max_score, elapsed_s,
         response_chars, prompt_tokens, generated_tokens, tok_s,
         details, thinking_chars, response_chars_total,
         started_at, completed_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'completed')
    """, (run_id, task_id, task_name, difficulty,
          score, max_score, round(elapsed_s, 1),
          response_chars, prompt_tokens or 0, generated_tokens or 0,
          round(tok_s, 1) if tok_s else None,
          json.dumps(details) if details else None,
          thinking_chars, response_chars_total))
    conn.commit()
    conn.close()


def get_model_id(key):
    """Get stable model ID by key."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id FROM models WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_run_id(event, model_id, run_number):
    """Get run ID for a model+run."""
    conn = get_db()
    c = conn.cursor()
    table = f"{event}_runs"
    c.execute(f"SELECT id FROM {table} WHERE model_id=? AND run_number=?", (model_id, run_number))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_completed_tasks(event, run_id):
    """Get set of completed task IDs for a run."""
    conn = get_db()
    c = conn.cursor()
    table = f"{event}_tasks"
    c.execute(f"SELECT task_id FROM {table} WHERE run_id=? AND status='completed'", (run_id,))
    tasks = {row[0] for row in c.fetchall()}
    conn.close()
    return tasks


if __name__ == "__main__":
    import json
    init_database()
    print("Database schema initialized.")
