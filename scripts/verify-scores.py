#!/usr/bin/env python3
"""
Re-run all hidden tests against saved response files to verify/correct DB scores.
This is NOT a shortcut — it runs the exact same test harness the benchmark uses.
"""
import sys, os, json, re, tempfile, subprocess, sqlite3, time
from pathlib import Path

# Add scripts dir to path for importing task definitions
scripts_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, scripts_dir)

# Import task definitions
import importlib.util
spec = importlib.util.spec_from_file_location("agent_event", os.path.join(scripts_dir, "agent-event.py"))
agent_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_mod)
AGENT_TASKS = agent_mod.TASKS

spec = importlib.util.spec_from_file_location("code_event", os.path.join(scripts_dir, "code-event.py"))
code_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(code_mod)
CODE_TASKS = code_mod.TASKS

spec = importlib.util.spec_from_file_location("reason_event", os.path.join(scripts_dir, "reason-event.py"))
reason_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reason_mod)
REASON_TASKS = reason_mod.TASKS

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'agon-bench.db')
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'results')

def strip_thinking(text):
    if 'thinking' in text:
        text = re.sub(r'(?s)\s*thinking\s*.*?response\s*\n?', '', text, count=1)
    if re.search(r'<think', text):
        text = re.sub(r'(?s)(?:^|\n)\s*<think.*? response\n?', '', text)
        if re.search(r'(?:^|\n)\s*<think', text):
            text = re.sub(r'(?s)(?:^|\n)\s*<think.*$', '', text)
    text = re.sub(r'^_T\s*>\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^_N\s*>\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^_T\s+user:\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^_\s*\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s+_\s*\n?', '', text, flags=re.MULTILINE)
    return text.strip()

def extract_code(response):
    """Extract code from response, same as benchmark scripts."""
    code_clean = response.strip()
    code_clean = strip_thinking(code_clean).strip()
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

def run_tests(code, tests, raw_response=None):
    """Run hidden tests, same as benchmark scripts."""
    if not tests:
        return 0, 0, []
    
    code_clean = extract_code(code)
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
                if raw_response:
                    raw_path = model_code_path.replace('.py', '_raw.txt')
                    with open(raw_path, 'w') as f:
                        f.write(raw_response)
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
        elif isinstance(test_item, dict) and test_item.get("type") == "static":
            check_name = test_item.get("check", "")
            weight = test_item.get("weight", 0.5)
            label = test_item.get("label", check_name)
            expected = test_item.get("expected", True)
            
            static_checks = {
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
            
            check_fn = static_checks.get(check_name)
            if check_fn:
                result = check_fn(code_clean)
                if result == expected:
                    passed += weight
                    details.append((label, expected, result, "PASS"))
                else:
                    details.append((label, expected, result, "FAIL"))
            else:
                details.append((label, expected, f"UNKNOWN CHECK: {check_name}", "ERROR"))
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

def verify_model(model_key, model_id):
    """Verify all runs for a model."""
    db = sqlite3.connect(DB_PATH)
    c = db.cursor()
    
    results_dir = Path(RESULTS_DIR) / model_key
    
    for event_name, tasks, run_table, task_table in [
        ('agent', AGENT_TASKS, 'agent_runs', 'agent_tasks'),
        ('code', CODE_TASKS, 'code_runs', 'code_tasks'),
        ('reason', REASON_TASKS, 'reason_runs', 'reason_tasks'),
    ]:
        event_dir = results_dir / event_name
        if not event_dir.exists():
            continue
        
        # Get runs
        runs = c.execute(f'SELECT id, run_number, total_score, max_score FROM {run_table} WHERE model_id=? ORDER BY run_number', (model_id,)).fetchall()
        
        for run_id, run_num, db_total, db_max in runs:
            run_dir = event_dir / f'run{run_num}'
            if not run_dir.exists():
                continue
            
            print(f"\n{'='*60}")
            print(f"{model_key} / {event_name} / run {run_num} (DB: {db_total}/{db_max})")
            print(f"{'='*60}")
            
            run_passed = 0
            run_total = 0
            
            for task in tasks:
                tid = task['id']
                task_dir = run_dir / f'task{tid}'
                response_file = task_dir / 'response.txt'
                
                if not response_file.exists():
                    print(f"  Task {tid} ({task['name']}): NO RESPONSE FILE")
                    continue
                
                response = response_file.read_text()
                
                # Run tests
                passed, total, details = run_tests(response, task['hidden_tests'], raw_response=response)
                
                # Get DB score
                db_score = c.execute(f'SELECT score, max_score FROM {task_table} WHERE run_id=? AND task_id=?', (run_id, tid)).fetchone()
                db_passed = db_score[0] if db_score else -1
                db_total_score = db_score[1] if db_score else -1
                
                # Get summary score
                summary_file = run_dir / 'summary.json'
                summary_passed = -1
                if summary_file.exists():
                    with open(summary_file) as f:
                        summary = json.load(f)
                    for st in summary['tasks']:
                        if st['id'] == tid:
                            summary_passed = st['hidden_tests_passed']
                            break
                
                status = "✓" if (passed == db_passed and passed == summary_passed) else "✗"
                if passed != db_passed or passed != summary_passed:
                    print(f"  {status} Task {tid} ({task['name']:30s}): actual={passed}/{total}, DB={db_passed}/{db_total_score}, summary={summary_passed}")
                    for d in details:
                        print(f"      {d[-1]}: {d[0][:50]}")
                
                run_passed += passed
                run_total += total
            
            if run_passed != db_total:
                print(f"  ** RUN TOTAL MISMATCH: actual={run_passed}/{run_total}, DB={db_total}/{db_max}")
    
    db.close()

if __name__ == '__main__':
    model_key = sys.argv[1] if len(sys.argv) > 1 else None
    model_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if model_key and model_id:
        verify_model(model_key, model_id)
    else:
        # Get all models
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        models = c.execute('SELECT id, key, label FROM models ORDER BY id').fetchall()
        db.close()
        
        for mid, key, label in models:
            if key == 'ornith_1_0_35b_mtp':
                continue  # Skip partial
            print(f"\n\n{'#'*70}")
            print(f"# {label} (id={mid}, key={key})")
            print(f"{'#'*70}")
            verify_model(key, mid)
