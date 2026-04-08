#!/usr/bin/env bash
# wisdomGraph CI — unit tests (no Neo4j required)
set -euo pipefail

echo "==> Creating venv"
python3 -m venv .venv
source .venv/bin/activate

echo "==> Installing dependencies"
pip install pytest -q

echo "==> Running tests"
python -m pytest tests/ -q

echo "==> All tests passed"
