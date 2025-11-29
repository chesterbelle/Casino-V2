#!/usr/bin/env python3
"""
Análisis Detallado de Progresión Paroli

Analiza los logs para rastrear la progresión Paroli (1x→4x→8x)
basándose en los cambios de estado del player.
"""

import re
from collections import Counter, defaultdict
from pathlib import Path


def analyze_paroli_progression(log_path):
    """Analiza la progresión Paroli desde el log."""

    # Patrón para extraer el estado del player
    state_pattern = re.compile(r"Player state updated: \{'unit': ([^,]+), 'step': (\d+)\}")

    # Contadores
    step_transitions = []  # Lista de transiciones de step
    progression_sequences = []  # Secuencias completas
    current_sequence = []

    step_counts = Counter()  # Cuántas veces se ejecutó cada step

    with open(log_path, "r") as f:
        lines = f.readlines()

    prev_step = 0

    for line in lines:
        state_match = state_pattern.search(line)

        if state_match:
            # unit_str = state_match.group(1)  # Unused
            step = int(state_match.group(2))

            # Registrar transición
            step_transitions.append(step)
            step_counts[step] += 1

            # Detectar progresión
            if prev_step == 0 and step == 1:
                # Inicio de nueva secuencia (ganó en step 0, avanza a step 1)
                current_sequence = [0]  # Empezó en 0 y ganó
            elif prev_step == 1 and step == 2:
                # Ganó en step 1, avanza a step 2
                if current_sequence and current_sequence[-1] == 0:
                    current_sequence.append(1)
            elif prev_step == 2 and step == 0:
                # Completó step 2 (ganó o perdió) y reinició
                if current_sequence and current_sequence[-1] == 1:
                    current_sequence.append(2)
                    progression_sequences.append(
                        {"sequence": current_sequence.copy(), "completed": True, "length": len(current_sequence)}
                    )
                else:
                    # Perdió en step 2
                    if current_sequence:
                        progression_sequences.append(
                            {
                                "sequence": current_sequence.copy(),
                                "completed": False,
                                "length": len(current_sequence),
                                "failed_at": prev_step,
                            }
                        )
                current_sequence = []
            elif step == 0 and prev_step != 0:
                # Perdió y reinició
                if current_sequence:
                    progression_sequences.append(
                        {
                            "sequence": current_sequence.copy(),
                            "completed": False,
                            "length": len(current_sequence),
                            "failed_at": prev_step,
                        }
                    )
                current_sequence = []

            prev_step = step

    return step_counts, step_transitions, progression_sequences


def print_detailed_analysis(step_counts, step_transitions, progression_sequences):
    """Imprime análisis detallado."""

    print("\n" + "=" * 70)
    print("📊 ANÁLISIS DETALLADO DE PROGRESIÓN PAROLI")
    print("=" * 70 + "\n")

    # Mapeo de steps a multiplicadores
    step_to_mult = {0: "1x", 1: "4x", 2: "8x"}

    # 1. Distribución por escalón
    print("=" * 70)
    print("📈 DISTRIBUCIÓN POR ESCALÓN")
    print("=" * 70 + "\n")

    total_steps = sum(step_counts.values())
    for step in sorted(step_counts.keys()):
        count = step_counts[step]
        mult = step_to_mult.get(step, "?")
        pct = (count / total_steps * 100) if total_steps > 0 else 0
        print(f"Step {step} ({mult}): {count} veces ({pct:.1f}%)")

    print(f"\nTotal de cambios de estado: {total_steps}")

    # 2. Análisis de progresiones
    print("\n" + "=" * 70)
    print("🎯 ANÁLISIS DE PROGRESIONES")
    print("=" * 70 + "\n")

    completed = [p for p in progression_sequences if p.get("completed", False)]
    failed_at_1 = [p for p in progression_sequences if not p.get("completed", False) and p.get("failed_at") == 1]
    failed_at_2 = [p for p in progression_sequences if not p.get("completed", False) and p.get("failed_at") == 2]

    print(f"Total de secuencias detectadas: {len(progression_sequences)}")
    print(f"Progresiones COMPLETAS (0→1→2): {len(completed)}")
    print(f"Fallidas en step 1 (4x): {len(failed_at_1)}")
    print(f"Fallidas en step 2 (8x): {len(failed_at_2)}")

    if len(progression_sequences) > 0:
        success_rate = (len(completed) / len(progression_sequences)) * 100
        print(f"\n✨ Tasa de éxito de progresión completa: {success_rate:.2f}%")

    # 3. Análisis de transiciones
    print("\n" + "=" * 70)
    print("🔄 ANÁLISIS DE TRANSICIONES")
    print("=" * 70 + "\n")

    transitions = defaultdict(int)
    for i in range(len(step_transitions) - 1):
        from_step = step_transitions[i]
        to_step = step_transitions[i + 1]
        transitions[(from_step, to_step)] += 1

    print("Transiciones más comunes:")
    for (from_s, to_s), count in sorted(transitions.items(), key=lambda x: x[1], reverse=True):
        from_mult = step_to_mult.get(from_s, "?")
        to_mult = step_to_mult.get(to_s, "?")
        print(f"  {from_s} ({from_mult}) → {to_s} ({to_mult}): {count} veces")

    # 4. Ejemplos de secuencias
    print("\n" + "=" * 70)
    print("📋 EJEMPLOS DE SECUENCIAS")
    print("=" * 70 + "\n")

    if completed:
        print("Progresiones completas (primeras 10):")
        for i, prog in enumerate(completed[:10], 1):
            seq_str = " → ".join([step_to_mult.get(s, "?") for s in prog["sequence"]])
            print(f"  {i}. {seq_str} ✅")

    if failed_at_1:
        print("\nFallidas en step 1 (primeras 5):")
        for i, prog in enumerate(failed_at_1[:5], 1):
            seq_str = " → ".join([step_to_mult.get(s, "?") for s in prog["sequence"]])
            print(f"  {i}. {seq_str} ❌ (perdió en 4x)")

    if failed_at_2:
        print("\nFallidas en step 2 (primeras 5):")
        for i, prog in enumerate(failed_at_2[:5], 1):
            seq_str = " → ".join([step_to_mult.get(s, "?") for s in prog["sequence"]])
            print(f"  {i}. {seq_str} ❌ (perdió en 8x)")

    # 5. Estadísticas de riesgo
    print("\n" + "=" * 70)
    print("⚠️ ANÁLISIS DE RIESGO")
    print("=" * 70 + "\n")

    # Calcular cuántas veces se arriesgó en cada nivel
    times_at_4x = step_counts.get(1, 0)
    times_at_8x = step_counts.get(2, 0)

    print(f"Veces que arriesgó 4x: {times_at_4x}")
    print(f"Veces que arriesgó 8x: {times_at_8x}")

    if times_at_4x > 0:
        success_4x_to_8x = len([p for p in progression_sequences if len(p["sequence"]) >= 2])
        rate_4x = (success_4x_to_8x / times_at_4x * 100) if times_at_4x > 0 else 0
        print(f"Tasa de éxito 1x→4x: {rate_4x:.2f}%")

    if times_at_8x > 0:
        success_8x = len(completed)
        rate_8x = (success_8x / times_at_8x * 100) if times_at_8x > 0 else 0
        print(f"Tasa de éxito 4x→8x: {rate_8x:.2f}%")


def main():
    logs_dir = Path("/home/chesterbelle/Casino-V2/logs")
    log_files = sorted(logs_dir.glob("main_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not log_files:
        print("❌ No se encontraron archivos de log")
        return

    latest_log = log_files[0]
    print(f"Analizando: {latest_log.name}\n")

    step_counts, step_transitions, progression_sequences = analyze_paroli_progression(latest_log)
    print_detailed_analysis(step_counts, step_transitions, progression_sequences)

    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
