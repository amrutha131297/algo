import os
import requests
import time
import datetime as dt
from typing import List, Optional
from flask import Flask

# ================= CONFIG (LIVE) =================
FYERS_BASE = "https://api.fyers.in"
FYERS_DATA_BASE = "https://api.fyers.in/data-rest/v2"
FYERS_ACCESS_TOKEN = "YOUR_FYERS_ACCESS_TOKEN"   # paste valid token
FYERS_APP_ID = "CGDSV5GE7E-100"
BANKNIFTY_SPOT = "NSE:NIFTYBANK-INDEX"
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3

# ========== TELEGRAM CONFIG ==========
TELEGRAM_BOT_TOKEN = "8428714129:AAERaYcX9fgLcQPWUwPP7z1C56EnvEf5jhQ"
TELEGRAM_CHAT_ID = "1597187434"


def send_telegram(msg: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("❌ Telegram error:", e)


class FyersBroker:
    def __init__(self, base_url: str, data_url: str, access_token: str, app_id: str):
        if not access_token:
            raise ValueError("❌ No access token found! Please paste it in FYERS_ACCESS_TOKEN")
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
                    data = resp.json()
                else:
                    resp.raise_for_status()
                    data = {"raw": resp.text}
                return data
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    time.sleep(1.0 * attempt)
                else:
                    raise
        raise last_err

    def get_candle(self, symbol: str, interval: str, start_time: str, end_time: str) -> Optional[List[List[float]]]:
        url = f"{self.data_url}/history/"
        params = {
            "symbol": symbol,
            "resolution": interval,
            "date_format": 1,
            "range_from": start_time,
            "range_to": end_time,
        }
        data = self._get(url, params=params)
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


def run_strategy():
    broker = FyersBroker(FYERS_BASE, FYERS_DATA_BASE, FYERS_ACCESS_TOKEN, FYERS_APP_ID)

    msg = "⏳ Waiting for 09:30 candle close..."
    print(msg)
    send_telegram(msg)

    # Wait until 9:30:05
    while dt.datetime.now().time() < dt.time(9, 30, 5):
        time.sleep(1)

    msg = "✅ 09:25-09:30 candle closed. Fetching high/low..."
    print(msg)
    send_telegram(msg)

    today = dt.datetime.now().strftime("%Y-%m-%d")
    start_time = f"{today} 09:25:00"
    end_time = f"{today} 09:30:00"

    candles = broker.get_candle(BANKNIFTY_SPOT, "5", start_time, end_time)
    if not candles:
        msg = "❌ Could not fetch 9:25-9:30 candle. Exiting."
        print(msg)
        send_telegram(msg)
        return

    c = candles[-1]
    if len(c) < 6:
        msg = f"❌ Unexpected candle format: {c}"
        print(msg)
        send_telegram(msg)
        return

    candle_high = float(c[2])
    candle_low = float(c[3])

    msg = f"✅ 9:25-9:30 Candle High: {candle_high:.2f}, Low: {candle_low:.2f}"
    print(msg)
    send_telegram(msg)

    spot_price = broker.get_ltp(BANKNIFTY_SPOT)
    if spot_price is None:
        msg = "❌ Could not fetch current spot price."
        print(msg)
        send_telegram(msg)
        return

    msg = f"📌 Current Spot Price: {spot_price:.2f}"
    print(msg)
    send_telegram(msg)

    if spot_price > candle_high:
        msg = "🚀 Breakout UP detected (spot > high)."
    elif spot_price < candle_low:
        msg = "🔻 Breakout DOWN detected (spot < low)."
    else:
        msg = "⏳ No breakout yet. Waiting/monitoring..."

    print(msg)
    send_telegram(msg)


# ================= FLASK APP =================
app = Flask(__name__)


@app.route("/")
def home():
    return "✅ Algo Bot is running on Railway 🚀"


@app.route("/run")
def run_now():
    try:
        run_strategy()
        return "✅ Strategy executed. Check Telegram for updates."
    except Exception as e:
        return f"❌ Error: {e}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
