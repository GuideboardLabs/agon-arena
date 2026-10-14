#!/usr/bin/env python3
"""Quick speed test: send a prompt, measure tok/s for N tokens."""
import json, sys, time, urllib.request, urllib.error

PROMPT = "Write a detailed explanation of how speculative decoding works in large language models, including the different approaches like draft models, MTP heads, and ngram caches. Cover the tradeoffs of each approach."
N_TOKENS = 512
URL = "http://127.0.0.1:8100/v1/completions"

def test(label):
    payload = json.dumps({
        "prompt": PROMPT,
        "n_predict": N_TOKENS,
        "temperature": 0.0,
        "cache_prompt": False,
    }).encode()
    req = urllib.request.Request(URL, data=payload, headers={"Content-Type": "application/json"})
    start = time.time()
    try:
        resp = urllib.request.urlopen(req, timeout=300)
        data = json.loads(resp.read())
        elapsed = time.time() - start
        generated = data.get("tokens_generated", 0) or data.get("usage", {}).get("completion_tokens", 0)
        tok_s = generated / elapsed if elapsed > 0 else 0
        print(f"{label}: {generated} tokens in {elapsed:.1f}s = {tok_s:.1f} tok/s")
        return tok_s
    except Exception as e:
        print(f"{label}: ERROR - {e}")
        return 0

if __name__ == "__main__":
    test(sys.argv[1] if len(sys.argv) > 1 else "test")
