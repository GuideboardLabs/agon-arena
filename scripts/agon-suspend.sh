#!/bin/bash
# Suspend the production services that compete with a local benchmark run.
# BINDING RULE: one model process at a time. Restore with agon-restore.sh.
# jacquard-status (:8195) is deliberately LEFT UP so the command center stays watchable.
set -u
UNIT_LIST="jacquard-image jacquard-decision jacquard-lfm jacquard-voice qwen21-rater qwen21-rater2 qwen21-rater3 qwen21-rater4"
STATE="$HOME/.local/state/agon-suspended.json"
echo "[]" > "$STATE"

echo "suspending production services:"
for s in $UNIT_LIST; do
  before=$(systemctl --user is-active "$s.service" 2>/dev/null)
  if [ "$before" = "active" ]; then
    systemctl --user stop "$s.service" 2>/dev/null
    after=$(systemctl --user is-active "$s.service" 2>/dev/null)
    if [ "$after" != "active" ]; then
      python3 - "$STATE" "$s" <<'PY'
import json,sys
p,unit=sys.argv[1],sys.argv[2]
d=json.load(open(p)); d.append(unit); json.dump(d,open(p,"w"))
PY
      printf '  %-20s %s -> %s  SUSPENDED\n' "$s" "$before" "$after"
    else
      printf '  %-20s %s -> %s  FAILED TO STOP\n' "$s" "$before" "$after"
    fi
  else
    printf '  %-20s was %s (not touched)\n' "$s" "$before"
  fi
done

echo
echo "waiting for VRAM/GTT to drain (GPU memory is released lazily):"
for i in $(seq 1 30); do
  v=$(cat /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo 0)
  g=$(cat /sys/class/drm/card1/device/mem_info_gtt_used 2>/dev/null || echo 0)
  vi=$(echo "$v/1073741824" | bc -l); gi=$(echo "$g/1073741824" | bc -l)
  printf '\r  t=%2ss  vram=%.2fGiB gtt=%.2fGiB' "$((i*2))" "$vi" "$gi"
  ok=$(echo "$vi < 0.5 && $gi < 1.0" | bc -l)
  [ "$ok" = "1" ] && { echo "  -> drained"; break; }
  sleep 2
done
echo
echo "suspended units recorded in $STATE:"
cat "$STATE"; echo
free -g | sed 's/^/  /'
