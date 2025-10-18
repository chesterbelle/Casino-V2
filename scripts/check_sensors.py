#!/usr/bin/env python3
"""
🔍 Verificador de Sensores Activos
===================================

Muestra qué sensores están configurados y activos.

Uso:
    python scripts/check_sensors.py
"""

import sys
from pathlib import Path

# Añadir raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from sensors.sensor_manager import SENSOR_REGISTRY


def check_sensors():
    """Verifica y muestra sensores activos"""
    
    print("\n" + "=" * 70)
    print("🔍 VERIFICACIÓN DE SENSORES")
    print("=" * 70)
    
    # Total disponibles
    total_available = len(SENSOR_REGISTRY)
    print(f"\n📊 Sensores disponibles en el sistema: {total_available}")
    
    # Configuración en config.py
    active_sensors = getattr(config, "ACTIVE_SENSORS", {})
    
    if not active_sensors:
        print("\n⚠️  ACTIVE_SENSORS no está configurado en config.py")
        print("   Por defecto, TODOS los sensores están activos.")
        active_count = total_available
        active_list = list(SENSOR_REGISTRY.keys())
    else:
        active_list = [name for name, enabled in active_sensors.items() if enabled]
        active_count = len(active_list)
    
    print(f"✅ Sensores activos: {active_count}")
    
    # Categorización
    mean_reversion = [
        "RSIReversion", "BollingerTouch", "KeltnerReversion",
        "StochasticReversion", "BollingerSqueeze", "WilliamsRReversion",
        "CCIReversion", "ZScoreReversion"
    ]
    
    momentum_trend = [
        "EMACrossover", "MACDCrossover", "Supertrend",
        "ADXFilter", "ParabolicSAR"
    ]
    
    volume = [
        "OBVBreakout", "VWAPDeviation", "MFIReversion",
        "AccumulationDistribution"
    ]
    
    # Mostrar por categoría
    print("\n📋 SENSORES POR CATEGORÍA:")
    print("-" * 70)
    
    def show_category(name, sensor_list):
        print(f"\n{name}:")
        active_in_cat = [s for s in sensor_list if s in active_list]
        for sensor in sensor_list:
            if sensor in SENSOR_REGISTRY:
                status = "✅" if sensor in active_list else "❌"
                print(f"  {status} {sensor}")
            else:
                print(f"  ⚠️  {sensor} (NO REGISTRADO)")
        return len(active_in_cat), len(sensor_list)
    
    mr_active, mr_total = show_category("📉 Mean Reversion", mean_reversion)
    mt_active, mt_total = show_category("📈 Momentum/Trend", momentum_trend)
    vol_active, vol_total = show_category("📊 Volume", volume)
    
    # Resumen
    print("\n" + "=" * 70)
    print("📊 RESUMEN:")
    print("-" * 70)
    print(f"  Mean Reversion:   {mr_active}/{mr_total}")
    print(f"  Momentum/Trend:   {mt_active}/{mt_total}")
    print(f"  Volume:           {vol_active}/{vol_total}")
    print(f"  {'─' * 40}")
    print(f"  TOTAL ACTIVOS:    {active_count}/{total_available}")
    print("=" * 70)
    
    # Recomendaciones
    if active_count == total_available:
        print("\n✅ ¡PERFECTO! Todos los sensores están activos.")
    elif active_count >= 15:
        print(f"\n🟢 BUENO: {active_count} sensores activos (suficiente cobertura)")
    elif active_count >= 10:
        print(f"\n🟡 REGULAR: {active_count} sensores activos (considera activar más)")
    else:
        print(f"\n🔴 BAJO: Solo {active_count} sensores activos (activa más para mejor cobertura)")
    
    # Mostrar desactivados si los hay
    if active_count < total_available:
        inactive = [s for s in SENSOR_REGISTRY.keys() if s not in active_list]
        if inactive:
            print("\n⚠️  Sensores DESACTIVADOS:")
            for sensor in inactive:
                print(f"  ❌ {sensor}")
    
    print("\n💡 Para activar todos los sensores:")
    print("   Edita config.py y asegúrate que ACTIVE_SENSORS tiene todos en True")
    print("   O simplemente NO definas ACTIVE_SENSORS (todos activos por defecto)")
    print("\n" + "=" * 70 + "\n")
    
    return active_count == total_available


if __name__ == "__main__":
    all_active = check_sensors()
    sys.exit(0 if all_active else 1)
