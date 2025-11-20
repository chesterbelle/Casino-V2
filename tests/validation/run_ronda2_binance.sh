#!/bin/sh
set -euo pipefail

# Ronda 2 - Binance (30 velas)
ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

echo "[ronda2] Iniciando Ronda 2 (Binance)"

# Run demo (30 minutes approx -> 30 velas 1m)
./.venv/bin/python main.py --mode=demo --player=paroli --duration=30m --symbol=BTC/USDT --interval=1m || true

# Download historical data
python tests/validation/download_historical_data.py --exchange binance --symbol BTC/USDT --interval 1m --limit 200 --out data/validation/historical_ronda2.csv || echo "[ronda2] download failed"

# Backtest
./.venv/bin/python main.py --mode=backtest --player=paroli --data=data/validation/historical_ronda2.csv --initial-balance=10000 || true

# Compare
python tests/validation/compare_results.py --demo-log logs/demo_*.json --backtest-log logs/backtest_*.json --out logs/comparison_ronda2.txt || echo "[ronda2] compare failed"

echo "[ronda2] Finalizado"
exit 0
