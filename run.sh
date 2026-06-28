#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD/src"
python -m autosub --source auto --language en --model base.en "$@"
