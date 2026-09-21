#!/usr/bin/env python3
"""Audit Agon event-script checks for assertions that cannot fail.

Why this exists
---------------
Two unfailable checks shipped and ran green for months:

  1. File Indexer. The check script printed exactly one of two constants --
     `print('BROKEN' if 'note3' in output else 'NO_BROKEN')` -- and the assertion
     was `CONTAINS:BROKEN`. BOTH branches contain BROKEN, so the check passed
     whether or not the model found the broken link. 69 runs banked the point.

  2. Task Runner. The setup computed `missing` (the files the model failed to
     emit), then the check ran a bare `print('OK')` with `expected: OK`. The
     answer was calculated and discarded. 66 runs banked the point.

Neither was visible in any log, because a check that always passes looks exactly
like a check that passes.

What this tool can prove
------------------------
Only the decidable shape: when every possible output of the check is
statically known (all print arguments are constants or constant ternaries) AND
the assertion accepts all of them, the check cannot fail. That is exactly
defect 1, and it is proven, not guessed.

What it cannot prove
--------------------
The general question "can this check fail?" is undecidable: a check may fail via
a non-zero exit code (uncaught exception) rather than via stdout, which is how
`from taskrunner.models import Task` legitimately fails. So the unused-variable
pass (#2) is reported as REVIEW, not DEFECT. A clean run here does not prove the
scripts are sound; it means no *statically provable* unfailable check remains.

Usage:
    python3 audit-checks.py             # human report; exit 1 if any defect
    python3 audit-checks.py --json      # machine-readable
    python3 audit-checks.py --strict    # exit 1 on REVIEW findings too
"""

import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ["code-event.py", "agent-event.py", "reason-event.py",
           "grade-all.py", "rerun-tests.py"]

CHECK_RE = re.compile(
    r'"label":\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'"setup":\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'"check":\s*"((?:[^"\\]|\\.)*)"\s*,\s*'
    r'"expected":\s*"((?:[^"\\]|\\.)*)"',
    re.DOTALL,
)


def unescape(s):
    return s.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")


def possible_outputs(check_body):
    """Statically enumerate the constants a check's print() calls can emit.

    Returns (outputs, complete). `complete` is False when the check prints
    something computed (so the output set is not known statically).
    """
    body = check_body.strip()
    if not body:
        return set(), True
    try:
        tree = ast.parse(body)
    except SyntaxError:
        return set(), False

    outs = set()
    complete = True
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
            if not node.args:
                outs.add("")
                continue
            arg = node.args[0]
            if isinstance(arg, ast.Constant):
                outs.add(str(arg.value))
            elif isinstance(arg, ast.IfExp):
                for branch in (arg.body, arg.orelse):
                    if isinstance(branch, ast.Constant):
                        outs.add(str(branch.value))
                    else:
                        complete = False
            else:
                complete = False
    return outs, complete


def assertion_accepts_all(expected, outputs):
    """Does `expected` accept every output in `outputs`? (imports the matcher)"""
    sys.path.insert(0, HERE)
    try:
        from assertions import match_assertion
    except ImportError:
        return None
    if not outputs:
        return None
    return all(match_assertion(o, expected)[0] for o in outputs)


def find_ignored_derived_values(setup, check):
    """REVIEW heuristic (defect 2's shape): setup computes a submission-derived
    value that the check's print never reads."""
    assigned = set(re.findall(r"^(\w+)\s*=\s*", setup, re.MULTILINE))
    if not assigned:
        return []
    prints = re.findall(r"print\((.*?)\)", check, re.DOTALL)
    printed = " ".join(prints)
    ignored = []
    for name in sorted(assigned):
        # only interesting when the value derives from the filesystem/run
        if name in ("tmpdir", "script_path", "files", "sys", "os", "shutil"):
            continue
        decl = re.search(rf"^{name}\s*=\s*(.*)$", setup, re.MULTILINE)
        if not decl:
            continue
        rhs = decl.group(1)
        derived = any(t in rhs for t in (".exists()", "tmpdir", "output", "result",
                                         "subprocess", "len(", "in "))
        if derived and name not in printed:
            ignored.append(name)
    return ignored


def audit():
    defects, reviews, audited = [], [], 0
    for name in SCRIPTS:
        path = os.path.join(HERE, name)
        try:
            src = open(path, errors="replace").read()
        except OSError:
            continue
        for m in CHECK_RE.finditer(src):
            label, setup, check, expected = (unescape(g) for g in m.groups())
            audited += 1

            outs, complete = possible_outputs(check)
            accepts = assertion_accepts_all(expected, outs) if complete else None
            if complete and accepts:
                defects.append({
                    "file": name, "label": label, "expected": expected,
                    "outputs": sorted(outs),
                    "reason": (f"every possible output {sorted(outs)} satisfies "
                               f"{expected!r}; the check cannot fail"),
                })
                continue

            ignored = find_ignored_derived_values(setup, check)
            if ignored:
                reviews.append({
                    "file": name, "label": label, "expected": expected,
                    "ignored": ignored,
                    "reason": ("setup computes submission-derived "
                               f"{ignored} but the check never reads it"),
                })

    return audited, defects, reviews


def main():
    as_json = "--json" in sys.argv
    strict = "--strict" in sys.argv
    audited, defects, reviews = audit()

    if as_json:
        print(json.dumps({"audited": audited, "defects": defects,
                          "reviews": reviews}, indent=2))
        return 1 if defects or (strict and reviews) else 0

    print(f"audited {audited} checks across {len(SCRIPTS)} scripts")
    if defects:
        print(f"\nDEFECTS ({len(defects)}) - proven unable to fail:\n")
        for d in defects:
            print(f"  [{d['file']}] {d['label']}")
            print(f"      expected : {d['expected']}")
            print(f"      outputs  : {d['outputs']}")
            print(f"      {d['reason']}")
            print()
    else:
        print("\nDEFECTS: none. No statically provable unfailable check remains.")

    if reviews:
        print(f"\nREVIEW ({len(reviews)}) - possible defect, not statically provable:")
        print("  (these may fail via non-zero exit code, which stdout cannot show)\n")
        for r in reviews:
            print(f"  [{r['file']}] {r['label']}: {r['reason']}")
        print()

    print("NOTE: a clean DEFECTS section does not prove the scripts are sound.")
    print("It means no check's output is provably constant-and-accepted.")
    return 1 if defects or (strict and reviews) else 0


if __name__ == "__main__":
    sys.exit(main())
