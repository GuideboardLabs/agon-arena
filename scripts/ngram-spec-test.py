#!/usr/bin/env python3
"""Test ngram speculative decoding strategies on a model.
Measures tok/s for each strategy on a 512-token generation.
"""
import subprocess, time, json, sys, os, signal

MODEL = "/mnt/blue/LLMbackups/omnicoder-9b-q4_k_m.gguf"
PORT = 8200
LLAMA_SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
PROMPT = "Write a detailed explanation of how transformer neural networks work, including attention mechanisms, positional encoding, and the feed-forward layers. Cover both the encoder and decoder architecture."

# Baseline args (no spec)
BASE_ARGS = [
    "--model", MODEL,
    "--port", str(PORT), "--host", "127.0.0.1",
    "--gpu-layers", "99", "--mlock",
    "--threads", "6", "--threads-batch", "6",
    "--cpu-mask", "0x3f", "--prio", "2",
    "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
    "--temp", "0.7", "--min-p", "0.05", "--parallel", "1",
]

STRATEGIES = {
    "baseline (no spec)": [],
    "spec-default": ["--spec-default"],
    "ngram-simple": ["--spec-ngram-simple-size-n", "12", "--spec-ngram-simple-size-m", "48", "--spec-ngram-simple-min-hits", "1"],
    "ngram-mod": ["--spec-ngram-mod-n-min", "48", "--spec-ngram-mod-n-max", "64", "--spec-ngram-mod-n-match", "24"],
    "ngram-map-k": ["--spec-ngram-map-k-size-n", "12", "--spec-ngram-map-k-size-m", "48", "--spec-ngram-map-k-min-hits", "1"],
    "ngram-map-k4v": ["--spec-ngram-map-k4v-size-n", "12", "--spec-ngram-map-k4v-size-m", "48", "--spec-ngram-map-k4v-min-hits", "1"],
}

def kill_server():
    subprocess.run(["pkill", "-9", "-f", "llama-server"], capture_output=True, timeout=5)
    time.sleep(2)

def start_server(extra_args):
    cmd = [LLAMA_SERVER] + BASE_ARGS + extra_args
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
    # Wait for ready
    for _ in range(60):
        time.sleep(2)
        try:
            import httpx
            r = httpx.get(f"http://127.0.0.1:{PORT}/v1/models", timeout=3)
            if r.status_code == 200:
                return proc
        except:
            pass
    print(f"  FAILED to start server with: {' '.join(extra_args)}")
    kill_server()
    return None

def measure_tok_s():
    import httpx
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 512,
        "temperature": 0.7,
        "stream": False,
    }
    start = time.time()
    resp = httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions", json=payload, timeout=300)
    elapsed = time.time() - start
    data = resp.json()
    timings = data.get("timings", {})
    gen_tok = timings.get("predicted_n", 0)
    gen_ms = timings.get("predicted_ms", 0)
    tps = gen_tok / (gen_ms / 1000) if gen_ms and gen_tok else 0
    prompt_tok = timings.get("prompt_n", 0)
    prompt_ms = timings.get("prompt_ms", 0)
    return tps, gen_tok, gen_ms, prompt_tok, prompt_ms, elapsed

print("=" * 60)
print("Ngram Speculative Decoding Benchmark")
print(f"Model: {MODEL}")
print(f"Prompt: {len(PROMPT)} chars, target: 512 tokens")
print("=" * 60)

results = []
for name, extra_args in STRATEGIES.items():
    print(f"\n--- {name} ---")
    kill_server()
    time.sleep(1)
    
    proc = start_server(extra_args)
    if not proc:
        results.append((name, 0, 0, 0, 0, 0, "FAILED"))
        continue
    
    time.sleep(2)  # settle
    
    # Run 3 measurements
    tps_list = []
    for i in range(3):
        tps, gen_tok, gen_ms, prompt_tok, prompt_ms, elapsed = measure_tok_s()
        tps_list.append(tps)
        print(f"  Run {i+1}: {tps:.1f} tok/s ({gen_tok} tokens in {gen_ms:.0f}ms, prompt {prompt_tok} in {prompt_ms:.0f}ms)")
    
    avg_tps = sum(tps_list) / len(tps_list)
    print(f"  AVG: {avg_tps:.1f} tok/s")
    results.append((name, avg_tps, tps_list[0], tps_list[1], tps_list[2], gen_tok, "OK"))
    
    # Kill server
    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    time.sleep(1)

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)
print(f"{'Strategy':<25} {'Avg tok/s':>10} {'Run 1':>8} {'Run 2':>8} {'Run 3':>8}")
print("-" * 60)
for name, avg, r1, r2, r3, gen_tok, status in results:
    print(f"{name:<25} {avg:>10.1f} {r1:>8.1f} {r2:>8.1f} {r3:>8.1f}")
print("-" * 60)

# Find best
best = max(results, key=lambda x: x[1])
print(f"\nBest: {best[0]} at {best[1]:.1f} tok/s")
