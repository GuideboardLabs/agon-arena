#!/usr/bin/env python3
"""Export the ranked board to results/agon-bench-results.json (schema v2).

Reuses dashboard-server's get_model_data() so the JSON, the board and the
README all derive from one scoring path: completeness gate, flagged rows,
normalized maxima, components rounded before the total.
"""
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ARENA = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import importlib.util

spec = importlib.util.spec_from_file_location("dashboard_server", os.path.join(HERE, "dashboard-server.py"))
ds = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ds)


def main():
    rows = ds.get_model_data()
    models = []
    for r in rows:
        models.append({
            "key": r["key"],
            "model": r["label"],
            "size_gb": round(r.get("size_gb") or 0, 2),
            "quant": r.get("quant") or "",
            "agent": round(r["agent"], 2),
            "agent_max": 24,
            "code": round(r["code"], 2),
            "code_max": 25,
            "reason": round(r["reason"], 2),
            "reason_max": 17,
            "total": round(r["total"], 2),
            "max": 66,
            "pct": round(r["total"] / 66 * 100, 2),
            "tok_s": round(r.get("tok_s") or 0, 1),
            "reference_only": bool(r.get("flagged")),
        })

    # rank on total, high to low; ties broken by label
    models.sort(key=lambda m: (-m["total"], m["model"]))
    for i, m in enumerate(models, 1):
        m["rank"] = i

    out = {
        "schema": "agon-bench/results-v2",
        "generated": date.today().isoformat(),
        "bench": "Agon-Bench v2",
        "max_score": 66,
        "hardware": "AMD RX 5700 XT 8GB (RDNA1), Ryzen 5 1600, 32GB RAM, llama.cpp Vulkan",
        "protocol": {
            "runs_per_event": 3,
            "ctx": {"agent": 4096, "code": 16384, "reason": 4096},
            "temperature": 0.3,
            "seed_sent": False,
        },
        "models": models,
    }

    path = os.path.join(ARENA, "results", "agon-bench-results.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
        f.write("\n")

    # self-check: every row must add up exactly as printed
    bad = [m for m in models if round(m["agent"] + m["code"] + m["reason"], 2) != m["total"]]
    print(f"wrote {path}: {len(models)} models, {sum(1 for m in models if m['reference_only'])} flagged")
    print("top 5:", ", ".join(f"{m['model']} {m['total']:.2f}" for m in models[:5]))
    if bad:
        print("FAIL: rows that do not reconcile:", [m["model"] for m in bad])
        sys.exit(1)


if __name__ == "__main__":
    main()
