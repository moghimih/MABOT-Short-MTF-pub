# MABOT — پژوهش و بک‌تست بازار اسپات

این نسخه برای **تحقیق، بک‌تست تاریخی و توسعه کنترل‌شده** آماده شده است. هیچ سفارش واقعی به صرافی ارسال نمی‌کند.

## وضعیت ایمنی

- `LIVE_TRADING_ENABLED = False`
- `PAPER_TRADING_ENABLED = True` فقط یک تنظیم است؛ هنوز اتصال کامل Paper Trading زنده به نوبیتکس در این نسخه پیاده‌سازی نشده است.
- هیچ API Key یا اطلاعات ورود صرافی در پروژه قرار ندهید.
- تا پیش از تکمیل و آزمون جداگانه ماژول داده زنده، تطبیق سفارش، خطاهای شبکه و بازیابی وضعیت، اجرای زنده ممنوع است.

## ساختار اصلی

- `data/`: بارگذاری و اعتبارسنجی داده‌های تاریخی
- `indicators/`: EMA، RSI، ATR و ADX با محاسبه جداگانه در هر segment
- `strategies/`: استراتژی‌های BASELINE، ADX و BREAKOUT
- `risk/`: اندازه موقعیت، ریسک پرتفوی، حد ضرر و اجرای حد ضرر
- `backtesting/`: موتور بک‌تست و موتور مدیریت ریسک
- `tests/`: آزمون‌های واحد و سناریوهای مصنوعی
- `research/`: تحلیل مسیر قیمت پس از سیگنال ورود
- `results/`: خروجی‌های تحقیق و گزارش‌های اجرای مجدد

## نصب در ویندوز

با Python 3.12:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## اجرای آزمون‌ها

```bat
python -m pytest -q
```

یا فایل `run_tests.bat` را اجرا کنید.

## اجرای بک‌تست مقایسه‌ای

```bat
python test_backtest_common_period_risk.py
```

این اسکریپت نتایج موتور قدیمی و موتور مدیریت ریسک را کنار هم ذخیره می‌کند. این دو موتور از نظر مدیریت سرمایه یکسان نیستند؛ بنابراین مقایسه مستقیم بازده آن‌ها معیار منصفانه‌ای برای انتخاب استراتژی نیست.

## تحلیل رفتار قیمت پس از سیگنال ورود

```bat
python -m research.forward_entry_diagnostics
```

خروجی‌ها در `results/` ذخیره می‌شوند. این تحلیل، فرصت‌های سیگنال را جداگانه بررسی می‌کند؛ نمونه‌ها ممکن است هم‌پوشانی داشته باشند و معادل معاملات مستقل یا بک‌تست پرتفوی نیستند.

## تنظیمات فعلی

- بازار هدف: اسپات
- تایم‌فریم: ۴ ساعته
- نمادها: BTCUSDT، ETHUSDT، ZECUSDT، XRPUSDT
- سرمایه اولیه بک‌تست: ۱۰۰ واحد
- کارمزد فرضی هر سمت: ۰٫۲٪
- لغزش فرضی هر سمت: ۰٫۰۵٪
- ریسک هدف هر معامله: ۱٪
- سقف ریسک باز پرتفوی: ۲٪
- حداکثر موقعیت هم‌زمان: ۲

این اعداد فرض‌های پژوهشی هستند و باید با شرایط واقعی کارمزد، نقدشوندگی و حداقل سفارش صرافی تطبیق داده شوند.

## محدودیت‌های مهم

1. سوددهی آینده تضمین نشده است؛ نتایج تاریخی ممکن است به رژیم بازار وابسته باشند.
2. نتایج BREAKOUT در داده فعلی بهتر از دو گزینه دیگر بوده، اما هنوز به اعتبارسنجی خارج از نمونه و Paper Trading طولانی نیاز دارد.
3. XRP در بررسی‌های قبلی ضعیف بوده و ZEC سهم مهمی از سود بعضی استراتژی‌ها داشته است؛ تمرکز نمادها باید در تحلیل‌های بعدی کنترل شود.
4. موتور زنده، اتصال امن به API، ثبت سفارش آزمایشی، تطبیق وضعیت سفارش و بازیابی پس از قطعی هنوز ساخته نشده‌اند.
5. بک‌تست از مدل ساده‌شده پرشدن سفارش و لغزش استفاده می‌کند؛ اجرای واقعی می‌تواند متفاوت باشد.


## Paper Trading — هسته محلی مرحله اول

هسته اولیه شبیه‌ساز معاملات فرضی در `paper_trading/` اضافه شده است:

- دفتر موجودی و موقعیت‌های اسپات با SQLite و بازیابی پس از راه‌اندازی مجدد
- اعمال کارمزد و لغزش نامساعد در خرید و فروش
- جلوگیری از سفارش تکراری با `event_id`
- محدودیت تعداد موقعیت‌های باز و کنترل موجودی مجازی
- تابع محاسبه اندازه موقعیت بر اساس ریسک تا حد ضرر

این هسته **محلی و مستقل** است و هیچ endpoint معاملاتی یا کلید API ندارد. هنوز دریافت‌کننده کندل زنده، زمان‌بند ۴ ساعته، پردازش سیگنال خودکار، کنترل کهنگی داده و پایش چندروزه پیاده‌سازی نشده‌اند؛ بنابراین این نسخه را Paper Trading زنده یا آماده اجرای پیوسته تلقی نکنید.

آزمون کامل پروژه پس از این تغییر: `29 passed`.

## Paper Trading Phase 2 (read-only market data)

A read-only 4h Nobitex market-data client and a local paper signal runner are now available:

```bash
python -m paper_trading.runner --once
python -m paper_trading.runner --interval 60
```

The runner stores virtual account state and processed candle keys in `results/mabot_paper.sqlite3` by default. It filters incomplete/stale candles, applies the existing gap-aware BREAKOUT strategy, and records simulated orders only. It has no live order-placement functionality. See `PAPER_TRADING_PHASE2_REPORT.md` for limitations and test coverage.

## Phase 3 operational safeguards

The paper runner now writes rotating logs (default `results/logs/paper_runner.log`), retries read-only candle requests with capped exponential backoff, isolates failures by symbol, and halts the current cycle after three consecutive symbol failures. Configure with:

```bash
python -m paper_trading.runner --interval 60 --retry-attempts 3 --log-file results/logs/paper_runner.log
```

This remains paper-only. Network/API availability must be verified on the deployment machine; a successful local unit test does not establish live endpoint connectivity.
