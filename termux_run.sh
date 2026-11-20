#!/data/data/com.termux/files/usr/bin/sh
# Optional timeframe: 1h, 4h (default), or 1d.
termux-wake-lock 2>/dev/null
cd "$(dirname "$0")"
TF="${1:-4h}"
case "$TF" in
  1h) DB="results/paper_1h.sqlite3"; LOG="results/logs/paper_1h.log"; PORT=8081 ;;
  4h) DB="results/paper_4h.sqlite3"; LOG="results/logs/paper_4h.log"; PORT=8082 ;;
  1d) DB="results/paper_1d.sqlite3"; LOG="results/logs/paper_1d.log"; PORT=8083 ;;
  *) echo "Choose 1h, 4h, or 1d"; exit 1 ;;
esac
python -m paper_trading.service --share --timeframe "$TF" --db "$DB" --log-file "$LOG" --port "$PORT"
