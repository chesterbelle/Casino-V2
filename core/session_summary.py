"""
Session summary and reporting utilities for Casino V2.
"""


def print_session_summary(stats: dict) -> None:
    """Imprime resumen de la sesión"""
    print("\n" + "=" * 60)
    print(f"📌 Dataset: {stats['dataset']}")
    print(f"🎮 Player:  {stats['player'].upper()}")
    print("-" * 60)
    init_balance = stats.get("initial_balance")
    if isinstance(init_balance, (int, float)):
        init_str = f"{init_balance:.2f}"
    else:
        init_str = str(init_balance) if init_balance is not None else "n/a"
    print(f"   Balance inicial       : {init_str}")
    print(f"   Velas procesadas      : {stats['candles']}")
    print(f"   Trades BET            : {stats['bet_trades']}")
    print(f"   Trades GHOST          : {stats['ghost_trades']}")
    print(f"   Trades SKIP           : {stats.get('skip_trades', 0)}")
    print(f"   Wins / Losses         : {stats['wins']} / {stats['losses']}")
    print(f"   WinRate (BET)         : {stats['winrate']:.2f}%")
    print(f"   Comisiones totales    : {stats['fees']:.2f}")
    print(f"   Funding total         : {stats.get('funding', 0.0):.2f}")
    print(f"   Liquidaciones         : {stats.get('liquidations', 0)}")
    print(f"   Balance final         : {stats['final_balance']:.2f}")
    pnl = stats["final_balance"] - stats["initial_balance"]
    pnl_pct = (pnl / stats["initial_balance"] * 100) if stats["initial_balance"] > 0 else 0.0
    print(f"   PnL Total             : {pnl:+.2f} ({pnl_pct:+.2f}%)")
    print("=" * 60 + "\n")
