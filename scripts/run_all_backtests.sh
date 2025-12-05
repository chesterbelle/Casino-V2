#!/bin/bash
# Multi-Strategy Backtest Runner
# Runs backtest.py for each strategy and collects results

DATA_FILE="data/raw/LTCUSDT_1m__30d.csv"
SYMBOL="LTC/USDT:USDT"
RESULTS_FILE="state/backtest_results_$(date +%Y%m%d_%H%M%S).txt"

STRATEGIES=(
    "TrendRider"
    "MeanReverter"
    "BreakoutHunter"
    "QuickScalper"
    "SmartMoneyFollower"
    "PatternTrader"
    "AlphaEdge"
    "SynergyFlow"
)

echo "========================================"
echo "🎰 CASINO-V3 MULTI-STRATEGY BACKTEST"
echo "========================================"
echo "Dataset: $DATA_FILE"
echo "Symbol: $SYMBOL"
echo "Strategies: ${#STRATEGIES[@]}"
echo "========================================"
echo ""

# Create results file
echo "CASINO-V3 BACKTEST RESULTS - $(date)" > $RESULTS_FILE
echo "Dataset: $DATA_FILE" >> $RESULTS_FILE
echo "========================================" >> $RESULTS_FILE

for i in "${!STRATEGIES[@]}"; do
    STRATEGY="${STRATEGIES[$i]}"
    echo ""
    echo "[$((i+1))/${#STRATEGIES[@]}] Testing $STRATEGY..."

    # Update strategy in Python
    python3 -c "
from config.strategies import STRATEGIES
# Disable all
for name in STRATEGIES:
    STRATEGIES[name]['enabled'] = False
# Enable target
STRATEGIES['$STRATEGY']['enabled'] = True
print(f'✅ Enabled: $STRATEGY')
"

    # Run backtest and capture output
    echo "--- $STRATEGY ---" >> $RESULTS_FILE
    python backtest.py --data=$DATA_FILE --symbol="$SYMBOL" 2>&1 | tee -a $RESULTS_FILE | tail -15
    echo "" >> $RESULTS_FILE
done

echo ""
echo "========================================"
echo "📊 All backtests complete!"
echo "Results saved to: $RESULTS_FILE"
echo "========================================"
