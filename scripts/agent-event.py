#!/usr/bin/env python3
"""
Agon-Bench: Agent Event — 6-task agentic capability benchmark with hidden tests.
"""
import argparse, json, os, sys, time, subprocess, tempfile, re
from pathlib import Path
import httpx

TASKS = [
    {
        "id": 1, "name": "Tool Calling", "difficulty": "Easy",
        "prompt": """Write a Python function `call_weather_api(city: str) -> dict` that constructs a proper tool call to a weather API. The function should return a dict with `tool_name: 'get_weather'`, `arguments: {city: city}`, and handle the case where city is empty by returning an error dict.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            ("call_weather_api('Tokyo')['tool_name']", "'get_weather'"),
            ("call_weather_api('Tokyo')['arguments']['city']", "'Tokyo'"),
            ("call_weather_api('')['error']", "True"),
        ]
    },
    {
        "id": 2, "name": "Orchestration", "difficulty": "Easy-Medium",
        "prompt": """Write a Python function `orchestrate(results: list[dict]) -> str` that takes a list of tool call results (each with `tool`, `status`, `data` keys) and decides the next action. If any result has status 'error', return 'retry'. If all results have status 'success' and contain 'answer' key, return 'complete'. If some results are missing, return 'fetch_more'. Return ONLY the function.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            ("orchestrate([{'tool': 'search', 'status': 'error', 'data': None}])", "'retry'"),
            ("orchestrate([{'tool': 'search', 'status': 'success', 'data': {'answer': 42}}])", "'complete'"),
            ("orchestrate([{'tool': 'search', 'status': 'success', 'data': {}}])", "'fetch_more'"),
        ]
    },
    {
        "id": 3, "name": "Error Handling", "difficulty": "Medium",
        "prompt": """Write a Python function `handle_tool_error(error: dict, context: dict) -> dict` that takes an error dict (with `code`, `message`, `recoverable` keys) and a context dict (with `retry_count`, `fallback_available` keys). If recoverable and retry_count < 3, return `{action: 'retry', delay: 2**retry_count}`. If not recoverable but fallback_available, return `{action: 'fallback'}`. Otherwise return `{action: 'fail', reason: message}`. Return ONLY the function.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            ("handle_tool_error({'code': 500, 'message': 'timeout', 'recoverable': True}, {'retry_count': 0, 'fallback_available': False})['action']", "'retry'"),
            ("handle_tool_error({'code': 500, 'message': 'timeout', 'recoverable': True}, {'retry_count': 0, 'fallback_available': False})['delay']", "1"),
            ("handle_tool_error({'code': 500, 'message': 'timeout', 'recoverable': False}, {'retry_count': 0, 'fallback_available': True})['action']", "'fallback'"),
            ("handle_tool_error({'code': 500, 'message': 'fatal', 'recoverable': False}, {'retry_count': 0, 'fallback_available': False})['action']", "'fail'"),
        ]
    },
    {
        "id": 4, "name": "Planning", "difficulty": "Medium-Hard",
        "prompt": """Write a Python function `make_plan(request: str, tools: list[str]) -> list[dict]` that takes a user request and available tools, and returns a step-by-step plan. Each step is a dict with `step`, `tool`, `goal`. For example, if request is 'What's the weather in Tokyo and is it a good day for a picnic?' and tools are ['get_weather', 'query_knowledge'], return a plan with 2-3 steps. The function should parse the request and match steps to tools. Return ONLY the function.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            {"type": "script", "label": "Plan returns list of steps",
             "setup": "plan = make_plan(\"What's the weather in Tokyo?\", ['get_weather'])",
             "check": "print('LIST' if isinstance(plan, list) and len(plan) > 0 else 'NOT_LIST')",
             "expected": "LIST"},
            {"type": "script", "label": "Plan steps have required keys",
             "setup": "plan = make_plan(\"What's the weather in Tokyo?\", ['get_weather'])",
             "check": "step = plan[0]\nprint('OK' if all(k in step for k in ['step', 'tool', 'goal']) else 'MISSING_KEYS')",
             "expected": "OK"},
        ]
    },
    {
        "id": 5, "name": "Parsing", "difficulty": "Medium",
        "prompt": """Write a Python function `parse_tool_output(raw: str, schema: dict) -> dict` that takes a raw string output from a tool and a schema dict (with `fields` list, each with `name`, `type`, `required`), and returns a parsed dict. Handle: JSON strings (parse them), CSV lines (split by comma), key=value pairs (split by =). If a required field is missing, set it to None. Return ONLY the function.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            {"type": "script", "label": "Parse JSON string",
             "setup": "schema = {'fields': [{'name': 'temp', 'type': 'int', 'required': True}]}\nresult = parse_tool_output('{\"temp\": 25}', schema)",
             "check": "print('OK' if result.get('temp') == 25 else f'FAIL: {result}')",
             "expected": "OK"},
            {"type": "script", "label": "Parse CSV line",
             "setup": "schema = {'fields': [{'name': 'name', 'type': 'str', 'required': True}, {'name': 'age', 'type': 'int', 'required': True}]}\nresult = parse_tool_output('Alice,30', schema)",
             "check": "print('OK' if result.get('name') == 'Alice' and result.get('age') == 30 else f'FAIL: {result}')",
             "expected": "OK"},
            {"type": "script", "label": "Parse key=value",
             "setup": "schema = {'fields': [{'name': 'city', 'type': 'str', 'required': True}]}\nresult = parse_tool_output('city=London', schema)",
             "check": "print('OK' if result.get('city') == 'London' else f'FAIL: {result}')",
             "expected": "OK"},
        ]
    },
    {
        "id": 6, "name": "Decision-Making", "difficulty": "Hard",
        "prompt": """Write a Python function `decide_action(state: dict, rules: list[dict]) -> str` that takes a state dict (with `confidence`, `urgency`, `resources` keys, each 0-1) and a list of rule dicts (each with `condition: str`, `action: str`). Conditions are Python expressions like 'confidence > 0.7 and urgency > 0.5'. Evaluate conditions against state, return the action of the first matching rule. If no rule matches, return 'wait'. Handle division by zero and missing keys gracefully. Return ONLY the function.

Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            {"type": "script", "label": "First matching rule wins",
             "setup": "state = {'confidence': 0.8, 'urgency': 0.6, 'resources': 0.5}\nrules = [{'condition': 'confidence > 0.7 and urgency > 0.5', 'action': 'act'}, {'condition': 'confidence > 0.5', 'action': 'plan'}]",
             "check": "result = decide_action(state, rules)\nprint('OK' if result == 'act' else f'FAIL: {result}')",
             "expected": "OK"},
            {"type": "script", "label": "No match returns wait",
             "setup": "state = {'confidence': 0.1, 'urgency': 0.1, 'resources': 0.1}\nrules = [{'condition': 'confidence > 0.7', 'action': 'act'}]",
             "check": "result = decide_action(state, rules)\nprint('OK' if result == 'wait' else f'FAIL: {result}')",
             "expected": "OK"},
            {"type": "script", "label": "Handles missing keys gracefully",
             "setup": "state = {'confidence': 0.5}\nrules = [{'condition': 'urgency > 0.5', 'action': 'urgent'}]",
             "check": "result = decide_action(state, rules)\nprint('OK' if result == 'wait' else f'FAIL: {result}')",
             "expected": "OK"},
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


def call_llm(url, model, prompt, seed=None, timeout=1800, max_retries=5):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 32768,
        "temperature": 0.3,
        "stream": False,
    }
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.post(f"{url}/v1/chat/completions", json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = str(e)
            if attempt < max_retries:
                wait = min(2 ** attempt, 30)
                print(f"  [retry {attempt}/{max_retries}] waiting {wait}s... ({last_error[:120]})")
                time.sleep(wait)
    return f"[ERROR] {last_error}"


def strip_thinking(text):
    """Remove thinking blocks from model output.
    
    Handles:
    - Qwen3.5 format: literal "thinking" then "response" as plain text markers
    - DeepSeek format: <think>...</think> HTML tags
    - No thinking: return as-is
    """
    import re
    # Qwen3.5 format: "thinking" then "response" as plain text markers
    if 'thinking' in text:
        text = re.sub(r'(?s)\s*thinking\s*.*?response\s*\n?', '', text, count=1)
    # DeepSeek format: <think>...</think> HTML tags
    if re.search(r'<think>', text):
        text = re.sub(r'(?s)(?:^|\n)\s*<think>.*?</think>\n?', '', text)
        if re.search(r'(?:^|\n)\s*<think>', text):
            text = re.sub(r'(?s)(?:^|\n)\s*<think>.*$', '', text)
    return text.strip()


def run_hidden_tests(code, tests):
    if not tests:
        return 0, 0, []
    code_clean = code.strip()
    code_clean = strip_thinking(code_clean).strip()
    code_clean = re.sub(r'```(?:python)?\s*\n?', '', code_clean)
    code_clean = re.sub(r'\n?```\s*', '', code_clean)
    code_clean = code_clean.strip()
    if not code_clean:
        return 0, len(tests), [(t.get("label", str(t)) if isinstance(t, dict) else str(t[0]), "EMPTY after cleaning") for t in tests]

    passed = 0
    details = []
    for test_item in tests:
        if isinstance(test_item, dict) and test_item.get("type") == "script":
            tmp_path = None
            try:
                test_script = code_clean + "\n\n" + test_item["setup"] + "\n\n" + test_item.get("check", "")
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_script)
                    tmp_path = f.name
                result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)
                if result.returncode != 0:
                    details.append((test_item.get("label", "script"), test_item["expected"], f"RUNTIME ERROR: {result.stderr[:200]}"))
                    continue
                actual = result.stdout.strip()
                expected = test_item["expected"]
                if actual == expected or (expected.startswith("CONTAINS:") and expected[9:] in actual):
                    passed += 1
                    details.append((test_item.get("label", "script"), expected, actual, "PASS"))
                else:
                    details.append((test_item.get("label", "script"), expected, actual, "FAIL"))
            except Exception as e:
                details.append((test_item.get("label", "script"), test_item["expected"], f"TEST ERROR: {str(e)[:200]}"))
                try:
                    if tmp_path: os.unlink(tmp_path)
                except: pass
        else:
            expr, expected = test_item
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code_clean + "\n\nimport json\n")
                    f.write(f"result = {expr}\n")
                    f.write("print(repr(result))\n")
                    tmp_path = f.name
                result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)
                if result.returncode != 0:
                    details.append((expr, expected, f"RUNTIME ERROR: {result.stderr[:100]}"))
                    continue
                actual = result.stdout.strip()
                if actual == expected or eval(actual) == eval(expected):
                    passed += 1
                    details.append((expr, expected, actual, "PASS"))
                else:
                    details.append((expr, expected, actual, "FAIL"))
            except Exception as e:
                details.append((expr, expected, f"TEST ERROR: {str(e)[:100]}"))
    return passed, len(tests), details


def main():
    parser = argparse.ArgumentParser(description="Agon-Bench: Agent Event")
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
        passed, total, details = run_hidden_tests(response, task["hidden_tests"])
        print(f"  Hidden tests: {passed}/{total} passed")
        for detail in details:
            status = "PASS" if detail[-1] == "PASS" else "ERROR"
            print(f"    {status}: {detail[0][:60]}... -> {detail[-1]}")
        results.append({
            "id": task["id"], "name": task["name"], "difficulty": task["difficulty"],
            "response_length": len(response), "elapsed_seconds": round(elapsed, 1),
            "hidden_tests_passed": passed, "hidden_tests_total": total,
            "response_file": f"{args.output}/task{task['id']}/response.txt",
        })
    summary = {
        "model": args.model, "model_url": args.model_url,
        "benchmark": "agent-event", "run": args.run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "tasks": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved to {args.output}/summary.json")

if __name__ == "__main__":
    main()
