#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
if [[ ! -f .env && -z ${DATABASE_URL:-} ]]; then
  ./AgroTrack --setup
fi
exec ./AgroTrack --open-browser
