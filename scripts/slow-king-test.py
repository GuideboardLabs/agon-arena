#!/usr/bin/env python3
"""
Spill-aware capability + speed test for Unsloth IQ3_XXS (the "slow king").
Serves it at a SHORT context (so the 10.18GB model + KV fits, mostly GPU,
minimal spill crash risk) and runs the SAME Agon Sprint subset as the other
quants. Purpose: measure what the slowness BUYS in capability.
"""
import os, subprocess, sys, time, json
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
SCRIPTS = Path("/home/sc/Documents/agon-arena/scripts")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/iq3xxs")
PORT = 8146
URL = f"http://127.0.0.1:{PORT}"

QUANT = "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq3xxs/Qwen3.8-27B-UD-IQ3_XXS.gguf"

# SHORT context (c4096) so the ~10.18GB model + KV fits mostly on GPU w/o spill crash.
# -ngl 999 forces full offload; llama will spill to CPU as needed.
SERVER_ARGS = [
    "-c", "4096", "-np", "1", "-ngl", "999",
    "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
    "--jinja", "--reasoning", "off", "--reasoning-format", "none",
    "-t", "6",
]

def serve():
    import httpx
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", QUANT, "--port", str(PORT), "--host", "127.0.0.1"] + SERVER_ARGS
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
    proc.kill(); raise RuntimeError("IQ3_XXS server failed to start")

def measure_tok(port):
    import httpx
    prompt = ("Write a detailed, thorough 300-word essay on the most important turning point "
              "in the history of computing, with concrete dates, names, and details. "
              "Do not stop early — write the full essay.")
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
        "model": "x", "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200, "temperature": 0.3, "stream": False,
    }, timeout=900)
    t = r.json().get("timings", {})
    return t

def main():
    RESULTS.mkdir(exist_ok=True)
    print("=== Serving IQ3_XXS (10.18GB, spill-aware, short ctx) ===", flush=True)
    proc = serve()
    try:
        # speed measurement
        t = measure_tok(PORT)
        print(f"  prompt={t.get('prompt_n')}t prefill={t.get('prompt_per_second')} t/s, decode={t.get('predicted_per_second')} t/s ({t.get('predicted_n')}t)")
        # run sprint events
        ev = {}
        for event in ["code", "reason", "agent"]:
            tasks = {"code": "1,2,3", "reason": "1,2,3", "agent": "1,2"}[event]
            cmd = [
                sys.executable, str(SCRIPTS / f"{event}-event.py"),
                "--model-url", f"http://127.0.0.1:{PORT}", "--model", "x",
                "--output", str(RESULTS / event), "--run", "1", "--seed", "42",
                "--tasks", tasks, "--task-timeout", "900", "--max-tokens", "2048",
            ]
            subprocess.run(cmd, timeout=3600)
            s = RESULTS / event / "summary.json"
            if s.exists():
                j = json.loads(s.read_text())
                ev[event] = {"score": sum(x.get("hidden_tests_passed",0) for x in j.get("tasks",[])),
                             "total": sum(x.get("hidden_tests_total",0) for x in j.get("tasks",[]))}
                print(f"  {event}: {ev[event]['score']}/{ev[event]['total']}")
            else:
                ev[event] = {"score": 0, "total": 0, "error": "no summary"}
        # save
        out = {"speed": {"decode": t.get("predicted_per_second"), "prefill": t.get("prompt_per_second")}, "events": ev}
        (RESULTS / "iq3xxs.json").write_text(json.dumps(out, indent=2))
        print("Saved:", RESULTS / "iq3xxs.json")
    finally:
        proc.kill(); proc.wait()

if __name__ == "__main__":
    main()
