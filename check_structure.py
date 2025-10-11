import os

EXPECTED_STRUCTURE = {
    "root": [
        "README.md",
        "config.py",
        "main.py",
        "protocolo.md",
    ],
    "gemini": [
        "__init__.py",
        "gemini_core.py",
        "bucket_manager.py",
        "memory.py",
    ],
    "sensors": [
        "__init__.py",
        "sensor_manager.py",
        "rsi_reversion.py",
        "bollinger_touch.py",
        "keltner_reversion.py",
    ],
    "croupier": [
        "__init__.py",
        "croupier.py",
        "broker_interface.py",
        "order_simulator.py",
        "order_realtime.py",
    ],
    "tables": [
        "__init__.py",
        "table_base.py",
        "table_backtest.py",
        "balance_manager.py",
        "data/raw/LTCUSDT_15min_bull.csv",
        "data/raw/LTCUSDT_15min_bear.csv",
        "data/exchange_profiles/",
    ],
}


def check_file(path):
    """Verifica si un archivo o carpeta existe."""
    if os.path.isdir(path):
        return os.path.exists(path)
    return os.path.isfile(path)


def check_structure(base_path="."):
    print("\n🎰 Verificando estructura del proyecto Casino V2\n")

    total_missing = 0
    for folder, items in EXPECTED_STRUCTURE.items():
        if folder == "root":
            print("📁 Carpeta raíz:")
            current_path = base_path
        else:
            print(f"\n📂 {folder}/")
            current_path = os.path.join(base_path, folder)

        for item in items:
            file_path = os.path.join(current_path, item)
            if check_file(file_path):
                print(f"   ✅ {item}")
            else:
                print(f"   ❌ {item} (FALTA)")
                total_missing += 1

    if total_missing == 0:
        print("\n✅ Estructura completa y en orden. ¡Todo listo para jugar en el casino!\n")
    else:
        print(f"\n⚠️ Faltan {total_missing} elementos. Revisa los ❌ marcados.\n")


if __name__ == "__main__":
    check_structure(".")

