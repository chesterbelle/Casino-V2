import os

EXPECTED_STRUCTURE = {
    "root": [
        "README.md",
        "config.py",
        "main.py",
    ],
    "gemini": [
        "__init__.py",
        "gemini_core.py",
        "memory.py",
    ],
    "oscar": [
        "__init__.py",
        "oscar_grind_machine.py",
        "oscar_trader.py",
    ],
    "sensors": [
        "__init__.py",
        "sensor_manager.py",
    ],
    "croupier": [
        "__init__.py",
        "croupier.py",
        "broker_interface.py",
    ],
    "tables": [
        "__init__.py",
        "table_base.py",
        "balance_manager.py",
        "data/raw/",
        "data/exchange_profiles/",
    ],
    "utils": [
        "__init__.py",
        "download_kline_dataset.py",
        "fetch_funding_rates.py",
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

