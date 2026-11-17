#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
test -f .env || cp .env.example .env
make doctor
make init db-up migrate seed
exec make dev
