import asyncio
import json
import os
import time
from pathlib import Path

from exchanges.connectors.binance.binance_connector import BinanceConnector

LOGS = Path("logs")
LOGS.mkdir(exist_ok=True)
OUT = LOGS / "force_order_market_ltc.json"


async def create_protective_orders(connector, symbol, side, size, tp_price, sl_price, ws_timeout_ms=3000, retries=3):
    results = {"tp": None, "sl": None, "tp_attempts": [], "sl_attempts": []}
    # create TP (limit) first
    # Accept either exchange-style side ('BUY'/'SELL') or logical ('LONG'/'SHORT')
    s = (side or "").upper()
    entry_is_long = s in ("LONG", "BUY")
    tp_side = "SELL" if entry_is_long else "BUY"
    sl_side = "SELL" if entry_is_long else "BUY"

    for attempt in range(1, retries + 1):
        t0 = time.time()
        try:
            payload = {
                "symbol": symbol,
                "side": tp_side,
                "amount": size,
                "price": tp_price,
                "order_type": "limit",
                "params": {"reduceOnly": True},
            }
            res = await connector.create_order(**payload, confirm_with_ws=True, ws_timeout_ms=ws_timeout_ms)
            t1 = time.time()
            results["tp"] = res
            results["tp_attempts"].append({"attempt": attempt, "ok": True, "duration_ms": int((t1 - t0) * 1000)})
            break
        except Exception as e:
            t1 = time.time()
            results["tp_attempts"].append(
                {"attempt": attempt, "ok": False, "error": str(e), "duration_ms": int((t1 - t0) * 1000)}
            )
            await asyncio.sleep(0.2 * attempt)

    for attempt in range(1, retries + 1):
        try:
            payload = {
                "symbol": symbol,
                "side": sl_side,
                "amount": size,
                "price": sl_price,
                "order_type": "STOP_MARKET",
                "params": {"stopPrice": sl_price, "reduceOnly": True},
            }
            t0 = time.time()
            res = await connector.create_order(**payload, confirm_with_ws=True, ws_timeout_ms=ws_timeout_ms)
            t1 = time.time()
            results["sl"] = res
            results["sl_attempts"].append({"attempt": attempt, "ok": True, "duration_ms": int((t1 - t0) * 1000)})
            break
        except Exception as e:
            t1 = time.time()
            results["sl_attempts"].append(
                {"attempt": attempt, "ok": False, "error": str(e), "duration_ms": int((t1 - t0) * 1000)}
            )
            await asyncio.sleep(0.2 * attempt)

    return results


async def run_market_then_protect(
    symbol="LTC/USDT:USDT", size=0.1, tp_factor=1.001, sl_factor=0.999, ws_timeout_ms=3000
):
    api_key = os.environ.get("BINANCE_API_KEY")
    secret = os.environ.get("BINANCE_API_SECRET")
    connector = BinanceConnector(api_key=api_key, secret=secret, mode="demo", enable_websocket=True)
    try:
        await connector.connect()
    except Exception as e:
        print("Connector connect exception:", e)

    # Step 1: Market entry (no TP/SL in payload)
    entry_payload = {
        "symbol": symbol,
        "side": "BUY",
        "order_type": "market",
        "amount": size,
    }
    out = {"entry": None, "protect": None, "errors": []}
    try:
        # Use connector.create_order directly to avoid Croupier's OCO validation
        entry_res = await connector.create_order(**entry_payload, confirm_with_ws=True, ws_timeout_ms=ws_timeout_ms)
        out["entry"] = entry_res
    except Exception as e:
        out["errors"].append({"stage": "entry", "error": str(e)})
        await connector.close()
        OUT.write_text(json.dumps(out, default=str, indent=2))
        return out

    # Ensure we have fill price and filled size
    filled_size = entry_res.get("filled", entry_res.get("size")) or 0
    entry_price = None
    for k in ("avgPrice", "price", "filled_avg_price"):
        if entry_res.get(k):
            entry_price = float(entry_res.get(k))
            break
    if entry_price is None:
        out["errors"].append({"stage": "entry_no_price", "detail": "No avgPrice/price found in entry result"})
        await connector.close()
        OUT.write_text(json.dumps(out, default=str, indent=2))
        return out

    tp_price = entry_price * tp_factor
    sl_price = entry_price * sl_factor

    # Step 2: Place TP/SL using the raw connector (respecting exact factors)
    protect_res = await create_protective_orders(
        connector, symbol, entry_payload["side"], filled_size, tp_price, sl_price, ws_timeout_ms=ws_timeout_ms
    )
    out["protect"] = protect_res

    # If either TP or SL is missing after retries, abort: cancel any created protect orders and CLOSE the position.
    tp_ok = protect_res.get("tp") is not None
    sl_ok = protect_res.get("sl") is not None

    if not (tp_ok and sl_ok):
        failure_info = {"tp_ok": tp_ok, "sl_ok": sl_ok, "actions": []}

        # Attempt to cancel any protective orders that were created
        for role in ("tp", "sl"):
            order = protect_res.get(role)
            if order and order.get("id"):
                try:
                    await connector.cancel_order(order.get("id"), symbol)
                    failure_info["actions"].append({"cancelled": order.get("id")})
                except Exception as e:
                    failure_info["actions"].append({"cancel_failed": str(e)})

        # Close the open position by placing a MARKET opposite order for the filled size
        try:
            close_side = "SELL" if entry_payload.get("side", "BUY").upper() in ("BUY", "LONG") else "BUY"
            close_payload = {"symbol": symbol, "side": close_side, "order_type": "market", "amount": filled_size}
            t_close_res = await connector.create_order(
                **close_payload, confirm_with_ws=True, ws_timeout_ms=ws_timeout_ms
            )
            failure_info["closed_position"] = t_close_res
            out.setdefault("errors", []).append({"stage": "protect_failed_closed_position", "detail": failure_info})
        except Exception as e:
            failure_info["close_error"] = str(e)
            out.setdefault("errors", []).append({"stage": "protect_failed_close_error", "detail": failure_info})

        out["protect"]["failure_action"] = failure_info

        # Append concise report to analysis file
        try:
            report = Path("logs/analysis_report.txt")
            with report.open("a") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": int(time.time() * 1000),
                            "symbol": symbol,
                            "entry": out["entry"],
                            "protect": protect_res,
                            "failure": failure_info,
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass

    await connector.close()
    OUT.write_text(json.dumps(out, default=str, indent=2))
    return out


if __name__ == "__main__":
    res = asyncio.run(run_market_then_protect())
    print("RESULT:", res)
