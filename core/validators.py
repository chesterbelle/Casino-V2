"""
Parameter validation utilities for Casino V2.

This module provides robust validation functions for all input parameters
used throughout the trading system.
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .exceptions import ValidationError, create_validation_error


def validate_positive_number(value: Any, field_name: str) -> float:
    """Validate that value is a positive number."""
    try:
        num = float(value)
        if num <= 0:
            raise ValidationError(f"{field_name} must be positive, got {num}")
        return num
    except (TypeError, ValueError) as e:
        raise create_validation_error(field_name, value, f"must be a positive number: {e}")


def validate_non_negative_number(value: Any, field_name: str) -> float:
    """Validate that value is a non-negative number."""
    try:
        num = float(value)
        if num < 0:
            raise ValidationError(f"{field_name} must be non-negative, got {num}")
        return num
    except (TypeError, ValueError) as e:
        raise create_validation_error(field_name, value, f"must be a non-negative number: {e}")


def validate_range(value: Any, field_name: str, min_val: float, max_val: float) -> float:
    """Validate that value is within a specified range."""
    num = validate_non_negative_number(value, field_name)
    if not (min_val <= num <= max_val):
        raise create_validation_error(field_name, value, f"must be between {min_val} and {max_val}")
    return num


def validate_string(value: Any, field_name: str, min_length: int = 1, max_length: int = 100) -> str:
    """Validate that value is a valid string within length constraints."""
    if not isinstance(value, str):
        raise create_validation_error(field_name, value, "must be a string")

    if not (min_length <= len(value.strip()) <= max_length):
        raise create_validation_error(
            field_name, value, f"length must be between {min_length} and {max_length} characters"
        )

    return value.strip()


def validate_symbol(symbol: str) -> str:
    """Validate trading symbol format."""
    symbol = validate_string(symbol, "symbol", 1, 20)

    # Basic symbol pattern: letters, numbers, hyphens, underscores, forward slashes
    if not re.match(r"^[A-Z0-9/_-]+$", symbol):
        raise create_validation_error("symbol", symbol, "invalid symbol format")

    return symbol


def validate_timestamp(timestamp: Any) -> Union[int, str]:
    """Validate timestamp format."""
    if isinstance(timestamp, str):
        # Try to parse as ISO format
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return timestamp
        except ValueError:
            raise create_validation_error("timestamp", timestamp, "invalid ISO format")
    elif isinstance(timestamp, (int, float)):
        # Assume milliseconds since epoch
        if timestamp < 0:
            raise create_validation_error("timestamp", timestamp, "cannot be negative")
        return int(timestamp)
    else:
        raise create_validation_error("timestamp", timestamp, "must be string or numeric")


def validate_order_side(side: str) -> str:
    """Validate order side."""
    side = validate_string(side, "side", 1, 10).upper()

    valid_sides = ["BUY", "SELL", "LONG", "SHORT"]
    if side not in valid_sides:
        raise create_validation_error("side", side, f"must be one of {valid_sides}")

    return side


def validate_order_type(order_type: str) -> str:
    """Validate order type."""
    order_type = validate_string(order_type, "order_type", 1, 20).lower()

    valid_types = ["market", "limit", "stop", "stop_limit"]
    if order_type not in valid_types:
        raise create_validation_error("order_type", order_type, f"must be one of {valid_types}")

    return order_type


def validate_balance_config(balance: Dict[str, Any]) -> Dict[str, Any]:
    """Validate balance configuration."""
    required_fields = ["initial_balance", "max_drawdown"]
    validated = {}

    for field in required_fields:
        if field not in balance:
            raise ValidationError(f"Missing required balance field: {field}")

        if field == "initial_balance":
            validated[field] = validate_positive_number(balance[field], field)
        elif field == "max_drawdown":
            validated[field] = validate_range(balance[field], field, 0.0, 1.0)

    # Optional fields
    if "min_balance" in balance:
        validated["min_balance"] = validate_non_negative_number(balance["min_balance"], "min_balance")

    return validated


def validate_risk_config(risk: Dict[str, Any]) -> Dict[str, Any]:
    """Validate risk management configuration."""
    validated = {}

    # Kelly fraction
    if "kelly_fraction" in risk:
        validated["kelly_fraction"] = validate_range(risk["kelly_fraction"], "kelly_fraction", 0.0, 1.0)

    # Max position size
    if "max_position_size" in risk:
        validated["max_position_size"] = validate_range(risk["max_position_size"], "max_position_size", 0.0, 1.0)

    # Stop loss
    if "stop_loss" in risk:
        validated["stop_loss"] = validate_range(risk["stop_loss"], "stop_loss", 0.0, 1.0)

    # Take profit
    if "take_profit" in risk:
        validated["take_profit"] = validate_positive_number(risk["take_profit"], "take_profit")

    return validated


def validate_candle_data(candle: Dict[str, Any]) -> Dict[str, Any]:
    """Validate OHLCV candle data."""
    required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
    validated = {}

    for field in required_fields:
        if field not in candle:
            raise ValidationError(f"Missing required candle field: {field}")

        if field == "timestamp":
            validated[field] = validate_timestamp(candle[field])
        elif field in ["open", "high", "low", "close"]:
            validated[field] = validate_positive_number(candle[field], f"candle.{field}")
        elif field == "volume":
            validated[field] = validate_non_negative_number(candle[field], f"candle.{field}")

    # Validate OHLC logic
    ohlc = [validated["open"], validated["high"], validated["low"], validated["close"]]
    if not (min(ohlc) == validated["low"] and max(ohlc) == validated["high"]):
        raise ValidationError("Invalid OHLC relationship in candle data")

    return validated


def validate_trade_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate trade result data."""
    validated = {}

    # Required fields
    required_fields = ["trade_id", "result", "pnl", "symbol"]
    for field in required_fields:
        if field not in result:
            raise ValidationError(f"Missing required trade result field: {field}")

        if field == "trade_id":
            validated[field] = validate_string(result[field], field, 1, 100)
        elif field == "result":
            validated[field] = validate_string(result[field], field, 1, 20)
        elif field == "pnl":
            validated[field] = float(result[field])  # Can be negative
        elif field == "symbol":
            validated[field] = validate_symbol(result[field])

    # Optional fields
    optional_fields = ["fee", "balance", "timestamp"]
    for field in optional_fields:
        if field in result:
            if field == "fee":
                validated[field] = validate_non_negative_number(result[field], field)
            elif field == "balance":
                validated[field] = validate_non_negative_number(result[field], field)
            elif field == "timestamp":
                validated[field] = validate_timestamp(result[field])

    return validated


def validate_config_section(
    config: Dict[str, Any],
    section_name: str,
    required_fields: List[str],
    validators: Optional[Dict[str, callable]] = None,
) -> Dict[str, Any]:
    """Validate a configuration section with custom validators."""
    validated = {}

    # Check required fields
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"Missing required {section_name} field: {field}")

    # Validate each field
    for key, value in config.items():
        if validators and key in validators:
            try:
                validated[key] = validators[key](value)
            except Exception as e:
                raise ValidationError(f"Validation failed for {section_name}.{key}: {e}")
        else:
            validated[key] = value

    return validated
