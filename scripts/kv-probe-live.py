#!/usr/bin/env python3
"""Live: measure where the KV cache actually sits on this box.
Serves Q3 at two contexts, polls BOTH vram_used and gtt_used during
a long-generation, and captures llama-server's own memory lines."""
import os, subprocess, sys, time, json, signal
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
GGUF = "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"
PORT = 8180

def mem(attr):
    try:
        return int(open(f"/sys/class/drm/card1/device/{attr}").read().strip())/1073741824
    except Exception:
        return None

def wait_free(timeout=60):
    t0=time.time()
    while time.time()-t0<timeout:
        if mem("mem_info_vram_used") is not None and mem("mem_info_vram_used")<0.3:
            return
        time.sleep(2)

def serve(ctx, logfile):
    env=os.environ.copy(); env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"]="1"
    cmd=[SERVER,"-m",GGUF,"--port",str(PORT),"--host","127.0.0.1","-c",str(ctx),
         "-np","1","-ngl","999","-ctk","q8_0","-ctv","q8_0","-fa","on","--jinja","-t","6"]
    logf=open(logfile,"w")
    proc=subprocess.Popen(cmd,env=env,stdout=logf,stderr=logf)
    import httpx
    for _ in range(120):
        time.sleep(2)
        try:
            if httpx.get(f"http://127.0.0.1:{PORT}/v1/models",timeout=5).status_code==200:
                return proc,logf
        except Exception: pass
    proc.kill(); logf.close(); return None,logf

for ctx in [16384, 65536]:
    wait_free()
    proc,logf = serve(ctx, f"/tmp/kvprobe-c{ctx}.log")
    if proc is None:
        print(f"ctx {ctx}: FAIL boot"); continue
    time.sleep(3)
    v0=mem("mem_info_vram_used"); g0=mem("mem_info_gtt_used")
    print(f"\nctx {ctx}: vram={v0:.3f}GiB gtt={g0:.3f}GiB (after boot)", flush=True)
    # long generation to fill KV
    import httpx
    prompt = ("Write an essay about the history of computing. " * 300)  # ~2k tokens
    t0=time.time()
    try:
        r=httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions",
            json={"model":"x","messages":[{"role":"user","content":prompt}],
                  "max_tokens":200,"temperature":0.3,"stream":False}, timeout=600)
        # poll during and after
        v1=mem("mem_info_vram_used"); g1=mem("mem_info_gtt_used")
        print(f"  after gen: vram={v1:.3f}GiB gtt={g1:.3f}GiB  wall={time.time()-t0:.0f}s", flush=True)
    except Exception as e:
        print(f"  gen FAIL: {repr(e)[:120]}", flush=True)
    proc.kill(); proc.wait(); logf.close()
    # grep server log for kv memory info
    print("  --- server log kv/alloc lines ---")
    for line in open(f"/tmp/kvprobe-c{ctx}.log", errors='ignore'):
        if any(k in line for k in ["kv","KV","buffer size","ggml_vulkan","Vulkan0","CPU buffer","offloaded"]):
            print("   ", line.strip()[:130])
    time.sleep(6)
print("\ndone")
