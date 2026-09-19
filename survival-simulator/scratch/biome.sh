#!/bin/bash
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
until grep -q "^done" scratch/day2.log; do sleep 60; done
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24)
$PY evaluate.py --seeds $S --repeat 2 --workers 12 --policy scratch.hm_biome:Hivemind > scratch/biome_full.txt 2>&1
grep POLICY scratch/biome_full.txt >> scratch/day2.log; echo "biome done $(date)" >> scratch/day2.log
