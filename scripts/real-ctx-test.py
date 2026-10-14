#!/usr/bin/env python3
"""
Real long-context processing test for Q3-DOWN-XS (the heaviest, least-slack quant).
Bounds all lighter quants.

Unlike find-ceilings2 (which only PROVED BOOT), this streams a real long prompt
through the server and verifies:
  1. The server can process N context tokens (prefill actually runs, not just boots)
  2. VRAM during real load (KV + prefill buffers allocated) - the "hidden math"
  3. The needle is retrievable at that context (needle-in-haystack proxy)
  4. Decode still works after a long prefill

Needle-in-haystack: place a unique needle sentence at position ~65% into a wall of
filler text, then ask a question whose answer requires retrieving it. If the model
recites the needle correctly, context is genuinely usable.

Usage: python3 real-ctx-test.py [--ctx 32768] [--port 8153]
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/real-ctx")

# ~28 tokens per filler sentence
FILLER = ("The quick brown fox jumps over the lazy dog while the sun sets behind the "
          "distant mountains and the river flows gently through the ancient valley. ")

def vram_used_gib():
    try:
        with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
            return int(f.read())/1073741824
    except Exception:
        return None

def wait_vram_free(timeout=60):
    t0 = time.time()
    while time.time()-t0 < timeout:
        u = vram_used_gib()
        if u is not None and u < 0.3:
            return u
        time.sleep(2)
    return vram_used_gib()

def serve(port, gguf, ctx, logfile):
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1",
           "-c", str(ctx), "-np", "1", "-ngl", "999",
           "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
           "--jinja", "-t", "6"]
    logf = open(logfile, "w")
    proc = subprocess.Popen(cmd, env=env, stdout=logf, stderr=logf)
    import httpx
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc, logf
        except Exception:
            pass
    proc.kill(); logf.close()
    return None, logf

def build_prompt(target_tokens, needle_pos_frac=0.65):
    """Build a prompt of ~target_tokens with a unique needle embedded."""
    needle = "SECRET-KEY-7729: the capital of Zanubia is the city of Maraketh."
    filler_tokens_per = len(FILLER.split())  # approx
    n_filler = int(target_tokens / filler_tokens_per) + 10
    parts = []
    pos_needle = int(n_filler * needle_pos_frac)
    for i in range(n_filler):
        if i == pos_needle:
            parts.append(needle + " ")
        parts.append(FILLER)
    body = "".join(parts)
    # estimate tokens
    prompt = ("Below is a long document. Read it carefully.\n\n" + body +
              "\n\nQuestion: What is the capital of Zanubia? Answer with just the city name.")
    return prompt

def call(port, prompt, max_tokens=120, reasoning_effort="medium"):
    import httpx
    t0 = time.time()
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
        "model":"x","messages":[{"role":"user","content":prompt}],
        "max_tokens":max_tokens,"temperature":0.0,"stream":False,
        "chat_template_kwargs":{"reasoning_effort":reasoning_effort},
        }, timeout=1800)
    wall = time.time()-t0
    tim = r.json().get("timings", {})
    msg = r.json()["choices"][0]["message"]
    return {
        "wall": round(wall,1), "content": msg.get("content") or "",
        "reasoning": msg.get("reasoning_content") or "",
        "prompt_tokens": tim.get("prompt_n"), "completion_tokens": tim.get("predicted_n"),
        "prefill_ps": tim.get("prompt_per_second"), "decode": tim.get("predicted_per_second"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--port", type=int, default=8153)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    gguf = "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"
    wait_vram_free()
    print(f"===== Q3 real-ctx test @ c{args.ctx} =====", flush=True)
    proc, logf = serve(args.port, gguf, args.ctx, RESULTS/f"q3-c{args.ctx}.log")
    if proc is None:
        print("SERVER FAILED TO BOOT"); return
    time.sleep(2)
    idle_vram = vram_used_gib()
    # build prompt ~85% of ctx so KV fills but leaves decode room
    target = int(args.ctx * 0.85)
    prompt = build_prompt(target)
    print(f"  prompt built (~{target} tokens, will fill ~85% of ctx)", flush=True)
    import httpx
    # prefill + needle retrieval in one call (medium reasoning - Q3's target)
    r = call(args.port, prompt, max_tokens=120, reasoning_effort="medium")
    load_vram = vram_used_gib()
    answer = r["content"]
    correct = "Maraketh" in answer
    print(f"  prompt_tokens={r['prompt_tokens']} wall={r['wall']}s prefill={r['prefill_ps']:.1f}t/s decode={r['decode']:.1f}t/s", flush=True)
    print(f"  idle_vram={idle_vram:.2f} load_vram={load_vram:.2f}GiB", flush=True)
    print(f"  reasoning_len={len(r['reasoning'])}", flush=True)
    print(f"  answer: {answer!r}", flush=True)
    print(f"  NEEDLE RETRIEVED: {correct}", flush=True)
    out = {"ctx":args.ctx,"idle_vram":idle_vram,"load_vram":load_vram,
           "prompt_tokens":r["prompt_tokens"],"prefill_ps":r["prefill_ps"],"decode":r["decode"],
           "reasoning_len":len(r["reasoning"]),
           "answer":answer,"needle_retrieved":correct,"wall":r["wall"]}
    (RESULTS/f"q3-c{args.ctx}.json").write_text(json.dumps(out, indent=2))
    proc.kill(); proc.wait(); logf.close()
    print("Done:", RESULTS/f"q3-c{args.ctx}.json")

if __name__ == "__main__":
    main()
