#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

export SPM_ENV=${SPM_ENV:-development}
export SPM_DEBUG=${SPM_DEBUG:-1}
export PYTHONPATH="$PWD"
export PORT=${PORT:-5001}

python src/backend/app.py
