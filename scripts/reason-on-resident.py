#!/usr/bin/env python3
"""
Reasoning-ON capability test — RESIDENT quants only (ngl 999, no spill).
Tests the hypothesis: does reasoning ON lift the "dumber" resident quants
toward the smart-but-unrunnable IQ3_XXS (24/26 with reasoning off)?

Same 8 tasks, same seed, reasoning ON for all. Full residency.
max_tokens raised to avoid truncation artifact on code tasks.

Quants: our Q3 winner, our 1-bit FFN probe, our 2-bit kernel, unsloth's 2-bit.
"""
import os, subprocess, sys, time, json, argparse
from pathlib import Path

SERVER = os.path.expanduser("~/llama.cpp/build-vulkan/bin/llama-server")
RESULTS = Path("/home/sc/Documents/agon-arena/sprint-results/full-v2-reasonon")

QUANTS = [
    ("ours_q3",      "Ours Q3-DOWN-XS",       "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q3-DOWN-XS.gguf"),
    ("ours_1bit",    "Ours Q1-FFN-PROBE",     "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-Q1-FFN-PROBE.gguf"),
    ("ours_2bit",    "Ours RDNA1-K 2-bit",    "/mnt/blue/qwen38-goal2/staging/Qwen3.8-27B-RDNA1-K-PROTECT63-64.gguf"),
    ("unsloth_iq2s", "Unsloth UD-IQ2_S",      "/mnt/blue/LLMbackups/unsloth-qwen38-27b-iq2s/Qwen3.8-27B-UD-IQ2_S.gguf"),
]

# same 8 tasks
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

def serve(port, gguf):
    import httpx
    env = os.environ.copy()
    env["GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM"] = "1"
    cmd = [SERVER, "-m", gguf, "--port", str(port), "--host", "127.0.0.1",
           "-c", "16384", "-np", "1", "-ngl", "999",
           "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
           "--jinja", "--reasoning", "on", "--reasoning-budget", "1024", "-t", "6"]
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

def call(port, prompt, max_tokens=8192):
    import httpx
    payload = {"model": "x", "messages": [{"role": "user", "content": prompt}],
               "max_tokens": max_tokens, "temperature": 0.3, "stream": False}
    t0 = time.time()
    r = httpx.post(f"http://127.0.0.1:{port}/v1/chat/completions", json=payload, timeout=3600)
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
    ap.add_argument("--port", type=int, default=8151)
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    index = {}
    for key, label, gguf in QUANTS:
        if args.quant and args.quant != key: continue
        if not os.path.exists(gguf):
            print(f"SKIP {key}: {gguf} missing"); continue
        qdir = RESULTS / key
        qdir.mkdir(exist_ok=True)
        print(f"\n=== {label} (reasoning ON, ngl 999) ===", flush=True)
        proc = serve(args.port, gguf)
        try:
            tasks_out = []
            for event, tid, name, prompt in TASKS:
                print(f"  [{event}:{tid}] {name}...", flush=True)
                r = call(args.port, prompt)
                (qdir / f"{event}-{tid}-{name.lower().replace(' ','_')}.json").write_text(json.dumps(r, indent=2))
                tasks_out.append({"event": event, "task": tid, "name": name, **r})
                print(f"    wall={r['wall_s']}s decode={r['decode']:.2f} t/s n={r['predicted_n']}")
            index[key] = {"label": label, "tasks": tasks_out}
            (RESULTS / "index.json").write_text(json.dumps(index, indent=2))
        finally:
            proc.kill(); proc.wait()
    print("\nDone. Responses in", RESULTS)

if __name__ == "__main__":
    main()
