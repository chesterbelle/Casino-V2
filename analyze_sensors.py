import numpy as np
import pandas as pd

# Rutas a los archivos
DECISIONS_FILE = "gemini/data/gemini_decisions.csv"
RESULTS_FILE = "gemini/data/gemini_trade_results.csv"


def analyze_sensor_performance():
    """
    Realiza un análisis avanzado del rendimiento de los sensores, incluyendo PnL.
    """
    try:
        # Cargar los archivos CSV
        print(f"Cargando decisiones desde {DECISIONS_FILE}...")
        decisions_df = pd.read_csv(DECISIONS_FILE, low_memory=False)

        print(f"Cargando resultados desde {RESULTS_FILE}...")
        results_df = pd.read_csv(RESULTS_FILE)

        print("Archivos cargados. Procesando...")

        # --- Pre-procesamiento ---
        # 1. Limpiar resultados: quedarse con columnas necesarias y trades reales
        results_df = results_df[["trade_id", "result", "pnl"]].copy()
        results_df.dropna(subset=["trade_id", "result", "pnl"], inplace=True)
        results_df = results_df[results_df["result"].isin(["WIN", "LOSS"])]

        # 2. Limpiar decisiones: quedarse con columnas necesarias y explotar 'contributors'
        decisions_df = decisions_df[["trade_id", "contributors"]].copy()
        decisions_df.dropna(subset=["trade_id", "contributors"], inplace=True)
        decisions_df["sensors"] = decisions_df["contributors"].str.split(",")
        decisions_df = decisions_df.explode("sensors")
        decisions_df.rename(columns={"sensors": "sensor"}, inplace=True)
        decisions_df["sensor"] = decisions_df["sensor"].str.strip()

        # --- Unión de Datos ---
        print("Cruzando decisiones con resultados...")
        merged_df = pd.merge(decisions_df, results_df, on="trade_id")

        if merged_df.empty:
            print("No se encontraron trades en común entre decisiones y resultados.")
            return

        # --- Cálculo de Estadísticas Avanzadas ---
        print("Calculando estadísticas avanzadas por sensor...")

        def calculate_stats(df):
            wins_df = df[df["result"] == "WIN"]
            losses_df = df[df["result"] == "LOSS"]

            total_trades = len(df)
            wins = len(wins_df)

            gross_profit = wins_df["pnl"].sum()
            gross_loss = abs(losses_df["pnl"].sum())

            return pd.Series(
                {
                    "total_trades": total_trades,
                    "wins": wins,
                    "win_rate": (wins / total_trades) * 100 if total_trades > 0 else 0,
                    "avg_win_pnl": wins_df["pnl"].mean() if wins > 0 else 0,
                    "avg_loss_pnl": losses_df["pnl"].mean() if len(losses_df) > 0 else 0,
                    "profit_factor": gross_profit / gross_loss if gross_loss > 0 else np.inf,
                    "total_pnl": df["pnl"].sum(),
                }
            )

        sensor_stats = merged_df.groupby("sensor").apply(calculate_stats)
        sensor_stats = sensor_stats.sort_values(by="profit_factor", ascending=False)

        # --- Presentación de Resultados ---
        print("\n--- Resultados del Análisis Avanzado de Sensores ---")
        print("Sensores ordenados por Profit Factor (Ganancia Bruta / Pérdida Bruta)")
        print("-----------------------------------------------------")
        print(sensor_stats.to_string(float_format="{:.2f}".format, formatters={"win_rate": "{:.2f}%".format}))
        print("-----------------------------------------------------")

    except FileNotFoundError as e:
        print(f"Error: No se encontró el archivo {e.filename}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")


if __name__ == "__main__":
    analyze_sensor_performance()
