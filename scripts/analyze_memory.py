"""
📊 Analizador de Memoria Entrenada
===================================

Muestra estadísticas detalladas de la memoria entrenada:
- Top estrategias por winrate
- Estrategias aprobadas vs pendientes
- Distribución por sensores
- Recomendaciones de configuración

Uso:
    python scripts/analyze_memory.py
"""

import json
import sys
from pathlib import Path

# Añadir raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_memory():
    """Carga el estado de la memoria"""
    memory_path = Path("gemini/data/memory_state.json")
    
    if not memory_path.exists():
        print("❌ No se encontró memoria entrenada")
        print("   Ruta esperada: gemini/data/memory_state.json")
        print("\n💡 Ejecuta primero:")
        print("   ./scripts/train_memory.sh")
        return None
    
    with open(memory_path, "r") as f:
        return json.load(f)


def analyze_strategies(state):
    """Analiza las estrategias en la memoria"""
    strategies = state.get("strategies", {})
    
    if not strategies:
        print("⚠️  Memoria vacía - sin estrategias entrenadas")
        return
    
    # Calcular métricas
    total_strategies = len(strategies)
    
    approved = []
    pending = []
    
    MIN_SUPPORT = 500  # Debe coincidir con config
    
    for name, data in strategies.items():
        total_trades = data.get("wins", 0) + data.get("losses", 0)
        winrate = data.get("winrate")
        
        if total_trades >= MIN_SUPPORT:
            approved.append({
                "name": name,
                "wins": data.get("wins", 0),
                "losses": data.get("losses", 0),
                "total": total_trades,
                "winrate": winrate
            })
        else:
            pending.append({
                "name": name,
                "total": total_trades,
                "needed": MIN_SUPPORT - total_trades
            })
    
    # Ordenar
    approved.sort(key=lambda x: x["winrate"] if x["winrate"] else 0, reverse=True)
    pending.sort(key=lambda x: x["total"], reverse=True)
    
    return {
        "total": total_strategies,
        "approved": approved,
        "pending": pending,
        "min_support": MIN_SUPPORT
    }


def print_analysis(analysis):
    """Imprime el análisis"""
    if not analysis:
        return
    
    print("\n" + "=" * 80)
    print("📊 ANÁLISIS DE MEMORIA ENTRENADA")
    print("=" * 80)
    
    # Resumen general
    print(f"\n📈 RESUMEN GENERAL")
    print(f"  Total estrategias: {analysis['total']}")
    print(f"  Aprobadas (>= {analysis['min_support']} trades): {len(analysis['approved'])}")
    print(f"  Pendientes: {len(analysis['pending'])}")
    
    # Top aprobadas
    if analysis['approved']:
        print(f"\n✅ TOP ESTRATEGIAS APROBADAS (por winrate):")
        print(f"{'#':<3} {'Estrategia':<60} {'Trades':<8} {'Winrate':<10}")
        print("-" * 85)
        
        for i, strat in enumerate(analysis['approved'][:20], 1):
            name = strat['name'][:60]
            total = strat['total']
            wr = strat['winrate']
            wr_str = f"{wr:.2%}" if wr is not None else "N/A"
            
            # Color según winrate
            if wr and wr > 0.55:
                emoji = "🟢"
            elif wr and wr > 0.52:
                emoji = "🟡"
            else:
                emoji = "🔴"
            
            print(f"{i:<3} {emoji} {name:<58} {total:<8} {wr_str:<10}")
        
        if len(analysis['approved']) > 20:
            print(f"\n  ... y {len(analysis['approved']) - 20} más")
    
    # Pendientes
    if analysis['pending']:
        print(f"\n⏳ ESTRATEGIAS PENDIENTES (más cercanas a aprobar):")
        print(f"{'#':<3} {'Estrategia':<60} {'Trades':<8} {'Faltan':<8}")
        print("-" * 85)
        
        for i, strat in enumerate(analysis['pending'][:10], 1):
            name = strat['name'][:60]
            total = strat['total']
            needed = strat['needed']
            
            print(f"{i:<3} {name:<60} {total:<8} {needed:<8}")
        
        if len(analysis['pending']) > 10:
            print(f"\n  ... y {len(analysis['pending']) - 10} más")
    
    # Distribución por sensor
    print(f"\n📊 DISTRIBUCIÓN POR SENSOR:")
    
    sensor_counts = {}
    for strat in analysis['approved']:
        # Extraer sensor del nombre (último componente)
        sensor = strat['name'].split("|")[-1] if "|" in strat['name'] else "Unknown"
        sensor_counts[sensor] = sensor_counts.get(sensor, 0) + 1
    
    if sensor_counts:
        sorted_sensors = sorted(sensor_counts.items(), key=lambda x: x[1], reverse=True)
        for sensor, count in sorted_sensors:
            bar = "█" * min(count, 50)
            print(f"  {sensor:<25} {count:>3} {bar}")
    
    # Recomendaciones
    print(f"\n💡 RECOMENDACIONES:")
    
    if len(analysis['approved']) < 10:
        print("  ⚠️  Pocas estrategias aprobadas - necesitas más datos de entrenamiento")
        print("     → Ejecuta: ./scripts/download_training_data.sh")
        print("     → Luego: ./scripts/train_memory.sh")
    elif len(analysis['approved']) >= 10:
        print("  ✅ Suficientes estrategias aprobadas para operar")
        print("     → Próximo paso: ./scripts/validate_strategies.sh")
    
    avg_wr = sum(s['winrate'] for s in analysis['approved'] if s['winrate']) / len(analysis['approved'])
    
    if avg_wr > 0.55:
        print(f"  🟢 Winrate promedio alto ({avg_wr:.2%}) - sistema prometedor")
    elif avg_wr > 0.52:
        print(f"  🟡 Winrate promedio moderado ({avg_wr:.2%}) - viable con gestión de riesgo")
    else:
        print(f"  🔴 Winrate promedio bajo ({avg_wr:.2%}) - revisar configuración")
    
    print("\n" + "=" * 80)


def main():
    """Función principal"""
    print("\n🔍 Cargando memoria...")
    
    state = load_memory()
    if not state:
        return 1
    
    print(f"✅ Memoria cargada")
    print(f"   Última actualización: {state.get('last_update', 'Unknown')}")
    print(f"   Ventana de memoria: {state.get('memory_window', 'Unknown')}")
    
    analysis = analyze_strategies(state)
    print_analysis(analysis)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
