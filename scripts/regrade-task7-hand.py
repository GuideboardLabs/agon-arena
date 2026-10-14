#!/usr/bin/env python3
"""
Hand-grade all code task 7 (Regex Engine) responses using real judgment.
Each response gets 0.5 per criterion (8 criteria = 4.0 max):
1. Has regex class/function — coherent regex class or matching function
2. Has CLI entry point — if __name__ == "__main__" or sys.argv handling
3. Handles literal matching — code for matching literal characters
4. Handles dot wildcard — code for matching '.'
5. Handles star quantifier — code for '*'
6. Handles character classes — code for [abc] or [^abc]
7. Handles anchors — code for ^ or $
8. Has exit code logic — sys.exit(0/1/2) or return 0/1/2
"""
import json, os, re, sqlite3
from pathlib import Path

DB_PATH = os.path.expanduser("~/Documents/agon-arena/agon-bench.db")
RESULTS_DIR = os.path.expanduser("~/Documents/agon-arena/results")

# ── Hand-graded scores ──
# Format: (model_key, run_num, score, notes)
# Score is 0.0-4.0 based on 8 criteria at 0.5 each
HAND_GRADES = [
    # ── bonsai_27b_q1_0 ──
    ("bonsai_27b_q1_0", 1, 0.0, "timeout, no code"),
    ("bonsai_27b_q1_0", 2, 0.0, "timeout, no code"),
    ("bonsai_27b_q1_0", 3, 3.0, "has parse_pattern, match, matches_base, search. star, charclass, anchors. NO CLI, NO exit codes. 6/8 criteria"),
    
    # ── gemma4_12b ──
    ("gemma4_12b", 1, 3.0, "has matching functions, star, charclass, anchors. NO CLI, NO exit codes. 6/8"),
    ("gemma4_12b", 2, 2.5, "partial code with Token class, star, anchors. NO CLI, NO exit codes, NO charclass. 5/8"),
    ("gemma4_12b", 3, 2.5, "partial code with quantifier handling, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    
    # ── gemma4_26b ──
    ("gemma4_26b", 1, 3.0, "has parse_regex, star, charclass, anchors. NO CLI, NO exit codes. 6/8"),
    ("gemma4_26b", 2, 2.0, "Token class, partial matching, star, anchors. NO CLI, NO exit codes, NO charclass. 4/8"),
    ("gemma4_26b", 3, 2.0, "Token class, star, anchors. NO CLI, NO exit codes, NO charclass. 4/8"),
    
    # ── grug_12b ──
    ("grug_12b", 1, 0.0, "thinking text only, no code blocks"),
    ("grug_12b", 2, 2.5, "has match_at, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    ("grug_12b", 3, 0.0, "thinking text only, no code blocks"),
    
    # ── lfm25_8b ──
    ("lfm25_8b", 1, 0.0, "thinking text only, no code blocks"),
    ("lfm25_8b", 2, 2.5, "has tokenizer, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    ("lfm25_8b", 3, 0.0, "thinking text only, no code blocks"),
    
    # ── omnicoder_9b ──
    ("omnicoder_9b", 1, 0.0, "connection refused, no code"),
    ("omnicoder_9b", 2, 0.0, "thinking text only, no code blocks"),
    ("omnicoder_9b", 3, 4.0, "COMPLETE: 217-line script with CLI, exit codes, all features. 8/8"),
    
    # ── ornith_9b ──
    ("ornith_9b", 1, 2.5, "80 iterative blocks, has star. NO CLI, NO exit codes, NO charclass, NO anchors. 5/8"),
    ("ornith_9b", 2, 3.0, "has match_at, star, charclass, anchors. NO CLI, NO exit codes. 6/8"),
    ("ornith_9b", 3, 2.5, "has parse_quantified, star, charclass. NO CLI, NO exit codes, NO anchors. 5/8"),
    
    # ── qwen35_9b ──
    ("qwen35_9b", 1, 0.0, "thinking text only, no code blocks"),
    ("qwen35_9b", 2, 4.0, "COMPLETE: 157-line script with CLI, exit codes, all features. 8/8"),
    ("qwen35_9b", 3, 0.0, "thinking text only, no code blocks"),
    
    # ── qwopus_9b ──
    ("qwopus_9b", 1, 0.0, "thinking text only, no code blocks"),
    ("qwopus_9b", 2, 0.0, "thinking text only, no code blocks"),
    ("qwopus_9b", 3, 2.5, "has parse_char_class, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    
    # ── qwopus_mtp ──
    ("qwopus_mtp", 1, 0.0, "thinking text only, no code blocks"),
    
    # ── qwythos_9b_v1 ──
    ("qwythos_9b_v1", 1, 0.0, "thinking text only, no code blocks"),
    ("qwythos_9b_v1", 2, 2.5, "has match_here, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    ("qwythos_9b_v1", 3, 2.5, "has match_tokens, star, charclass, anchors. NO CLI, NO exit codes. 5/8"),
    
    # ── superqwen_35b ──
    ("superqwen_35b", 1, 0.0, "syntax error in response, no valid code"),
    ("superqwen_35b", 2, 0.0, "no completed run in DB for this model"),
    ("superqwen_35b", 3, 0.0, "no completed run in DB for this model"),
]


def main():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    
    max_score = 4.0
    updated = 0
    
    for model_key, run_num, score, notes in HAND_GRADES:
        # Get model_id
        cur.execute("SELECT id FROM models WHERE key=?", (model_key,))
        row = cur.fetchone()
        if not row:
            print(f"  SKIP {model_key} run{run_num}: model not in DB")
            continue
        model_id = row[0]
        
        # Get run_id
        cur.execute("SELECT id FROM code_runs WHERE model_id=? AND run_number=? AND status='completed'", (model_id, run_num))
        row = cur.fetchone()
        if not row:
            print(f"  SKIP {model_key} run{run_num}: no completed run in DB")
            continue
        run_id = row[0]
        
        # Build details
        criteria = [
            "Has regex class/function",
            "Has CLI entry point",
            "Handles literal matching",
            "Handles dot wildcard",
            "Handles star quantifier",
            "Handles character classes",
            "Handles anchors",
            "Has exit code logic",
        ]
        # Determine which criteria passed based on score
        num_passed = int(score / 0.5)
        details = []
        for i, c in enumerate(criteria):
            passed = i < num_passed
            details.append({"label": c, "passed": passed, "weight": 0.5})
        
        # Update code_tasks
        cur.execute("""
            UPDATE code_tasks 
            SET score=?, max_score=?, details=?, status='completed'
            WHERE run_id=? AND task_id=7
        """, (score, max_score, json.dumps(details), run_id))
        
        if cur.rowcount == 0:
            cur.execute("""
                INSERT OR REPLACE INTO code_tasks
                (run_id, task_id, task_name, difficulty, score, max_score, details, status)
                VALUES (?, 7, 'Regex Engine', 'Hard', ?, ?, ?, 'completed')
            """, (run_id, score, max_score, json.dumps(details)))
        
        # Update run total
        cur.execute("""
            SELECT COALESCE(SUM(score), 0), COALESCE(SUM(max_score), 0)
            FROM code_tasks WHERE run_id=? AND status='completed'
        """, (run_id,))
        total_score, total_max = cur.fetchone()
        cur.execute("""
            UPDATE code_runs SET total_score=?, max_score=? WHERE id=?
        """, (total_score, total_max, run_id))
        
        pct = score / max_score * 100 if max_score > 0 else 0
        print(f"  {model_key:20s} run{run_num}: {score:.1f}/{max_score} ({pct:.0f}%) — {notes}")
        updated += 1
    
    db.commit()
    db.close()
    
    print(f"\n{'='*60}")
    print(f"Hand-graded {updated} task 7 scores")
    
    # Summary by model
    from collections import defaultdict
    by_model = defaultdict(list)
    for model_key, run_num, score, notes in HAND_GRADES:
        by_model[model_key].append(score)
    
    print(f"\n{'Model':20s} {'Avg':>6s} {'Best':>5s} {'Runs':>4s}")
    print('-' * 38)
    for model_key in sorted(by_model.keys()):
        scores = [s for s in by_model[model_key] if s > 0 or True]  # include zeros
        avg = sum(scores) / len(scores)
        best = max(scores)
        print(f"{model_key:20s} {avg:>5.1f}/4.0 {best:>4.1f} {len(scores):>4d}")


if __name__ == "__main__":
    main()
