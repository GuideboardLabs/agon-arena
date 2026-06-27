# Capturing Throughput from llama.cpp Server Logs

## The problem

The summary.json files record `response_length` (character count) and `elapsed_seconds` (wall clock). **Dividing these gives chars/s, not tok/s** — and elapsed_seconds includes prompt processing, network latency, and queue wait time, not just generation.

Reporting chars/s as tok/s is wrong and will be caught.

## Correct approach: parse server timing

llama.cpp's server prints generation timing after each completion:

```
I slot print_timing: id  0 | task 42629 |        eval time =    1934.14 ms /   100 tokens (   19.34 ms per token,    51.70 tokens per second)
```

The key fields: `predicted_n` (tokens generated), `predicted_ms` (generation time), `predicted_per_second` (tokens/sec).

## Capturing from server stdout

If the server is running in a systemd service:

```bash
journalctl --user -u model-name.service --since "5 min ago" --no-pager | grep 'print_timing' | grep 'predicted'
```

If running in a terminal session, grep the output file.

## Capturing from the API response

The `/v1/chat/completions` response includes a `timings` object:

```json
"timings": {
  "predicted_n": 100,
  "predicted_ms": 1934.137,
  "predicted_per_token_ms": 19.34,
  "predicted_per_second": 51.70
}
```

The benchmark runner scripts can capture this by parsing the full response JSON instead of just `choices[0].message.content`.

## If you must estimate from summary.json

```python
# Rough estimate only — use actual server timing when possible
chars = task["response_length"]
elapsed = task["elapsed_seconds"]
# Subtract ~2s for prompt processing (varies by model/prompt length)
gen_time = max(elapsed - 2, 1)
# Average ~4 chars per token for English text + code
estimated_tok_s = (chars / 4) / gen_time
```

This is still an estimate. Prefer actual server timing.

## Measured throughput on this hardware (RX 5700 XT, 8GB VRAM, Vulkan)

| Model | Quant | tok/s | Notes |
|-------|-------|:-----:|-------|
| Gemma4-12B QAT | UD-Q4_K_XL | ~22 | q8_0 KV cache, 8192 ctx |
| Ornith-1.0-9B | Q4_K_M | ~47 | Fastest in 8-9B tier |
| LFM2.5-8B-A1B | UD-Q4_K_XL | ~105 | Verbose thinking traces inflate char count |
| Jackrong Qwen3.5-9B | Q4_K_M | ~33 | Comparable to Qwen3.5 baseline |
