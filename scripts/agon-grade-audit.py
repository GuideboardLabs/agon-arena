#!/usr/bin/env python3
"""Agon grading audit for LFM2.5-24B-A2B.

Purpose: decide whether LFM2.5's score is a capability signal or a harness artefact.
The specific worry is grading bias: the arena is Qwen-heavy, so a non-Qwen model can
lose points to harness assumptions (answer format, reasoning handling, token budget)
rather than to being worse.

Checks, in order of how much they can distort a "band":
  1. Hard failures       - timeouts at task_timeout_s, truncation at max_tokens, empty
                           responses. These zero a task the model may have solved.
  2. Token blowup        - generated tokens vs the sibling median. A reasoning model that
                           runs unbounded burns wall clock and starts hitting those
                           timeouts.
  3. Speed sanity        - measured tok_s vs the swept 25.8. A big shortfall means the
                           card was contended or experts spilled, which corrupts timing.
  4. Reasoning leak      - thinking_chars == 0 while content carries think text. If the
                           split fails, graders read the scratchpad.
  5. Event/task delta    - where LFM2.5 loses vs its siblings, and whether the losses sit
                           on knowledge/coding (card-predicted) or look like format bugs.
"""
import os
import sqlite3
import statistics
import sys

DB = "/home/sc/Documents/agon-arena/agon-bench.db"
ME = "lfm25_24b_a2b_q4"
SIBLINGS = ["qwen36_35b_q4_ncmoe40", "minicpm_v47_35b_a3b_q4",
            "qwen38_35b_a3b_distill", "gemma4_26b"]
TABLES = (("agent", "agent_runs", "agent_tasks"),
          ("code", "code_runs", "code_tasks"),
          ("reason", "reason_runs", "reason_tasks"))


def con():
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def model_id(c, key):
    r = c.execute("select id from models where key=?", (key,)).fetchone()
    return r[0] if r else None


def runs(c, mid, run_tab):
    return c.execute(f"select id,run_number,status,total_score,max_score,"
                     f"total_elapsed_s,avg_tok_s,total_generated_tokens "
                     f"from {run_tab} where model_id=? order by run_number",
                     (mid,)).fetchall()


def tasks(c, task_tab, rid):
    cols = [r[1] for r in c.execute(f"pragma table_info({task_tab})")]
    want = [k for k in ("task_id", "task_name", "difficulty", "score", "max_score",
                        "elapsed_s", "response_chars", "generated_tokens", "tok_s",
                        "thinking_chars", "response_chars_total", "status")
            if k in cols]
    q = f"select {','.join(want)} from {task_tab} where run_id=? order by task_id"
    return [dict(zip(want, row)) for row in c.execute(q, (rid,))]


def parse_server_log(paths=None):
    """Pull llama.cpp's own per-request timings out of the server stderr log.

    The runner discards these from the DB (generated_tokens/thinking_chars are NULL
    everywhere), and the log is the only record of how many tokens each request
    actually cost. Format:

      0.50.332.796 I slot print_timing: id  0 | task 0 | prompt eval time =  304.17 ms /  17 tokens ( ... , 55.89 tokens per second)
      0.50.332.801 I slot print_timing: id  0 | task 0 |        eval time = 3828.95 ms / 105 tokens ( ... , 27.16 tokens per second)
    """
    import re
    if paths is None:
        # ONLY the current log. server-stderr.log.1 is a ~1 GB rotated file holding
        # previous days' runs by OTHER models, and mixing it in silently attributes
        # their requests (including their truncations) to this model. That mistake
        # produced a false "hit the 8192 cap" reading once already.
        paths = ["/home/sc/Documents/agon-arena/server-stderr.log"]
    # Requests are paired prompt-line-then-eval-line, IN LINE ORDER, and never
    # deduplicated. Do NOT key them on (slot, task): llama.cpp resets its task
    # counter on every server start, so a restart makes the new server's request 0
    # collide with the old server's request 0 and overwrite it, hiding real requests
    # and undercounting tokens. Line order is chronological, which is what we want.
    out = []
    pending = None
    pat_prompt = re.compile(
        r"^([\d.]+) I slot print_timing: id\s+(\d+) \| task\s+(-?\d+) \| "
        r"prompt eval time =\s+([\d.]+) ms /\s+(\d+) tokens .*?,\s+([\d.]+) tokens per second")
    pat_eval = re.compile(
        r"^([\d.]+) I slot print_timing: id\s+(\d+) \| task\s+(-?\d+) \|\s+"
        r"eval time =\s+([\d.]+) ms /\s+(\d+) tokens .*?,\s+([\d.]+) tokens per second")
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, "r", errors="replace") as f:
            for line in f:
                m = pat_prompt.match(line)
                if m:
                    t, slot, task, ms, n, tps = m.groups()
                    # A new prompt line starts a fresh request. If the previous one
                    # never produced an eval line it is discarded rather than merged.
                    pending = {"t": t, "slot": slot, "task": task,
                               "prompt": int(n), "prompt_tps": float(tps)}
                    continue
                m = pat_eval.match(line)
                if m:
                    t, slot, task, ms, n, tps = m.groups()
                    rec = pending if pending is not None else {
                        "t": t, "slot": slot, "task": task,
                        "prompt": 0, "prompt_tps": 0.0}
                    rec["gen"] = int(n)
                    rec["decode_tps"] = float(tps)
                    out.append(rec)
                    pending = None
    return out


def main():
    c = con()
    me = model_id(c, ME)
    if me is None:
        sys.exit(f"{ME} not in the DB yet")

    print("=" * 78)
    print("1. HARD FAILURES (each one can zero a task the model actually solved)")
    print("=" * 78)
    total_tasks = 0
    for ev, run_tab, task_tab in TABLES:
        for rid, rn, st, ts, ms, el, tps, gt in runs(c, me, run_tab):
            for t in tasks(c, task_tab, rid):
                total_tasks += 1
                flags = []
                if t.get("status") not in (None, "completed"):
                    flags.append(f"status={t['status']}")
                if (t.get("elapsed_s") or 0) >= 1190:
                    flags.append(f"TIMEOUT-ish {t['elapsed_s']:.0f}s")
                if (t.get("generated_tokens") or 0) >= 8190:
                    flags.append(f"TRUNCATED {t['generated_tokens']}")
                if (t.get("response_chars") or 0) == 0:
                    flags.append("EMPTY response")
                if (t.get("max_score") or 0) and (t.get("score") or 0) == 0:
                    flags.append("ZERO score")
                if flags:
                    print(f"  {ev} run{rn} t{t['task_id']} [{t.get('difficulty')}] "
                          f"{t.get('score')}/{t.get('max_score')} :: " + "; ".join(flags))
    print(f"  ({total_tasks} task rows scanned)")

    print()
    print("=" * 78)
    print("2. TOKEN BLOWUP - from llama.cpp's own per-request timings")
    print("=" * 78)
    print("  The DB's generated_tokens and thinking_chars columns are NULL for this")
    print("  harness build, so the blowup has to be read out of the server log, which")
    print("  is the only place llama.cpp records per-request token counts.")
    timings = parse_server_log()
    if not timings:
        print("  no slot print_timing lines found in the server log")
    else:
        gent = [t["gen"] for t in timings if t["gen"]]
        # ratio of generated tokens to answer size, the reasoning overhead signature
        over = [t for t in timings if t["gen"] and t["gen"] > 1000]
        print(f"  requests logged        : {len(timings)}")
        print(f"  median generated tokens: {statistics.median(gent):.0f}" if gent else "")
        print(f"  requests over 1000 tok : {len(over)}")
        dec = [t["decode_tps"] for t in timings if t["decode_tps"]]
        if dec:
            print(f"  decode t/s  min/med/max: {min(dec):.1f} / "
                  f"{statistics.median(dec):.1f} / {max(dec):.1f}")
        print()
        print("  per-request (ts, prompt_tok, gen_tok, decode t/s):")
        for t in timings[-40:]:
            print(f"    {t['t']:>10}  p={t['prompt']:>6}  g={t['gen']:>6}  "
                  f"{t['decode_tps']:>6.2f} t/s")

    def sib_tokens(ev, run_tab, task_tab):
        out = []
        for key in SIBLINGS:
            sib = model_id(c, key)
            if sib is None:
                continue
            for rid, rn, *_ in runs(c, sib, run_tab):
                if rn == 1:
                    out += [t["generated_tokens"] for t in tasks(c, task_tab, rid)
                            if t.get("generated_tokens")]
        return out

    print()
    print("=" * 78)
    print("3. SPEED SANITY (registered sweep says 25.8 t/s decode)")
    print("=" * 78)
    for ev, run_tab, task_tab in TABLES:
        for rid, rn, st, ts, ms, el, tps, gt in runs(c, me, run_tab):
            print(f"  {ev:6s} run{rn} {str(st):10s} avg_tok_s={tps} "
                  f"elapsed={el or 0:.0f}s  gen={gt}")

    print()
    print("=" * 78)
    print("4. REASONING LEAK CHECK (thinking_chars == 0 but long response?)")
    print("=" * 78)
    leaks = 0
    for ev, run_tab, task_tab in TABLES:
        for rid, rn, *_ in runs(c, me, run_tab):
            for t in tasks(c, task_tab, rid):
                th = t.get("thinking_chars")
                rc = t.get("response_chars") or 0
                if th == 0 and rc > 3000:
                    leaks += 1
                    print(f"  SUSPECT {ev} run{rn} t{t['task_id']}: thinking=0 but "
                          f"response={rc} chars")
    if not leaks:
        print("  none: no task shows a blank thinking count with a huge response body")
    print("  (note: thinking_chars being NULL for every model means this harness build")
    print("   does not populate the column at all, which is itself worth knowing)")

    print()
    print("=" * 78)
    print("5. COMPOSITE + BAND")
    print("=" * 78)
    rows = c.execute("""
      select m.name, sum(x.total_score) s, sum(x.max_score) mx
      from models m join (
        select model_id,total_score,max_score from agent_runs
        union all select model_id,total_score,max_score from code_runs
        union all select model_id,total_score,max_score from reason_runs) x
        on x.model_id=m.id
      group by m.id having mx>0 order by 1.0*s/mx desc
    """).fetchall()
    for i, (n, s, mx) in enumerate(rows, 1):
        mark = "  <== LFM2.5" if n.startswith("LFM2.5-24B") else ""
        print(f"  {i:2d}. {n[:34]:36s} {s:6.1f}/{mx:6.1f} = {100*s/mx:5.1f}%{mark}")

    print()
    print("=" * 78)
    print("6. PER-TASK DELTA vs Qwen3.6-35B (run 1, where the points actually went)")
    print("=" * 78)
    qid = model_id(c, "qwen36_35b_q4_ncmoe40")
    for ev, run_tab, task_tab in TABLES:
        mrow = runs(c, me, run_tab)
        qrow = runs(c, qid, run_tab) if qid else []
        if not mrow or not qrow:
            continue
        mt = {t["task_id"]: t for t in tasks(c, task_tab, mrow[0][0])}
        qt = {t["task_id"]: t for t in tasks(c, task_tab, qrow[0][0])}
        print(f"  -- {ev}")
        for tid in sorted(set(mt) | set(qt)):
            a, b = mt.get(tid), qt.get(tid)
            sa = f"{a['score']}/{a['max_score']}" if a else "  -  "
            sb = f"{b['score']}/{b['max_score']}" if b else "  -  "
            nm = (a or b or {}).get("task_name", "")
            delta = ""
            if a and b and a.get("score") is not None and b.get("score") is not None:
                d = a["score"] - b["score"]
                delta = f"  delta {d:+.0f}"
            print(f"     t{tid} LFM {sa:6s} Qwen {sb:6s}{delta:12s} {nm}")

    c.close()


if __name__ == "__main__":
    main()
