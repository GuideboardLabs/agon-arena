#!/usr/bin/env python3
"""Shared assertion matching for the Agon benchmark harness.

Why this module exists
----------------------
The three event runners each grew their own copy of the assertion check, and all
of them were a bare substring test:

    actual == expected or (expected.startswith("CONTAINS:") and expected[9:] in actual)

That is exploitable in two distinct ways, both observed in this repo:

1. **Inverted-meaning matches (real bug, real lost points).** The File Indexer
   check prints exactly one of two strings:

       print('BROKEN' if 'note3' in output else 'NO_BROKEN')

   and the assertion was `CONTAINS:BROKEN`. *Both* branches contain the
   substring `BROKEN`, so the assertion could never fail: every File Indexer
   run banked 1/2 regardless of what the model did. That is 70 guaranteed points
   across the recorded code event, and it inflates each model's File Indexer
   score by half. `CONTAINS:BINARY` had the same shape (`NOT_BINARY` /
   `NO_BINARY` also contain `BINARY`).

2. **Negation blindness.** `CONTAINS:not` matched *cannot*, *notable*, *notice*,
   *nothing*. A response asserting the opposite of the expected claim
   ("Tickets cannot increase" for "Tickets would not increase") scored full
   credit. Same for numeric prefixes: `CONTAINS:150` matched `1500`,
   `CONTAINS:60` matched `600`.

Rule for the fix
----------------
Keep the declared semantics of `CONTAINS:` (it genuinely means "this substring
appears") but make it mean what a human reviewer would mean:

  - Case-insensitive, matching the reason-event behaviour.
  - Word/number-boundary aware, so `150` does not match `1500` and `not` does
    not match `notable`.
  - Negation-aware for the specific inverted-meaning case: an assertion for a
    token must not be satisfied by that token appearing inside an
    explicit negation of it (`NO_BROKEN`, `NOT_BINARY`).
  - `EXACT:` added for assertions that must match the whole trimmed value.
    This is what the indexer/binary checks should have used from the start.

Both the lenient and strict interpretations are exposed so a re-grade can be
reported two ways instead of silently rewriting history.
"""

import re

# Prefixes that invert the meaning of a following token.
_NEGATION_PREFIXES = ("no", "not", "non", "never")
_NEGATION_SEPARATORS = ("_", "-", " ", "", ":")


def _word_bounded(token: str, text: str) -> bool:
    """True if `token` appears in `text` without being glued to a longer token.

    Numeric and alphabetic tokens need different boundary rules, because the
    failure modes are not the same:

      - Numeric: `150` must not match `1500` or `2.55`, but `60` SHOULD match
        `60t` (the equation 60*t is a legitimate hit for "Shows equations").
        So a following/preceding DIGIT or decimal point disqualifies a match,
        while a following letter does not.
      - Alphabetic: `not` must not match `notable` (suffix) or `cannot`
        (prefix), and `dave` must not match `evidently`. So any adjacent
        letter disqualifies a match.
    """
    is_numeric = bool(token) and token[0].isdigit()
    esc = re.escape(token)
    # Boundary rules only make sense when the token EDGE is alphanumeric. A
    # token ending in punctuation (e.g. "9:") legitimately matches when followed
    # by anything -- "9:" is present in "9:00" -- so requiring a trailing word
    # boundary there would reject real matches.
    lead_alnum = token[0].isalnum()
    tail_alnum = token[-1].isalnum()
    pre = r"(?<![0-9A-Za-z.])" if lead_alnum else ""
    if not tail_alnum:
        post = ""
    elif is_numeric:
        # Reject only digit/decimal adjacency, so 60t stays a match for "60".
        post = r"(?![\d])"
    else:
        post = r"(?![0-9A-Za-z])"
    pattern = pre + esc + post
    return re.search(pattern, text, re.IGNORECASE) is not None


def _is_negated(token: str, text: str) -> bool:
    """True if every occurrence of `token` sits inside an explicit negation.

    Catches the inverted-meaning bug: the File Indexer check prints
    'NO_BROKEN' when it found NO broken links, and a naive substring test for
    'BROKEN' scores that as a pass.
    """
    token_l = token.lower()
    text_l = text.lower()
    occurrences = [m.start() for m in re.finditer(re.escape(token_l), text_l)]
    if not occurrences:
        return False
    for pos in occurrences:
        before = text_l[:pos]
        negated = False
        for prefix in _NEGATION_PREFIXES:
            for sep in _NEGATION_SEPARATORS:
                if before.endswith(prefix + sep):
                    negated = True
                    break
            if negated:
                break
        if not negated:
            return False  # at least one occurrence is a genuine, un-negated hit
    return True


def match_assertion(actual_raw, expected_raw, strict=True):
    """Evaluate one assertion.

    Returns (passed: bool, reason: str). `strict=False` reproduces the historical
    naive substring behaviour so historical scores can be compared against a
    corrected re-grade rather than silently replaced.
    """
    actual = (actual_raw or "").strip()
    expected = (expected_raw or "").strip()

    if expected.startswith("EXACT:"):
        want = expected[6:].strip()
        if strict:
            return actual.strip() == want, f"EXACT {want!r}" + ("" if actual.strip() == want else f" != {actual[:80]!r}")
        return want.lower() in actual.lower(), f"lenient EXACT-as-CONTAINS {want!r}"

    if expected.startswith("CONTAINS:"):
        token = expected[9:]
        if not strict:
            return token.lower() in actual.lower(), f"lenient substring {token!r}"

        if not token:
            return False, "empty CONTAINS token"
        al, tl = actual.lower(), token.lower()
        if tl not in al:
            return False, f"{token!r} not present"
        if _is_negated(token, actual):
            return False, f"{token!r} appears ONLY negated (inverted-meaning trap)"
        if not _word_bounded(token, actual):
            return False, f"{token!r} present but not word-bounded (prefix/suffix of a longer token)"
        return True, f"{token!r} present and bounded"

    # Plain equality assertion.
    if strict:
        return actual == expected, f"equality {expected!r}"
    return actual.lower() == expected.lower(), f"lenient equality {expected!r}"


def score_text_tests(response, tests, strict=True):
    """Grade a reason-event style text task. Returns (passed, total, details)."""
    if not tests:
        return 0, 0, []
    passed = 0
    details = []
    for item in tests:
        if item.get("type") != "text":
            continue
        label = item.get("label", "text test")
        expected = item.get("expected", "")
        ok, why = match_assertion(response, expected, strict=strict)
        if ok:
            passed += 1
            details.append((label, expected, "PASS"))
        else:
            details.append((label, expected, f"FAIL - {why}"))
    return passed, len(tests), details


if __name__ == "__main__":
    # Self-check: the two real bugs, as regression tests.
    cases = [
        # (actual, expected, should_pass_strict, note)
        ("BROKEN",   "CONTAINS:BROKEN", True,  "genuine detection must still pass"),
        ("NO_BROKEN","CONTAINS:BROKEN", False, "the inversion trap: NO broken links"),
        ("BINARY",   "CONTAINS:BINARY", True,  "genuine detection must still pass"),
        ("NOT_BINARY","CONTAINS:BINARY",False, "inversion trap"),
        ("NO_BINARY","CONTAINS:BINARY", False, "inversion trap"),
        ("This is notable", "CONTAINS:not", False, "'not' inside 'notable'"),
        ("Tickets cannot increase", "CONTAINS:not", False, "'not' inside 'cannot'"),
        ("Tickets would not increase", "CONTAINS:not", True, "genuine 'not'"),
        ("1500 km",  "CONTAINS:150", False, "numeric prefix must not match"),
        ("150 km",   "CONTAINS:150", True,  "genuine number"),
        ("600t",     "CONTAINS:60",  False, "numeric prefix must not match"),
        ("60t",      "CONTAINS:60",  True,  "genuine number"),
        ("dave",     "CONTAINS:dave", True,  "genuine"),
        ("Room B",   "CONTAINS:Room B", True,"multiword genuine"),
        ("BROKEN",   "EXACT:BROKEN", True,  "EXACT pass"),
        ("NO_BROKEN","EXACT:BROKEN", False, "EXACT rejects inversion"),
    ]
    fails = 0
    for actual, expected, want, note in cases:
        got, why = match_assertion(actual, expected, strict=True)
        ok = "ok  " if got == want else "FAIL"
        if got != want:
            fails += 1
        print(f"{ok} actual={actual!r:28} expected={expected:20} strict={got!s:5} want={want!s:5} {note}")
    print()
    print(f"{len(cases)-fails}/{len(cases)} self-checks passed")
    raise SystemExit(1 if fails else 0)
