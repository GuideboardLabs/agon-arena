#!/usr/bin/env python3
"""
Re-grade all existing code task 7 (Regex Engine) responses using the new
partial-credit static analysis tests. Updates the DB with new scores.
"""
import json, os, re, sqlite3, sys
from pathlib import Path

DB_PATH = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
RESULTS_DIR = os.path.expanduser("~/Documents/agon-arena/results")

# ── Static analysis tests (mirrors code-event.py) ──
STATIC_TESTS = [
    {"label": "Has regex class/function", "weight": 0.5, "check": "has_regex_class_or_function"},
    {"label": "Has CLI entry point", "weight": 0.5, "check": "has_cli_entry"},
    {"label": "Handles literal matching", "weight": 0.5, "check": "has_literal_match"},
    {"label": "Handles dot wildcard", "weight": 0.5, "check": "has_dot_wildcard"},
    {"label": "Handles star quantifier", "weight": 0.5, "check": "has_star_quantifier"},
    {"label": "Handles character classes", "weight": 0.5, "check": "has_char_class"},
    {"label": "Handles anchors", "weight": 0.5, "check": "has_anchors"},
    {"label": "Has exit code logic", "weight": 0.5, "check": "has_exit_codes"},
]

STATIC_CHECKS = {
    "has_regex_class_or_function": lambda c: bool(
        re.search(r'(?:class\s+\w+|def\s+\w+).*?(?:regex|match|pattern)', c, re.I)
    ),
    "has_cli_entry": lambda c: bool(
        re.search(r'(?:if\s+__name__\s*==\s*["\']__main__["\']|sys\.argv|argparse)', c)
    ),
    "has_literal_match": lambda c: bool(
        re.search(r'(?:literal|char\s*==|text\[i\]\s*==|pattern\[j\]\s*==)', c, re.I)
    ),
    "has_dot_wildcard": lambda c: bool(
        re.search(r'(?:\.\s*==\s*["\'].["\']|==\s*["\']\.["\']|dot|wildcard|any_char|match_any)', c, re.I)
    ),
    "has_star_quantifier": lambda c: bool(
        re.search(r'(?:star|\*|zero_or_more|kleene|repeat_zero)', c, re.I)
    ),
    "has_char_class": lambda c: bool(
        re.search(r'(?:char_class|\[\^?|character_class|class.*?\[|in_brackets|bracket)', c, re.I)
    ),
    "has_anchors": lambda c: bool(
        re.search(r'(?:anchor|\^|\$|start_of|end_of|begin|caret)', c, re.I)
    ),
    "has_exit_codes": lambda c: bool(
        re.search(r'(?:exit\s*\(\s*[012]\)|sys\.exit|return\s+[012]\b)', c)
    ),
}


def clean_code(content):
    """Extract and clean code from model response (mirrors code-event.py)."""
    code_clean = content.strip()
    
    # Strip thinking tags
    if 'thinking' in code_clean:
        code_clean = re.sub(r'(?s)\s*thinking\s*.*?response\s*\n?', '', code_clean, count=1)
    if re.search(r'<think', code_clean):
        code_clean = re.sub(r'(?s)(?:^|\n)\s*<think.*? response\n?', '', code_clean)
        if re.search(r'(?:^|\n)\s*<think', code_clean):
            code_clean = re.sub(r'(?s)(?:^|\n)\s*<think.*$', '', code_clean)
    code_clean = re.sub(r'^_T\s*>\s*\n?', '', code_clean, flags=re.MULTILINE)
    code_clean = re.sub(r'^_N\s*>\s*\n?', '', code_clean, flags=re.MULTILINE)
    code_clean = re.sub(r'^_T\s+user:\s*\n?', '', code_clean, flags=re.MULTILINE)
    code_clean = re.sub(r'^_\s*\n?', '', code_clean, flags=re.MULTILINE)
    code_clean = re.sub(r'^\s+_\s*\n?', '', code_clean, flags=re.MULTILINE)
    code_clean = code_clean.strip()
    
    # Extract code blocks
    if '```' in code_clean:
        parts = re.split(r'```(?:python)?\s*\n?', code_clean)
        code_blocks = []
        for i in range(1, len(parts), 2):
            if i < len(parts):
                block = parts[i]
                block = re.sub(r'\n?```\s*$', '', block)
                code_blocks.append(block.strip())
        if code_blocks:
            code_clean = '\n\n'.join(code_blocks)
        else:
            fence_pos = code_clean.find('```')
            if fence_pos > 0:
                code_clean = code_clean[fence_pos:]
            code_clean = re.sub(r'```(?:python)?\s*\n?', '', code_clean)
            code_clean = re.sub(r'\n?```\s*', '', code_clean)
    else:
        code_clean = re.sub(r'^Final answer:\s*\n?', '', code_clean, flags=re.IGNORECASE)
    
    return code_clean.strip()


def run_static_tests(code):
    """Run all 8 static tests, return (score, max_score, details)."""
    max_score = sum(t["weight"] for t in STATIC_TESTS)
    score = 0.0
    details = []
    
    for test in STATIC_TESTS:
        check_fn = STATIC_CHECKS.get(test["check"])
        if not check_fn:
            continue
        result = check_fn(code)
        if result == True:
            score += test["weight"]
            details.append((test["label"], True, "PASS"))
        else:
            details.append((test["label"], False, "FAIL"))
    
    return score, max_score, details


def find_all_task7_responses():
    """Find all code task 7 response files."""
    responses = []
    for root, dirs, files in os.walk(RESULTS_DIR):
        if 'task7' in root and 'response.txt' in files:
            path = Path(root) / 'response.txt'
            # Extract model key and run number from path
            rel = path.relative_to(RESULTS_DIR)
            parts = rel.parts
            # e.g. ornith_9b/code/run1/task7/response.txt
            if len(parts) >= 4 and parts[1] == 'code' and parts[2].startswith('run'):
                model_key = parts[0]
                run_num = int(parts[2].replace('run', ''))
                responses.append((model_key, run_num, path))
    return responses


def get_model_id(db, model_key):
    cur = db.cursor()
    cur.execute("SELECT id FROM models WHERE key=?", (model_key,))
    row = cur.fetchone()
    return row[0] if row else None


def get_run_id(db, model_id, run_num):
    cur = db.cursor()
    cur.execute("SELECT id FROM code_runs WHERE model_id=? AND run_number=? AND status='completed'", (model_id, run_num))
    row = cur.fetchone()
    return row[0] if row else None


def main():
    db = sqlite3.connect(DB_PATH)
    responses = find_all_task7_responses()
    print(f"Found {len(responses)} code task 7 response files\n")
    
    results = []
    for model_key, run_num, path in responses:
        model_id = get_model_id(db, model_key)
        if not model_id:
            print(f"  SKIP {model_key} run{run_num}: model not in DB")
            continue
        
        run_id = get_run_id(db, model_id, run_num)
        if not run_id:
            print(f"  SKIP {model_key} run{run_num}: no completed run in DB")
            continue
        
        with open(path) as f:
            content = f.read()
        
        code = clean_code(content)
        score, max_score, details = run_static_tests(code)
        
        # Update DB
        cur = db.cursor()
        cur.execute("""
            UPDATE code_tasks 
            SET score=?, max_score=?, details=?, status='completed'
            WHERE run_id=? AND task_id=7
        """, (score, max_score, json.dumps(details), run_id))
        
        if cur.rowcount == 0:
            # Insert if not exists
            cur.execute("""
                INSERT OR REPLACE INTO code_tasks
                (run_id, task_id, task_name, difficulty, score, max_score, details, status)
                VALUES (?, 7, 'Regex Engine', 'Hard', ?, ?, ?, 'completed')
            """, (run_id, score, max_score, json.dumps(details)))
        
        db.commit()
        
        # Update run total
        cur.execute("""
            SELECT COALESCE(SUM(score), 0), COALESCE(SUM(max_score), 0)
            FROM code_tasks WHERE run_id=? AND status='completed'
        """, (run_id,))
        total_score, total_max = cur.fetchone()
        cur.execute("""
            UPDATE code_runs SET total_score=?, max_score=? WHERE id=?
        """, (total_score, total_max, run_id))
        db.commit()
        
        pct = score / max_score * 100 if max_score > 0 else 0
        results.append((model_key, run_num, score, pct))
        print(f"  {model_key:20s} run{run_num}: {score:.1f}/{max_score} ({pct:.0f}%)")
    
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Updated {len(results)} task 7 scores")
    
    # Summary by model
    from collections import defaultdict
    by_model = defaultdict(list)
    for model_key, run_num, score, pct in results:
        by_model[model_key].append(score)
    
    print(f"\n{'Model':20s} {'Avg':>6s} {'Runs':>4s}")
    print('-' * 32)
    for model_key in sorted(by_model.keys()):
        scores = by_model[model_key]
        avg = sum(scores) / len(scores)
        print(f"{model_key:20s} {avg:>5.1f}/4.0 {len(scores):>4d}")


if __name__ == "__main__":
    main()
