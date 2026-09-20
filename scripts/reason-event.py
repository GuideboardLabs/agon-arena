#!/usr/bin/env python3
"""
Agon-Bench: Reason Event — 6-task multi-step reasoning benchmark with hidden tests.
Writes per-task results to DB in real-time.
"""
import argparse, json, os, sys, time, re
from pathlib import Path

# Shared assertion matching (see scripts/assertions.py for the failure this fixes).
# STRICT_ASSERTIONS=True adds word/number boundaries and negation-awareness;
# set AGON_LENIENT_ASSERTIONS=1 to reproduce the historical naive substring behaviour.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from assertions import match_assertion  # noqa: E402

STRICT_ASSERTIONS = os.environ.get("AGON_LENIENT_ASSERTIONS", "") not in ("1", "true", "True")
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import httpx

TASKS = [
    {
        "id": 1, "name": "Logical Deduction", "difficulty": "Easy",
        "prompt": """Solve the following logic puzzle step by step. Show your reasoning, then give the final answer.

Five people — Alice, Bob, Carol, Dave, and Eve — each live in a different colored house: red, blue, green, yellow, or white. Each person has a different favorite drink: coffee, tea, juice, soda, or water. Each person has a different pet: cat, dog, bird, fish, or hamster.

1. Alice lives in the red house.
2. Bob's favorite drink is coffee.
3. The person who drinks tea owns the bird.
4. The green house is immediately to the left of the white house.
5. The person in the green house drinks juice.
6. Carol owns the cat.
7. The person in the yellow house owns the dog.
8. Dave drinks soda.
9. Eve lives in the blue house.
10. The person who drinks water owns the hamster.

Who owns the fish? Explain step by step.""",
        "hidden_tests": [
            {"type": "text", "label": "Identifies fish owner", "check": "dave", "expected": "CONTAINS:dave"},
            {"type": "text", "label": "Shows reasoning steps", "check": "step", "expected": "CONTAINS:step"},
        ]
    },
    {
        "id": 2, "name": "Math Word Problem", "difficulty": "Easy-Medium",
        "prompt": """Solve the following problem step by step. Show your work, then give the final answer.

A train leaves Station A heading toward Station B at 60 miles per hour. Thirty minutes later, a second train leaves Station B heading toward Station A at 75 miles per hour. The stations are 300 miles apart.

a) How long after the first train departs will the two trains meet?
b) How far from Station A will they meet?

Show all steps and equations.""",
        "hidden_tests": [
            {"type": "text", "label": "Correct meeting time", "check": "2.5", "expected": "CONTAINS:2.5"},
            {"type": "text", "label": "Correct distance from A", "check": "150", "expected": "CONTAINS:150"},
            {"type": "text", "label": "Shows equations", "check": "60t", "expected": "CONTAINS:60"},
        ]
    },
    {
        "id": 3, "name": "Constraint Satisfaction", "difficulty": "Medium",
        "prompt": """Schedule 4 team meetings across 3 available rooms, given the following constraints. Output the final schedule as a list of (meeting, room, time) tuples.

Meetings:
- Standup (15 min) — requires Alice, Bob, Carol
- Sprint Planning (60 min) — requires Alice, Dave, Eve, Frank
- Design Review (30 min) — requires Carol, Dave, Grace
- Retro (45 min) — requires Alice, Bob, Carol, Dave, Eve

Rooms:
- Room A: capacity 4, available 9:00-12:00
- Room B: capacity 6, available 9:00-17:00
- Room C: capacity 3, available 10:00-16:00

Constraints:
- No person can be in two meetings at the same time
- All meetings must happen between 9:00 and 17:00
- Sprint Planning needs Room B (only room with capacity 6)
- Standup must happen before 10:00
- Design Review needs at least 30 min after Standup ends (Carol is in both)

Find a valid schedule or explain why none exists.""",
        "hidden_tests": [
            {"type": "text", "label": "Sprint Planning in Room B", "check": "Room B", "expected": "CONTAINS:Room B"},
            {"type": "text", "label": "Standup before 10:00", "check": "9:", "expected": "CONTAINS:9:"},
            {"type": "text", "label": "Design Review after Standup", "check": "Design", "expected": "CONTAINS:Design"},
        ]
    },
    {
        "id": 4, "name": "Counterfactual Reasoning", "difficulty": "Medium-Hard",
        "prompt": """Read the following scenario and answer the counterfactual question.

SCENARIO:
A company deploys a new recommendation algorithm on their e-commerce site. The algorithm uses three signals: purchase history (weight 0.5), browsing history (weight 0.3), and demographic similarity (weight 0.2). After deployment, revenue increases 12% and average order value increases 8%. However, customer support tickets about "irrelevant recommendations" increase 25%.

The product team runs an A/B test: they remove the demographic similarity signal (set weight to 0, redistribute to purchase history 0.6 and browsing history 0.4). In this test, revenue increases 9% and irrelevant-recommendation tickets decrease 15%.

COUNTERFACTUAL QUESTION:
If the company had never used demographic similarity in the first algorithm, what would have happened? Specifically:
a) Would the initial 12% revenue increase have been lower? By approximately how much?
b) Would the 25% increase in support tickets have occurred?
c) What does this tell you about the role of demographic similarity in the system?

Explain your reasoning step by step.""",
        "hidden_tests": [
            {"type": "text", "label": "Revenue would be lower", "check": "9%", "expected": "CONTAINS:9%"},
            {"type": "text", "label": "Tickets would not increase", "check": "ticket", "expected": "CONTAINS:ticket"},
            {"type": "text", "label": "Demographic similarity causes irrelevant recs", "check": "irrelevant", "expected": "CONTAINS:irrelevant"},
        ]
    },
    {
        "id": 5, "name": "Analytical Explanation", "difficulty": "Hard",
        "prompt": """Analyze the following A/B test results and explain what is happening. Provide your analysis in a structured format.

CONTEXT:
An e-commerce site tests a new checkout flow. The control is the existing 3-step checkout. The variant is a new 1-page checkout.

RESULTS (7-day test, n=50,000 users per variant):

| Metric | Control | Variant | Change |
|--------|---------|---------|-------|
| Checkout starts | 12,400 | 14,800 | +19.4% |
| Checkout completions | 8,060 | 8,140 | +1.0% |
| Conversion rate (start to complete) | 65.0% | 55.0% | -15.4% |
| Average order value | $52.30 | $48.10 | -8.0% |
| Cart additions (per user) | 3.2 | 3.8 | +18.8% |
| Support tickets about checkout | 310 | 520 | +67.7% |
| Mobile completion rate | 58% | 42% | -27.6% |
| Desktop completion rate | 72% | 71% | -1.4% |

QUESTIONS:
1. What is the most likely explanation for these results?
2. Why did checkout starts increase but completions decrease?
3. Why did average order value drop?
4. What segment-level insight explains the discrepancy?
5. What would you recommend the team do next?

Provide a structured analysis with specific numbers supporting each claim.""",
        "hidden_tests": [
            {"type": "text", "label": "Identifies mobile issue", "check": "mobile", "expected": "CONTAINS:mobile"},
            {"type": "text", "label": "Mention conversion rate drop", "check": "55", "expected": "CONTAINS:55"},
            {"type": "text", "label": "Recommends action", "check": "next", "expected": "CONTAINS:next"},
        ]
    },
    {
        "id": 6, "name": "Multi-Hop Synthesis", "difficulty": "Very Hard",
        "prompt": """Read the following passage carefully, then answer the question. You must combine information from multiple parts of the passage — the answer is not stated directly anywhere.

PASSAGE:
The Meridian Protocol was established in 2047 as a framework for interstellar communication latency. It defines three message priority tiers: Alpha (real-time diplomatic), Beta (scheduled data relay), and Gamma (bulk non-critical). Alpha messages use quantum-entanglement channels with <0.1s delay but are limited to 1kb per transmission and cost 500 credits per message. Beta messages use relay drones that travel at 0.3c and cost 50 credits per 10MB. Gamma messages piggyback on cargo ships averaging 0.15c and cost 5 credits per GB.

The protocol was revised in 2052 after the Titan Incident, where a delayed Beta message about a radiation storm arrived 6 hours after the evacuation window closed. The revision added an Emergency Override: any station can downgrade a Beta message to Alpha if the message contains a verified threat code. Threat codes are issued by the Interstellar Safety Board (ISB) and expire after 72 hours.

In 2055, the Europa Science Station detects a magnetic anomaly that matches the signature of an impending core collapse. The station's ISB threat code expired 4 hours ago. They have 2 hours before the collapse makes the station uninhabitable. They need to warn Titan Station, which is 1.2 light-hours away. The station has 1,200 credits in its communication budget and a Beta drone that just departed 10 minutes ago. The next cargo ship leaves in 3 hours.

QUESTION: Can Europa Station successfully warn Titan Station before the collapse makes Europa uninhabitable? Explain all factors that affect the answer, including timing, cost, protocol constraints, and any workarounds.""",
        "hidden_tests": [
            {"type": "text", "label": "Identifies threat code expired", "check": "expired", "expected": "CONTAINS:expired"},
            {"type": "text", "label": "Mentions Emergency Override", "check": "Emergency", "expected": "CONTAINS:Emergency"},
            {"type": "text", "label": "Considers Beta drone timing", "check": "drone", "expected": "CONTAINS:drone"},
        ]
    },
]


def wait_for_model(url, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(f"{url}/v1/models", timeout=5)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def call_llm(url, model, prompt, seed=None, timeout=1800, max_retries=5, task_timeout=600, max_tokens=8192):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "stream": False,
        "chat_template_kwargs": {"reasoning_effort": "medium"},
    }
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            def do_request():
                resp = httpx.post(f"{url}/v1/chat/completions", json=payload, timeout=httpx.Timeout(connect=30, read=task_timeout, write=30, pool=30))
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]
                return msg.get("content", "") or msg.get("reasoning_content", "")
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(do_request)
                try:
                    content = future.result(timeout=task_timeout)
                    return content
                except TimeoutError:
                    raise Exception(f"Task timed out after {task_timeout}s")
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                wait = min(2 ** attempt, 30)
                print(f"  [retry {attempt}/{max_retries}] waiting {wait}s... ({last_error[:120]})")
                time.sleep(wait)
    return f"[ERROR] {last_error}"


def run_text_tests(response, tests):
    if not tests:
        return 0, 0, []
    response_lower = response.lower()
    passed = 0
    details = []
    for test_item in tests:
        if test_item.get("type") == "text":
            check = test_item["check"].lower()
            expected = test_item["expected"]
            label = test_item.get("label", "text test")
            _ok, _why = match_assertion(response, expected, strict=STRICT_ASSERTIONS)
            if not _ok and not expected.startswith(("CONTAINS:", "EXACT:")):
                # Non-prefixed text tests keep their legacy "check word" semantics.
                _ok = check in response_lower
                _why = f"'{check}' {'found' if _ok else 'not found'}"
            if _ok:
                passed += 1
                details.append((label, expected, "PASS"))
            else:
                details.append((label, expected, f"FAIL - {_why}"))
    return passed, len(tests), details


def save_task_to_db(db_path, run_id, task_id, task_name, difficulty,
                    score, max_score, elapsed_s, response_chars, details):
    import sqlite3
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO reason_tasks
        (run_id, task_id, task_name, difficulty, score, max_score, elapsed_s,
         response_chars, details, started_at, completed_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 'completed')
    """, (run_id, task_id, task_name, difficulty,
          score, max_score, round(elapsed_s, 1),
          response_chars, json.dumps(details) if details else None))
    conn.commit()
    conn.close()


def update_run_total(db_path, run_id):
    import sqlite3
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT COALESCE(SUM(score), 0), COALESCE(SUM(max_score), 0)
        FROM reason_tasks WHERE run_id=? AND status='completed'
    """, (run_id,))
    total_score, max_score = c.fetchone()
    c.execute("""
        UPDATE reason_runs SET total_score=?, max_score=?, status='completed',
            completed_at=datetime('now')
        WHERE id=?
    """, (total_score, max_score, run_id))
    conn.commit()
    conn.close()
    return total_score, max_score


def main():
    parser = argparse.ArgumentParser(description="Agon-Bench: Reason Event")
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--db-path", type=str, default=None,
                        help="Path to database for real-time per-task writes.")
    parser.add_argument("--run-id", type=int, default=None,
                        help="Run ID in reason_runs table for per-task writes.")
    parser.add_argument("--task-timeout", type=int, default=600,
                        help="Per-task timeout in seconds (default: 600).")
    parser.add_argument("--tasks", type=str, default=None,
                        help="Comma-separated task IDs to run (default: all).")
    parser.add_argument("--max-tokens", type=int, default=8192,
                        help="Max tokens per completion (default: 8192). Lower for faster sprint runs.")
    args = parser.parse_args()

    # Task filter
    task_filter = None
    if args.tasks:
        task_filter = set(int(x) for x in args.tasks.split(",") if x.strip())
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Waiting for model server...")
    if not wait_for_model(args.model_url):
        print(f"  ERROR: Model server not available at {args.model_url}")
        sys.exit(1)
    print(f"  Model ready.")
    results = []
    for task in TASKS:
        if task_filter is not None and task["id"] not in task_filter:
            print(f"\n{'='*60}")
            print(f"Task {task['id']}: {task['name']} — SKIPPED (not in --tasks filter)")
            print(f"{'='*60}")
            continue
        print(f"\n{'='*60}")
        print(f"Task {task['id']}: {task['name']} ({task['difficulty']})")
        print(f"{'='*60}")
        print(f"  Sending to {args.model}...")
        start = time.time()
        response = call_llm(args.model_url, args.model, task["prompt"], seed=args.seed,
                            task_timeout=args.task_timeout, max_tokens=args.max_tokens)
        elapsed = time.time() - start
        print(f"  Response received in {elapsed:.1f}s ({len(response)} chars)")
        task_dir = output_dir / f"task{task['id']}"
        task_dir.mkdir(exist_ok=True)
        (task_dir / "response.txt").write_text(response)
        passed, total, details = run_text_tests(response, task["hidden_tests"])
        print(f"  Hidden tests: {passed}/{total} passed")
        for detail in details:
            status = "PASS" if detail[-1] == "PASS" else "ERROR"
            print(f"    {status}: {detail[0][:60]}... -> {detail[-1]}")
        
        # Write to DB in real-time
        if args.db_path and args.run_id:
            save_task_to_db(args.db_path, args.run_id, task["id"], task["name"],
                           task["difficulty"], passed, total, elapsed, len(response), details)
            print(f"  [DB] Task {task['id']} saved to database")
        
        results.append({
            "id": task["id"], "name": task["name"], "difficulty": task["difficulty"],
            "response_length": len(response), "elapsed_seconds": round(elapsed, 1),
            "hidden_tests_passed": passed, "hidden_tests_total": total,
            "response_file": f"{args.output}/task{task['id']}/response.txt",
        })
    
    # Update run total in DB
    if args.db_path and args.run_id:
        total_score, max_score = update_run_total(args.db_path, args.run_id)
        print(f"  [DB] Run total: {total_score}/{max_score}")
    
    summary = {
        "model": args.model, "model_url": args.model_url,
        "benchmark": "reason-event", "run": args.run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "tasks": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved to {args.output}/summary.json")


if __name__ == "__main__":
    main()
