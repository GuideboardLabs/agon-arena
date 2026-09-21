#!/usr/bin/env python3
"""
Re-run hidden tests against existing response files using the fixed harness.
"""
import json, os, sys, re, subprocess, tempfile, shutil
from pathlib import Path

RESULTS_BASE = Path(os.environ.get("AGON_RESULTS_DIR", str(Path(__file__).resolve().parent.parent / "results")))

TASKS = [
    {
        "id": 1, "name": "String Cleaner",
        "hidden_tests": [
            ("clean_text('  Hello   World!  ')", "'Hello World'"),
            ("clean_text('')", "'INVALID'"),
            ("clean_text('   ')", "'INVALID'"),
            ("clean_text('Hello-World')", "'Hello-World'"),
            ("clean_text('a' * 300)", repr('a' * 200)),
        ]
    },
    {
        "id": 2, "name": "Log Parser",
        "hidden_tests": [
            ("parse_logs(['[2024-01-15 10:30:45] ERROR: disk full'])['counts']", "{'ERROR': 1}"),
            ("len(parse_logs(['[2024-01-15 10:30:45] ERROR: disk full'])['errors'])", "1"),
            ("len(parse_logs([])['counts'])", "0"),
            ("len(parse_logs(['bad line'])['counts'])", "0"),
        ]
    },
    {
        "id": 3, "name": "LRU Cache",
        "hidden_tests": [
            {"type": "script", "label": "LRU evicts oldest when full",
             "setup": "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(3, 3)",
             "check": "result = c.get(1)\nprint(repr(result))", "expected": "-1"},
            {"type": "script", "label": "LRU get returns value",
             "setup": "c = LRUCache(1)\nc.put(1, 1)",
             "check": "result = c.get(1)\nprint(repr(result))", "expected": "1"},
            {"type": "script", "label": "LRU get refreshes order",
             "setup": "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.get(1)\nc.put(3, 3)",
             "check": "result = c.get(2)\nprint(repr(result))", "expected": "-1"},
        ]
    },
    {
        "id": 4, "name": "File Indexer",
        "hidden_tests": [
            {"type": "script", "label": "Indexer finds wikilinks",
             "setup": "import tempfile, os, sys, json\nfrom pathlib import Path\ntmpdir = tempfile.mkdtemp()\n(Path(tmpdir) / 'note1.md').write_text('Link to [[note2]] and [[note3]]')\n(Path(tmpdir) / 'note2.md').write_text('Has a [[markdown link]](https://example.com)')\nscript_path = os.path.join(tmpdir, 'indexer.py')\nimport shutil\nshutil.copy(MODEL_CODE_PATH, script_path)",
             "check": "import subprocess\nresult = subprocess.run([sys.executable, script_path, tmpdir], capture_output=True, text=True, timeout=10)\noutput = result.stdout\nprint('BROKEN' if 'note3' in output else 'NO_BROKEN')\nshutil.rmtree(tmpdir, ignore_errors=True)",
             "expected": "EXACT:BROKEN"},
            {"type": "script", "label": "Indexer skips hidden dirs",
             "setup": "import tempfile, os, sys\nfrom pathlib import Path\ntmpdir = tempfile.mkdtemp()\n(Path(tmpdir) / 'visible.md').write_text('Hello')\nhidden = Path(tmpdir) / '.hidden'\nhidden.mkdir()\n(hidden / 'secret.md').write_text('[[hidden]]')\nscript_path = os.path.join(tmpdir, 'indexer.py')\nimport shutil\nshutil.copy(MODEL_CODE_PATH, script_path)",
             "check": "import subprocess\nresult = subprocess.run([sys.executable, script_path, tmpdir], capture_output=True, text=True, timeout=10)\noutput = result.stdout + result.stderr\nprint('OK' if '.hidden' not in output and result.returncode == 0 else 'FAIL')\nshutil.rmtree(tmpdir, ignore_errors=True)",
             "expected": "OK"},
        ]
    },
    {
        "id": 5, "name": "Task Runner CLI",
        "hidden_tests": [
            {"type": "script", "label": "TaskRunner creates project structure",
             "setup": "import tempfile, os, sys, re, shutil\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nresponse = Path(MODEL_CODE_PATH).read_text()\ncurrent_file = None\ncurrent_content = []\nfor line in response.split('\n'):\n    m = re.match(r'^#+\s+(\S+)\s*$', line)\n    if m:\n        if current_file and current_content:\n            file_path = tmpdir / current_file\n            file_path.parent.mkdir(parents=True, exist_ok=True)\n            file_path.write_text('\n'.join(current_content))\n        current_file = m.group(1)\n        current_content = []\n    elif current_file:\n        current_content.append(line)\nif current_file and current_content:\n    file_path = tmpdir / current_file\n    file_path.parent.mkdir(parents=True, exist_ok=True)\n    file_path.write_text('\n'.join(current_content))\nfiles = ['taskrunner/__init__.py', 'taskrunner/runner.py', 'taskrunner/cli.py', 'taskrunner/models.py']\nmissing = [f for f in files if not (tmpdir / f).exists()]\nprint('OK' if not missing else f'MISSING: {missing}')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "check": "pass  # setup already prints the verdict",
             "expected": "OK"},
            {"type": "script", "label": "TaskRunner models import correctly",
             "setup": "import tempfile, os, sys, re, shutil\nfrom pathlib import Path\ntmpdir = Path(tempfile.mkdtemp())\nresponse = Path(MODEL_CODE_PATH).read_text()\ncurrent_file = None\ncurrent_content = []\nfor line in response.split('\n'):\n    m = re.match(r'^#+\s+(\S+)\s*$', line)\n    if m:\n        if current_file and current_content:\n            file_path = tmpdir / current_file\n            file_path.parent.mkdir(parents=True, exist_ok=True)\n            file_path.write_text('\n'.join(current_content))\n        current_file = m.group(1)\n        current_content = []\n    elif current_file:\n        current_content.append(line)\nif current_file and current_content:\n    file_path = tmpdir / current_file\n    file_path.parent.mkdir(parents=True, exist_ok=True)\n    file_path.write_text('\n'.join(current_content))\nsys.path.insert(0, str(tmpdir))",
             "check": "from taskrunner.models import Task, Result\nt = Task(name='test', command='echo hi', timeout=30, retries=0)\nr = Result(task_name='test', exit_code=0, stdout='hi', stderr='', duration=0.1, retry_count=0)\nprint('OK')\nshutil.rmtree(str(tmpdir), ignore_errors=True)",
             "expected": "OK"},
        ]
    },
    {
        "id": 6, "name": "Constrained Diff Tool",
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
             "expected": "EXACT:BINARY"},
        ]
    },
]


def strip_thinking(text):
    """Remove thinking blocks from model output.
    
    Handles:
    - Qwen3.5 format: literal "thinking" then "response" as plain text markers
    - DeepSeek format: <think>...</think> HTML tags
    - No thinking: return as-is
    """
    import re
    # Qwen3.5 format: " thinking
...
 response

actual content"
    if 'thinking' in text:
        text = re.sub(r'(?s)\s*thinking\s*.*?response\s*\n?', '', text, count=1)
    # DeepSeek format: <think>...</think> HTML tags
    if re.search(r'<think>', text):
        text = re.sub(r'(?s)(?:^|\n)\s*<think>.*?</think>\n?', '', text)
        if re.search(r'(?:^|\n)\s*<think>', text):
            text = re.sub(r'(?s)(?:^|\n)\s*<think>.*$', '', text)
    return text.strip()


def clean_code(code):
    code = strip_thinking(code)
    code = re.sub(r'```(?:python)?\s*\n?', '', code)
    code = re.sub(r'\n?```\s*', '', code)
    blocks = re.split(r'```(?:python)?\s*\n?', code)
    if len(blocks) > 1:
        code = blocks[-1]
        code = re.sub(r'\n?```\s*', '', code)
    code = code.strip()
    if code and not code.startswith(('def ', 'class ', 'import ', 'from ', '"""', '```')):
        lines = code.split('\n')
        code_lines = []
        in_code = False
        for line in lines:
            if re.match(r'^(def |class |import |from )', line):
                in_code = True
            if in_code:
                code_lines.append(line)
        if code_lines:
            code = '\n'.join(code_lines)
    return code.strip()


def dicts_match(actual, expected):
    """Compare two dicts — actual may have extra keys (0-count levels)."""
    try:
        a = eval(actual)
        e = eval(expected)
        if isinstance(a, dict) and isinstance(e, dict):
            # Check that all expected keys match
            for k, v in e.items():
                if k not in a or a[k] != v:
                    return False
            return True
        return a == e
    except:
        return actual == expected


def run_simple_test(code_clean, expr, expected):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code_clean + "\n\nimport json\n")
            f.write(f"result = {expr}\n")
            f.write("print(repr(result))\n")
            tmp_path = f.name
        result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=10)
        os.unlink(tmp_path)
        if result.returncode != 0:
            return ("RUNTIME ERROR", result.stderr[:100])
        actual = result.stdout.strip()
        if actual == expected or dicts_match(actual, expected):
            return ("PASS", actual)
        return ("FAIL", actual)
    except Exception as e:
        return ("TEST ERROR", str(e)[:100])


def run_script_test(code_clean, test_item):
    tmp_path = None
    model_code_path = None
    try:
        if "MODEL_CODE_PATH" in test_item.get("setup", "") or "MODEL_CODE_PATH" in test_item.get("check", ""):
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code_clean)
                model_code_path = f.name
            test_script = test_item["setup"] + "\n\n" + test_item.get("check", "")
            test_script = test_script.replace("MODEL_CODE_PATH", repr(model_code_path))
        else:
            test_script = code_clean + "\n\n" + test_item["setup"] + "\n\n" + test_item.get("check", "")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            tmp_path = f.name
        result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=15)
        if model_code_path:
            try: os.unlink(model_code_path)
            except: pass
        os.unlink(tmp_path)
        if result.returncode != 0:
            return ("RUNTIME ERROR", result.stderr[:200])
        actual = result.stdout.strip()
        expected = test_item["expected"]
        if actual == expected or (expected.startswith("CONTAINS:") and expected[9:] in actual):
            return ("PASS", actual)
        return ("FAIL", actual)
    except Exception as e:
        try:
            if tmp_path: os.unlink(tmp_path)
        except: pass
        try:
            if model_code_path: os.unlink(model_code_path)
        except: pass
        return ("TEST ERROR", str(e)[:200])


def rerun_model(model_name, run_dirs):
    for run_dir in run_dirs:
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            print(f"  [SKIP] No summary.json in {run_dir}")
            continue
        summary = json.loads(summary_path.read_text())
        run_num = summary.get("run", "?")
        print(f"\n  {'='*50}")
        print(f"  {model_name} — Run {run_num}")
        print(f"  {'='*50}")
        total_passed = 0
        total_tests = 0
        task_results = []
        for task in TASKS:
            task_id = task["id"]
            task_dir = run_dir / f"task{task_id}"
            response_file = task_dir / "response.txt"
            if not response_file.exists():
                print(f"    Task {task_id} ({task['name']}): NO RESPONSE FILE")
                task_results.append({"id": task_id, "name": task["name"], "passed": 0, "total": 0, "details": []})
                continue
            code = response_file.read_text()
            code_clean = clean_code(code)
            if not code_clean:
                print(f"    Task {task_id} ({task['name']}): EMPTY after cleaning")
                task_results.append({"id": task_id, "name": task["name"], "passed": 0, "total": 0, "details": []})
                continue
            passed = 0
            details = []
            for test_item in task["hidden_tests"]:
                if isinstance(test_item, dict) and test_item.get("type") == "script":
                    status, info = run_script_test(code_clean, test_item)
                else:
                    expr, expected = test_item
                    status, info = run_simple_test(code_clean, expr, expected)
                if isinstance(test_item, dict):
                    label = test_item.get("label", "script test")
                else:
                    label = str(test_item[0])[:60]
                if status == "PASS":
                    passed += 1
                    details.append(f"      ✓ {label}")
                else:
                    details.append(f"      ✗ {label}: {status} — {info}")
            total = len(task["hidden_tests"])
            total_passed += passed
            total_tests += total
            task_results.append({"id": task_id, "name": task["name"], "passed": passed, "total": total, "details": details})
            if total > 0:
                print(f"    Task {task_id} ({task['name']}): {passed}/{total}")
                for d in details:
                    print(d)
            else:
                print(f"    Task {task_id} ({task['name']}): no tests")
        print(f"\n    TOTAL: {total_passed}/{total_tests}")
        for i, tr in enumerate(task_results):
            if i < len(summary["tasks"]):
                summary["tasks"][i]["hidden_tests_passed"] = tr["passed"]
                summary["tasks"][i]["hidden_tests_total"] = tr["total"]
        summary_path.write_text(json.dumps(summary, indent=2))
        print(f"    Updated {summary_path}")


def main():
    models = ["gemma4-12b", "ornith-1.0-9b", "lfm2.5-8b", "jackrong"]
    for model in models:
        model_dir = RESULTS_BASE / model / "code"
        if not model_dir.exists():
            print(f"\n{'='*60}\n{model}: No code results directory")
            continue
        run_dirs = sorted(model_dir.glob("run*"))
        if not run_dirs:
            print(f"\n{'='*60}\n{model}: No run directories found")
            continue
        print(f"\n{'='*60}\n{model}: {len(run_dirs)} run(s) found")
        rerun_model(model, run_dirs)

if __name__ == "__main__":
    main()
