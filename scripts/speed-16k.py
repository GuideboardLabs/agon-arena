#!/usr/bin/env python3
"""
Same-harness 16k speed test for GGUF quants.

Every quant is served on the SAME llama.cpp Vulkan fork with identical flags
(c16384, ngl 999, q8_0 KV, jinja, reasoning off) and measured with the SAME
16k-context prompt (~8k prompt tokens -> output tokens) so the tok/s is
directly comparable. Uses the server's own timing, so decode and prefill are
both reported per quant. The IQ3_XXS quant intentionally overflows 8GB (the
"slow king") - that's the whole point of comparing it.

Usage:
  python3 speed-16k.py [--quant KEY] [--port 8140]
"""
import argparse, os, subprocess, time, json
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path(os.path.expanduser("~/Documents/agon-arena/sprint-results/speed16k"))

QUANTS = [
    ("unsloth_iq1s",    "Unsloth UD-IQ1_S",   "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq1s/Qwen3.8-27B-UD-IQ1_S.gguf"),
    ("unsloth_iq2s",    "Unsloth UD-IQ2_S",   "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf"),
    ("ours_2bit",       "Ours RDNA1-K 2-bit", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf"),
    ("ours_3bit",       "Ours Q3-DOWN-XS",    "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"),
    ("unsloth_iq3xxs",  "Unsloth UD-IQ3_XXS", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq3xxs/Qwen3.8-27B-UD-IQ3_XXS.gguf"),
]

SERVER_ARGS = [
    "-c", "16384", "-np", "1", "-ngl", "999",
    "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
    "--jinja", "--reasoning", "off", "--reasoning-format", "none",
    "-t", "6",
]

# ~8k-token prompt (~4 chars/token for prose) so the response has ~8k of the
# 16k context left to decode into (prompt + output share the KV cache).
# End with a task that forces a long, sustained generation (not an early stop).
_SENT = "The history of computing is a story of exponential progress. From mechanical calculators through vacuum tubes, transistors, integrated circuits, and modern microprocessors, each generation has expanded what machines can do. The thread runs from Ada Lovelace's analytical engine through Turing, von Neumann, the ENIAC, the transistor radio, the silicon chip, the microprocessor, the personal computer, the internet, and the smartphone, each step compounding the last. "
PROMPT_SRC = _SENT * 60 + "\n\nNow write a detailed, thorough 400-word essay expanding on the most important turning point in that history, with concrete details, dates, and named people. Do not stop early — write the full essay."  # ~8k prompt + sustained generation demand

def serve(port, gguf):
    import httpx
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1"] + SERVER_ARGS
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
    proc.kill(); raise RuntimeError(f"server fail {gguf}")

def measure(port, prompt, n_out=200):
    import httpx
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
        "model": "s", "messages": [{"role": "user", "content": prompt}],
        "max_tokens": n_out, "temperature": 0.3, "stream": False,
    }, timeout=900)
    t = r.json().get("timings", {})
    predicted_n = t.get("predicted_n")
    predicted_ps = t.get("predicted_per_second")
    # Robustness: if the response was truncated to < ~30 real tokens, decode is
    # not a meaningful sustained measurement. Flag it.
    flag = ""
    if predicted_n is not None and predicted_n < 30:
        flag = " (LOW TOKENS - decode not sustained)"
    return {
        "prompt_tokens": t.get("prompt_n"),
        "predicted_tokens": predicted_n,
        "prompt_ps": t.get("prompt_per_second"),
        "predicted_ps": predicted_ps,
        "flag": flag.strip(),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8140)
    ap.add_argument("--quant", default=None)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    json_path = RESULTS / "speed16k.json"
    out = {}
    if json_path.exists():
        try:
            out = json.loads(json_path.read_text())
        except Exception:
            out = {}
    for key, label, gguf in QUANTS:
        if args.quant and args.quant != key: continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: {gguf} missing"); continue
        print(f"\n=== {label} ===", flush=True)
        proc = serve(args.port, gguf)
        try:
            m = measure(args.port, PROMPT_SRC)
            pp = m.get("prompt_ps"); dp = m.get("predicted_ps")
            pt = m.get("predicted_tokens")
            print(f"  prompt={m.get('prompt_tokens')}t, prefill={pp if pp is not None else '?'} t/s, decode={dp if dp is not None else '?'} t/s ({pt}t){' '+m['flag'] if m['flag'] else ''}")
            out[key] = {"label": label, **m}
        except Exception as e:
            print(f"  ERROR measuring {key}: {e}")
            out[key] = {"label": label, "error": str(e)}
        finally:
            proc.kill(); proc.wait()
            json_path.write_text(json.dumps(out, indent=2))  # incremental save
    print("\n=== 16k SPEED SUMMARY (same harness, ~8k prompt / ~8k out) ===")
    for k, d in out.items():
        if "error" in d:
            print(f"{d['label']:22s} ERROR: {d['error'][:60]}")
        else:
            print(f"{d['label']:22s} prefill={d['prompt_ps']:6.1f}  decode={d['predicted_ps']:6.2f} t/s")
    print("Saved:", json_path)

if __name__ == "__main__":
    main()
