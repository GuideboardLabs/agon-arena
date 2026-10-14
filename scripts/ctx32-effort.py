#!/usr/bin/env python3
"""
32k capability+speed harness - reasoning EFFORT (not budget), full capture.

The three requested configs at the usable ceiling (32k, where prefill is 101 t/s;
64k prefill collapses):
  - ours Q3-DOWN-XS @ medium reasoning
  - our 2-bit kernel @ xhigh reasoning
  - their 2-bit (Unsloth IQ2_S) @ xhigh reasoning

Same 8 tasks, reasoning_effort passed via chat_template_kwargs (the trained
behavioral switch - NOT a token budget). Captures reasoning_content AND content
for hand grading. One quant at a time, VRAM-free gated.

Usage: python3 ctx32-effort.py [--quant KEY] [--port 8154]
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/ctx32-effort")

QUANTS = [
    ("ours_q3",   "Ours Q3-DOWN-XS",     "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf",       "medium"),
    ("ours_2bit", "Ours RDNA1-K 2-bit",  "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf", "xhigh"),
    ("theirs_2bit","Unsloth UD-IQ2_S",   "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf","xhigh"),
]

TASKS = [
    ("code", 1, "String Cleaner",
     "Write a Python function `clean_text(text: str) -> str` that: strips leading/trailing whitespace; collapses multiple spaces into one; removes any character that isn't alphanumeric, space, hyphen, apostrophe, or period; truncates to at most 200 characters ending on a complete word; returns 'INVALID' if empty after cleaning. Return ONLY the function definition."),
    ("code", 2, "Log Parser",
     "Write a Python function `parse_logs(log_lines: list[str]) -> dict` that: parses lines in format `[2024-01-15 10:30:45] LEVEL: message`; valid LEVELs INFO/WARN/ERROR/DEBUG; returns counts per level, errors list of (timestamp,message), warnings list, first and last timestamp; skips malformed lines. Return ONLY the function definition."),
    ("code", 3, "LRU Cache",
     "Write a Python class `LRUCache` with __init__(capacity), get(key)->any (or -1 if absent), put(key,value); evicts least-recently-used at capacity; both get and put count as use. Return ONLY the class definition."),
    ("reason", 1, "Logical Deduction",
     "Solve: Five people (Alice,Bob,Carol,Dave,Eve) live in red/blue/green/yellow/white houses; each has a favorite drink (coffee,tea,juice,soda,water) and pet (cat,dog,bird,fish,hamster). Clues: Alice=red; Bob=coffee; tea owner has bird; green is immediately left of white; green=juice; Carol=cat; yellow=dog; Dave=soda; Eve=blue; water=hamster. Who owns the fish? Show reasoning step by step."),
    ("reason", 2, "Math Word Problem",
     "A train leaves Station A toward B at 60 mph. 30 minutes later a second train leaves B toward A at 75 mph. Stations 300 miles apart. a) How long after the first departs do they meet? b) How far from A? Show work."),
    ("reason", 3, "Constraint Satisfaction",
     "Schedule 4 meetings (Standup 15m needs A,B,C; Sprint Planning 60m needs A,D,E,F; Design Review 30m needs C,D,G; Retro 45m needs A,B,C,D,E) into 3 rooms across the day. Output schedule as (meeting, room, time) tuples. Show reasoning."),
    ("agent", 1, "Tool Calling",
     "Write a Python function `call_weather_api(city: str) -> dict` returning {tool_name:'get_weather', arguments:{city}} and an error dict if city empty. Return ONLY the function."),
    ("agent", 2, "Orchestration",
     "Write a Python function `orchestrate(results: list[dict]) -> str`: if any status 'error' return 'retry'; if all success with 'answer' return 'complete'; if some missing return 'fetch_more'. Return ONLY the function."),
]

def vram_gib():
    try:
        with open("/sys/class/drm/card1/device/mem_info_vram_used") as f:
            return int(f.read())/1073741824
    except Exception:
        return None

def wait_vram_free(timeout=60):
    t0=time.time()
    while time.time()-t0<timeout:
        u=vram_gib()
        if u is not None and u<0.3: return u
        time.sleep(2)
    return vram_gib()

def serve(port, gguf, logfile, ctx=32768):
    env=os.environ.copy(); env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"]="1"
    cmd=[SERVER,"-m",gguf,"--port",str(port),"--host","127.0.0.1",
         "-c",str(ctx),"-np","1","-ngl","999","-ctk","q8_0","-ctv","q8_0","-fa","on",
         "--jinja","-t","6"]
    logf=open(logfile,"w"); proc=subprocess.Popen(cmd,env=env,stdout=logf,stderr=logf)
    import httpx
    for _ in range(120):
        time.sleep(2)
        try:
            r=httpx.get(f"http://127.0.0.1:{port}/v1/models",timeout=5)
            if r.status_code==200: return proc,logf
        except Exception: pass
    proc.kill(); logf.close(); return None,logf

def call(port, prompt, effort, max_tokens=60000, think_budget=8192):
    import httpx
    payload={"model":"x","messages":[{"role":"user","content":prompt}],
             "max_tokens":max_tokens,"temperature":0.3,"stream":False,
             "thinking_budget_tokens":think_budget,
             "chat_template_kwargs":{"reasoning_effort":effort}}
    t0=time.time()
    r=httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions",json=payload,timeout=3600)
    wall=time.time()-t0
    tim=r.json().get("timings",{}); msg=r.json()["choices"][0]["message"]
    return {"wall_s":round(wall,1),"reasoning":msg.get("reasoning_content") or "",
            "content":msg.get("content") or "","prompt_ps":tim.get("prompt_per_second"),
            "decode":tim.get("predicted_per_second"),"predicted_n":tim.get("predicted_n")}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--quant",default=None); ap.add_argument("--port",type=int,default=8154); ap.add_argument("--ctx",type=int,default=32768); ap.add_argument("--effort",default=None); ap.add_argument("--think",type=int,default=0)
    args=ap.parse_args(); RESULTS.mkdir(exist_ok=True); index={}
    for key,label,gguf,effort in QUANTS:
        if args.quant and args.quant!=key: continue
        if not os.path.exists(gguf): print(f"SKIP {key}"); continue
        if args.effort: effort=args.effort
        wait_vram_free()
        # distinct output dir: key-effort-ctx-thinkbudget so prior runs are preserved
        qdir=RESULTS/f"{key}-{effort}-c{args.ctx}-tb{args.think}"; qdir.mkdir(exist_ok=True)
        print(f"\n===== {label} | reasoning_effort={effort} | ctx {args.ctx} | think_budget={args.think} =====",flush=True)
        proc,logf=serve(args.port,gguf,qdir/"server.log",ctx=args.ctx)
        if proc is None: print("FAIL boot"); continue
        time.sleep(2); print(f"  vram={vram_gib():.2f}GiB resident",flush=True)
        try:
            tasks=[]
            for event,tid,name,prompt in TASKS:
                print(f"  [{event}:{tid}] {name} (effort={effort})...",flush=True)
                r=call(args.port,prompt,effort,max_tokens=60000,think_budget=args.think)
                (qdir/f"{event}-{tid}-{name.lower().replace(' ','_')}.json").write_text(json.dumps(r,indent=2))
                tasks.append({"event":event,"task":tid,"name":name,"effort":effort,**r})
                print(f"    wall={r['wall_s']}s decode={r['decode']:.1f} n={r['predicted_n']} reasoning={len(r['reasoning'])} content={len(r['content'])}",flush=True)
            index[key]={"label":label,"effort":effort,"tasks":tasks}
            (RESULTS/"index.json").write_text(json.dumps(index,indent=2))
        finally:
            proc.kill(); proc.wait(); logf.close(); time.sleep(4)
    print("\nDone:",RESULTS)

if __name__=="__main__":
    main()
