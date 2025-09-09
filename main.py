import os
import time
import requests
import datetime as dt
from typing import List, Optional
from zoneinfo import ZoneInfo

# ================= CONFIG =================
FYERS_BASE = os.getenv("FYERS_BASE", "https://api.fyers.in")
FYERS_DATA_BASE = os.getenv("FYERS_DATA_BASE", "https://api.fyers.in/data-rest/v2")
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiZDoxIiwiZDoyIiwieDowIiwieDoxIiwieDoyIl0sImF0X2hhc2giOiJnQUFBQUFCb3YtZjljNGVhVGZ0cVJXaVlnZFRFdVZlcnVCejh3NGV1ZXpILXgySy1yYW9EbHNyT1oxQzRPSmVQeDNIZDc2UHNLd2FuQzVKMEJfOTM4YVYzZFE2STJPWlJiMm0tVGFoQ2tzQ2R5SGE2Z3dtQll5ST0iLCJkaXNwbGF5X25hbWUiOiIiLCJvbXMiOiJLMSIsImhzbV9rZXkiOiI5YmU1NGU0ZjRjZTJkOTFhMTVkZWQ4YzcyODVkMDMyODA5NWFkNTcyMTc5MjNlMjEzOWZjOGRkMSIsImlzRGRwaUVuYWJsZWQiOiJOIiwiaXNNdGZFbmFibGVkIjoiTiIsImZ5X2lkIjoiWUEyNDY0MCIsImFwcFR5cGUiOjEwMCwiZXhwIjoxNzU3NDY0MjAwLCJpYXQiOjE3NTc0MDcyMjksImlzcyI6ImFwaS5meWVycy5pbiIsIm5iZiI6MTc1NzQwNzIyOSwic3ViIjoiYWNjZXNzX3Rva2VuIn0.6SZs3jxGOTMfxDPHvh59n81PzGzawrKUCQW-_W2DJJs" )
FYERS_APP_ID = os.getenv("FYERS_APP_ID", "CGDSV5GE7E-100")
BANKNIFTY_SPOT = os.getenv("BANKNIFTY_SPOT", "NSE:NIFTYBANK-INDEX")

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# ========== TELEGRAM CONFIG ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8428714129:AAERaYcX9fgLcQPWUwPP7z1C56EnvEf5jhQ")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1597187434")

IST = ZoneInfo("Asia/Kolkata")


def send_telegram(msg: str):
    """Send a Telegram message."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram creds not set; skipping message:", msg)
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("❌ Telegram error:", e)


class FyersBroker:
    def __init__(self, base_url: str, data_url: str, access_token: str, app_id: str):
        if not access_token:
            raise ValueError("❌ No access token found! Set FYERS_ACCESS_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.data_url = data_url.rstrip("/")
        self.access_token = access_token
        self.app_id = app_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        })

    def _get(self, url: str, params: dict) -> dict:
        last_err = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                if resp.headers.get("Content-Type", "").startswith("application/json"):
                    return resp.json()
                resp.raise_for_status()
                return {"raw": resp.text}
            except Exception as e:
                last_err = e
                print(f"⚠️ GET retry {attempt}/{MAX_RETRIES} failed: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(1.0 * attempt)
        raise last_err

    def get_candle(
        self, symbol: str, interval: str, start_time: str, end_time: str
    ) -> Optional[List[List[float]]]:
        url = f"{self.data_url}/history/"
        params = {
            "symbol": symbol,
            "resolution": interval,
            "date_format": 1,
            "range_from": start_time,
            "range_to": end_time,
        }
        data = self._get(url, params)
        if isinstance(data, dict) and "candles" in data and data["candles"]:
            return data["candles"]
        msg = f"❌ Candle fetch error: {data}"
        print(msg)
        send_telegram(msg)
        return None

    def get_ltp(self, symbol: str) -> Optional[float]:
        url = f"{self.data_url}/quotes/"
        params = {"symbols": symbol}
        try:
            data = self._get(url, params=params)
            if "d" in data and data["d"] and "v" in data["d"][0] and "lp" in data["d"][0]["v"]:
                return data["d"][0]["v"]["lp"]
        except Exception as e:
            msg = f"❌ LTP fetch error: {repr(e)}"
            print(msg)
            send_telegram(msg)
        return None


def wait_until_ist(target_h: int, target_m: int, target_s: int):
    now_ist = dt.datetime.now(IST)
    target = now_ist.replace(hour=target_h, minute=target_m, second=target_s, microsecond=0)
    if target <= now_ist:
        target = target + dt.timedelta(days=1)
    seconds = (target - now_ist).total_seconds()
    print(f"⏳ Sleeping {int(seconds)}s until {target.astimezone(IST).time()} IST")
    time.sleep(max(0, seconds))


def main():
    broker = FyersBroker(FYERS_BASE, FYERS_DATA_BASE, FYERS_ACCESS_TOKEN, FYERS_APP_ID)

    send_telegram("⏳ Waiting for 09:30 candle close (IST)...")
    wait_until_ist(9, 30, 5)

    send_telegram("✅ 09:25–09:30 candle closed. Fetching high/low...")

    today_ist = dt.datetime.now(IST).date()
    start_time = f"{today_ist} 09:25:00"
    end_time   = f"{today_ist} 09:30:00"

    candles = broker.get_candle(BANKNIFTY_SPOT, "5", start_time, end_time)
    if not candles:
        send_telegram("❌ Could not fetch 09:25–09:30 candle. Exiting.")
        return

    c = candles[-1]
    if len(c) < 4:
        send_telegram(f"❌ Unexpected candle format: {c}")
        return

    candle_high = float(c[2])
    candle_low  = float(c[3])

    send_telegram(f"📊 09:25–09:30 Candle: High={candle_high:.2f}, Low={candle_low:.2f}")

    spot_price = broker.get_ltp(BANKNIFTY_SPOT)
    if spot_price is None:
        send_telegram("❌ Could not fetch current spot price.")
        return

    send_telegram(f"📌 Current Spot Price: {spot_price:.2f}")

    if spot_price > candle_high:
        send_telegram("🚀 Breakout UP detected (spot > high).")
    elif spot_price < candle_low:
        send_telegram("🔻 Breakout DOWN detected (spot < low).")
    else:
        send_telegram("⏳ No breakout yet. Waiting/monitoring...")


if __name__ == "__main__":
    main()
