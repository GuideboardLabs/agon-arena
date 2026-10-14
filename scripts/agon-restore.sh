#!/bin/bash
# Restore exactly the units agon-suspend.sh stopped. Reads the recorded list so
# nothing is re-enabled that was already intentionally off.
set -u
STATE="$HOME/.local/state/agon-suspended.json"
if [ ! -f "$STATE" ]; then
  echo "no suspend state at $STATE - nothing to restore"; exit 0
fi
echo "restoring production services:"
python3 - "$STATE" <<'PY' > /tmp/agon-restore-list.txt
import json,sys
print(" ".join(json.load(open(sys.argv[1]))))
PY
LIST=$(cat /tmp/agon-restore-list.txt)
if [ -z "${LIST// }" ]; then echo "  (list empty)"; else
  for s in $LIST; do
    systemctl --user start "$s.service" 2>/dev/null
    st=$(systemctl --user is-active "$s.service" 2>/dev/null)
    printf '  %-20s -> %s\n' "$s" "$st"
  done
fi
echo "[]" > "$STATE"

echo
echo "waiting for jacquard services to answer:"
for i in $(seq 1 40); do
  ok=0
  curl -s -o /dev/null -m 3 -w '' http://127.0.0.1:8195/ 2>/dev/null && ok=$((ok+1))
  curl -s -o /dev/null -m 3 -w '' http://127.0.0.1:8191/ 2>/dev/null && ok=$((ok+1))
  printf '\r  t=%2ss  responsive endpoints: %s/2' "$((i*3))" "$ok"
  [ "$ok" -ge 2 ] && { echo "  -> up"; break; }
  sleep 3
done
echo
echo "final state:"
for s in jacquard-image jacquard-decision jacquard-lfm jacquard-voice jacquard-status qwen21-rater qwen21-rater2 qwen21-rater3 qwen21-rater4; do
  printf '  %-20s %s\n' "$s" "$(systemctl --user is-active $s.service 2>/dev/null)"
done
free -g | sed 's/^/  /'
