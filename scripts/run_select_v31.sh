#!/usr/bin/env bash
# v3.1 selection launcher: select_meta + exit marker for the watcher.
cd "$(dirname "$(readlink -f "$0")")/.."
export NN_META_POOL=v31
./venv/bin/python -m nn_meta.select_meta > v31_select.log 2>&1 \
  && echo "SELECT-EXIT:0" >> v31_select.log \
  || echo "SELECT-EXIT:1" >> v31_select.log
