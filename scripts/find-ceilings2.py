#!/usr/bin/env python3
"""
Context ceiling finder v2 — CORRECTED.

Fixes the v1 bug: v1 waited only 2s between server kill and next load, so
leftover VRAM from the just-killed server contaminated the next fit (caused
Q3 to falsely "fail" at c8192 while 2-bit "ran" at c24576).

v2 gates each step on VRAM returning to baseline before loading, and reports
ACTUAL residency (VRAM used during the run) so we can tell a real ceiling from
a silent CPU spill.

Each step:
  1. confirm no llama-server running, port free
  2. wait until VRAM used < 0.15 GiB (baseline = desktop only)
  3. start server with -ngl 999, wait ready
  4. confirm VRAM now ~weights size (real residency) 
  5. probe a tiny generation -> decode t/s
  6. report, kill, wait VRAM back to baseline

Usage: python3 find-ceilings2.py [--quant KEY] [--port 8152]
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/ceilings")
BASELINE_GB = 0.10  # VRAM used by desktop alone, GiB
WAIT_FREE_TIMEOUT = 60

QUANTS = {
    "ours_q3":    ("Ours Q3-DOWN-XS",   "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf",      7.91),
    "ours_2bit":  ("Ours RDNA1-K 2-bit", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf", 7.79),
    "theirs_2bit":("Unsloth UD-IQ2_S",  "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf", 7.80),
    "theirs_1bit":("Unsloth UD-IQ1_S",  "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq1s/Qwen3.8-27B-UD-IQ1_S.gguf", 5.77),
}

CTX_LADDER = [8192, 16384, 24576, 32768, 49152, 65536, 98304, 131072, 163840, 196608, 229376, 262144]

def vram_used_gib():
    try:
        with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
            return int(f.read())/1073741824
    except Exception:
        return None

def wait_vram_free(timeout=WAIT_FREE_TIMEOUT):
    """Wait until VRAM is back near baseline (desktop only)."""
    t0 = time.time()
    while time.time()-t0 < timeout:
        used = vram_used_gib()
        if used is not None and used < BASELINE_GB*3:
            return used
        time.sleep(2)
    return vram_used_gib()

def serve(port, gguf, ctx, ngl, logfile):
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1",
           "-c", str(ctx), "-np", "1", "-ngl", str(ngl),
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
    proc.kill()
    logf.close()
    return None, logf

def probe(port):
    import httpx
    try:
        r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
            "model":"x","messages":[{"role":"user","content":"Say hello"}],
            "max_tokens":8,"temperature":0.3,"stream":False}, timeout=180)
        if r.status_code == 200:
            tim = r.json().get("timings", {})
            return {"ok":True, "decode": tim.get("predicted_per_second"), "prefill": tim.get("prompt_per_second")}
        return {"ok":False, "status":r.status_code}
    except Exception as e:
        return {"ok":False, "err": repr(e)[:100]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quant", default=None)
    ap.add_argument("--port", type=int, default=8152)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    report = {}
    for key,(label,gguf,wts_gb) in QUANTS.items():
        if args.quant and args.quant != key: continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: missing"); continue
        print(f"\n===== {label} (weights {wts_gb}GB) =====", flush=True)
        qres = []
        for ctx in CTX_LADDER:
            # 1. VRAM free gate
            base = wait_vram_free()
            print(f"  ctx={ctx} | vram_baseline={base:.2f}GiB", flush=True)
            # 2. serve
            proc, logf = serve(args.port, gguf, ctx, 999, RESULTS/f"{key}-c{ctx}.log")
            if proc is None:
                print(f"    FAIL not_ready at ctx={ctx}", flush=True)
                qres.append({"ctx":ctx,"status":"not_ready"}); break
            time.sleep(2)
            # 3. actual residency check
            used = vram_used_gib()
            resident = used is not None and used > wts_gb*0.6  # >60% of weights in VRAM = real residency
            p = probe(args.port)
            print(f"    vram_used={used:.2f}GiB resident={resident} probe={p}", flush=True)
            qres.append({"ctx":ctx,"status":"ok" if (p.get("ok") and resident) else "spill_or_fail",
                         "probe":p,"vram_used":used,"resident":resident})
            proc.kill(); proc.wait(); logf.close()
            # wait for VRAM release before next
            time.sleep(5)
            if not (p.get("ok") and resident):
                # if it stopped being resident/working, that's likely near the ceiling
                # but keep going a bit to map spill falloff; break on hard fail
                if not p.get("ok"):
                    break
        report[key] = {"label":label, "weights_gb":wts_gb, "results":qres}
        (RESULTS/"report2.json").write_text(json.dumps(report, indent=2))
    print("\nReport:", RESULTS/"report2.json")

if __name__ == "__main__":
    main()
