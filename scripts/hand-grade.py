#!/usr/bin/env python3
"""
Hand-grade all model responses by running the actual test harness.
This is the ground truth — it runs the same tests the benchmark does.
"""
import re, tempfile, subprocess, sys, os, json, sqlite3
from pathlib import Path

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
DB_PATH = os.path.join(BASE_DIR, 'agon-bench.db')

# Import task definitions
import importlib.util
for name, file in [('agent', 'agent-event.py'), ('code', 'code-event.py'), ('reason', 'reason-event.py')]:
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS_DIR, file))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    globals()[f'{name.upper()}_TASKS'] = mod.TASKS

def extract_code(response):
    """Extract code from response, handling various model output formats."""
    # Try to find code blocks first
    blocks = re.findall(r'```(?:python)?\s*\n(.*?)```', response, re.DOTALL)
    if blocks:
        for block in reversed(blocks):
            stripped = block.strip()
            if stripped and ('def ' in stripped or 'class ' in stripped or 'import ' in stripped or 'if __name__' in stripped):
                return stripped
        return blocks[-1].strip()
    
    # No code blocks - check if the response IS code
    stripped = response.strip()
    if stripped.startswith('def ') or stripped.startswith('class ') or stripped.startswith('import '):
        return stripped
    
    # Check for thinking noise with code at the end
    lines = stripped.split('\n')
    code_lines = []
    in_code = False
    for line in lines:
        if line.startswith('def ') or line.startswith('class ') or line.startswith('import '):
            in_code = True
        if in_code:
            code_lines.append(line)
    
    if code_lines:
        return '\n'.join(code_lines)
    
    return ''

def run_tests(code, tests):
    """Run hidden tests, same as benchmark scripts."""
    if not tests or not code:
        return 0, len(tests) if tests else 0
    
    passed = 0
    for test_item in tests:
        if isinstance(test_item, dict) and test_item.get("type") == "script":
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code)
                    model_code_path = f.name
                test_script = test_item["setup"] + "\n\n" + test_item.get("check", "")
                test_script = test_script.replace("MODEL_CODE_PATH", repr(model_code_path))
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(test_script)
                    tmp_path = f.name
                result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=15)
                os.unlink(tmp_path)
                try: os.unlink(model_code_path)
                except: pass
                if result.returncode != 0:
                    continue
                actual = result.stdout.strip()
                expected = test_item["expected"]
                if actual == expected or (expected.startswith("CONTAINS:") and expected[9:] in actual):
                    passed += 1
            except:
                try:
                    if tmp_path: os.unlink(tmp_path)
                except: pass
                try:
                    if model_code_path: os.unlink(model_code_path)
                except: pass
        elif isinstance(test_item, dict) and test_item.get("type") == "static":
            check_name = test_item.get("check", "")
            weight = test_item.get("weight", 0.5)
            
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
            if check_fn and check_fn(code):
                passed += weight
        else:
            expr, expected = test_item
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                    f.write(code + "\n\nimport json\n")
                    f.write(f"result = {expr}\n")
                    f.write("print(repr(result))\n")
                    tmp_path = f.name
                result = subprocess.run([sys.executable, tmp_path], capture_output=True, text=True, timeout=10)
                os.unlink(tmp_path)
                if result.returncode != 0:
                    continue
                actual = result.stdout.strip()
                if actual == expected or eval(actual) == eval(expected):
                    passed += 1
            except:
                pass
    
    return passed

def grade_model(model_key, model_id):
    """Grade all runs for a model."""
    results_dir = Path(BASE_DIR) / 'results' / model_key
    
    scores = {}
    
    for event_name, tasks in [('agent', AGENT_TASKS), ('code', CODE_TASKS), ('reason', REASON_TASKS)]:
        event_dir = results_dir / event_name
        if not event_dir.exists():
            continue
        
        for run_num in [1, 2, 3]:
            run_dir = event_dir / f'run{run_num}'
            if not run_dir.exists():
                continue
            
            run_passed = 0
            run_max = 0
            
            for task in tasks:
                tid = task['id']
                task_dir = run_dir / f'task{tid}'
                response_file = task_dir / 'response.txt'
                
                if not response_file.exists():
                    continue
                
                response = response_file.read_text()
                code = extract_code(response)
                
                if not code:
                    continue
                
                passed = run_tests(code, task['hidden_tests'])
                run_passed += passed
                run_max += sum(
                    t.get('weight', 1) if isinstance(t, dict) and t.get('type') == 'static' else 1 
                    for t in task['hidden_tests']
                )
            
            scores[(event_name, run_num)] = (run_passed, run_max)
    
    return scores

if __name__ == '__main__':
    model_key = sys.argv[1] if len(sys.argv) > 1 else None
    model_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if model_key and model_id:
        scores = grade_model(model_key, model_id)
        print(f"\n=== {model_key} ===")
        for (event, run), (passed, max_s) in sorted(scores.items()):
            print(f"  {event} run {run}: {passed}/{max_s}")
    else:
        db = sqlite3.connect(DB_PATH)
        c = db.cursor()
        models = c.execute('SELECT id, key, label FROM models ORDER BY id').fetchall()
        db.close()
        
        for mid, key, label in models:
            if key in ('ornith_1_0_35b', 'qwythos_9b_v2', 'holo_3_1_9b_coder', 'qwopus_3_5_9b_coder_mtp', 'ornith_1_0_35b_mtp'):
                continue
            scores = grade_model(key, mid)
            if scores:
                print(f"\n=== {label} ===")
                for (event, run), (passed, max_s) in sorted(scores.items()):
                    print(f"  {event} run {run}: {passed}/{max_s}")
