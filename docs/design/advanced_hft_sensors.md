# Advanced HFT Scalping Sensors Proposal

## Overview
Based on research into high-frequency trading (HFT) and institutional scalping strategies, we propose 4 new sensors designed to capture market microstructure signals using 1-minute candle data.

## 1. VWAP Momentum (Institutional Trend)
**Concept:** VWAP (Volume Weighted Average Price) is the benchmark for institutional execution.
-   **Logic:**
    -   **Bullish:** Price > VWAP AND Price bounces off VWAP (retest).
    -   **Bearish:** Price < VWAP AND Price rejects off VWAP.
-   **Why:** Institutions defend VWAP. Scalping near VWAP offers high R:R.

## 2. Keltner Channel Breakout (Volatility Expansion)
**Concept:** Unlike Bollinger Bands (Standard Deviation), Keltner Channels use ATR.
-   **Logic:**
    -   **Breakout:** Price closes outside the Keltner Channel (2.0 ATR).
    -   **Confirmation:** ADX > 20 (Trend starting).
-   **Why:** Keltner Channels are less prone to "whipsaws" than Bollinger Bands in trending markets.

## 3. Volume Flow Imbalance (OFI Proxy)
**Concept:** Approximates Order Flow Imbalance using candle internal structure.
-   **Logic:**
    -   Calculate `BuyingPressure = Close - Low`
    -   Calculate `SellingPressure = High - Close`
    -   **Signal:** If `BuyingPressure > SellingPressure * 3` AND `Volume > AvgVolume`, it implies aggressive buying (absorption/push).
-   **Why:** Detects hidden aggression inside the candle body/wicks without needing L2 data.

## 4. Hurst Regime Filter (Chaos Theory)
**Concept:** The Hurst Exponent (H) measures the long-term memory of a time series.
-   **Logic:**
    -   `H < 0.5`: Mean Reverting (Range) -> Activates Reversion Sensors.
    -   `H > 0.5`: Trending -> Activates Trend Sensors.
-   **Why:** More scientifically accurate than ADX for distinguishing "Choppy" vs "Trending" markets.

## Implementation Plan
1.  Create `sensors/high_frequency_scalping/vwap_momentum.py`
2.  Create `sensors/high_frequency_scalping/keltner_breakout.py`
3.  Create `sensors/high_frequency_scalping/volume_imbalance.py`
4.  Create `sensors/high_frequency_scalping/hurst_regime.py`
5.  Register in `SensorManager` and `config/sensors.py`.
