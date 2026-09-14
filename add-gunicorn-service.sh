#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# Backward-compatibility wrapper -> redirects to 'hdg'
# ──────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/hdg" "$@"