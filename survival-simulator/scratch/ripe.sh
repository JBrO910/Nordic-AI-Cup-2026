#!/bin/bash
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24)
for v in ripe_pop12 ripe_pop16; do
  $PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_$v:Hivemind > scratch/${v}_full.txt 2>&1
  grep POLICY scratch/${v}_full.txt >> scratch/ripe.log
done
echo done >> scratch/ripe.log
$PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_avoid:Hivemind > scratch/avoid_full.txt 2>&1
grep POLICY scratch/avoid_full.txt >> scratch/ripe.log
echo done2 >> scratch/ripe.log
