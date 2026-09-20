fix(harness): assertion matcher could not fail on File Indexer; add boundaries and negation awareness

## The bug

Three event runners each had their own copy of the assertion check, all of them
a bare substring test:

```python
if actual == expected or (expected.startswith("CONTAINS:") and expected[9:] in actual):
```

The File Indexer task's check script prints **exactly one of two strings**:

```python
print('BROKEN' if 'note3' in output else 'NO_BROKEN')
```

and the assertion was `"expected": "CONTAINS:BROKEN"`.

**Both branches contain the substring `BROKEN`.** The assertion could not fail.
Every File Indexer run banked 1/2 regardless of whether the model's indexer
found the broken link. `CONTAINS:BINARY` had the identical shape, since
`NOT_BINARY` and `NO_BINARY` also contain `BINARY`.

Measured effect on the recorded database (70 runs):

| | recorded | actually earned |
|---|---|---|
| File Indexer | 111/140 (79.3%) | 41/140 (29.3%) |
| code event aggregate | 971/1742 (55.7%) | 901/1742 (51.7%) |

70 free points, 4.0 percentage points of aggregate code score. Per-model File
Indexer scores were inflated by half of that task's weight.

## Second, latent bug

`CONTAINS:` was negation- and boundary-blind in both directions. Demonstrated
false credits:

- `CONTAINS:not` matches *cannot*, *notable*, *notice* — a response asserting
  the **opposite** of the expected claim scored full credit
  (`"Tickets cannot increase"` for "Tickets would not increase").
- `CONTAINS:150` matches `1500`; `CONTAINS:60` matches `600`.

Re-grading the stored reason-event responses (7 model directories, 137 checks)
with the corrected matcher shows **zero corrections there** — the reason tasks
happened to never trigger it. The code event is where the damage is. Fixing
this is about making the harness trustworthy, not about rewriting existing
reason scores.

## The fix

New `scripts/assertions.py`, used by all three runners. `CONTAINS:` keeps its
declared meaning ("this substring appears") but now means what a human reviewer
would mean:

- case-insensitive (matching the reason-event behaviour)
- boundary-aware, with different rules for numeric and alphabetic tokens:
  `150` must not match `1500`, but `60` **must** match `60t` (the equation
  60·t is a legitimate hit for "Shows equations")
- tokens ending in punctuation still match (`9:` matches `9:00`)
- negation-aware: a token appearing only inside an explicit negation
  (`NO_BROKEN`, `NOT_BINARY`) does not satisfy the assertion
- new `EXACT:` prefix for assertions that must match the whole trimmed value,
  which is what the indexer/binary checks should have used from the start

The indexer and binary assertions are promoted to `EXACT:` in all 5 sites
(`code-event.py`, `grade-all.py`, `rerun-tests.py`).

`STRICT_ASSERTIONS` defaults on. Set `AGON_LENIENT_ASSERTIONS=1` to reproduce the
historical behaviour, so a re-grade can report both numbers rather than silently
replacing published scores.

## Tests

`scripts/test_assertions.py` — 29 checks, no dependencies, exits non-zero on
failure. Covers the inversion trap, negation blindness, numeric prefixes, the
`60t` case that must still pass, punctuation-terminated tokens, and both strict
and lenient modes. No CI exists in this repo yet, so this needs to be run
manually; adding a workflow is a reasonable follow-up.

```
$ python3 scripts/test_assertions.py
all 29 checks passed
```

## Re-grade tooling

`scripts/regrade-strict.py <model_dir>` re-grades stored `sprint-results/`
responses under both matchers and reports the correction, including each false
credit the old matcher granted.

```
$ python3 scripts/regrade-strict.py unsloth_iq1s
  TOTAL  lenient 7/18  (39%)   strict 7/18  (39%)
  correction: -0 checks (0% of the task set)
```

## Open question for the maintainer

The published leaderboard in `README.md` was produced with the faulty matcher.
Correcting it means either re-running the code event or publishing corrected
File Indexer numbers with a note. I have not touched published scores here. If
the intent is to keep historical comparability, the cleanest path is to re-run
the code event on the corrected harness so the ranking is measured on a harness
that can actually fail a task.

## Related

`CONTAINS:9:` for "Standup before 10:00" remains a weak proxy — it passes on any
mention of a 9:xx time anywhere in the response, including purely hypothetical
ones. On the current stored data every response does genuinely place Standup
before 10:00, so it is producing no false credits today, but the assertion does
not actually verify the claim. Worth replacing with a schedule parse.
