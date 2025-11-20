#!/bin/sh
set -euo pipefail

# Ronda 3 - Binance (60 velas)
ROOT_DIR=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT_DIR"

echo "[ronda3] Iniciando Ronda 3 (Binance)"

# Run demo using uniform flags (60 velas)
./.venv/bin/python main.py --mode=demo --exchange=binance --player=paroli --symbol=LTC/USDT:USDT --interval=1m --max-candles=60 || true

# Download historical data
python tests/validation/download_historical_data.py --exchange binance --symbol BTC/USDT --interval 1m --limit 500 --out data/validation/historical_ronda3.csv || echo "[ronda3] download failed"

# Backtest
./.venv/bin/python main.py --mode=backtest --player=paroli --data=data/validation/historical_ronda3.csv --initial-balance=10000 || true

# Compare
python tests/validation/compare_results.py --demo-log logs/demo_*.json --backtest-log logs/backtest_*.json --out logs/comparison_ronda3.txt || echo "[ronda3] compare failed"

echo "[ronda3] Finalizado"
exit 0
