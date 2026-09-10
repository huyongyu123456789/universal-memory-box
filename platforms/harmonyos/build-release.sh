#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x ./hvigorw ]]; then
  echo "hvigorw is normally generated/provided by DevEco Studio. Open this project in DevEco Studio 6.1+ and Sync Project first." >&2
  exit 2
fi
./hvigorw --mode project -p product=default -p buildMode=release assembleApp
