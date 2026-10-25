#!/bin/zsh
# run_all.sh — renders the Python parts of the hurricane video one after the other (at most 2 processes: 8 GB of RAM), then composes.
# The view3d part (rec_job.js) must already be in ~/gta6_hurricane_work/rec.
set -e
cd "$(dirname "$0")"
PY=/usr/local/bin/python3
nice $PY arrival_hi.py | tail -3
nice $PY space.py | tail -1
nice $PY ground2.py
( nice $PY topdown.py B 1 2 0 | tail -1 ) & ( nice $PY topdown.py B 1 2 1 | tail -1 ) & wait
( nice $PY topdown.py D 1 2 0 | tail -1 ) & ( nice $PY topdown.py D 1 2 1 | tail -1 ) & wait
nice $PY compose.py | tail -2
