#!/usr/bin/env bash
# Agon-Bench v2: Resume for remaining 3 models
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${AGON_RESULTS_DIR:-$HOME/Documents/agon-results}"

MODELS=(
  "qwen35-base:Qwen3.5-9B Base:8084"
  "omnicoder-9b:OmniCoder-9B:8083"
  "lfm2.5-8b:LFM2.5-8B-A1B:8096"
)

mkdir -p "$RESULTS_DIR"

for model_entry in "${MODELS[@]}"; do
  IFS=':' read -r name label port <<< "$model_entry"
  
  echo ""
  echo "=============================================="
  echo "  MODEL: $label ($name)"
  echo "=============================================="
  
  echo "  Switching to $name..."
  ~/.local/bin/local-llm "$name" 2>&1 || {
    echo "  [ERROR] Failed to switch to $name, skipping..."
    continue
  }
  
  echo "  Waiting for server on port $port..."
  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$port/v1/models" > /dev/null 2>&1; then
      echo "  Server ready."
      break
    fi
    sleep 2
  done
  
  for run in 1 2 3; do
    echo ""
    echo "  --- Run $run/3 ---"
    
    echo "  [Agent v2] Starting..."
    python3 "$SCRIPT_DIR/agent-event.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/agent/run$run" \
      --run "$run" 2>&1 | tail -10
    
    echo "  [Reason v2] Starting..."
    python3 "$SCRIPT_DIR/reason-event-v2.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/reason/run$run" \
      --run "$run" 2>&1 | tail -10
    
    echo "  [Code v2] Starting..."
    python3 "$SCRIPT_DIR/code-event.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/code/run$run" \
      --run "$run" 2>&1 | tail -10
  done
  
  echo "  Completed all 3 runs for $label"
done

echo ""
echo "=============================================="
echo "  RESUME COMPLETE"
echo "=============================================="
