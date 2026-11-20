"""Read-only summary of the paper account: python -m paper_trading.report [--db PATH]"""
import argparse
import sqlite3

import pandas as pd


def build_report(db_path: str) -> dict:
    with sqlite3.connect(db_path) as con:
        events = pd.read_sql_query(
            "SELECT rowid AS n, event_id, side, symbol, quantity, price, fee, cash_after FROM events ORDER BY rowid", con)
        snaps = pd.read_sql_query("SELECT * FROM equity_snapshots ORDER BY timestamp", con)
        cash = con.execute("SELECT cash FROM account WHERE id=1").fetchone()[0]
        positions = pd.read_sql_query("SELECT * FROM positions", con)
    trips, open_buy = [], {}
    for e in events.itertuples():
        if e.side == "BUY":
            open_buy[e.symbol] = e
        elif e.symbol in open_buy:
            b = open_buy.pop(e.symbol)
            cost = b.quantity * b.price + b.fee
            proceeds = e.quantity * e.price - e.fee
            trips.append({"symbol": e.symbol, "entry": b.event_id, "exit": e.event_id,
                          "net_pnl": proceeds - cost, "return_pct": (proceeds / cost - 1) * 100,
                          "reason": e.event_id.rsplit(":", 1)[-1]})
    trips = pd.DataFrame(trips)
    out = {"cash": cash, "open_positions": positions, "round_trips": trips, "snapshots": snaps}
    if not snaps.empty:
        eq = snaps["equity"]
        out["equity"], out["max_drawdown_pct"] = float(eq.iloc[-1]), float((eq / eq.cummax() - 1).min() * 100)
    if not trips.empty:
        wins, losses = trips.loc[trips.net_pnl > 0, "net_pnl"].sum(), -trips.loc[trips.net_pnl < 0, "net_pnl"].sum()
        out.update({"trades": len(trips), "win_rate_pct": float((trips.net_pnl > 0).mean() * 100),
                    "profit_factor": float(wins / losses) if losses > 0 else float("nan"),
                    "net_pnl": float(trips.net_pnl.sum())})
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="results/mabot_paper.sqlite3")
    r = build_report(parser.parse_args().db)
    print("MABOT PAPER REPORT (simulation only)")
    for key in ("equity", "cash", "max_drawdown_pct", "trades", "win_rate_pct", "profit_factor", "net_pnl"):
        if key in r:
            print(f"  {key}: {r[key]:.2f}")
    print("  open positions:", len(r["open_positions"]))
    print("  NOTE: judge only after >= 30 closed trades and 8-12 weeks; compare with the backtest, do not trust a few trades.")


if __name__ == "__main__":
    main()
