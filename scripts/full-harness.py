#!/usr/bin/env python3
"""
Full capability + speed harness v2 — reasoning ON, uniform 16k context,
smart spill, wall-clock + prefill + decode, full reasoning+content capture
for hand grading.

Every quant runs on the SAME llama.cpp Vulkan fork, c16384, reasoning ON,
same 8 deterministic tasks, same seed. Each quant gets an ngl that keeps the
KV/weights resident (smart spill): the 4 that fit get 999 (fully resident);
IQ3_XXS (10.18GB) gets a reduced ngl so it spills to CPU instead of wedging.
Captures reasoning_content AND content per task for partial-credit grading.

Usage: python3 full-harness.py [--quant KEY] [--port 8150]
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/full-v2")
SCRIPTS = Path("/home/sc/Documents/agon-arena/scripts")

# quant_key -> (label, gguf, ngl)
QUANTS = [
    ("unsloth_iq3xxs", "Unsloth UD-IQ3_XXS", "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq3xxs/Qwen3.8-27B-UD-IQ3_XXS.gguf", 48),
    ("ours_3bit",      "Ours Q3-DOWN-XS",    "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf", 999),
    ("unsloth_iq2s",   "Unsloth UD-IQ2_S",   "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf", 999),
    ("unsloth_iq1s2",  "Unsloth UD-IQ1_S",   "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq1s/Qwen3.8-27B-UD-IQ1_S.gguf", 999),
    ("ours_2bit",      "Ours RDNA1-K 2-bit", "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf", 999),
]

# same 8 tasks: (event, id, name, prompt)
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

def serve(port, gguf, ngl):
    import httpx
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1",
           "-c", "16384", "-np", "1", "-ngl", str(ngl),
           "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
           "--jinja", "--reasoning", "on",  # reasoning ON for all
           "-t", "6"]
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        time.sleep(2)
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5)
            if r.status_code == 200:
                return proc
        except Exception:
            pass
    proc.kill(); raise RuntimeError(f"server fail {gguf} ngl={ngl}")

def call(port, prompt, max_tokens=4096):
    import httpx
    payload = {"model": "x", "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": False}
    t0 = time.time()
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json=payload, timeout=1800)
    wall = time.time() - t0
    msg = r.json()["choices"][0]["message"]
    tim = r.json().get("timings", {})
    return {
        "wall_s": round(wall, 1),
        "reasoning": msg.get("reasoning_content") or "",
        "content": msg.get("content") or "",
        "prompt_ps": tim.get("prompt_per_second"),
        "decode": tim.get("predicted_per_second"),
        "predicted_n": tim.get("predicted_n"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quant", default=None)
    ap.add_argument("--port", type=int, default=8150)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    index = {}
    for key, label, gguf, ngl in QUANTS:
        if args.quant and args.quant != key: continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: {gguf} missing"); continue
        qdir = RESULTS / key
        qdir.mkdir(exist_ok=True)
        print(f"\n=== {label} (ngl={ngl}) ===", flush=True)
        proc = serve(args.port, gguf, ngl)
        try:
            tasks_out = []
            for event, tid, name, prompt in TASKS:
                print(f"  [{event}:{tid}] {name}...", flush=True)
                r = call(args.port, prompt)
                # save response
                (qdir / f"{event}-{tid}-{name.lower().replace(' ','_')}.json").write_text(json.dumps(r, indent=2))
                tasks_out.append({"event": event, "task": tid, "name": name, **r})
                print(f"    wall={r['wall']}s decode={r['decode']:.2f} t/s")
            index[key] = {"label": label, "ngl": ngl, "tasks": tasks_out}
            (RESULTS / "index.json").write_text(json.dumps(index, indent=2))
        finally:
            proc.kill(); proc.wait()
    print("\nDone. Responses in", RESULTS)

if __name__ == "__main__":
    main()
