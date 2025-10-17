#!/usr/bin/env python3
"""
Analiza el historial de decisiones de Gemini para entender la distribución
de los tamaños de apuesta recomendados por el Kelly fraccional.
"""

from __future__ import annotations

import csv
import os
from collections import Counter, defaultdict

# --- Configuración ---
# Límite a comparar (el MAX_POSITION_SIZE actual)
LIMIT_TO_CHECK = 0.02
# ---

def analyze_decisions():
    """
    Lee el archivo gemini_decisions.csv y calcula estadísticas sobre los
    valores de Kelly para las operaciones aceptadas (BET).
    """
    # Construir la ruta absoluta al archivo de decisiones
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    decisions_path = os.path.join(project_root, "gemini", "data", "gemini_decisions.csv")

    if not os.path.exists(decisions_path):
        print(f"⚠️ No se encontró el archivo de decisiones en: {decisions_path}")
        print("Asegúrate de haber corrido un backtest para generarlo.")
        return

    # Agrupamos los kelly por trade_id para encontrar el min_kelly que se usó para la decisión
    trades = defaultdict(list)
    try:
        with open(decisions_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "action" not in reader.fieldnames or "kelly" not in reader.fieldnames or "trade_id" not in reader.fieldnames:
                print("❌ El archivo CSV no contiene las columnas 'action', 'kelly' y 'trade_id' requeridas.")
                return

            for row in reader:
                if row.get("action") == "BET":
                    try:
                        kelly_val = float(row.get("kelly", 0.0))
                        if kelly_val > 0:
                            trades[row["trade_id"]].append(kelly_val)
                    except (ValueError, TypeError):
                        continue
    except Exception as e:
        print(f"❌ Ocurrió un error al leer el archivo: {e}")
        return

    if not trades:
        print("ℹ️ No se encontraron valores de Kelly válidos para operaciones 'BET'.")
        return

    # Ahora obtenemos el valor de kelly que realmente se usó para cada apuesta (el mínimo de los participantes)
    min_kelly_values = []
    for trade_id, kelly_list in trades.items():
        if kelly_list:
            min_kelly_values.append(min(kelly_list))

    if not min_kelly_values:
        print("ℹ️ No se pudieron extraer los valores de Kelly para el análisis.")
        return

    # --- Calculations ---
    avg_kelly = sum(min_kelly_values) / len(min_kelly_values)
    max_kelly = max(min_kelly_values)
    
    times_capped = sum(1 for k in min_kelly_values if k > LIMIT_TO_CHECK)
    percent_capped = (times_capped / len(min_kelly_values)) * 100 if min_kelly_values else 0

    # Distribution
    bins = {
        "0-1%":   lambda k: 0 < k <= 0.01,
        "1-2%":   lambda k: 0.01 < k <= 0.02,
        "2-3%":   lambda k: 0.02 < k <= 0.03,
        "3-5%":   lambda k: 0.03 < k <= 0.05,
        ">5%":    lambda k: k > 0.05,
    }
    distribution = Counter()
    for k in min_kelly_values:
        for label, check in bins.items():
            if check(k):
                distribution[label] += 1
                break

    # --- Print Results ---
    print("="*60)
    print("Análisis de Recomendaciones de Apuesta de Kelly (Fraccional)")
    print("="*60)
    print(f"Analizando {len(min_kelly_values)} decisiones de apuesta ('BET') únicas.")
    print(f"Límite MAX_POSITION_SIZE actual para la comparación: {LIMIT_TO_CHECK:.2%}\n")
    
    print(f"  - Apuesta Promedio Recomendada: {avg_kelly:.4%}")
    print(f"  - Apuesta Máxima Recomendada:   {max_kelly:.4%}\n")
    
    print(f"El límite de {LIMIT_TO_CHECK:.2%} fue superado en {times_capped} de {len(min_kelly_values)} ocasiones.")
    print(f"➡️  El {percent_capped:.2f}% de las veces, MAX_POSITION_SIZE está limitando la apuesta.\n")

    print("Distribución de las Apuestas Recomendadas por Kelly:")
    sorted_dist = sorted(distribution.items(), key=lambda item: list(bins.keys()).index(item[0]))
    for label, count in sorted_dist:
        percentage = (count / len(min_kelly_values)) * 100
        print(f"  - {label:<5}: {count:>5} veces ({percentage:.2f}%)")
    print("="*60)


if __name__ == "__main__":
    analyze_decisions()
