#!/usr/bin/env bash
# Agon-Bench: Full 3-Run Matrix Runner
# Runs all 3 events × 3 runs for a single model, then moves to the next.
# Usage: bash run-agon-full.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="${AGON_RESULTS_DIR:-$HOME/agon-arena/results}"
MODELS=(
  "gemma4-12b:Gemma4-12B QAT:8094"
  "ornith-1.0-9b:Ornith-1.0-9B:8095"
  "lfm2.5-8b:LFM2.5-8B-A1B:8096"
)

mkdir -p "$RESULTS_DIR"

for model_entry in "${MODELS[@]}"; do
  IFS=':' read -r name label port <<< "$model_entry"
  
  echo ""
  echo "=============================================="
  echo "  MODEL: $label ($name)"
  echo "=============================================="
  
  # Switch to this model (stops current, starts new)
  echo "  Switching to $name..."
  ~/.local/bin/local-llm "$name" 2>&1 || {
    echo "  [ERROR] Failed to switch to $name, skipping..."
    continue
  }
  
  # Wait for server to be fully ready
  echo "  Waiting for server on port $port..."
  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:$port/v1/models" > /dev/null 2>&1; then
      echo "  Server ready."
      break
    fi
    sleep 2
  done
  
  # Run 3 runs of each event
  for run in 1 2 3; do
    echo ""
    echo "  --- Run $run/3 ---"
    
    # Code event
    echo "  [Code] Starting..."
    python3 "$SCRIPT_DIR/code-event.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/code/run$run" \
      --run "$run" 2>&1 | tail -5
    
    # Agent event
    echo "  [Agent] Starting..."
    python3 "$SCRIPT_DIR/agent-event.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/agent/run$run" \
      --run "$run" 2>&1 | tail -5
    
    # Reason event
    echo "  [Reason] Starting..."
    python3 "$SCRIPT_DIR/reason-event.py" \
      --model-url "http://127.0.0.1:$port" \
      --model "$name" \
      --output "$RESULTS_DIR/$name/reason/run$run" \
      --run "$run" 2>&1 | tail -5
  done
  
  echo "  Completed all 3 runs for $label"
done

echo ""
echo "=============================================="
echo "  ALL MODELS COMPLETE"
echo "  Results: $RESULTS_DIR/"
echo "=============================================="
