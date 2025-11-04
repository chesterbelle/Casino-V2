#!/bin/bash
# Monitor testing mode progress

echo "🔍 Monitoreando testing mode..."
echo "================================"
echo ""

# Show last 20 lines with key events
tail -f testing_30_candles.log | grep -E "(New candle|signal|Order built|Order executed|TP/SL configured|Creating order|Error|Session completed)" --line-buffered
