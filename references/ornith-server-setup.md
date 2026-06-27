# Ornith-1.0-9B Server Setup

## Status (June 26, 2026)

Ornith-1.0-9B (Q4_K_M) is available on disk but has NO systemd service. It must be started manually for benchmark runs.

## Manual Start

```bash
/home/sc/llama.cpp/build-vulkan/bin/llama-server \
  -m /home/sc/models/ornith-1.0-9b-Q4_K_M.gguf \
  --alias ornith-1.0-9b \
  -c 32768 \
  -np 1 \
  -ngl 99 \
  -ctk q8_0 \
  -ctv q8_0 \
  -fa on \
  --threads 8 \
  --threads-batch 12 \
  --jinja \
  --reasoning off \
  --no-mmproj \
  --timeout 1800 \
  --host 0.0.0.0 \
  --port 8094
```

## Model File

- **Path:** `/home/sc/models/ornith-1.0-9b-Q4_K_M.gguf`
- **Source:** `deepreinforce-ai/Ornith-1.0-9B-GGUF` on Hugging Face
- **Quant:** Q4_K_M
- **Size:** ~5.3GB

## Performance (RX 5700 XT, Vulkan)

Measured ~47 tok/s on code/agent tasks. Fastest model in the 8-9B tier on this hardware.

## TODO

- [ ] Create systemd user service at `~/.config/systemd/user/local-llm-ornith.service`
- [ ] Register in `~/.config/local-llm/models.json`
- [ ] Add to `local-llm` switcher
