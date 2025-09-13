import os
import time
import requests
import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

# ================= CONFIG =================
FYERS_BASE = os.getenv("FYERS_BASE", "https://api.fyers.in")
FYERS_DATA_BASE = os.getenv("FYERS_DATA_BASE", "https://api.fyers.in/data-rest/v2")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")
FYERS_APP_ID = os.getenv("FYERS_APP_ID")

BANKNIFTY_SPOT = "NSE:NIFTYBANK-INDEX"
IST = ZoneInfo("Asia/Kolkata")

# ================= TELEGRAM CONFIG =================
TELEGRAM_TOKEN = "8428714129:AAERaYcX9fgLcQPWUwPP7z1C56EnvEf5jhQ"
TELEGRAM_CHAT_ID = "1597187434"  


def send_telegram(msg: str):
    """Send notification to Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})
        if resp.status_code != 200:
            print("⚠️ Telegram send failed:", resp.text)
    except Exception as e:
        print("⚠️ Telegram error:", e)


# ================= BROKER CLASS =================
class FyersBroker:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}"
        })

    def _get(self, url: str, params=None, max_retries=10, delay=5):
        """ GET request with retry logic """
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as e:
                last_err = e
                print(f"⚠️ GET retry {attempt+1}/{max_retries} failed: {e}")
                time.sleep(delay)
            except Exception as e:
                last_err = e
                print(f"⚠️ Other error: {e}")
                time.sleep(delay)
        print("❌ Could not fetch data after retries. Skipping this candle...")
        return None

    def get_candle(self, symbol: str, resolution: str, start: dt.datetime, end: dt.datetime):
        url = f"{FYERS_DATA_BASE}/history/"
        params = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": 1,
            "range_from": start.strftime("%Y-%m-%d %H:%M:%S"),
            "range_to": end.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data = self._get(url, params)
        if not data or "candles" not in data:
            return []
        return data["candles"]


# ================= MAIN STRATEGY =================
def main():
    broker = FyersBroker(FYERS_ACCESS_TOKEN)

    # Sleep until 9:30:05 IST
    now = dt.datetime.now(IST)
    target_time = now.replace(hour=9, minute=30, second=5, microsecond=0)
    if now > target_time:
        target_time = target_time + dt.timedelta(days=1)

    sleep_sec = (target_time - now).total_seconds()
    msg = f"⏳ Sleeping {int(sleep_sec)}s until {target_time.strftime('%H:%M:%S %Z')}"
    print(msg)
    send_telegram(msg)
    time.sleep(sleep_sec)

    # Get 9:25–9:30 candle
    start_time = target_time.replace(hour=9, minute=25, second=0)
    end_time = target_time.replace(hour=9, minute=30, second=0)

    candles = broker.get_candle(BANKNIFTY_SPOT, "5", start_time, end_time)
    if not candles:
        msg = "⚠️ No candle data received. Skipping today's trade."
        print(msg)
        send_telegram(msg)
        return

    # Got candle data
    o, h, l, c, v = candles[0]
    msg = f"✅ Candle received (09:25–09:30)\nO:{o}, H:{h}, L:{l}, C:{c}, V:{v}"
    print(msg)
    send_telegram(msg)

    # === your strategy logic here ===
    # Example breakout conditions can be coded below


if __name__ == "__main__":
    main()
