#!/usr/bin/env python3
"""Win-back re-run: redo the task-runs that were CUT, with enough room to finish.

Only the truncated failures are candidates. Measured from the official run:
  code  t7 x3   3,594 / 66,476 / 67,551 chars, 0-1 fences, cut   (lost 12)
  reason t1 x3  31,545 / 32,371 / 32,205 chars, 0 fences, cut    (lost 3)
Everything else failed with a COMPLETE answer (code t5 8 fences, agent t8 2,879-4,135
chars, reason t4 3,390-3,939 chars) so more context cannot recover it.

The artefact, proven separately: at ctx 16384 the think block never closes, so llama.cpp
cannot split it and the raw truncated stream is recorded as the answer. At ctx 32768 the
same task produced a complete 5 KB answer and scored 2/4 and 4/4.

Two settings change:
  - server `-c 32768` (from 16384 agent/code, 8192 reason)
  - reason event `--max-tokens 32768` (its default of 8192 caps it regardless of context)

Runs OUTSIDE the database: no --db-path is passed, so the official 171/198 is untouched.

Usage: agon-winback-rerun.py [--port 8174]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = os.environ.get("AGON_HOME", str(Path(__file__).resolve().parent.parent))
SCRATCH = os.environ.get("WINBACK_SCRATCH", os.path.join(REPO, "winback"))
BIN = os.environ.get("LLAMA_SERVER", "llama-server")
MODELS_DIR = os.environ.get("AGON_MODELS_DIR", os.path.expanduser("~/models"))
GGUF = os.path.join(MODELS_DIR, "LFM2.5-24B-A2B-Q4_K_M.gguf")
CTX = 32768
ARGS = ("-ngl 999 -fa on -ncmoe 25 -c 32768 --threads 6 --threads-batch 6 "
        "--cpu-mask 0x3f --prio 2 --jinja --temp 0.7 --min-p 0.05 --parallel 1")
MARKER = "-c 32768"

# official scores for the same task-runs, for the delta
OFFICIAL = {("code", 7, 1): "0/4", ("code", 7, 2): "0/4", ("code", 7, 3): "0/4",
            ("reason", 1, 1): "1/2", ("reason", 1, 2): "1/2", ("reason", 1, 3): "1/2"}

JOBS = [("code", 7, r) for r in (1, 2, 3)] + [("reason", 1, r) for r in (1, 2, 3)]


def log(m):
    print(f"  [{time.strftime('%H:%M:%S')}] {m}", flush=True)


def vram():
    try:
        return (int(open("/sys/class/drm/card1/device/mem_info_vram_used").read()) / 1073741824,
                int(open("/sys/class/drm/card1/device/mem_info_gtt_used").read()) / 1073741824)
    except Exception:
        return -1.0, -1.0


def listening_pids(port):
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            cmd = open(f"/proc/{p}/cmdline", "rb").read().replace(b"\0", b" ").decode()
        except Exception:
            continue
        if "llama-server" in cmd and f"--port {port} " in cmd + " ":
            out.append((int(p), cmd))
    return out


def start_and_verify(port):
    unit = "agon-winback"
    cmd = ["systemd-run", "--user", "--scope", "-u", unit, "-p", "MemoryMax=22G",
           BIN, "--model", GGUF, "--port", str(port), "--host", "127.0.0.1",
           "--no-warmup"] + ARGS.split()
    log(f"launching server on port {port} (ctx {CTX})")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    for _ in range(300):
        time.sleep(1)
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "3", f"http://127.0.0.1:{port}/health"],
                           capture_output=True, text=True)
        if r.stdout.strip() == "200":
            break
    else:
        raise RuntimeError("server never became ready")
    pids = listening_pids(port)
    if len(pids) != 1:
        raise RuntimeError(f"expected 1 llama-server on {port}, found {len(pids)}")
    pid, cmdline = pids[0]
    if MARKER not in cmdline:
        raise RuntimeError(f"WRONG SERVER on {port}: {MARKER!r} absent from pid {pid}")
    log(f"PRE-FLIGHT OK: pid {pid} carries {MARKER!r}; vram {vram()[0]:.2f} GiB")
    return unit, pid


def stop_server(unit, pid):
    subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"],
                   capture_output=True, timeout=180)
    for _ in range(60):
        if not os.path.exists(f"/proc/{pid}"):
            break
        time.sleep(2)
    else:
        subprocess.run(["kill", "-9", str(pid)], capture_output=True)
        time.sleep(5)
    for _ in range(60):
        if vram()[0] < 1.0:
            break
        time.sleep(2)
    log(f"server down; vram {vram()[0]:.2f} GiB")


def run_job(port, event, task, rep):
    out = os.path.join(SCRATCH, f"{event}-t{task}-r{rep}")
    os.makedirs(out, exist_ok=True)
    ev = f"{event}-event.py"
    # reason's default cap is 8192; raise it or the context increase cannot help it
    cap = 32768
    cmd = [sys.executable, f"{REPO}/scripts/{ev}",
           "--model-url", f"http://127.0.0.1:{port}", "--model", "lfm25_24b_a2b_q4",
           "--output", out, "--run", str(rep), "--tasks", str(task),
           "--task-timeout", "1800", "--max-tokens", str(cap)]
    log(f"{event} t{task} r{rep}: running (max_tokens={cap})")
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=3600)
    open(os.path.join(out, "stdout.log"), "w").write(p.stdout)
    # stderr must be kept: a child that dies in its model-server wait prints nothing to
    # stdout, and losing stderr makes the failure undiagnosable.
    open(os.path.join(out, "stderr.log"), "w").write(p.stderr or "")
    el = time.time() - t0
    if p.returncode != 0:
        log(f"{event} t{task} r{rep}: child exited {p.returncode} in {el:.1f}s; "
            f"stderr -> {os.path.join(out, 'stderr.log')}")
        log(f"    stderr tail: {(p.stderr or '').strip()[-300:]}")
    score = None
    for line in p.stdout.splitlines():
        if "Hidden tests:" in line:
            score = line.split("Hidden tests:")[1].strip().split()[0]
    f = os.path.join(out, f"task{task}", "response.txt")
    size = os.path.getsize(f) if os.path.exists(f) else 0
    fences = 0
    cut = None
    if size:
        t = open(f, errors="replace").read()
        fences = t.count("```")
        # "." matters: reason answers end on "Dave owns the fish." and were being
        # reported as cut when they were complete.
        cut = not t.rstrip().endswith(("```", '"', ")", "}", ".", "!", "?"))
    log(f"{event} t{task} r{rep}: score={score}  {el/60:.1f} min  {size} B  fences={fences}  cut={cut}")
    return {"event": event, "task": task, "rep": rep, "score": score,
            "official": OFFICIAL.get((event, task, rep)), "min": round(el / 60, 1),
            "bytes": size, "fences": fences, "cut": cut}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8174)
    a = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    if listening_pids(a.port):
        print(f"  ABORT: port {a.port} already held"); sys.exit(3)

    unit, pid = start_and_verify(a.port)
    results = []
    # idempotent: a job that already produced a score is not repeated. Lets a re-run after
    # a transient child failure redo only the failed job instead of all six.
    done = {}
    rj = os.path.join(SCRATCH, "results.json")
    if os.path.exists(rj):
        try:
            for r in json.load(open(rj)):
                if r.get("score"):
                    done[(r["event"], r["task"], r["rep"])] = r
        except Exception:
            pass
    if done:
        log(f"already scored, skipping: {sorted(f'{k[0]} t{k[1]} r{k[2]}' for k in done)}")
    try:
        for event, task, rep in JOBS:
            if (event, task, rep) in done:
                results.append(done[(event, task, rep)])
                continue
            results.append(run_job(a.port, event, task, rep))
    finally:
        stop_server(unit, pid)

    json.dump(results, open(os.path.join(SCRATCH, "results.json"), "w"), indent=2)
    print()
    print("  === WIN-BACK RESULT ===")
    print(f"  {'task-run':22s} {'official':>9s} {'now':>6s}  {'delta':>6s}  min   bytes  cut")
    gained = 0
    possible = 0
    for r in results:
        off = r["official"] or "?"
        d = ""
        if off and off != "?" and r["score"]:
            on, om = off.split("/"); sn, sm = r["score"].split("/")
            delta = int(sn) - int(on)
            gained += delta
            possible += int(om) - int(on)
            d = f"{delta:+d}"
        print(f"  {r['event'].capitalize()+' t'+str(r['task'])+' r'+str(r['rep']):22s} "
              f"{off:>9s} {str(r['score']):>6s}  {d:>6s}  {r['min']:>5} {r['bytes']:>6}  {r['cut']}")
    print()
    print(f"  points won back: {gained} (of {possible} that were recoverable on these runs)")
    print(f"  composite if this holds: {171+gained}/198 = {(171+gained)/198*100:.1f}%")


if __name__ == "__main__":
    main()
