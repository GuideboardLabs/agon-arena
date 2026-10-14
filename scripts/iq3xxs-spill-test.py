#!/usr/bin/env python3
"""
Spill-balanced 16k test for IQ3_XXS (the slow king).

The earlier "crash" used -ngl 999 which forced full GPU offload of a 10.18GB
model + 16k KV -> VRAM overflow -> wedged GPU. This test does it RIGHT:
- Let llama.cpp AUTO-FIT layers to free VRAM (no forced ngl), or try a specific
  -ngl that leaves room for the KV, so the model spills to CPU instead of
  crashing. Measure: does it run at 16k, and at what (slow) speed?
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/speed16k")
QUANT = "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq3xxs/Qwen3.8-27B-UD-IQ3_XXS.gguf"
PORT = 8147

# ~8k prompt (shared KV with 16k context)
_SENT = ("The history of computing is a story of exponential progress. From mechanical calculators "
         "through vacuum tubes, transistors, integrated circuits, and modern microprocessors, each "
         "generation has expanded what machines can do. The thread runs from Ada Lovelace's analytical "
         "engine through Turing, von Neumann, the ENIAC, the transistor radio, the silicon chip, the "
         "microprocessor, the personal computer, the internet, and the smartphone, each step "
         "compounding the last. ")
PROMPT = _SENT * 60 + "\n\nNow write a detailed, thorough 400-word essay on the most important turning point in that history. Do not stop early."

def serve(ngl, ctx=16384):
    import httpx
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", QUANT, "--port", str(PORT), "--host", "127.0.0.1",
           "-c", str(ctx), "-np", "1", "-ngl", str(ngl),
           "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
           "--jinja", "--reasoning", "off", "--reasoning-format", "none",
           "-t", "6"]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
    proc.kill(); raise RuntimeError(f"server fail at ngl={ngl}")

def measure():
    import httpx
    t0 = time.time()
    try:
        r = httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions", json={
            "model": "x", "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": 200, "temperature": 0.3, "stream": False,
        }, timeout=1800)
        tim = r.json().get("timings", {})
        return {"ok": True, "elapsed": round(time.time()-t0,1),
                "prompt_ps": tim.get("prompt_per_second"),
                "decode": tim.get("predicted_per_second"),
                "predicted_n": tim.get("predicted_n")}
    except Exception as e:
        return {"ok": False, "elapsed": round(time.time()-t0,1), "err": repr(e)[:150]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ngl", type=int, default=48, help="layers to GPU")
    ap.add_argument("--ctx", type=int, default=16384)
    args = ap.parse_args()
    print(f"=== IQ3_XXS spill-balanced: ngl={args.ngl} ctx={args.ctx} ===", flush=True)
    proc = serve(args.ngl, args.ctx)
    try:
        m = measure()
        print(json.dumps(m, indent=2))
    finally:
        proc.kill(); proc.wait()

if __name__ == "__main__":
    main()
