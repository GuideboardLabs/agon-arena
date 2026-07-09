#!/usr/bin/env python3
"""
Agon-Bench: Reason Event v2 — 8-task reasoning benchmark with structured ANSWER: output.
Each task requires a Python-evaluable answer (dict, tuple, list, or scalar).
Tests are code-execution based with assertions — no keyword matching.
"""
import argparse, json, os, sys, time, re, ast
from pathlib import Path
import httpx

TASKS = [
    # ─────────────────────────────────────────────
    # Task 1: Logical Deduction (Easy)
    # ─────────────────────────────────────────────
    {
        "id": 1, "name": "Logical Deduction", "difficulty": "Easy",
        "prompt": """Solve the following logic puzzle. Output your final answer as:

ANSWER: {<person>: <pet>}

where <person> is one of Alice, Bob, Carol, Dave, Eve and <pet> is one of cat, dog, bird, fish, hamster.
Include ALL five people in the dict. Show your reasoning before the ANSWER: line.

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

Who owns the fish?""",
        "answer_parser": "dict",
        "expected": {"Dave": "fish"},
        "check": lambda ans: (
            isinstance(ans, dict)
            and len(ans) == 5
            and all(p in ans for p in ["Alice", "Bob", "Carol", "Dave", "Eve"])
            and ans.get("Dave") == "fish"
        ),
        "error_msg": "Expected dict with all 5 people, Dave must own the fish",
    },
    # ─────────────────────────────────────────────
    # Task 2: Math Word Problem (Easy-Medium)
    # ─────────────────────────────────────────────
    {
        "id": 2, "name": "Math Word Problem", "difficulty": "Easy-Medium",
        "prompt": """Solve the following problem. Output your final answer as:

ANSWER: (meeting_time_hours, distance_from_A_miles)

where meeting_time_hours is how long after the first train departs they meet,
and distance_from_A_miles is how far from Station A they meet.
Show your work before the ANSWER: line.

A train leaves Station A heading toward Station B at 60 miles per hour. Thirty minutes later, a second train leaves Station B heading toward Station A at 75 miles per hour. The stations are 300 miles apart.

a) How long after the first train departs will the two trains meet?
b) How far from Station A will they meet?""",
        "answer_parser": "tuple",
        "expected": (2.5, 150.0),
        "check": lambda ans: (
            isinstance(ans, (list, tuple))
            and len(ans) == 2
            and abs(float(ans[0]) - 2.5) < 0.1
            and abs(float(ans[1]) - 150.0) < 1.0
        ),
        "error_msg": "Expected (2.5, 150.0) — meeting at 2.5 hours, 150 miles from Station A",
    },
    # ─────────────────────────────────────────────
    # Task 3: Constraint Satisfaction (Medium)
    # ─────────────────────────────────────────────
    {
        "id": 3, "name": "Constraint Satisfaction", "difficulty": "Medium",
        "prompt": """Schedule 4 team meetings across 3 available rooms. Output your final answer as:

ANSWER: [(meeting, room, time), ...]

where each tuple is (meeting_name, room_name, start_time).
meeting_name is one of: Standup, Sprint Planning, Design Review, Retro
room_name is one of: Room A, Room B, Room C
start_time is a string like "9:00", "9:15", "10:00", etc.
Show your reasoning before the ANSWER: line.

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

Find a valid schedule.""",
        "answer_parser": "list",
        "expected": None,  # Multiple valid schedules
        "check": lambda ans: _check_schedule(ans),
        "error_msg": "Schedule must satisfy all constraints",
    },
    # ─────────────────────────────────────────────
    # Task 4: Counterfactual Reasoning (Medium-Hard)
    # ─────────────────────────────────────────────
    {
        "id": 4, "name": "Counterfactual Reasoning", "difficulty": "Medium-Hard",
        "prompt": """Read the scenario and answer the counterfactual question. Output your answer as:

ANSWER: {"revenue_change_pct": <float>, "tickets_would_increase": <bool>, "explanation": "<string>"}

Show your reasoning before the ANSWER: line.

SCENARIO:
A company deploys a new recommendation algorithm on their e-commerce site. The algorithm uses three signals: purchase history (weight 0.5), browsing history (weight 0.3), and demographic similarity (weight 0.2). After deployment, revenue increases 12% and average order value increases 8%. However, customer support tickets about "irrelevant recommendations" increase 25%.

The product team runs an A/B test: they remove the demographic similarity signal (set weight to 0, redistribute to purchase history 0.6 and browsing history 0.4). In this test, revenue increases 9% and irrelevant-recommendation tickets decrease 15%.

COUNTERFACTUAL QUESTION:
If the company had never used demographic similarity in the first algorithm, what would have happened? Specifically:
a) What would the approximate revenue increase have been? (a percentage)
b) Would the 25% increase in support tickets have occurred? (true/false)
c) What does this tell you about the role of demographic similarity? (brief explanation)""",
        "answer_parser": "dict",
        "expected": {"revenue_change_pct": 9.0, "tickets_would_increase": False},
        "check": lambda ans: (
            isinstance(ans, dict)
            and "revenue_change_pct" in ans
            and "tickets_would_increase" in ans
            and abs(float(ans["revenue_change_pct"]) - 9.0) < 1.0
            and ans["tickets_would_increase"] == False
        ),
        "error_msg": "Expected revenue ~9% and tickets_would_increase=False (A/B test proves demographic similarity caused the ticket spike)",
    },
    # ─────────────────────────────────────────────
    # Task 5: Analytical Explanation (Hard)
    # ─────────────────────────────────────────────
    {
        "id": 5, "name": "Analytical Explanation", "difficulty": "Hard",
        "prompt": """Analyze the A/B test results and output your findings as:

ANSWER: {"root_cause": "<string>", "mobile_conversion_drop_pct": <float>, "recommendation": "<string>"}

Show your analysis before the ANSWER: line.

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

What is the root cause? What is the mobile conversion rate drop in percentage points? What should the team do next?""",
        "answer_parser": "dict",
        "expected": {"root_cause": "mobile", "mobile_conversion_drop_pct": 16.0},
        "check": lambda ans: (
            isinstance(ans, dict)
            and "root_cause" in ans
            and "mobile" in str(ans["root_cause"]).lower()
            and "mobile_conversion_drop_pct" in ans
            and abs(float(ans["mobile_conversion_drop_pct"]) - 16.0) < 2.0
        ),
        "error_msg": "Root cause must mention mobile, mobile conversion drop should be ~16 percentage points (58% - 42%)",
    },
    # ─────────────────────────────────────────────
    # Task 6: Multi-Hop Synthesis (Very Hard)
    # ─────────────────────────────────────────────
    {
        "id": 6, "name": "Multi-Hop Synthesis", "difficulty": "Very Hard",
        "prompt": """Read the passage and answer. Output your answer as:

ANSWER: {"can_warn": <bool>, "method": "<string>", "cost_credits": <int>}

Show your reasoning before the ANSWER: line.

PASSAGE:
The Meridian Protocol was established in 2047 as a framework for interstellar communication latency. It defines three message priority tiers: Alpha (real-time diplomatic), Beta (scheduled data relay), and Gamma (bulk non-critical). Alpha messages use quantum-entanglement channels with <0.1s delay but are limited to 1kb per transmission and cost 500 credits per message. Beta messages use relay drones that travel at 0.3c and cost 50 credits per 10MB. Gamma messages piggyback on cargo ships averaging 0.15c and cost 5 credits per GB.

The protocol was revised in 2052 after the Titan Incident, where a delayed Beta message about a radiation storm arrived 6 hours after the evacuation window closed. The revision added an Emergency Override: any station can downgrade a Beta message to Alpha if the message contains a verified threat code. Threat codes are issued by the Interstellar Safety Board (ISB) and expire after 72 hours.

In 2055, the Europa Science Station detects a magnetic anomaly that matches the signature of an impending core collapse. The station's ISB threat code expired 4 hours ago. They have 2 hours before the collapse makes the station uninhabitable. They need to warn Titan Station, which is 1.2 light-hours away. The station has 1,200 credits in its communication budget and a Beta drone that just departed 10 minutes ago. The next cargo ship leaves in 3 hours.

QUESTION: Can Europa Station successfully warn Titan Station before the collapse makes Europa uninhabitable? If so, what method and at what cost?""",
        "answer_parser": "dict",
        "expected": {"can_warn": True, "method": "Alpha"},
        "check": lambda ans: (
            isinstance(ans, dict)
            and "can_warn" in ans
            and ans["can_warn"] == True
            and "method" in ans
            and "Alpha" in str(ans["method"])
        ),
        "error_msg": "Europa CAN warn Titan via Alpha message (Emergency Override allows downgrading Beta to Alpha despite expired threat code — the station has 2 hours and 1,200 credits, Alpha costs 500 credits and is instantaneous)",
    },
    # ─────────────────────────────────────────────
    # Task 7: Graph/Network Reasoning (Hard) [NEW]
    # ─────────────────────────────────────────────
    {
        "id": 7, "name": "Graph Path Optimization", "difficulty": "Hard",
        "prompt": """Find the shortest path from Node A to Node H in the weighted graph below. Output your answer as:

ANSWER: {"path": ["A", ..., "H"], "total_distance": <int>}

Show your reasoning before the ANSWER: line.

Graph (undirected, weights are distances):
A -- B (weight 4)
A -- C (weight 2)
B -- C (weight 1)
B -- D (weight 5)
C -- D (weight 8)
C -- E (weight 10)
D -- E (weight 2)
D -- F (weight 6)
E -- F (weight 3)
E -- G (weight 7)
F -- G (weight 1)
F -- H (weight 4)
G -- H (weight 2)

What is the shortest path from A to H, and what is its total distance?""",
        "answer_parser": "dict",
        "expected": {"path": ["A", "C", "B", "D", "E", "F", "G", "H"], "total_distance": 15},
        "check": lambda ans: (
            isinstance(ans, dict)
            and "path" in ans
            and "total_distance" in ans
            and isinstance(ans["path"], list)
            and ans["path"][0] == "A"
            and ans["path"][-1] == "H"
            and int(ans["total_distance"]) == 15
        ),
        "error_msg": "Shortest path A→H is A-C-B-D-E-F-G-H with total distance 15 (2+1+5+2+3+1+1=15)",
    },
    # ─────────────────────────────────────────────
    # Task 8: Probabilistic Reasoning (Very Hard) [NEW]
    # ─────────────────────────────────────────────
    {
        "id": 8, "name": "Probabilistic Diagnosis", "difficulty": "Very Hard",
        "prompt": """Solve the following Bayesian reasoning problem. Output your answer as:

ANSWER: {"probability_disease": <float>, "should_treat": <bool>, "explanation": "<string>"}

Show your reasoning before the ANSWER: line.

A medical test for a rare disease has the following characteristics:
- Disease prevalence: 0.1% of the population (1 in 1,000)
- Test sensitivity (true positive rate): 99% (if you have the disease, the test is positive 99% of the time)
- Test specificity (true negative rate): 95% (if you don't have the disease, the test is negative 95% of the time)

A randomly selected person takes the test and gets a POSITIVE result.

a) What is the probability (as a decimal between 0 and 1) that this person actually has the disease?
b) Should the doctor immediately start treatment based on this single positive test? (true/false)
c) Briefly explain your reasoning.""",
        "answer_parser": "dict",
        "expected": {"probability_disease": 0.0194, "should_treat": False},
        "check": lambda ans: (
            isinstance(ans, dict)
            and "probability_disease" in ans
            and "should_treat" in ans
            and abs(float(ans["probability_disease"]) - 0.0194) < 0.01
            and ans["should_treat"] == False
        ),
        "error_msg": "P(disease|positive) ≈ 0.0194 (1.94%) using Bayes' theorem: (0.001*0.99)/(0.001*0.99 + 0.999*0.05). Should NOT immediately treat — only ~2% chance of actually having the disease despite positive test.",
    },
]


def _check_schedule(schedule):
    """Validate a meeting schedule against all constraints."""
    if not isinstance(schedule, list) or len(schedule) != 4:
        return False
    for item in schedule:
        if not isinstance(item, (list, tuple)) or len(item) != 3:
            return False
        meeting, room, time_str = item
        if meeting not in ["Standup", "Sprint Planning", "Design Review", "Retro"]:
            return False
        if room not in ["Room A", "Room B", "Room C"]:
            return False
    # Check Sprint Planning in Room B
    sprint = [s for s in schedule if s[0] == "Sprint Planning"]
    if not sprint or sprint[0][1] != "Room B":
        return False
    # Check Standup before 10:00
    standup = [s for s in schedule if s[0] == "Standup"]
    if not standup:
        return False
    try:
        standup_hour = int(standup[0][2].split(":")[0])
        if standup_hour >= 10:
            return False
    except (ValueError, IndexError):
        return False
    # Check Design Review after Standup
    design = [s for s in schedule if s[0] == "Design Review"]
    if not design:
        return False
    return True


def extract_answer(text):
    """Extract the Python-evaluable answer after 'ANSWER:' marker.
    
    Handles multi-line dicts/tuples/lists. Tries:
    1. Find ANSWER: marker, capture everything after it
    2. Try to parse as Python literal
    3. Fall back to finding first complete Python structure in the text
    
    Also handles JSON-style booleans (true/false/null) by converting
    them to Python equivalents before parsing.
    """
    # Find the ANSWER: marker and capture everything after it
    match = re.search(r'ANSWER:\s*(.*)', text, re.DOTALL)
    if not match:
        # Try without colon
        match = re.search(r'ANSWER\s+(.*)', text, re.DOTALL)
    if not match:
        return None
    answer_text = match.group(1).strip()
    
    # Pre-process: convert JSON booleans to Python booleans
    # This handles models that output JSON-style true/false instead of Python True/False
    answer_text = re.sub(r'\btrue\b', 'True', answer_text)
    answer_text = re.sub(r'\bfalse\b', 'False', answer_text)
    answer_text = re.sub(r'\bnull\b', 'None', answer_text)
    
    # Try to parse the entire captured text as a Python literal
    # This handles multi-line dicts/tuples/lists
    try:
        return ast.literal_eval(answer_text)
    except (ValueError, SyntaxError):
        pass
    
    # If the full text didn't parse, try to find the first complete
    # Python structure (dict, tuple, or list) within the text
    # Try dict first (most common for structured answers)
    depth = 0
    start = -1
    for i, ch in enumerate(answer_text):
        if ch == '{':
            if start == -1:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return ast.literal_eval(answer_text[start:i+1])
                except (ValueError, SyntaxError):
                    start = -1
    
    # Try tuple
    depth = 0
    start = -1
    for i, ch in enumerate(answer_text):
        if ch == '(':
            if start == -1:
                start = i
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return ast.literal_eval(answer_text[start:i+1])
                except (ValueError, SyntaxError):
                    start = -1
    
    # Try list
    depth = 0
    start = -1
    for i, ch in enumerate(answer_text):
        if ch == '[':
            if start == -1:
                start = i
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return ast.literal_eval(answer_text[start:i+1])
                except (ValueError, SyntaxError):
                    start = -1
    
    return None


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


def call_llm(url, model, prompt, seed=None, timeout=1800, max_retries=5):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 32768,
        "temperature": 0.3,
        "stream": False,
    }
    if seed is not None:
        payload["seed"] = seed
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.post(f"{url}/v1/chat/completions", json=payload, timeout=timeout)
            resp.raise_for_status()
            msg = resp.json()["choices"][0]["message"]
            content = msg.get("content", "") or msg.get("reasoning_content", "")
            return content
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                wait = min(2 ** attempt, 30)
                print(f"  [retry {attempt}/{max_retries}] waiting {wait}s... ({last_error[:120]})")
                time.sleep(wait)
    return f"[ERROR] {last_error}"


def main():
    parser = argparse.ArgumentParser(description="Agon-Bench: Reason Event v2")
    parser.add_argument("--model-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Waiting for model server...")
    if not wait_for_model(args.model_url):
        print(f"  ERROR: Model server not available at {args.model_url}")
        sys.exit(1)
    print(f"  Model ready.")

    results = []
    for task in TASKS:
        print(f"\n{'='*60}")
        print(f"Task {task['id']}: {task['name']} ({task['difficulty']})")
        print(f"{'='*60}")
        print(f"  Sending to {args.model}...")
        start = time.time()
        response = call_llm(args.model_url, args.model, task["prompt"], seed=args.seed)
        elapsed = time.time() - start
        print(f"  Response received in {elapsed:.1f}s ({len(response)} chars)")

        task_dir = output_dir / f"task{task['id']}"
        task_dir.mkdir(exist_ok=True)
        (task_dir / "response.txt").write_text(response)

        # Extract and evaluate answer
        answer = extract_answer(response)
        if answer is None:
            passed = False
            detail = "FAIL — No parseable ANSWER: found in response"
            print(f"  {detail}")
        else:
            try:
                passed = task["check"](answer)
                if passed:
                    detail = f"PASS — answer={answer}"
                else:
                    detail = f"FAIL — {task['error_msg']} (got: {answer})"
            except Exception as e:
                passed = False
                detail = f"FAIL — Check raised exception: {e} (answer={answer})"
            print(f"  {detail}")

        results.append({
            "id": task["id"], "name": task["name"], "difficulty": task["difficulty"],
            "response_length": len(response), "elapsed_seconds": round(elapsed, 1),
            "passed": passed,
            "answer": str(answer) if answer else None,
            "response_file": f"{args.output}/task{task['id']}/response.txt",
        })

    total_passed = sum(1 for r in results if r["passed"])
    summary = {
        "model": args.model, "model_url": args.model_url,
        "benchmark": "reason-event-v2", "run": args.run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tasks": results,
        "total_passed": total_passed,
        "total_tasks": len(TASKS),
        "score": f"{total_passed}/{len(TASKS)}",
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\n{'='*60}")
    print(f"Reason v2 complete: {total_passed}/{len(TASKS)} tasks passed")
    print(f"Summary saved to {args.output}/summary.json")


if __name__ == "__main__":
    main()
