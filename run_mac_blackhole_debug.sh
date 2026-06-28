#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD/src"
# Debug mode: shows RMS levels. Add --print-captions only when you intentionally want terminal captions.
python -m autosub --source blackhole --language en --model base.en --show-levels "$@"
