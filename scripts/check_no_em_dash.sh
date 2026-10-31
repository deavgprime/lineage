#!/usr/bin/env bash
# Fail if any given file contains an em-dash (U+2014).
set -u
dash=$(printf '\342\200\224')
status=0
for f in "$@"; do
  if LC_ALL=C grep -nF -- "$dash" "$f" >/dev/null 2>&1; then
    echo "em-dash found in $f" >&2
    status=1
  fi
done
exit $status
