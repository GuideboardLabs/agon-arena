#!/usr/bin/env python3
"""Small controlled A/B: does adjusting reasoning rescue the code tasks that failed?

Motivation: both hard failures in LFM2.5's code event are budget-shaped. At ctx 16384
the model reasons first and then writes code, and reasoning + answer SHARE the window.
code t7 generated exactly 16112 tokens (= 16384 - prompt) in all three runs and scored
0/4 each time, while reasoning-suppressed Qwen3.6 scored 4/2/3. Reason t1 did the same
thing at the reason event's 8192.

This runs ONLY the two failed code tasks (5 and 7) at a fixed seed, once per reasoning
configuration, with no --db-path / --run-id so the official results are untouched. It
answers one question: is a full re-run worth it, and with which recipe?

  control      - the recipe the official runs used (unrestricted thinking)
  budget2048   - --reasoning-budget 2048, so thinking is capped and the answer gets the rest
  reasoningoff - --reasoning off, matching the bar's suppressed configuration

Usage: agon-code-reasoning-ab.py <config> [port]
"""
import json
import os
import subprocess
import sys
import time

REPO = "/home/sc/Documents/agon-arena"
SCRATCH = os.path.expanduser("~/.hermes/cache/scratch/code-ab")
BIN = "/home/sc/llama-mcpv47/build-vulkan/bin/llama-server"
GGUF = "/mnt/blue/LLMbackups/LFM2.5-24B-A2B-Q4_K_M.gguf"
SEED = "42"           # matches official code run 1, held constant across configs
TASKS = "5,7"         # the two that failed in the official runs

BASE = ("-ngl 999 -fa on -ncmoe 21 -c 16384 --threads 6 --threads-batch 6 "
        "--cpu-mask 0x3f --prio 2 --jinja --temp 0.7 --min-p 0.05 --parallel 1")

CONFIGS = {
    "control": BASE,
    "budget2048": BASE + " --reasoning-budget 2048",
    "reasoningoff": BASE + " --reasoning off --reasoning-format none",
    # Diagnostic only: does more context alone fix it? ncmoe 25 to make room for the
    # larger KV cache, so this one changes two variables and is labelled as such.
    "bigctx": ("-ngl 999 -fa on -ncmoe 25 -c 32768 --threads 6 --threads-batch 6 "
               "--cpu-mask 0x3f --prio 2 --jinja --temp 0.7 --min-p 0.05 --parallel 1"),
}


def log(m):
    print(f"  [{time.strftime('%H:%M:%S')}] {m}", flush=True)


def vram():
    try:
        with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
            v = int(f.read().strip()) / 1073741824
        with open("/sys/class/drm/card1/device/mem_info_gtt_used") as f:
            g = int(f.read().strip()) / 1073741824
        return v, g
    except Exception:
        return -1, -1


def start_server(config, port):
    unit = f"agon-ab-{config}"
    args = CONFIGS[config].split()
    cmd = ["systemd-run", "--user", "--scope", "-u", unit, "-p", "MemoryMax=22G",
           BIN, "--model", GGUF, "--port", str(port), "--host", "127.0.0.1",
           "--no-warmup"] + args
    log(f"launching server ({unit}) port {port}")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    url = f"http://127.0.0.1:{port}/health"
    for i in range(240):
        time.sleep(1)
        r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                            "--max-time", "3", url], capture_output=True, text=True)
        if r.stdout.strip() == "200":
            log(f"server ready after {i + 1}s")
            return unit
    raise RuntimeError("server never became ready")


def stop_server(unit):
    subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True, timeout=120)
    # the scope can take a while to release the GPU; wait for VRAM to actually drop
    for _ in range(60):
        v, _ = vram()
        if v < 1.0:
            break
        time.sleep(2)
    log(f"server stopped, vram {vram()[0]:.2f} GiB")


def run_tasks(config, port):
    out = os.path.join(SCRATCH, config)
    os.makedirs(out, exist_ok=True)
    cmd = [sys.executable, f"{REPO}/scripts/code-event.py",
           "--model-url", f"http://127.0.0.1:{port}",
           "--model", "lfm25_24b_a2b_q4",
           "--output", out, "--run", "0", "--seed", SEED,
           "--tasks", TASKS, "--task-timeout", "1200"]
    log(f"running code tasks {TASKS} at seed {SEED} -> {out}")
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=5400)
    os.makedirs(SCRATCH, exist_ok=True)
    with open(os.path.join(SCRATCH, f"{config}.stdout.log"), "w") as f:
        f.write(p.stdout)
    return out, p.stdout


def parse_scores(stdout):
    """Pull per-task scores out of the event script's own output."""
    res = {}
    cur = None
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Task "):
            try:
                cur = int(line.split()[1].rstrip(":"))
            except Exception:
                cur = None
        elif "Hidden tests:" in line and cur is not None:
            frac = line.split("Hidden tests:")[1].strip().split()[0]
            passed, total = frac.split("/")
            res[cur] = (int(passed), int(total))
    return res


def main():
    config = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8171
    if config not in CONFIGS:
        print(f"unknown config {config}; pick one of {list(CONFIGS)}")
        sys.exit(2)
    os.makedirs(SCRATCH, exist_ok=True)

    unit = start_server(config, port)
    try:
        out, stdout = run_tasks(config, port)
        scores = parse_scores(stdout)
    finally:
        stop_server(unit)

    v, g = vram()
    rec = {"config": config, "seed": SEED, "tasks": TASKS,
           "scores": {str(k): list(v) for k, v in scores.items()},
           "total": [sum(v[0] for v in scores.values()),
                     sum(v[1] for v in scores.values())]}
    path = os.path.join(SCRATCH, "results.json")
    allr = {}
    if os.path.exists(path):
        allr = json.load(open(path))
    allr[config] = rec
    json.dump(allr, open(path, "w"), indent=2)

    print()
    print(f"  === {config} ===")
    for t in sorted(scores):
        print(f"    code t{t}: {scores[t][0]}/{scores[t][1]}")
    print(f"    TOTAL: {rec['total'][0]}/{rec['total'][1]}")
    print(f"    results appended to {path}")


if __name__ == "__main__":
    main()
