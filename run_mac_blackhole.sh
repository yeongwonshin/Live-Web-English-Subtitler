#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD/src"
python -m autosub --source blackhole --language en --model base.en --show-levels "$@"
