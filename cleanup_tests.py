#!/usr/bin/env python3
"""
Test Cleanup and Reorganization Script

Follows the structure defined in VISION.md:
tests/
├── test_phase1.py        # Basic system tests
├── test_gemini.py        # Gemini tests
└── test_players.py       # Player strategy tests
"""

import os
import shutil
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestCleanup")

# Project root
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = PROJECT_ROOT / "tests"

# Files to keep according to VISION.md structure
ESSENTIAL_TESTS = {
    "test_phase1.py": "Basic system tests",
    "test_gemini.py": "Gemini decision engine tests",
    "test_players.py": "Player strategy tests"
}

# Files to remove (redundant/debugging tests)
REDUNDANT_TESTS = [
    "test_core_architecture.py",
    "test_mejoras_futurechanges.py",
    "test_websocket_integration.py",
    "test_websocket_live.py",
    "test_table_backtest_multiasset.py"
]

# Files to integrate into essential tests
TESTS_TO_INTEGRATE = {
    "test_core_integration.py": "test_phase1.py",
    "test_new_sensors.py": "test_gemini.py"
}

def cleanup_tests():
    """Main cleanup function"""
    logger.info("Starting test cleanup and reorganization")
    
    # Step 1: Remove redundant test files
    for test_file in REDUNDANT_TESTS:
        file_path = TESTS_DIR / test_file
        if file_path.exists():
            logger.info(f"Removing redundant test: {test_file}")
            os.remove(file_path)
    
    # Step 2: Create essential test files if missing
    for test_file, description in ESSENTIAL_TESTS.items():
        file_path = TESTS_DIR / test_file
        if not file_path.exists():
            logger.info(f"Creating essential test file: {test_file}")
            with open(file_path, "w") as f:
                f.write(f""""""
# {description}
""""""
""")
    
    # Step 3: Integrate content from other tests
    for source_file, target_file in TESTS_TO_INTEGRATE.items():
        source_path = TESTS_DIR / source_file
        target_path = TESTS_DIR / target_file
        
        if source_path.exists():
            logger.info(f"Integrating {source_file} into {target_file}")
            with open(source_path, "r") as src, open(target_path, "a") as tgt:
                tgt.write("\n\n# Integrated from {source_file}\n")
                tgt.write(src.read())
            os.remove(source_path)
    
    # Step 4: Remove root-level test files
    for file_path in PROJECT_ROOT.glob("test_*.py"):
        if file_path.name != "cleanup_tests.py":  # Don't remove this script
            logger.info(f"Removing root-level test: {file_path.name}")
            os.remove(file_path)
    
    logger.info("Test cleanup completed successfully")

if __name__ == "__main__":
    cleanup_tests()
