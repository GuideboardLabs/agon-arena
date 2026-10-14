#!/usr/bin/env python3
"""Targeted re-test of a single task at a chosen reasoning_effort.
Reuses code-event.py's hidden-test grader + extraction. Serves the quant,
calls it with reasoning_effort=<effort>, grades, writes response + result.
Usage: python3 retest-task.py --quant ours_3bit --event code --task 1 --effort low
"""
import argparse, os, subprocess, sys, time, json, re
from pathlib import Path
import importlib.util

# code-event.py has a hyphen, so load via importlib by path
_spec = importlib.util.spec_from_file_location(
    "code_event", "/home/sc/Documents/agon-arena/scripts/code-event.py")
code_event = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(code_event)
SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
QUANTS = {
    "ours_3bit": ("Ours Q3-DOWN-XS", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"),
    "ours_2bit": ("Ours RDNA1-K 2-bit", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf"),
    "unsloth_iq2s": ("Unsloth UD-IQ2_S", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf"),
    "unsloth_iq1s": ("Unsloth UD-IQ1_S", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq1s/Qwen3.8-27B-UD-IQ1_S.gguf"),
}
OUT = Path("/home/sc/Documents/agon-arena/sprint-results/retry-low")
EVENTS = {"code": code_event.TASKS, "reason": None, "agent": None}

def vram():
    with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
        return int(f.read())/1073741824

def serve(port, gguf):
    env = os.environ.copy(); env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"]="1"
    cmd=[SERVER,"-m",gguf,"--port",str(port),"--host","127.0.0.1","-c","16384","-np","1",
         "-ngl","999","-ctk","q8_0","-ctv","q8_0","-fa","on","--jinja","-t","6"]
    proc=subprocess.Popen(cmd,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    import httpx
    for _ in range(120):
        time.sleep(2)
        try:
            r=httpx.get(f"http://127.0.0.1:{port}/v1/models",timeout=5)
            if r.status_code==200: return proc
        except Exception: pass
    proc.kill(); raise RuntimeError(f"boot fail {gguf}")

def call(port, prompt, effort, max_tokens=12000):
    import httpx
    payload={"model":"x","messages":[{"role":"user","content":prompt}],
             "max_tokens":max_tokens,"temperature":0.3,"stream":False,
             "chat_template_kwargs":{"reasoning_effort":effort}}
    t0=time.time()
    r=httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions",json=payload,timeout=3600)
    wall=time.time()-t0
    msg=r.json()["choices"][0]["message"]
    return {"wall":round(wall,1),"content":msg.get("content") or "",
            "reasoning_len":len(msg.get("reasoning_content") or "")}

def main():
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--event",default="code")
    ap.add_argument("--task",type=int,required=True)
    ap.add_argument("--effort",default="low"); ap.add_argument("--port",type=int,default=8170)
    args=ap.parse_args()
    label,gguf=QUANTS[args.model]
    task=next(t for t in EVENTS[args.event] if t["id"]==args.task)
    # wait for VRAM free
    for _ in range(30):
        if vram()<0.3: break
        time.sleep(2)
    proc=serve(args.port,gguf)
    print(f"===== {label} | {args.event} task {args.task} | effort={args.effort} =====",flush=True)
    try:
        r=call(args.port, task["prompt"], args.effort)
        passed,total,details=code_event.run_hidden_tests(r["content"], task["hidden_tests"], raw_response=r["content"])
        print(f"content={len(r['content'])}c reasoning={r['reasoning_len']}c wall={r['wall']}s",flush=True)
        print(f"RESULT: {passed}/{total}",flush=True)
        for d in details:
            print(f"   {'PASS' if d[-1]=='PASS' else 'FAIL'}: {d[0][:70]} -> {d[-1][:80]}",flush=True)
        out=OUT/f"{args.model}-{args.event}{args.task}-{args.effort}"
        out.mkdir(parents=True,exist_ok=True)
        (out/"response.txt").write_text(r["content"])
        (out/"result.json").write_text(json.dumps({**r,"passed":passed,"total":total}))
    finally:
        proc.kill(); proc.wait(); time.sleep(4)

if __name__=="__main__":
    main()
