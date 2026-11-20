import requests
from datetime import datetime
from decimal import Decimal

API_URL = "https://apiv2.nobitex.ir/v3/orderbook/BTCUSDT"

def analyze_market():

    print("\n========== MABOT AI ==========")
    print("Market Analysis Engine")
    print("=============================\n")

    try:
        response = requests.get(
            API_URL,
            headers={"User-Agent": "MABOT/0.1.0"},
            timeout=15
        )

        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            print("Market API returned an unexpected status.")
            return

        bids = data.get("bids", [])
        asks = data.get("asks", [])

        if not bids or not asks:
            print("Order book is empty.")
            return

        best_bid = Decimal(bids[0][0])
        best_ask = Decimal(asks[0][0])
        last_price = Decimal(data["lastTradePrice"])

        spread = best_ask - best_bid
        spread_percent = (spread / best_bid) * 100

        print("Symbol: BTC/USDT")
        print("Last Price:", last_price)
        print("Best Bid:", best_bid)
        print("Best Ask:", best_ask)
        print("Spread:", spread)
        print("Spread Percent:", round(spread_percent, 4), "%")

        print(
            "Received At:",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        print("\nConnection: SUCCESS")
        print("Trading: DISABLED")

    except Exception as error:
        print("\nConnection Error:", error)


if __name__ == "__main__":
    analyze_market()