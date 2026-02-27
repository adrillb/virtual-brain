#!/usr/bin/env bash
# ------------------------------------------------------------------
# Virtual Brain -- Raspberry Pi setup script
# Run once:  chmod +x setup.sh && ./setup.sh
# ------------------------------------------------------------------
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Creating Python virtual environment..."
python3 -m venv .venv

echo "==> Installing dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "==> Created .env file. Edit it now:"
    echo "    nano $SCRIPT_DIR/.env"
    echo ""
else
    echo "==> .env already exists, skipping."
fi

echo "==> Setup complete!"
echo ""
echo "To start the bot:"
echo "    cd $SCRIPT_DIR"
echo "    .venv/bin/python main.py"
echo ""
