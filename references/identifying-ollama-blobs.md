# Orphaned Blobs in Ollama Cache

## Problem

Ollama stores model weights as opaque SHA256-named blobs in `/usr/share/ollama/.ollama/models/blobs/`. A 20GB blob like `sha256-6f5c72e2...` gives no indication of which model it belongs to. Orphaned blobs (not referenced by any manifest) waste disk space.

## Identification Method

1. **List blobs sorted by size:**
   ```bash
   ls -lh /usr/share/ollama/.ollama/models/blobs/ | sort -k5 -h | tail -20
   ```

2. **List manifests to see which models are registered:**
   ```bash
   find /usr/share/ollama/.ollama/models/manifests -type f
   ```

3. **Read each manifest to find which blob it references:**
   ```bash
   cat /usr/share/ollama/.ollama/models/manifests/registry.ollama.ai/library/<model>/<tag> | python3 -m json.tool
   ```
   The `layers[0].digest` field (e.g. `sha256:6f5c72e2...`) maps to the blob filename.

4. **Find orphaned blobs** — blobs not referenced by any manifest. Cross-reference all `digest` values from all manifests against the blob directory.

## Example from June 26, 2026

| Blob | Size | Identity | Status |
|------|:----:|:---------|:-------|
| `sha256-6f5c72e2...` | 20GB | Qwen3.6-35B-A3B (35B MoE, 3B active) | Referenced by `qwen3.6-35b-a3b:latest` |
| `sha256-d797b531...` | 17GB | Orphaned — no manifest references it | Leftover from interrupted/failed pull |

Both were deleted (37GB freed). The 35B model won't fit in 8GB VRAM even at Q4.

## Deletion

Files are owned by `ollama:ollama` and require sudo:
```bash
sudo rm -v /usr/share/ollama/.ollama/models/blobs/<sha256-hash>
```
