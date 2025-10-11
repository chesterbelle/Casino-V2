"""
🎛️ BucketManager
-----------------
Clasifica señales en "buckets de contexto" según sus características.
Cada bucket mantiene su propia estadística de winrate (p̂).
"""

import pandas as pd
import numpy as np

class BucketManager:
    def __init__(self, window=120, min_support=20):
        self.window = window
        self.min_support = min_support

    def identify_bucket(self, signal: dict) -> str:
        """Clasifica el contexto de la señal."""
        bbw = signal["features"].get("bbw", 0)
        range_score = signal.get("range_score", 1)
        hour = pd.to_datetime(signal["timestamp"]).hour

        # Clasificación simple
        vol_bucket = "L" if bbw < 0.3 else "M" if bbw < 0.6 else "H"
        hour_bucket = "N" if hour < 6 else "M" if hour < 12 else "T" if hour < 18 else "N2"

        return f"BBW={vol_bucket}|RS{range_score}|H={hour_bucket}"

