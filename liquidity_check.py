import requests

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "ZECUSDT",
    "XRPUSDT",
    "SOLUSDT",
    "ZILUSDT",
]

BASE_URL = "https://apiv2.nobitex.ir/v3/orderbook/"


def check_market(symbol):

    response = requests.get(
        BASE_URL + symbol,
        headers={"User-Agent": "MABOT/0.1.0"},
        timeout=15
    )

    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok":
        raise ValueError("Unexpected API response")

    bids = data.get("bids", [])
    asks = data.get("asks", [])

    if not bids or not asks:
        raise ValueError("Empty order book")

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])

    mid = (best_bid + best_ask) / 2
    spread = (best_ask - best_bid) / mid * 100

    bid_depth = sum(
        float(p) * float(q)
        for p, q in bids
        if float(p) >= mid * 0.99
    )

    ask_depth = sum(
        float(p) * float(q)
        for p, q in asks
        if float(p) <= mid * 1.01
    )

    return spread, bid_depth, ask_depth


print("\nMABOT - LIQUIDITY ANALYSIS")
print("=" * 65)

for symbol in SYMBOLS:

    try:
        spread, bids, asks = check_market(symbol)

        print(f"\n{symbol}")
        print(f"Spread: {spread:.4f}%")
        print(f"Bid depth (1%): {bids:.2f} USDT")
        print(f"Ask depth (1%): {asks:.2f} USDT")

    except Exception as error:
        print(f"\n{symbol} ERROR: {error}")