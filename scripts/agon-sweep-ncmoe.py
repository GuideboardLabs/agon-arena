#!/usr/bin/env python3
"""Sweep -ncmoe for LFM2.5-24B-A2B and find the VRAM-fit optimum.

The rule (established on the MiniCPM-V 4.7 sibling): the best N is the largest N
whose REMAINING expert weight still fits in VRAM. Past that, experts spill into GTT
and performance collapses. So this walks N downward from "safely all on CPU" toward
"too much on GPU" and reports where it falls off a cliff.

All configs run in ONE process, back to back, on the same 14.5 GB file so the page
cache state is identical between measurements. Decode speed is read from llama.cpp's
own timings.predicted_per_second, not a wall clock I compute.
"""
import json
import os
import subprocess
import time

import httpx

BIN = os.path.expanduser("~/llama-mcpv47/build-vulkan/bin/llama-server")
GGUF = "/mnt/blue/LLMbackups/LFM2.5-24B-A2B-Q4_K_M.gguf"
LOG = "/home/sc/Documents/agon-arena/sweep-stderr.log"
PORT = 8172
PROMPT = ("Write a short technical paragraph explaining why a mixture-of-experts "
          "language model with 64 experts and only 4 active experts can be faster "
          "than a dense model of similar total parameter count.")

SWEEP = [38, 30, 25, 21, 18, 14, 10]


def mem(name):
    try:
        with open(f"/sys/class/drm/card1/device/mem_info_{name}_used") as f:
            return int(f.read().strip()) / 1024 ** 3
    except Exception:
        return float("nan")


def stop(unit):
    subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"],
                   capture_output=True, timeout=60)
    time.sleep(3)


def wait_ready(port, timeout_s=900):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if httpx.get(f"http://127.0.0.1:{port}/v1/models", timeout=5).status_code == 200:
                return time.time() - t0
        except Exception:
            pass
        time.sleep(3)
    return None


def measure(port):
    body = {"prompt": PROMPT, "max_tokens": 256, "temperature": 0.0, "stream": False}
    t0 = time.time()
    r = httpx.post(f"http://127.0.0.1:{port}/v1/completions", json=body, timeout=1800)
    wall = time.time() - t0
    d = r.json()
    tm = d.get("timings") or {}
    usage = d.get("usage") or {}
    return {
        "decode_t_s": tm.get("predicted_per_second"),
        "prefill_t_s": tm.get("prompt_per_second"),
        "n_prompt": usage.get("prompt_tokens"),
        "n_gen": usage.get("completion_tokens"),
        "predicted_ms": tm.get("predicted_ms"),
        "wall_s": wall,
        "text_head": (d["choices"][0]["text"] or "")[:60].replace("\n", " "),
    }


def main():
    results = []
    print(f"{'ncmoe':>6} {'vram_GiB':>9} {'gtt_GiB':>8} {'load_s':>7} "
          f"{'decode_t/s':>11} {'prefill_t/s':>12} {'gen':>4}")
    for n in SWEEP:
        unit = f"agon-sweep-{n}"
        stop(unit)
        env = dict(os.environ, GGML_VK_DISABLE_HOST_VISIBLE_VMID="1",
                   GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM="1")
        cmd = [
            "systemd-run", "--user", "--scope", f"--unit={unit}",
            "--property=MemoryAccounting=yes", "--collect",
            BIN, "--model", GGUF, "--port", str(PORT), "--host", "0.0.0.0",
            "--no-warmup", "-ngl", "999", "-fa", "on", "-ncmoe", str(n),
            "-c", "16384", "--threads", "6", "--threads-batch", "6",
            "--cpu-mask", "0x3f", "--prio", "2", "--jinja",
            "--temp", "0.0", "--parallel", "1",
        ]
        with open(LOG, "ab") as lf:
            lf.write(f"\n\n===== ncmoe {n} =====\n".encode())
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=lf,
                                 env=env, preexec_fn=os.setsid)
        load_s = wait_ready(PORT)
        if load_s is None:
            print(f"{n:>6}  FAILED TO START")
            subprocess.run(["systemctl", "--user", "stop", f"{unit}.scope"],
                           capture_output=True, timeout=60)
            results.append({"ncmoe": n, "failed": True})
            continue
        v, g = mem("vram"), mem("gtt")
        m = measure(PORT)
        print(f"{n:>6} {v:>9.2f} {g:>8.2f} {load_s:>7.0f} "
              f"{m['decode_t_s'] or 0:>11.2f} {m['prefill_t_s'] or 0:>12.1f} "
              f"{m['n_gen'] or 0:>4}")
        results.append({"ncmoe": n, "vram": v, "gtt": g, "load_s": load_s, **m})
        stop(unit)

    out = "/home/sc/.hermes/cache/scratch/lfm25-ncmoe-sweep.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print("\nsaved:", out)

    ok = [r for r in results if not r.get("failed") and r.get("decode_t_s")]
    if ok:
        best = max(ok, key=lambda r: r["decode_t_s"])
        print(f"\nBEST: -ncmoe {best['ncmoe']}  "
              f"{best['decode_t_s']:.2f} t/s decode, "
              f"vram {best['vram']:.2f} GiB, gtt {best['gtt']:.2f} GiB")
    print("all servers stopped")


if __name__ == "__main__":
    main()
