#!/usr/bin/env python3
"""Pre-flight for LFM2.5-24B-A2B.

Drives the Agon runner's own start_server() so the real fork selection, the
RDNA1 GGML_VK_DISABLE_HOST_VISIBLE_VIDMEM env, and the systemd scope launch are
all exercised exactly as the benchmark will use them.

Then it inspects one real completion to answer the question the benchmark
depends on: does the open " thinking" tag that the chat template puts at the END
of the prompt get split into reasoning_content, or does it leak into content?
If it leaks, the graders see thinking text and LFM2.5 is scored against its own
scratchpad rather than its answer.
"""
import importlib.util
import json
import os
import time

import httpx

RUNNER = os.path.expanduser("~/Documents/agon-arena/scripts/run-benchmark.py")
KEY = "lfm25_24b_a2b_q4"
PORT = 8171

spec = importlib.util.spec_from_file_location("rb", RUNNER)
rb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rb)

cfg = rb.MODEL_CONFIG[KEY]
print("== config ==")
print("  gguf          :", cfg["gguf"])
print("  exists        :", os.path.exists(cfg["gguf"]))
print("  fork          :", cfg.get("llama_fork"), "->", rb.LLAMA_SERVER_MCPV47)
print("  binary exists :", os.path.exists(rb.LLAMA_SERVER_MCPV47))
print("  scoped launch :", rb.USE_SCOPED_LAUNCH)
print("  server_args   :", cfg["server_args"])
print()


def vram():
    out = {}
    for name, p in (("vram", "/sys/class/drm/card1/device/mem_info_vram_used"),
                    ("gtt", "/sys/class/drm/card1/device/mem_info_gtt_used")):
        try:
            with open(p) as f:
                out[name] = int(f.read().strip()) / 1024 ** 3
        except Exception:
            out[name] = float("nan")
    return out


log_size_before = os.path.getsize(rb.SERVER_LOG) if os.path.exists(rb.SERVER_LOG) else 0
print(f"== starting server on :{PORT} (log at {log_size_before} bytes) ==")
t0 = time.time()
proc = rb.start_server(KEY, PORT)
if proc is None:
    raise SystemExit("start_server returned None - server did not come up")
print(f"== server up in {time.time()-t0:.0f}s ==")
print("  vram=%.2f GiB  gtt=%.2f GiB" % (vram()["vram"], vram()["gtt"]))

# What the loader actually decided about layer placement.
print()
print("== loader decisions from the server log ==")
if os.path.exists(rb.SERVER_LOG):
    with open(rb.SERVER_LOG, "rb") as f:
        f.seek(log_size_before)
        chunk = f.read().decode("utf-8", "replace")
    keep = ("offload", "ncmoe", "n_cpu_moe", "buffer size", "CPU_Mapped", "Vulkan",
            "layer", "type  =", "llama_model_load", "arch", "n_expert", "n_embd")
    for line in chunk.splitlines():
        if any(k.lower() in line.lower() for k in keep):
            print ("  " + line.strip()[:160])

# The actual question: is thinking split out of content?
print()
print("== reasoning split probe ==")
msgs = [{"role": "user", "content": "Reply with exactly the word: ready"}]
body = {"model": KEY, "messages": msgs, "max_tokens": 200, "temperature": 0.0,
        "stream": False}
r = httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions", json=body, timeout=300)
print("  HTTP", r.status_code)
d = r.json()
msg = d["choices"][0]["message"]
print("  message keys      :", sorted(msg.keys()))
print("  finish_reason     :", d["choices"][0].get("finish_reason"))
print("  usage             :", d.get("usage"))
rc = msg.get("reasoning_content")
print("  reasoning_content :", None if rc is None else f"{len(rc)} chars")
print("  content len       :", len(msg.get("content") or ""))
print("  content repr      :", repr((msg.get("content") or "")[:300]))
if rc:
    print("  reasoning repr    :", repr(rc[:200]))
print()
print("  FULL MESSAGE:")
print(json.dumps(msg, indent=2)[:2500])
print()
print("  vram=%.2f GiB  gtt=%.2f GiB" % (vram()["vram"], vram()["gtt"]))
print()
print(f"== server left RUNNING on :{PORT} for the sweep; stop with:  "
      f"systemctl --user stop agon-llama-{PORT}.scope ==")
