import requests

URL = "https://apiv2.nobitex.ir/market/stats"

def main():
    print("MABOT - USDT MARKET DISCOVERY")
    print("=" * 45)

    try:
        response = requests.get(URL, timeout=20)
        response.raise_for_status()

        data = response.json()

        if data.get("status") != "ok":
            print("API Error")
            return

        markets = data.get("stats", {})
        results = []

        for symbol, info in markets.items():

            if not symbol.endswith("-usdt"):
                continue

            if info.get("isClosed"):
                continue

            volume = float(info.get("volumeDst") or 0)
            price = float(info.get("latest") or 0)

            if volume <= 0 or price <= 0:
                continue

            results.append({
                "symbol": symbol,
                "volume": volume,
                "price": price
            })

        results.sort(
            key=lambda x: x["volume"],
            reverse=True
        )

        print("USDT markets found:", len(results))
        print("\nTOP 10 USDT MARKETS\n")

        for item in results[:10]:
            print(
                f"{item['symbol']:15} "
                f"Volume: {item['volume']:,.2f} USDT "
                f"Price: {item['price']:,.6f}"
            )

    except Exception as error:
        print("ERROR:", error)


if __name__ == "__main__":
    main()