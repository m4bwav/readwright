#!/bin/sh
# macOS/Linux launcher: rw.sh <command> [args]  (same as python3 rw.py)
d=$(cd "$(dirname "$0")" && pwd)
if python3 -c "import sys" >/dev/null 2>&1; then py=python3; else py=python; fi
exec "$py" "$d/rw.py" "$@"
