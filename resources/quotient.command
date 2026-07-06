#!/bin/bash

set -e

# ── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}✔ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
fail() { echo -e "${RED}✖ $1${NC}"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo "  www.quotech.co – Copyright (c) 2026 Nicholas Stewart"
echo "  ─────────────────────────────────────────────────────"
echo ""

# ── 1. Check Python 3 ────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  fail "python3 not found. Install it via: brew install python"
fi

PYTHON_VERSION=$(python3 --version 2>&1)
log "Found $PYTHON_VERSION"

# ── 2. Create virtual environment ────────────────────────────────────────────
if [ -d "$VENV_DIR" ]; then
  warn "Virtual environment already exists – skipping creation"
else
  python3 -m venv "$VENV_DIR"
  log "Created virtual environment at .venv"
fi

# ── 3. Activate venv ─────────────────────────────────────────────────────────
source "$VENV_DIR/bin/activate"
log "Activated virtual environment"

# ── 4. Upgrade pip (quietly) ─────────────────────────────────────────────────
pip install --upgrade pip --quiet
log "pip up to date"

# ── 5. Install dependencies ──────────────────────────────────────────────────
REQUIREMENTS="$SCRIPT_DIR/app/requirements.txt"

if [ ! -f "$REQUIREMENTS" ]; then
  fail "requirements.txt not found in $SCRIPT_DIR"
fi

pip install -r "$REQUIREMENTS" --quiet
log "Dependencies installed from requirements.txt"

# ── 6. Run project ───────────────────────────────────────────────────────────
ENTRY="$SCRIPT_DIR/app/quotient.py"

if [ ! -f "$ENTRY" ]; then
  fail "quotient.py not found in $SCRIPT_DIR"
fi

echo ""
echo "────────────────────────────────────"
log "Starting quotient.py …"
echo "────────────────────────────────────"
echo ""

python3 "$ENTRY"
