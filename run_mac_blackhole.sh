#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$PWD/src"
# Low-latency user mode: captions appear only in the overlay, never in the terminal.
# Use tiny.en by default for better audio/video sync on MacBook CPU. Override with --model base.en for accuracy.
python -m autosub \
  --source blackhole \
  --language en \
  --model tiny.en \
  --beam-size 1 \
  --min-chunk-seconds 0.55 \
  --partial-chunk-seconds 0.9 \
  --partial-overlap-seconds 0.25 \
  --max-chunk-seconds 1.6 \
  --silence-hold-seconds 0.22 \
  --transcriber-queue-size 1 \
  --subtitle-ttl 3.0 \
  "$@"
