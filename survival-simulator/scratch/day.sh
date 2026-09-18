#!/bin/bash
# In-game flee-net training (60 PPO iters x 20 full games) from the served v1 weights, then a 48-game confirm of the best.
cd "C:/Users/jbro9/Desktop/SDU/Nordic-AI-Cup-2026/survival-simulator"
PY=.venv/Scripts/python.exe; S=$(seq -s ' ' 1 24); OUT="$PWD/scratch/flee_weights_game.npz"
echo "game-train start $(date)" > scratch/day.log
$PY scratch/train_flee_game.py 60 src/utils/controllers/flee_weights.npz "$OUT" > scratch/flee_train_game.txt 2>&1
echo "game-train end $(date); 48-game confirm" >> scratch/day.log
FLEE_WEIGHTS="$OUT" $PY evaluate.py --seeds $S --repeat 2 --workers 12 > scratch/day_game_full.txt 2>&1
echo "done $(date)" >> scratch/day.log
grep POLICY scratch/day_game_full.txt >> scratch/day.log
