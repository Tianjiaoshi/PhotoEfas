#!/bin/bash
# PhotoEfas - One-click startup script

set -e

echo "========================================"
echo "  PhotoEfas - Image Watermark System"
echo "  SM2 + RSA Hybrid Encryption"
echo "========================================"
echo

cd "$(dirname "$0")"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found. Please install Python 3.10+"
    exit 1
fi

if [ ! -f "venv/bin/python" ]; then
    echo "[1/3] Creating virtual environment..."
    "$PYTHON" -m venv venv
fi

echo "[2/3] Installing dependencies..."
venv/bin/pip install -q -r requirements.txt 2>/dev/null

echo "[3/3] Initializing database..."
venv/bin/python init_db.py

echo
echo "========================================"
echo "  URL:   http://localhost:5000"
echo "  Admin: admin / admin123"
echo "  Press Ctrl+C to stop"
echo "========================================"
echo

venv/bin/python run.py
