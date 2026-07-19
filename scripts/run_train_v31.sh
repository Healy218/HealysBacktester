#!/usr/bin/env bash
# v3.1 training launcher: full train_meta grid + exit marker for the watcher.
cd /home/mrhea/HealysBacktester
export NN_META_POOL=v31
./venv/bin/python -m nn_meta.train_meta > v31_train.log 2>&1 \
  && echo "TRAIN-EXIT:0" >> v31_train.log \
  || echo "TRAIN-EXIT:1" >> v31_train.log
