#!/bin/sh
# POP_CAP schedule sweep: one policy copy per variant, 24 seeds each, results in scratch/cap_<name>.txt
# usage: sh scratch/cap_sweep.sh   (from survival-simulator/)
PY="C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator/.venv/Scripts/python.exe"
while IFS='|' read -r name cap; do
  grep -q "^POLICY" "scratch/cap_$name.txt" 2>/dev/null && continue   # already finished
  sed "s/^POP_CAP = .*/POP_CAP = $cap/" src/utils/controllers/simple_policy.py > "scratch/sp_cap_$name.py"
  grep -qF "POP_CAP = $cap" "scratch/sp_cap_$name.py" || { echo "sed failed for $name"; exit 1; }
  "$PY" evaluate.py --seeds $(seq 1 24) --workers 12 --policy "scratch.sp_cap_$name:Hivemind" > "scratch/cap_$name.txt" 2> "scratch/cap_$name.err"
  tail -1 "scratch/cap_$name.txt"
done <<'VARIANTS'
base|[(0, 12), (600, 12), (1800, 5)]
flat8|[(0, 8)]
flat10|[(0, 10)]
flat12|[(0, 12)]
flat14|[(0, 14)]
down10_5|[(0, 10), (600, 10), (1800, 5)]
down12_3|[(0, 12), (600, 12), (1800, 3)]
taper_early|[(0, 12), (300, 12), (1200, 5)]
taper_late|[(0, 12), (1200, 12), (2400, 5)]
up8_14|[(0, 8), (600, 8), (1800, 14)]
up6_12|[(0, 6), (900, 12)]
VARIANTS
echo SWEEP DONE
