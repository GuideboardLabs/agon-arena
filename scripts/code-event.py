#!/usr/bin/env python3
"""
Agon-Bench: Code Event — 6-task code generation benchmark.
Part of Agon-Bench (Agent + Reason + Code).
"""
import argparse, json, os, sys, time, subprocess, tempfile
from pathlib import Path
import httpx

TASKS = [
    {
        "id": 1, "name": "String Cleaner", "difficulty": "Easy",
        "prompt": """Write a Python function `clean_text(text: str) -> str` that:
- Strips leading/trailing whitespace
- Collapses multiple spaces into one
- Removes any character that isn't alphanumeric, space, hyphen, apostrophe, or period
- Truncates to at most 200 characters, ending on a complete word (no mid-word cut)
- Returns "INVALID" if the result is empty after cleaning
Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            ("clean_text('  Hello   World!  ')", "'Hello World'"),
            ("clean_text('')", "'INVALID'"),
            ("clean_text('   ')", "'INVALID'"),
            ("clean_text('Hello-World')", "'Hello-World'"),
            ("clean_text('a' * 300)", repr('a' * 200)),
        ]
    },
    {
        "id": 2, "name": "Log Parser", "difficulty": "Easy-Medium",
        "prompt": """Write a Python function `parse_logs(log_lines: list[str]) -> dict` that:
- Parses lines in format: `[2024-01-15 10:30:45] LEVEL: message`
- Valid LEVEL values: INFO, WARN, ERROR, DEBUG
- Returns a dict with:
  - "counts": {LEVEL: count} for each level
  - "errors": list of (timestamp, message) tuples for ERROR lines
  - "warnings": list of (timestamp, message) tuples for WARN lines
  - "first_timestamp" and "last_timestamp": earliest and latest timestamps found
- Malformed lines are silently skipped
Return ONLY the function definition. No explanations, no test code.""",
        "hidden_tests": [
            ("parse_logs(['[2024-01-15 10:30:45] ERROR: disk full'])['counts']", "{'ERROR': 1}"),
            ("len(parse_logs(['[2024-01-15 10:30:45] ERROR: disk full'])['errors'])", "1"),
            ("len(parse_logs([])['counts'])", "0"),
            ("len(parse_logs(['bad line'])['counts'])", "0"),
        ]
    },
    {
        "id": 3, "name": "LRU Cache", "difficulty": "Medium",
        "prompt": """Write a Python class `LRUCache` that:
- __init__(self, capacity: int) — sets max items
- get(key) -> any — returns value or -1 if not found
- put(key, value) -> None — inserts or updates; evicts least recently used if at capacity
- Both get and put count as "use" for LRU ordering
- Must be O(1) average time for both operations
Return ONLY the class definition. No explanations, no test code.""",
        "hidden_tests": [
            {"type": "script", "label": "LRU evicts oldest when full", "setup": "exec(open(MODEL_CODE_PATH).read())\nc = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(3, 3)", "check": "result = c.get(1)\nprint(repr(result))", "expected": "-1"},
            {"type": "script", "label": "LRU get returns value", "setup": "exec(open(MODEL_CODE_PATH).read())\nc = LRUCache(1)\nc.put(1, 1)", "check": "result = c.get(1)\nprint(repr(result))", "expected": "1"},
            {"type": "script", "label": "LRU get refreshes order", "setup": "exec(open(MODEL_CODE_PATH).read())\nc = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.get(1)\nc.put(3, 3)", "check": "result = c.get(2)\nprint(repr(result))", "expected": "-1"},
        ]
    },
    {
        "id": 4, "name": "File Indexer", "difficulty": "Medium-Hard",
        "prompt": """Write a Python script `indexer.py` that:
- Takes a directory path as a command-line argument
- Recursively walks all .md files
- For each file, extracts all [[wikilinks]] and [markdown](links)
- Builds an in-memory index: {source_file: {wikilinks: [...], markdown_links: [...]}}
- Writes a report to stdout: for each file, list its broken links
- Handles symlinks (follow them), hidden directories (skip .-prefixed dirs), and permission errors (skip and continue)
Return the COMPLETE script. No explanations.""",
        "hidden_tests": [
            {"type": "script", "label": "Indexer finds wikilinks", "setup": "import tempfile, os, sys, json\nfrom pathlib import Path\ntmpdir = tempfile.mkdtemp()\n(Path(tmpdir) / 'note1.md').write_text('Link to [[note2]] and [[note3]]')\n(Path(tmpdir) / 'note2.md').write_text('Has a [[markdown link]](https://example.com)')\nscript_path = os.path.join(tmpdir, 'indexer.py')\nimport shutil\nshutil.copy(MODEL_CODE_PATH, script_path)", "check": "import subprocess\nresult = subprocess.run([sys.executable, script_path, tmpdir], capture_output=True, text=True, timeout=10)\noutput = result.stdout\nprint('BROKEN' if 'note3' in output else 'NO_BROKEN')\nshutil.rmtree(tmpdir, ignore_errors=True)", "expected": "CONTAINS:BROKEN"},
            {"type": "script", "label": "Indexer skips hidden dirs", "setup": "import tempfile, os, sys\nfrom pathlib import Path\ntmpdir = tempfile.mkdtemp()\n(Path(tmpdir) / 'visible.md').write_text('Hello')\nhidden = Path(tmpdir) / '.hidden'\nhidden.mkdir()\n(hidden / 'secret.md').write_text('[[hidden]]')\nscript_path = os.path.join(tmpdir, 'indexer.py')\nimport shutil\nshutil.copy(MODEL_CODE_PATH, script_path)", "check": "import subprocess\nresult = subprocess.run([sys.executable, script_path, tmpdir], capture_output=True, text=True, timeout=10)\noutput = result.stdout + result.stderr\nprint('OK' if '.hidden' not in output and result.returncode == 0 else 'FAIL')\nshutil.rmtree(tmpdir, ignore_errors=True)", "expected": "OK"},
        ]
    },
    {
        "id": 5, "name": "Task Runner CLI", "difficulty": "Hard",
        "prompt": """Write a multi-file Python project `taskrunner/` with:
- taskrunner/__init__.py — exports run_task(name)
- taskrunner/runner.py — core logic: reads tasks from a JSON file, executes shell commands, captures stdout/stderr/exit code, writes results
- taskrunner/cli.py — CLI entry point using argparse with commands: run <task-name>, list, status
- taskrunner/models.py — dataclasses for Task(name, command, timeout, retries) and Result(task_name, exit_code, stdout, stderr, duration, retry_count)
- Tasks JSON format: [{"name": "test", "command": "pytest", "timeout": 30, "retries": 0}]
- run executes a task, retries on failure up to retries count, writes result to results/{task_name}.json
- list prints all task names and their current status (from results dir)
- status shows a summary table of all results
Return ALL four files, each clearly marked with filename headers.""",
        "hidden_tests": [
            {"type": "script", "label": "TaskRunner creates project structure",
             "setup": "import tempfile, os, sys, re, shutil\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nresponse = Path(MODEL_CODE_PATH).read_text()\ncurrent_file = None\ncurrent_content = []\nfor line in response.split('\\n'):\n    m = re.match(r'^#+\\s+(\\S+)\\s*$', line)\n    if m:\n        if current_file and current_content:\n            file_path = tmpdir / current_file\n            file_path.parent.mkdir(parents=True, exist_ok=True)\n            file_path.write_text('\\n'.join(current_content))\n        current_file = m.group(1)\n        current_content = []\n    elif current_file:\n        current_content.append(line)\nif current_file and current_content:\n    file_path = tmpdir / current_file\n    file_path.parent.mkdir(parents=True, exist_ok=True)\n    file_path.write_text('\\n'.join(current_content))\nfiles = ['taskrunner/__init__.py', 'taskrunner/runner.py', 'taskrunner/cli.py', 'taskrunner/models.py']\nmissing = [f for f in files if not (tmpdir / f).exists()]\nprint('OK' if not missing else f'MISSING: {missing}')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "check": "print('OK')",
             "expected": "OK"},
            {"type": "script", "label": "TaskRunner models import correctly",
             "setup": "import tempfile, os, sys, re, shutil\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nresponse = Path(MODEL_CODE_PATH).read_text()\ncurrent_file = None\ncurrent_content = []\nfor line in response.split('\\n'):\n    m = re.match(r'^#+\\s+(\\S+)\\s*$', line)\n    if m:\n        if current_file and current_content:\n            file_path = tmpdir / current_file\n            file_path.parent.mkdir(parents=True, exist_ok=True)\n            file_path.write_text('\\n'.join(current_content))\n        current_file = m.group(1)\n        current_content = []\n    elif current_file:\n        current_content.append(line)\nif current_file and current_content:\n    file_path = tmpdir / current_file\n    file_path.parent.mkdir(parents=True, exist_ok=True)\n    file_path.write_text('\\n'.join(current_content))\nsys.path.insert(0, str(tmpdir))",
             "check": "from taskrunner.models import Task, Result\nt = Task(name='test', command='echo hi', timeout=30, retries=0)\nr = Result(task_name='test', exit_code=0, stdout='hi', stderr='', duration=0.1, retry_count=0)\nprint('OK')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "expected": "OK"},
        ]
    },
    {
        "id": 6, "name": "Constrained Diff Tool", "difficulty": "Very Hard",
        "prompt": """Write a Python script `diff.py` that implements a line-by-line diff tool with NO external dependencies (stdlib only). It must:
- Accept two file paths as arguments
- Output a unified diff format (like diff -u) to stdout
- Handle files of different lengths
- Implement at least one optimization: Myers' diff algorithm or patience diff
- Include a --color flag that highlights additions in green and removals in red using ANSI codes
- Include a --context N flag that shows N lines of context around each change (default 3)
- Handle binary files gracefully (detect null bytes, print "Binary files differ" and exit 0)
- Handle very large files (100K+ lines) without running out of memory
Return the COMPLETE script. No explanations.""",
        "hidden_tests": [
            {"type": "script", "label": "Diff detects identical files",
             "setup": "import tempfile, os, sys\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nscript_path = tmpdir / 'diff.py'\nimport shutil\nshutil.copy(MODEL_CODE_PATH, str(script_path))\nfile_a = tmpdir / 'a.txt'\nfile_b = tmpdir / 'b.txt'\nfile_a.write_text('line1\\nline2\\nline3\\n')\nfile_b.write_text('line1\\nline2\\nline3\\n')",
             "check": "import subprocess\nresult = subprocess.run([sys.executable, str(script_path), str(file_a), str(file_b)], capture_output=True, text=True, timeout=10)\noutput = result.stdout.strip()\nprint('OK' if output == '' or 'No differences' in output else 'HAS_DIFF')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "expected": "OK"},
            {"type": "script", "label": "Diff detects changes",
             "setup": "import tempfile, os, sys\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nscript_path = tmpdir / 'diff.py'\nimport shutil\nshutil.copy(MODEL_CODE_PATH, str(script_path))\nfile_a = tmpdir / 'a.txt'\nfile_b = tmpdir / 'b.txt'\nfile_a.write_text('line1\\nline2\\nline3\\n')\nfile_b.write_text('line1\\nchanged\\nline3\\n')",
             "check": "import subprocess\nresult = subprocess.run([sys.executable, str(script_path), str(file_a), str(file_b)], capture_output=True, text=True, timeout=10)\noutput = result.stdout\nprint('OK' if 'changed' in output and ('-' in output or '+' in output) else 'NO_DIFF')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "expected": "OK"},
            {"type": "script", "label": "Diff handles binary files",
             "setup": "import tempfile, os, sys\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nscript_path = tmpdir / 'diff.py'\nimport shutil\nshutil.copy(MODEL_CODE_PATH, str(script_path))\nfile_a = tmpdir / 'a.bin'\nfile_b = tmpdir / 'b.bin'\nfile_a.write_bytes(b'hello\\x00world\\n')\nfile_b.write_bytes(b'hello\\x00there\\n')",
             "check": "import subprocess\nresult = subprocess.run([sys.executable, str(script_path), str(file_a), str(file_b)], capture_output=True, text=True, timeout=10)\noutput = (result.stdout + result.stderr).lower()\nprint('BINARY' if 'binary' in output else 'NO_BINARY')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "expected": "CONTAINS:BINARY"},
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
    - DeepSeek format:  thinking... response HTML tags
    - No thinking: return as-is
    """
    import re
    # Qwen3.5 format: "thinking" then "response" as plain text markers
    if 'thinking' in text:
        text = re.sub(r'(?s)\s*thinking\s*.*?response\s*\n?', '', text, count=1)
    # DeepSeek format:  thinking... response HTML tags
    if re.search(r'<think>', text):
        text = re.sub(r'(?s)(?:^|\n)\s*<think>.*?</think>\n?', '', text)
        if re.search(r'(?:^|\n)\s*<think>', text):
            text = re.sub(r'(?s)(?:^|\n)\s*<think>.*$', '', text)
    return text.strip()


def run_hidden_tests(code, tests):
    if not tests:
        return 0, 0, []
    import re
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
            model_code_path = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code_clean)
                    model_code_path = f.name
                test_script = test_item["setup"] + "\n\n" + test_item.get("check", "")
                test_script = test_script.replace("MODEL_CODE_PATH", repr(model_code_path))
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_script)
                    tmp_path = f.name
                result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=15)
                if model_code_path:
                    try: os.unlink(model_code_path)
                    except: pass
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
                try:
                    if model_code_path: os.unlink(model_code_path)
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
                # Compare as Python literals — handles dicts with extra keys
                if actual == expected or eval(actual) == eval(expected):
                    passed += 1
                    details.append((expr, expected, actual, "PASS"))
                else:
                    details.append((expr, expected, actual, "FAIL"))
            except Exception as e:
                details.append((expr, expected, f"TEST ERROR: {str(e)[:100]}"))
    return passed, len(tests), details


def main():
    parser = argparse.ArgumentParser(description="Agon-Bench: Code Event")
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
        "benchmark": "code-event", "run": args.run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "tasks": results,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary saved to {args.output}/summary.json")

if __name__ == "__main__":
    main()
