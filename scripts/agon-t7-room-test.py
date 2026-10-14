#!/usr/bin/env python3
"""Test ONE thing properly: does giving task 7 enough context let it finish?

The reasoning A/B that preceded this was void. Its stop used the bare unit name
`agon-ab-control`, which systemctl resolves to `inactive` even while
`agon-ab-control.scope` is running, so the first server never died, held the port, and
every later config silently scored against it. Proof: every response, including the
"-c 32768" variant, was cut mid-sentence at ~16.1k tokens (~67,000 B). A 32768 window
allows ~136,000 B.

So this script tests ONE configuration, on ONE task, with a hard pre-flight assertion:
after the server reports ready, the PID actually listening on the port MUST have the
config's marker in its command line. If it does not, the run aborts instead of producing
a number that belongs to a different server.

Also note: the event scripts accept --seed and never send it, so every completion is an
uncontrolled sample. One sample cannot settle anything, hence --reps.

Usage: agon-t7-room-test.py [--port 8172] [--reps 2]
"""
import argparse
import json
import os
import subprocess
import sys
import time

REPO = "/home/sc/Documents/agon-arena"
SCRATCH = os.path.expanduser("~/.hermes/cache/scratch/t7-room")
BIN = "/home/sc/llama-mcpv47/build-vulkan/bin/llama-server"
GGUF = "/mnt/blue/LLMbackups/LFM2.5-24B-A2B-Q4_K_M.gguf"

# t7's derivation alone filled a 16384 window (~16.1k tokens) before any code appeared,
# and a regex engine needs maybe 2-4k tokens on top, so 32768 is the smallest window with
# a chance of fitting. ncmoe 25 (not 21) frees VRAM for the larger KV cache.
ARGS = ("-ngl 999 -fa on -ncmoe 25 -c 32768 --threads 6 --threads-batch 6 "
        "--cpu-mask 0x3f --prio 2 --jinja --temp 0.7 --min-p 0.05 --parallel 1")
MARKER = "-c 32768"          # must appear in the serving process's own cmdline
EXPECTED_CTX = 32768


def log(m):
    print(f"  [{time.strftime('%H:%M:%S')}] {m}", flush=True)


def vram():
    try:
        v = int(open("/sys/class/drm/card1/device/mem_info_vram_used").read()) / 1073741824
        g = int(open("/sys/class/drm/card1/device/mem_info_gtt_used").read()) / 1073741824
        return v, g
    except Exception:
        return -1.0, -1.0


def listening_pids(port):
    """Find PIDs serving this port by reading each process's own command line."""
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
    unit = "agon-t7-room"
    cmd = ["systemd-run", "--user", "--scope", "-u", unit, "-p", "MemoryMax=22G",
           BIN, "--model", GGUF, "--port", str(port), "--host", "127.0.0.1",
           "--no-warmup"] + ARGS.split()
    log(f"launching server on port {port}")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)

    url = f"http://127.0.0.1:{port}/health"
    for i in range(300):
        time.sleep(1)
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "3", url], capture_output=True, text=True)
        if r.stdout.strip() == "200":
            break
    else:
        raise RuntimeError("server never became ready")

    # ---- PRE-FLIGHT: the server that answers must be the one we asked for ----
    pids = listening_pids(port)
    if not pids:
        raise RuntimeError(f"port {port} answers but no llama-server owns it")
    if len(pids) > 1:
        raise RuntimeError(f"{len(pids)} llama-servers claim port {port}")
    pid, cmdline = pids[0]
    if MARKER not in cmdline:
        raise RuntimeError(
            f"WRONG SERVER on {port}: marker {MARKER!r} absent from pid {pid} cmdline")
    log(f"PRE-FLIGHT OK: pid {pid} owns {port} and carries {MARKER!r}")
    log(f"  argv: {cmdline[:150]}")
    log(f"  vram {vram()[0]:.2f} GiB  gtt {vram()[1]:.2f} GiB")
    return unit, pid


def stop_server(unit, pid):
    # FULL name: the bare name does not resolve for a transient scope and the stop
    # silently does nothing, which is exactly how the previous run was broken.
    subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"],
                   capture_output=True, timeout=180)
    for _ in range(90):
        if not os.path.exists(f"/proc/{pid}"):
            break
        time.sleep(2)
    else:
        log(f"WARN: pid {pid} survived its stop, killing by PID")
        subprocess.run(["kill", "-9", str(pid)], capture_output=True)
        time.sleep(5)
    for _ in range(60):
        if vram()[0] < 1.0:
            break
        time.sleep(2)
    log(f"server down (pid {pid} gone={not os.path.exists(f'/proc/{pid}')}), "
        f"vram {vram()[0]:.2f} GiB")


def run_t7(port, rep):
    out = os.path.join(SCRATCH, f"rep{rep}")
    os.makedirs(out, exist_ok=True)
    cmd = [sys.executable, f"{REPO}/scripts/code-event.py",
           "--model-url", f"http://127.0.0.1:{port}", "--model", "lfm25_24b_a2b_q4",
           "--output", out, "--run", "0", "--tasks", "7", "--task-timeout", "1200"]
    log(f"rep{rep}: running code task 7 only -> {out}")
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=5400)
    open(os.path.join(out, "stdout.log"), "w").write(p.stdout)
    return out, p.stdout


def read_result(out, stdout):
    score = None
    elapsed = None
    for line in stdout.splitlines():
        s = line.strip()
        if "Hidden tests:" in s:
            frac = s.split("Hidden tests:")[1].strip().split()[0]
            score = frac
        if "Response received in" in s:
            elapsed = float(s.split("Response received in")[1].split("s")[0].strip())
    f = os.path.join(out, "task7", "response.txt")
    size = os.path.getsize(f) if os.path.exists(f) else 0
    fences = 0
    ends_cut = None
    if size:
        txt = open(f, errors="replace").read()
        fences = txt.count("```")
        ends_cut = not txt.rstrip().endswith(("```", '"', ")", "."))
    return score, elapsed, size, fences, ends_cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8172)
    ap.add_argument("--reps", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)

    # nothing else may be holding the port before we start
    for p in (a.port,):
        pre = listening_pids(p)
        if pre:
            print(f"  ABORT: port {p} already held by pid {pre[0][0]}: {pre[0][1][:120]}")
            sys.exit(3)

    results = []
    for rep in range(1, a.reps + 1):
        unit, pid = start_and_verify(a.port)
        try:
            out, stdout = run_t7(a.port, rep)
            score, elapsed, size, fences, cut = read_result(out, stdout)
        finally:
            stop_server(unit, pid)
        # est tokens: a 16384 window cuts at ~16.1k tok / ~67k B. If this rep stops at the
        # same place, the bigger window never served.
        est_tok = size / 4.2 if size else 0
        rec = {"rep": rep, "score": score, "elapsed_s": elapsed, "bytes": size,
               "code_fences": fences, "ends_cut": cut, "est_tokens": round(est_tok)}
        results.append(rec)
        print()
        print(f"  === rep {rep}: t7 @ ctx {EXPECTED_CTX} ===")
        print(f"    score      : {score}")
        print(f"    elapsed    : {elapsed}s")
        print(f"    response   : {size} B (~{est_tok:.0f} tok), code fences={fences}")
        print(f"    ends mid-sentence: {cut}")
        print(f"    (a 16384 window cuts at ~67,000 B / ~16.1k tok; 32768 allows ~136,000 B)")
        print()

    json.dump(results, open(os.path.join(SCRATCH, "results.json"), "w"), indent=2)
    ok = [r for r in results if r["score"] and r["score"].split("/")[0] != "0"]
    print(f"  SUMMARY: {len(ok)}/{len(results)} reps scored above zero; "
          f"max response {max(r['bytes'] for r in results)} B")


if __name__ == "__main__":
    main()
