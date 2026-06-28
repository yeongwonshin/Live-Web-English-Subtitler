#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD/src"
# User mode: captions appear only in the overlay, never in the terminal.
python -m autosub --source blackhole --language en --model base.en "$@"
