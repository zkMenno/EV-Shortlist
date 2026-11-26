#!/bin/sh
# T-158 / T-165 (G-52, G-59, G-54, G-63): is PR <n> safe to merge right now? Run it as its own step, right
# before the merge command, never chained to it. Exit 0 = ready, 1 = not ready, 2 = GitHub error.
#   sh scripts/merge_ready.sh 195
exec python3 "$(dirname "$0")/merge_ready.py" "$@"
