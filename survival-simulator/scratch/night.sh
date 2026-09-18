#!/bin/bash
# Overnight: train flee net v2 (3000 PPO iters from padded v1), then full-game eval v2 vs v1 (24 seeds x 2 passes each).
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24); V2="$PWD/scratch/flee_weights_v2.npz"
echo "train start $(date)" > scratch/night.log
$PY scratch/train_flee.py 3000 resume "$V2" > scratch/flee_train_v2.txt 2>&1
echo "train end $(date); eval v2" >> scratch/night.log
FLEE_WEIGHTS="$V2" $PY evaluate.py --seeds $S --repeat 2 --workers 12 > scratch/night_v2_full.txt 2>&1
echo "eval v1 $(date)" >> scratch/night.log
$PY evaluate.py --seeds $S --repeat 2 --workers 12 > scratch/night_v1_full.txt 2>&1
echo "done $(date)" >> scratch/night.log
grep POLICY scratch/night_v2_full.txt scratch/night_v1_full.txt >> scratch/night.log
