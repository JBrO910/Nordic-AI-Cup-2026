#!/bin/bash
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24)
for v in disperse disperse_pop; do
  echo "$v start $(date)" >> scratch/forage.log
  $PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_$v:Hivemind > scratch/forage_${v}_r2_full.txt 2>&1
  grep POLICY scratch/forage_${v}_r2_full.txt >> scratch/forage.log
done
echo "done3 $(date)" >> scratch/forage.log
