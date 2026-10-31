#!/usr/bin/env bash
# Fail if any given file contains a character the project does not use in text.
set -u
dash=$(printf '\342\200\224')
status=0
for f in "$@"; do
  if LC_ALL=C grep -nF -- "$dash" "$f" >/dev/null 2>&1; then
    echo "disallowed punctuation in $f" >&2
    status=1
  fi
done
exit $status
