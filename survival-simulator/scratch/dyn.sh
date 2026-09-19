#!/bin/bash
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24)
for v in nocap dyn; do
  $PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_$v:Hivemind > scratch/${v}_full.txt 2>&1
  grep POLICY scratch/${v}_full.txt >> scratch/dyn.log
done
echo done >> scratch/dyn.log
$PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_dyn200:Hivemind > scratch/dyn200_full.txt 2>&1
grep POLICY scratch/dyn200_full.txt >> scratch/dyn.log
echo done2 >> scratch/dyn.log
