#!/usr/bin/env python3
"""
Parse `logs/oco_debug_*.json` files and extract EXECUTE_ORDER and VERIFY_TPSL_ORDERS events.
Compute latencies from EXECUTE_ORDER -> TP verify and -> SL verify.
Produce a concise report with counts and latency statistics and sample payloads.
"""
import json
import statistics
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("logs")

FMT_ISO = "%Y-%m-%dT%H:%M:%S.%f"


def parse_ts(s):
    try:
        return datetime.strptime(s, FMT_ISO)
    except Exception:
        return None


def analyze_file(p: Path):
    try:
        arr = json.load(p.open("r", encoding="utf-8"))
    except Exception:
        return None
    results = []
    # Iterate entries looking for EXECUTE_ORDER, then following VERIFY_TPSL_ORDERS
    for i, entry in enumerate(arr):
        step = entry.get("step")
        if step == "EXECUTE_ORDER":
            exec_ts = parse_ts(entry.get("timestamp"))
            exec_data = entry.get("data") or {}
            main_id = None
            if exec_data.get("result"):
                main_id = exec_data["result"].get("main_order_id") or exec_data["result"].get("id")
            # look ahead for TP/SL verification
            tp_ts = None
            sl_ts = None
            tp_order_info = None
            sl_order_info = None
            for j in range(i + 1, min(i + 10, len(arr))):
                e2 = arr[j]
                if e2.get("step") == "VERIFY_TPSL_ORDERS" and "tp_order" in (e2.get("data") or {}):
                    # sometimes two VERIFY entries (TP then SL)
                    d = e2.get("data") or {}
                    if "tp_order" in d and not tp_ts:
                        tp_ts = parse_ts(e2.get("timestamp"))
                        tp_order_info = d.get("tp_order")
                    if "sl_order" in d and not sl_ts:
                        sl_ts = parse_ts(e2.get("timestamp"))
                        sl_order_info = d.get("sl_order")
                elif e2.get("step") == "VERIFY_TPSL_ORDERS" and "sl_order" in (e2.get("data") or {}):
                    d = e2.get("data") or {}
                    if "sl_order" in d and not sl_ts:
                        sl_ts = parse_ts(e2.get("timestamp"))
                        sl_order_info = d.get("sl_order")
                elif e2.get("step") == "VERIFY_TPSL_ORDERS" and (
                    "tp_order" in (e2.get("data") or {}) or "sl_order" in (e2.get("data") or {})
                ):
                    # catch the other forms
                    d = e2.get("data") or {}
                    if "tp_order" in d and not tp_ts:
                        tp_ts = parse_ts(e2.get("timestamp"))
                        tp_order_info = d.get("tp_order")
                    if "sl_order" in d and not sl_ts:
                        sl_ts = parse_ts(e2.get("timestamp"))
                        sl_order_info = d.get("sl_order")
            results.append(
                {
                    "file": p.name,
                    "exec_ts": exec_ts,
                    "main_order_id": main_id,
                    "tp_ts": tp_ts,
                    "sl_ts": sl_ts,
                    "exec_entry": exec_data,
                    "tp_order_info": tp_order_info,
                    "sl_order_info": sl_order_info,
                }
            )
    return results


def main():
    files = sorted(LOGS_DIR.glob("oco_debug_*.json"))
    all_results = []
    for p in files:
        res = analyze_file(p)
        if res:
            all_results.extend(res)

    if not all_results:
        print("No EXECUTE_ORDER entries found in oco_debug files.")
        return

    tp_latencies = []
    sl_latencies = []
    for r in all_results:
        if r["exec_ts"] and r["tp_ts"]:
            tp_latencies.append((r["file"], (r["tp_ts"] - r["exec_ts"]).total_seconds() * 1000.0))
        if r["exec_ts"] and r["sl_ts"]:
            sl_latencies.append((r["file"], (r["sl_ts"] - r["exec_ts"]).total_seconds() * 1000.0))

    def stats(lst):
        if not lst:
            return None
        values = [v for _, v in lst]
        return {
            "count": len(values),
            "mean_ms": statistics.mean(values),
            "median_ms": statistics.median(values),
            "min_ms": min(values),
            "max_ms": max(values),
        }

    tp_stats = stats(tp_latencies)
    sl_stats = stats(sl_latencies)

    print("OCO Debug Analysis Report")
    print("========================")
    print(f"Total EXECUTE_ORDER entries: {len(all_results)}")
    print(f"Total with TP verify timestamps: {len(tp_latencies)}")
    print(f"Total with SL verify timestamps: {len(sl_latencies)}")
    print("")
    print("TP latency stats (ms):")
    if tp_stats:
        for k, v in tp_stats.items():
            print(f"  {k}: {v:.1f}" if isinstance(v, float) else f"  {k}: {v}")
    else:
        print("  no samples")
    print("")
    print("SL latency stats (ms):")
    if sl_stats:
        for k, v in sl_stats.items():
            print(f"  {k}: {v:.1f}" if isinstance(v, float) else f"  {k}: {v}")
    else:
        print("  no samples")

    # show up to 5 samples
    print("\nSamples (up to 5):")
    for r in all_results[:5]:
        print("---")
        print("file:", r["file"])
        print("exec_ts:", r["exec_ts"])
        print("main_order_id:", r["main_order_id"])
        print("tp_ts:", r["tp_ts"], "sl_ts:", r["sl_ts"])
        if r["tp_order_info"]:
            print("tp_order.id:", r["tp_order_info"].get("id") if isinstance(r["tp_order_info"], dict) else "N/A")
        if r["sl_order_info"]:
            print("sl_order.id:", r["sl_order_info"].get("id") if isinstance(r["sl_order_info"], dict) else "N/A")


if __name__ == "__main__":
    main()
