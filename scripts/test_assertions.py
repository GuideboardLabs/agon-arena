#!/usr/bin/env python3
"""Regression tests for the Agon assertion matcher.

These exist because the harness shipped an assertion that could not fail:

    print('BROKEN' if 'note3' in output else 'NO_BROKEN')   # the check script
    "expected": "CONTAINS:BROKEN"                           # the assertion

Both branches of that print contain the substring "BROKEN", so the check passed
whether or not the model's indexer found the broken link. 70 recorded File
Indexer runs each banked 1/2 for free. The recorded rate was 79.3%; the
actually-earned rate was 29.3%.

Run: python3 scripts/test_assertions.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assertions import match_assertion, score_text_tests  # noqa: E402

CASES = [
    # (actual, expected, want_strict, note)
    # -- the inverted-meaning bug (this is the one that cost real points)
    ("BROKEN",            "CONTAINS:BROKEN",  True,  "genuine broken-link detection"),
    ("NO_BROKEN",         "CONTAINS:BROKEN",  False, "found NO broken links must not pass"),
    ("BROKEN",            "EXACT:BROKEN",     True,  "EXACT accepts the real value"),
    ("NO_BROKEN",         "EXACT:BROKEN",     False, "EXACT rejects the inversion"),
    ("BINARY",            "EXACT:BINARY",     True,  "genuine binary detection"),
    ("NOT_BINARY",        "EXACT:BINARY",     False, "negated detection must not pass"),
    ("NO_BINARY",         "EXACT:BINARY",     False, "negated detection must not pass"),
    # -- negation blindness
    ("This is notable",            "CONTAINS:not", False, "'not' inside 'notable'"),
    ("The tickets cannot increase","CONTAINS:not", False, "'not' inside 'cannot'"),
    ("There is no notice of this", "CONTAINS:not", False, "'not' inside 'notice'"),
    ("Tickets would not increase", "CONTAINS:not", True,  "a genuine 'not'"),
    # -- numeric prefixes
    ("1500 km",  "CONTAINS:150", False, "150 must not match inside 1500"),
    ("150 km",   "CONTAINS:150", True,  "genuine 150"),
    ("2.55",     "CONTAINS:2.5", False, "2.5 must not match inside 2.55"),
    ("2.5 hours","CONTAINS:2.5", True,  "genuine 2.5"),
    # -- numbers followed by a symbol must still match (60t is the equation)
    ("600t",     "CONTAINS:60",  False, "600 must not match 60"),
    ("60t",      "CONTAINS:60",  True,  "60t is the legitimate equation"),
    # -- punctuation-terminated tokens
    ("Starts at 9:00",  "CONTAINS:9:", True, "'9:' must match inside '9:00'"),
    ("Starts at 10:00", "CONTAINS:9:", False, "no 9: present"),
    # -- word tokens
    ("The owner is dave", "CONTAINS:dave", True,  "genuine"),
    ("Nobody, evidently", "CONTAINS:dave", False, "'dave' inside 'evidently'"),
    ("Sprint Planning in Room B", "CONTAINS:Room B", True, "multiword genuine"),
    # -- equality
    ("OK", "OK", True, "plain equality"),
    ("FAIL", "OK", False, "plain inequality"),
]


def main():
    fails = []
    for actual, expected, want, note in CASES:
        got, why = match_assertion(actual, expected, strict=True)
        if got != want:
            fails.append((actual, expected, got, want, note, why))
        status = "ok  " if got == want else "FAIL"
        print(f"{status} actual={actual!r:32} expected={expected:20} strict={got!s:5} want={want!s:5} {note}")

    # Lenient mode must still reproduce the historical behaviour, so a re-grade
    # can report both numbers instead of silently rewriting history.
    lenient_checks = [
        ("NO_BROKEN", "CONTAINS:BROKEN", True,  "lenient keeps the old behaviour"),
        ("1500",      "CONTAINS:150",    True,  "lenient keeps the old behaviour"),
        ("notable",   "CONTAINS:not",    True,  "lenient keeps the old behaviour"),
    ]
    print()
    for actual, expected, want, note in lenient_checks:
        got, _ = match_assertion(actual, expected, strict=False)
        if got != want:
            fails.append((actual, expected, got, want, note, "lenient"))
        status = "ok  " if got == want else "FAIL"
        print(f"{status} LENIENT actual={actual!r:20} expected={expected:20} got={got!s:5} want={want!s:5} {note}")

    # Reason-event style scoring path
    tests = [
        {"type": "text", "label": "fish owner", "check": "dave", "expected": "CONTAINS:dave"},
        {"type": "text", "label": "not increase", "check": "not", "expected": "CONTAINS:not"},
    ]
    p, t, _ = score_text_tests("The owner is Dave. Tickets would not increase.", tests)
    if (p, t) != (2, 2):
        fails.append(("score_text_tests good", "2/2", f"{p}/{t}", "2/2", "scoring", ""))
    print(f"\n{'ok  ' if (p,t)==(2,2) else 'FAIL'} score_text_tests(genuine) = {p}/{t}")

    p2, t2, _ = score_text_tests("Nobody knows. This is notable.", tests)
    if (p2, t2) != (0, 2):
        fails.append(("score_text_tests bad", "0/2", f"{p2}/{t2}", "0/2", "scoring", ""))
    print(f"{'ok  ' if (p2,t2)==(0,2) else 'FAIL'} score_text_tests(negated/dodged) = {p2}/{t2}")

    total = len(CASES) + len(lenient_checks) + 2
    print()
    if fails:
        print(f"{len(fails)} FAILURES:")
        for f in fails:
            print("   ", f)
        return 1
    print(f"all {total} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
