#!/bin/zsh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$HERE/MemoryBox-CLI" ]; then
  "$HERE/MemoryBox-CLI" model-install
elif command -v memorybox >/dev/null 2>&1; then
  memorybox model-install
else
  python3 "$HERE/../memorybox_main.py" model-install
fi
read "?Neural model installation finished. Press Return to close."
