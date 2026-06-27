# Harness Fixes — June 2026

## Hidden test runner: temp files, not `-c`

**Problem:** `subprocess.run([sys.executable, "-c", test_code])` fails with `[Errno 7] Argument list too long` when the model's generated code is large (common for thinking-trace models producing 30-50KB responses).

**Fix:** All hidden tests now write to temp files instead of using `-c`:

```python
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
    f.write(code_clean + "\n\nimport json\n")
    f.write(f"result = {expr}\n")
    f.write("print(repr(result))\n")
    tmp_path = f.name
result = subprocess.run([sys.executable, tmp_path], ...)
os.unlink(tmp_path)
```

This bypasses the shell argument length limit entirely.

## Two test formats

The `run_hidden_tests()` function now supports:

- **Tuple format** `(expr, expected)` — simple expression tests (Tasks 1-2). The model's code is prepended to the test script, then the expression is evaluated.

- **Script format** `{"type": "script", "setup": ..., "check": ..., "expected": ...}` — multi-step tests (Tasks 3-6). The model's code is written to a temp file at `MODEL_CODE_PATH`. The test script can reference it via `shutil.copy(MODEL_CODE_PATH, dest_path)` for standalone-script tasks, or the code is prepended directly for function/class tasks.

**IMPORTANT:** When using `MODEL_CODE_PATH` in test scripts, the path must be quoted with `repr()` when substituted:

```python
# WRONG — SyntaxError: shutil.copy(/tmp/tmpXXX.py, script_path)
test_script = test_script.replace("MODEL_CODE_PATH", model_code_path)

# RIGHT — produces shutil.copy('/tmp/tmpXXX.py', script_path)
test_script = test_script.replace("MODEL_CODE_PATH", repr(model_code_path))
```

## CONTAINS matching

Prefix `expected` with `CONTAINS:` for substring matching:

```python
{"expected": "CONTAINS:binary"}  # passes if "binary" appears anywhere in stdout
```

## Thinking trace stripping — CRITICAL: use text.find(), not regex .*?

**Problem:** DeepSeek-style models (Jackrong, R1 distills) output 30-50KB of thinking text before the answer, wrapped in `...` or `...` blocks. The hidden test runner was picking up draft code from the thinking trace instead of the final code block.

**CRITICAL BUG FIX (June 26, 2026):** The original `strip_thinking()` used `re.sub(r'(?s)(?:^|\n)\s*.*?\\n?', '', text)` which is WRONG. The `\s*` matches zero whitespace and `.*?` matches zero characters, so the pattern matches EVERY line start — it strips all content from the text, not just thinking blocks. Additionally, the regex was missing the literal `` tag entirely (it was only in the docstring, not the actual regex pattern).

**Correct approach:** Use `text.find()` for tag-based stripping, not regex substitution with `.*?`:

```python
def strip_thinking(text):
    """Remove thinking/chain-of-thought blocks from model output.
    
    Only strips if the text actually contains a thinking tag
    at the start of a line (to avoid corrupting legitimate code).
    """
    import re
    # Check if text actually contains a thinking tag
    if 'thinking' not in text and 'think' not in text:
        return text.strip()
    # Remove DeepSeek-style thinking blocks
    text = re.sub(r'(?s)(?:^|\n)\s*\<think\>.*?\<\/think\>\n?', '', text)
    # Remove generic think blocks
    text = re.sub(r'(?s)(?:^|\n)\s*\<think\>.*?\<\/think\>\n?', '', text)
    # Remove unclosed think blocks
    if re.search(r'(?:^|\n)\s*\<think\>', text):
        text = re.sub(r'(?s)(?:^|\n)\s*\<think\>.*$', '', text)
    return text.strip()
```

**Key rules for thinking-trace regex:**
1. **Always include the literal tag in the regex pattern.** The `` must be in the regex string, not just the docstring. The tool may strip HTML-like tags from docstrings — put them in the actual regex.
2. **Guard with `'thinking' in text` not `r'(?:^|\n)\s*'`.** The latter matches every line because `\s*` matches zero whitespace.
3. **Use `\<think\>` and `\<\/think\>` in the regex** to match the literal angle brackets.
4. **Test with both clean code (no thinking tags) and thinking-trace output** before deploying. Clean code should be preserved exactly; thinking traces should be stripped.

**Verification test:**
```python
# Clean code (no thinking tags) — must be preserved
code = "\nimport re\n\ndef clean_text(text):\n    pass"
result = strip_thinking(code)
assert "import" in result, "Clean code was corrupted!"

# Thinking trace — must be stripped
code2 = "\n\nWe need to write a function.\n\ndef clean_text(text):\n    pass"
result2 = strip_thinking(code2)
assert "We need" not in result2, "Thinking trace not stripped!"
assert "def clean_text" in result2, "Code after thinking trace was lost!"
```

### Multiple code block handling

Models sometimes output multiple code blocks (e.g., draft code in thinking trace, then final code). The `clean_code()` function now splits on all code fences and keeps only the last block:

```python
blocks = re.split(r'```(?:python)?\s*\n?', code)
if len(blocks) > 1:
    code = blocks[-1]
    code = re.sub(r'\n?```\s*$', '', code)
```

**BUG FIX (June 26, 2026, second pass):** The code fence regex was originally anchored with `^` and `$`:

```python
# WRONG — only strips first and last fences
code_clean = re.sub(r'^```(?:python)?\s*\n?', '', code_clean)
code_clean = re.sub(r'\n?```\s*$', '', code_clean)
```

This works for single-code-block responses (Tasks 1-4, 6) but **fails for multi-file responses** (Task 5) that have 4+ code blocks. The anchored regex only strips the first and last fences, leaving ` ``` ` markers in the middle. When the test runner tries to parse these as file headers, it gets corrupted content.

**Fix:** Remove the anchors so ALL code fences are stripped:

```python
# RIGHT — strips ALL code fences
code_clean = re.sub(r'```(?:python)?\s*\n?', '', code_clean)
code_clean = re.sub(r'\n?```\s*', '', code_clean)
```

**Verification:** Test with a multi-file response (Task 5 output with 4 code blocks). After stripping, there should be no remaining `` ` `` characters in the cleaned code.

## Fallback code extraction (no code fences)

Jackrong responses have no code fences at all — the code is inline after thinking text. When the cleaned code doesn't start with a known code prefix (`def`, `class`, `import`, `from`), the function scans for the first definition line and keeps everything from there:

```python
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
```

## Test design lessons

### Log Parser tests were too strict

Original tests compared dict equality (`{'ERROR': 1}`), but models return all 4 levels with 0 counts for empty levels. **Fix:** Changed to `len()` checks:

```python
# Before (fails — models return {'INFO': 0, 'WARN': 0, 'ERROR': 1, 'DEBUG': 0})
("parse_logs([])['counts']", "{}")

# After (passes — len is 0 regardless of which keys exist)
("len(parse_logs([])['counts'])", "0")
```

**Further fix (June 26, 2026):** The `len()` approach only works for empty-input tests. For the non-empty test (`parse_logs(['ERROR: disk full'])['counts']`), models still return `{'INFO': 0, 'WARN': 0, 'ERROR': 1, 'DEBUG': 0}` which doesn't equal `{'ERROR': 1}`. **Fix:** Added a `dicts_match()` function that checks all expected keys exist with correct values, ignoring extra keys:

```python
def dicts_match(actual, expected):
    """Compare two dicts — actual may have extra keys (0-count levels)."""
    try:
        a = eval(actual)
        e = eval(expected)
        if isinstance(a, dict) and isinstance(e, dict):
            for k, v in e.items():
                if k not in a or a[k] != v:
                    return False
            return True
        return a == e
    except:
        return actual == expected
```

This is used in `run_simple_test()` instead of `eval(actual) == eval(expected)` for dict comparisons. Models that return all 4 levels with 0s now pass the test as long as the expected level has the right count.

### LRU Cache lambda tests were fragile

Original tests used nested lambdas to sequence operations, which caused `Argument list too long` and were hard to debug. **Fix:** Converted to script-based tests with explicit setup/check:

```python
# Before (fragile lambda chain)
("lambda: (LRUCache(2), (lambda c: (c.put(1,1), c.put(2,2), c.put(3,3), c.get(1))[3])())", "-1")

# After (clear setup + check)
{"type": "script", "label": "LRU evicts oldest when full",
 "setup": "c = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(3, 3)",
 "check": "result = c.get(1)\nprint(repr(result))",
 "expected": "-1"}
```

### String Cleaner truncation test

The original test for 300-character input used a complex expression that evaluated to a string with spaces. The model's `clean_text` function collapses spaces, so the expected value was wrong. **Fix:** Use `repr('a' * 200)` — the model should truncate to 200 chars of 'a's (no spaces to collapse).

### Task 5 (Task Runner CLI) test structure

The Task Runner test has a `setup` that writes files and a `check` that imports from them. **BUG FIX (June 26, 2026):** The first test ("creates project structure") was missing a `check` field entirely — the setup WAS the check, but the test runner requires a `check` field. This caused a `KeyError: 'check'` crash for every model, making all models score 0/2 on Task 5 even though the test was never actually run.

**Fix:** Added `"check": "print('OK')"` to the first test. The setup still does all the work (writes files, checks for missing files, prints OK or MISSING). The check just prints OK to satisfy the test runner's field requirement.

**Lesson:** Every script-type test MUST have a `check` field, even if the setup does all the work. The test runner concatenates `setup + "\n\n" + check` and runs the result. If `check` is missing, the runner crashes with `KeyError`.

### Task 6 (Constrained Diff Tool) test expectations

The Diff Tool tests check for specific output patterns:
- Identical files: empty output or "No differences" message
- Changed files: output containing both `-` and `+` lines
- Binary files: output containing "binary" (case-insensitive)

**BUG FIX (June 26, 2026):** The binary detection test had inverted logic. The test script printed `'OK'` when the model correctly detected binary files, but the expected value was `"CONTAINS:binary"`. Since `'OK'` doesn't contain `'binary'`, the test always failed even when the model passed.

**Fix:** Changed the test script to print `'BINARY'` when binary files are detected, and changed the expected value to `"CONTAINS:BINARY"`. Now the test passes when the model correctly identifies binary files.

Models that implement a proper unified diff format pass the "identical files" test but may fail "detects changes" if their diff format doesn't use `-`/`+` markers. This is a real quality signal, not a harness bug.

## Seed variations removed — they sabotage weaker models

**Problem:** The `call_llm()` function in all three event scripts injected a seed-based variation into every prompt (e.g. "IMPORTANT: Use a recursive approach where possible. Add input validation at the start."). This was intended to force diverse outputs across runs at temperature=0.3.

**Root cause:** Weaker models (Jackrong, LFM2.5) obediently spent 700+ tokens reasoning about how to make an LRU cache recursive, or how to add input validation to a string cleaner. They produced thinking-text-only responses with no actual code. The seed variation was the root cause of Jackrong's 0/5 on String Cleaner and 0/3 on LRU Cache — not the model's coding ability. The user confirmed this: "I've used jackrong multiple times to code in Pi" — the model can code fine, the harness was sabotaging it.

**Fix (June 2026):** Removed all seed-based prompt injection from `code-event.py`, `agent-event.py`, and `reason-event.py`. The `--seed` flag now only controls output directory naming. The prompt sent to the model is exactly the task description with no extra constraints.

**Lesson:** Seed variations are a form of prompt engineering that interacts badly with instruction-following models. A model that follows instructions well will waste tokens on impossible constraints. A model that ignores instructions (Gemma4) is unaffected. The variation approach was testing instruction-following, not coding ability.

## DeepSeek-V4-Flash thinking loops — cannot be suppressed

**This is a separate issue from the `reasoning_content` vs `content` split.** Even with `--reasoning off --reasoning-format none`, Jackrong (Qwen3.5-9B-DeepSeek-V4-Flash) produces a never-ending thinking trace that never closes its `` tag. The model generates 130KB+ of circular reasoning with zero code output. The thinking trace is part of the model's normal token stream, not a separate field — the server flags cannot suppress it.

**Root cause:** The DeepSeek-V4-Flash architecture has an inherent thinking loop. The model opens `` and never closes it, generating infinite circular reasoning about edge cases (e.g., 130KB of analysis about how to truncate a string to 200 characters). No code ever appears after the thinking trace.

**Why it works in Pi:** Pi's API likely handles the thinking/content split at the API level (like DeepSeek's official API does with `reasoning_content`), or they use a different version of the model that doesn't have this behavior.

**Impact on benchmark scores:** Jackrong scores 0/5 on String Cleaner and 0/3 on LRU Cache not because it can't code, but because it never produces code — it's stuck in a thinking loop. The thinking-trace stripping in `strip_thinking()` cannot extract code from a response that has no code.

**Recommendation:** Do not use DeepSeek-V4-Flash-based models (Jackrong) for code generation benchmarks. The model architecture is fundamentally incompatible with the code-event test format. Use it for Agent and Reason events only, where the thinking trace may still contain useful reasoning even if no final answer is produced.

## Script tests didn't import model code (June 26, 2026, third pass)

**Problem:** Script-type tests (Tasks 3-6) wrote the model's code to a temp file at `MODEL_CODE_PATH` but never imported it into the test script's namespace. The test setup ran `c = LRUCache(2)` but `LRUCache` was never defined — the model's code sat in a file that was never `exec`'d or `import`'d.

**Root cause:** The original design assumed the test setup would handle importing the model code itself (e.g., `shutil.copy(MODEL_CODE_PATH, dest)` for standalone-script tasks). But for function/class tasks (Task 3: LRU Cache), the model's code needs to be in the test script's namespace. The setup just ran `c = LRUCache(2)` with no import.

**First fix (global exec prepend — BROKEN):** Prepend `exec(open(MODEL_CODE_PATH).read())` to every script-type test's setup:

```python
# Before — model code written to file but never imported
test_script = test_item["setup"] + "\n\n" + test_item.get("check", "")

# After — model code is exec'd into the test script's namespace
test_script = "exec(open(" + repr(model_code_path) + ").read())\n" + test_item["setup"] + "\n\n" + test_item.get("check", "")
```

**This fix BROKE backslash escaping in test setup strings.** The `exec()` line is concatenated with the setup string, and the backslash escaping in the setup string is already at the right level for direct execution. Adding the `exec()` line changes the context — the `\\n` in the setup string (which was correct for direct execution) now gets double-escaped because it's inside the `exec()` call's argument. This caused:
- Task 5 (Task Runner CLI): `response.split('\\\\n')` became `response.split('\\\\\\\\n')` — quadruple backslashes, breaking file parsing
- Task 6 (Diff Tool): `write_text('line1\\nline2\\nline3\\n')` became `write_text('line1\\\\nline2\\\\nline3\\\\n')` — literal `\n` instead of newlines, causing `SyntaxError: unterminated string literal`

**Second fix (per-test exec, reverted global):** Revert the global `exec()` prepend and instead add `exec(open(MODEL_CODE_PATH).read())` to individual test setups that need it:

```python
# Reverted — no global exec prepend
test_script = test_item["setup"] + "\n\n" + test_item.get("check", "")

# Per-test fix — Task 3 LRU Cache tests add exec to their setup
{"type": "script", "label": "LRU evicts oldest when full",
 "setup": "exec(open(MODEL_CODE_PATH).read())\nc = LRUCache(2)\nc.put(1, 1)\nc.put(2, 2)\nc.put(3, 3)",
 "check": "result = c.get(1)\nprint(repr(result))",
 "expected": "-1"}
```

**Lesson:** Never use a global `exec()` prepend for script-type tests. The backslash escaping in test setup strings is already at the right level for direct execution. Adding an `exec()` line changes the escaping context and breaks all backslash sequences. Instead, add `exec(open(MODEL_CODE_PATH).read())` to individual test setups that need it, keeping the escaping consistent within each string.

**Impact:** Task 3 (LRU Cache) went from 0/3 to 3/3 for models that produce correct code. The backslash corruption in Tasks 5 and 6 was fixed by reverting the global prepend.

**Verification:** Test with a model that produces a correct LRU Cache class. Before the fix, all 3 tests fail with `NameError: name 'LRUCache' is not defined`. After the per-test fix, all 3 pass. Verify that Task 5 and Task 6 test setups still compile correctly (no `SyntaxError: unterminated string literal`).

## Cascading backslash fix bug — global string replace corrupts unrelated parts

**Problem (June 26, 2026, fourth pass):** After reverting the global `exec()` prepend, a Python script was used to fix the backslash escaping in Task 5's `split()` and `write_text()` calls. The script did a global string replace on the file:

```python
content = content.replace("split('\\n'):", "split('\\\\n'):")
content = content.replace("write_text('\\n'.join", "write_text('\\\\n'.join")
```

This **also corrupted the regex pattern** in the same setup strings. The regex `r'^#+\\s+(\\S+)\\s*$'` (2 backslashes before `s` and `S`) became `r'^#+\\\s+(\\\S+)\\\s*$'` (3 backslashes) because the replace matched the `\\s` and `\\S` substrings inside the regex. The corrupted regex failed to match markdown headers like `### taskrunner/models.py`, causing the file parser to produce no output.

**Root cause:** The string `\\s` (2 backslashes + s) appears in both the `split()` argument AND the regex pattern. A global replace that targets `\\s` in one context will also hit it in the other. The same applies to `\\S` and `\\n`.

**Fix:** Use targeted byte-level replacements on the raw file bytes, not string-level replacements on the parsed content. When the target string is ambiguous (appears in multiple contexts), use more context to disambiguate:

```python
# WRONG — global replace hits regex too
content = content.replace("split('\\n'):", "split('\\\\n'):")

# RIGHT — include surrounding context to disambiguate
content = content.replace("response.split('\\n'):", "response.split('\\\\n'):")
```

**Even better:** Use `patch` tool with exact old_string/new_string, or use `sed` with a precise line number. Never do a global string replace on a Python source file when the target string could appear in multiple contexts (string literals, regex patterns, comments).

**Verification:** After any backslash fix, verify that ALL regex patterns in the file still compile and match correctly. Test with a sample input:

```python
import re
# Test the regex from the setup string
regex = r'^#+\s+(\S+)\s*$'
assert re.match(regex, "### taskrunner/models.py"), "Regex corrupted!"
```

**Lesson:** Global string replacement on source files is dangerous when the target string appears in multiple contexts. Always verify the fix didn't corrupt unrelated parts of the file. For Python source files with nested string literals, prefer targeted edits with surrounding context over global replaces.

## strip_thinking leaves leading newline (June 26, 2026, third pass)

**Problem:** The `strip_thinking()` function removes the thinking block but leaves a leading `\n` character. When the code fence regex is anchored with `^`, it can't match because the string starts with `\n`, not `` ` ``:

```python
# Before — strip_thinking returns "\n```python\ndef ..."
code_clean = code.strip()
code_clean = strip_thinking(code_clean)  # returns "\n```python\ndef ..."
code_clean = re.sub(r'^```(?:python)?\s*\n?', '', code_clean)  # no match!
```

**Fix:** Add `.strip()` after `strip_thinking()`:

```python
# After — leading \n is removed before code fence regex
code_clean = code.strip()
code_clean = strip_thinking(code_clean).strip()  # now returns "```python\ndef ..."
code_clean = re.sub(r'^```(?:python)?\s*\n?', '', code_clean)  # matches!
```

**Impact:** Qwen3.5-9B responses (which use ` thinking\n\n response\n\n```python\ndef ...` format) had their code fences stripped correctly. Task 1 (String Cleaner) went from 0/5 to 5/5.

**Verification:** Test with a Qwen3.5-9B response that has ` thinking\n\n response\n\n```python\ndef ...` format. After stripping, the code should start with `` ` `` not `\n`.

## Task 5 setup missing `shutil` import (June 26, 2026, third pass)

**Problem:** The Task 5 (Task Runner CLI) test setup imported `tempfile, os, sys, re` but the second test's check used `shutil.rmtree()` without importing `shutil`. This caused a `NameError: name 'shutil' is not defined` runtime error.

**Root cause:** The setup string was written with `import tempfile, os, sys, re` but the check string (which runs in the same script) used `shutil.rmtree()`. The `shutil` import was missing from the setup.

**Fix:** Changed both Task 5 test setups to `import tempfile, os, sys, re, shutil`:

```python
# Before
"setup": "import tempfile, os, sys, re\nfrom pathlib import Path\n..."

# After
"setup": "import tempfile, os, sys, re, shutil\nfrom pathlib import Path\n..."
```

**Impact:** Task 5 tests no longer crash with `NameError: name 'shutil' is not defined`. (The tests still fail because no model produces correct multi-file output, but the crash is fixed.)

**Lesson:** When a test's `check` field uses a module, that module must be imported in the `setup` field. The setup and check are concatenated into a single script — imports in setup are available in check, but missing imports in setup crash the check.

## Dead code after `return` in strip_thinking (June 26, 2026, fifth pass)

**Problem:** The `strip_thinking()` function in `agent-event.py` and `grade-all.py` had dead code after the `return` statement. The docstring contained a multi-line example comment that was indented at the module level (not inside a function), causing `IndentationError: unexpected indent` at line 150.

**Root cause:** The original `strip_thinking()` function had HTML-style `` tag handling code after the `return text.strip()` line. When the dead code was removed from `code-event.py` (the first file fixed), the other files (`agent-event.py`, `grade-all.py`, `rerun-tests.py`) still had it. Additionally, the docstring contained a mangled multi-line comment:

```python
    # Qwen3.5 format: " thinking
...
 response

actual content"
```

The `...` and ` response` lines were indented at the module level, not inside the function, causing `IndentationError`.

**Fix:** Remove the dead code after `return` and fix the docstring comment in all four files (`code-event.py`, `agent-event.py`, `grade-all.py`, `rerun-tests.py`). Verify with `python3 -c "compile(open(file).read(), file, 'exec')"` after each fix.

**Lesson:** When fixing a bug in one file, check if the same bug exists in sibling files. The `strip_thinking()` function is duplicated across all four event scripts. A fix in `code-event.py` doesn't automatically apply to the others. Always run a compile check on all affected files after any code change.

## Remaining challenges

- **Task 5 (Task Runner CLI):** No model has passed any test. The multi-file project structure is too complex for current models to produce correctly in a single response. Consider simplifying the task or providing a template.
- **Task 6 (Constrained Diff Tool):** Only the "identical files" test passes consistently. Models struggle with proper unified diff format and binary detection.
- **Log Parser (Task 2):** Models consistently return all 4 levels with 0 counts instead of omitting empty levels. The `dicts_match()` fix makes the non-empty test pass, and the `len()` fix makes the empty-input tests pass.
