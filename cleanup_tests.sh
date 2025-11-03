#!/bin/bash

# Navigate to project root
cd /home/pedro/ProyectosGITHUB/Casino-V2

echo "=== Cleaning up test files in root directory ==="
# Remove all test_*.py files from root directory
rm -f test_*.py

# Remove any other test files that might have been missed
rm -f *_test.py

echo "=== Cleaning up redundant test files in tests/ directory ==="
# Remove redundant test files
rm -f tests/test_core_architecture.py
rm -f tests/test_mejoras_futurechanges.py
rm -f tests/test_websocket_integration.py
rm -f tests/test_websocket_live.py

# Rename files to match our structure
if [ -f "tests/test_table_backtest_multiasset.py" ]; then
    mv tests/test_table_backtest_multiasset.py tests/test_backtest.py
fi

if [ -f "tests/test_core_integration.py" ]; then
    mv tests/test_core_integration.py tests/test_integration.py
fi

if [ -f "tests/test_new_sensors.py" ]; then
    mv tests/test_new_sensors.py tests/test_sensors.py
fi

echo "=== Final test structure ==="
ls -la tests/
