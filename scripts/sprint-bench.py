#!/usr/bin/env python3
"""
Agon Sprint — a fast, focused capability comparison for GGUF quantizations.

Serves each quant on the SAME llama.cpp Vulkan fork (same GPU, same flags) and
runs a discriminating subset of Agon tasks across code/reason/agent. Reports
score + measured tok/s per quant. Purpose: apples-to-apples "how smart is this
quant" comparison WITHOUT a full 3x3x3 Agon run (which would take hours per model
at 6-24 tok/s).

Subset chosen for discrimination power (all exact-output / deterministic):
  CODE   : 1 String Cleaner, 2 Log Parser, 3 LRU Cache
  REASON : 1 Logical Deduction, 2 Math Word Problem, 3 Constraint Satisfaction
  AGENT  : 1 Tool Calling, 2 Orchestration
Total: 8 tasks, one run each, seed 42.

Usage:
  python3 sprint-bench.py [--port 8139] [--no-serve]
"""
import argparse, json, os, subprocess, sys, time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path(os.path.expanduser("~/Documents/agon-arena/sprint-results/medium-26"))

# (quant_key, label, gguf, size_gb)
QUANTS = [
    ("unsloth_iq1s", "Unsloth UD-IQ1_S", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq1s/Qwen3.8-27B-UD-IQ1_S.gguf", 5.77),
    ("unsloth_iq2s", "Unsloth UD-IQ2_S", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf", 7.80),
    ("ours_2bit",   "Ours RDNA1-K (2-bit)", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf", 7.79),
    ("ours_3bit",   "Ours Q3-DOWN-XS", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf", 7.91),
    ("abliterated_3bit", "SuperQwen abliterated Q3-DOWN-XS", "/mnt/blue/superqwen-abliterated/SuperQwen3.8-27B-abliterated-Q3-DOWN-XS.gguf", 8.29),
]

EVENT_SCRIPTS = {
    "code": SCRIPTS_DIR / "code-event.py",
    "reason": SCRIPTS_DIR / "reason-event.py",
    "agent": SCRIPTS_DIR / "agent-event.py",
}

# task subset per event
TASK_FILTERS = {
    "code": [1, 2, 3],
    "reason": [1, 2, 3],
    "agent": [1, 2],
}

# bound generation but allow room for medium-reasoning + answer
MAX_TOKENS = {"code": 12000, "reason": 12000, "agent": 12000}

SERVER_ARGS = [
    "-c", "16384", "-np", "1", "-ngl", "999",
    "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
    "--jinja", "-t", "6",
]


def serve(port, gguf):
    """Start llama-server, return Popen. Caller must kill."""
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1"] + SERVER_ARGS
    proc = subprocess.Popen(cmd, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # wait for readiness
    import httpx
    for _ in range(90):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
    proc.kill()
    raise RuntimeError(f"server failed to start for {gguf}")


def run_event(event, port, output_dir):
    script = EVENT_SCRIPTS[event]
    tasks = ",".join(str(t) for t in TASK_FILTERS[event])
    cmd = [
        sys.executable, str(script),
        "--model-url", f"http://127.0.0.1:{port}",
        "--model", "sprint",
        "--output", str(output_dir),
        "--run", "1", "--seed", "42",
        "--tasks", tasks,
        "--task-timeout", "900",
        "--max-tokens", str(MAX_TOKENS[event]),
    ]
    subprocess.run(cmd, timeout=3600)
    summary_path = output_dir / "summary.json"
    if not summary_path.exists():
        return 0, 0, {}
    s = json.loads(summary_path.read_text())
    score = sum(t.get("hidden_tests_passed", 0) for t in s.get("tasks", []))
    total = sum(t.get("hidden_tests_total", 0) for t in s.get("tasks", []))
    return score, total, s


def measure_tok_s(port, prompt="Write a short paragraph about the history of computing.", n=60):
    import httpx
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
        "model": "sprint", "messages": [{"role": "user", "content": prompt}],
        "max_tokens": n, "temperature": 0.3, "stream": False,
    }, timeout=180)
    d = r.json()
    t = d.get("timings", {})
    return t.get("predicted_per_second")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8139)
    ap.add_argument("--quant", default=None, help="single quant key to run")
    args = ap.parse_args()

    RESULTS.mkdir(exist_ok=True)
    all_results = {}
    for key, label, gguf, size in QUANTS:
        if args.quant and args.quant != key:
            continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: {gguf} missing"); continue
        print(f"\n=== Serving {label} ({size} GB) ===", flush=True)
        outdir = RESULTS / key
        outdir.mkdir(exist_ok=True)
        proc = serve(args.port, gguf)
        try:
            tok_s = measure_tok_s(args.port)
            ev = {}
            for event in ["code", "reason", "agent"]:
                sc, tot, s = run_event(event, args.port, outdir / event)
                ev[event] = {"score": sc, "total": tot}
                print(f"  {event}: {sc}/{tot}")
            all_results[key] = {"label": label, "tok_s": round(tok_s, 2) if tok_s else None,
                        "size_gb": size, "events": ev}
        finally:
            proc.kill()
            proc.wait()

    # summary
    print("\n=== SPRINT RESULTS ===")
    for key, d in all_results.items():
        tot = sum(e["score"] for e in d["events"].values())
        max_ = sum(e["total"] for e in d["events"].values())
        print(f"{d['label']:22s} {d['tok_s']:>6.1f} t/s  {tot}/{max_}")
    (RESULTS / "summary.json").write_text(json.dumps(all_results, indent=2))
    print("Saved:", RESULTS / "summary.json")


if __name__ == "__main__":
    main()
