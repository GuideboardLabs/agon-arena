#!/usr/bin/env python3
"""
Context ceiling finder for the three quants on 8GB RDNA1.

For each quant, walk context up in a ladder and find the largest context that
serves WITHOUT wedging the GPU. Reports residency (VRAM used) and whether the
KV stays resident (ngl 999) or spills (reduced ngl / CPU fallback).

We serve with -ngl 999 first (full residency). If the model+KV overflows VRAM
we'll see a wedged GPU; we then back off the context. Uses a short single-token
generation just to confirm the server is alive at that context, not a full
capability run.

Usage: python3 find-ceilings.py [--quant KEY] [--port 8152]
"""
import os, subprocess, sys, time, json, argparse, re
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/ceilings")

QUANTS = {
    "ours_q3":   ("Ours Q3-DOWN-XS",   "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"),
    "ours_2bit": ("Ours RDNA1-K 2-bit", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf"),
    "ours_1bit": ("Ours Q1-FFN-PROBE", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q1-FFN-PROBE.gguf"),
}

# context ladder to probe
CTX_LADDER = [2048, 4096, 8192, 16384, 24576, 32768, 49152, 65536, 98304, 131072]

def vram_free_gib():
    try:
        with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
            used = int(f.read())
        return 8.57 - used/1073741824
    except Exception:
        return None

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
    ready = False
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if r.status_code == 200:
                ready = True
                break
        except Exception:
            pass
    if not ready:
        proc.kill()
        logf.close()
        return None, "not_ready"
    return proc, logf

def probe(port):
    import httpx
    try:
        r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json={
            "model":"x", "messages":[{"role":"user","content":"Say hello"}],
            "max_tokens": 8, "temperature":0.3, "stream":False
        }, timeout=180)
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
    for key,(label,gguf) in QUANTS.items():
        if args.quant and args.quant != key: continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: missing"); continue
        print(f"\n===== {label} =====", flush=True)
        qres = []
        for ctx in CTX_LADDER:
            print(f"  ctx={ctx} ngl=999 ...", flush=True)
            proc, logf = serve(args.port, gguf, ctx, 999, RESULTS/f"{key}-c{ctx}.log")
            if proc is None:
                print(f"    FAIL not_ready at ctx={ctx}", flush=True)
                qres.append({"ctx":ctx,"status":"not_ready"})
                break
            p = probe(args.port)
            free = vram_free_gib()
            print(f"    probe={p} free_vram={free:.2f}GiB", flush=True)
            qres.append({"ctx":ctx,"status": "ok" if p.get("ok") else "fail", "probe":p, "free_vram":free})
            # if it wedged (probe fail), stop this quant
            if not p.get("ok"):
                proc.kill(); proc.wait(); logf.close()
                # wait for GPU to recover
                print("    GPU may be wedged - waiting 10s", flush=True)
                time.sleep(10)
                break
            proc.kill(); proc.wait(); logf.close()
            time.sleep(2)
        report[key] = {"label":label, "results":qres}
        (RESULTS/"report.json").write_text(json.dumps(report, indent=2))
    print("\nReport:", RESULTS/"report.json")

if __name__ == "__main__":
    main()
