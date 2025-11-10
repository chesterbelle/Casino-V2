#!/usr/bin/env python3
"""Test environment variable loading."""
import os

from dotenv import load_dotenv

print("=" * 60)
print("TEST: Environment Variable Loading")
print("=" * 60)

# Load .env
load_dotenv()

# Check variables
api_key = os.getenv("BYBIT_API_KEY")
secret = os.getenv("BYBIT_API_SECRET")

print(f"\nBYBIT_API_KEY: {api_key[:15] + '...' if api_key else 'NOT FOUND'}")
print(f"BYBIT_API_SECRET: {secret[:15] + '...' if secret else 'NOT FOUND'}")

if api_key and secret:
    print("\n✅ Both credentials loaded successfully!")
else:
    print("\n❌ Missing credentials!")
    if not api_key:
        print("   - BYBIT_API_KEY not found")
    if not secret:
        print("   - BYBIT_API_SECRET not found")

print("=" * 60)
