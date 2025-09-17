import os
import requests
import time
import datetime as dt
import logging
from typing import List, Optional
from flask import Flask, request, jsonify

# ==============================
# Logging Setup
# ==============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ================= CONFIG (LIVE) =================
FYERS_BASE = "https://api.fyers.in"
FYERS_DATA_BASE = "https://api.fyers.in/data-rest/v2"
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN")  # set in Railway variables
FYERS_APP_ID = os.getenv("FYERS_APP_ID", "CGDSV5GE7E-100")
BANKNIFTY_SPOT = "NSE:NIFTYBANK-INDEX"
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3

# ========== TELEGRAM CONFIG ==========
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")

# ==============================
# Telegram Helper
# ==============================
def send_telegram(msg: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("❌ TELEGRAM_TOKEN or CHAT_ID not set in Railway variables!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, data=payload, timeout=5)
        logging.info(f"📩 Sent Telegram: {msg}")
    except Exception as e:
        logging.error(f"❌ Telegram error: {e}")

# ==============================
# Fyers Broker Class
# ==============================
class FyersBroker:
    def __init__(self, base_url: str, data_url: str, access_token: str, app_id: str):
        if not access_token:
            raise ValueError("❌ No access token found! Please set FYERS_ACCESS_TOKEN in Railway variables.")
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
        logging.error(msg)
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
            logging.error(msg)
            send_telegram(msg)
        return None

# ==============================
# Strategy Logic
# ==============================
def run_strategy():
    broker = FyersBroker(FYERS_BASE, FYERS_DATA_BASE, FYERS_ACCESS_TOKEN, FYERS_APP_ID)

    msg = "⏳ Waiting for 09:30 candle close..."
    logging.info(msg)
    send_telegram(msg)

    while dt.datetime.now().time() < dt.time(9, 30, 5):
        time.sleep(1)

    msg = "✅ 09:25-09:30 candle closed. Fetching high/low..."
    logging.info(msg)
    send_telegram(msg)

    today = dt.datetime.now().strftime("%Y-%m-%d")
    start_time = f"{today} 09:25:00"
    end_time = f"{today} 09:30:00"

    candles = broker.get_candle(BANKNIFTY_SPOT, "5", start_time, end_time)
    if not candles:
        msg = "❌ Could not fetch 9:25-9:30 candle. Exiting."
        logging.error(msg)
        send_telegram(msg)
        return

    c = candles[-1]
    if len(c) < 6:
        msg = f"❌ Unexpected candle format: {c}"
        logging.error(msg)
        send_telegram(msg)
        return

    candle_high = float(c[2])
    candle_low = float(c[3])

    msg = f"✅ 9:25-9:30 Candle High: {candle_high:.2f}, Low: {candle_low:.2f}"
    logging.info(msg)
    send_telegram(msg)

    spot_price = broker.get_ltp(BANKNIFTY_SPOT)
    if spot_price is None:
        msg = "❌ Could not fetch current spot price."
        logging.error(msg)
        send_telegram(msg)
        return

    msg = f"📌 Current Spot Price: {spot_price:.2f}"
    logging.info(msg)
    send_telegram(msg)

    if spot_price > candle_high:
        msg = "🚀 Breakout UP detected (spot > high)."
    elif spot_price < candle_low:
        msg = "🔻 Breakout DOWN detected (spot < low)."
    else:
        msg = "⏳ No breakout yet. Waiting/monitoring..."

    logging.info(msg)
    send_telegram(msg)

# ==============================
# Flask App
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Algo Bot + Telegram running on Railway 🚀"

@app.route("/run")
def run_now():
    try:
        run_strategy()
        return "✅ Strategy executed. Check Telegram for updates."
    except Exception as e:
        return f"❌ Error: {e}"

@app.route("/send-test")
def send_test():
    send_telegram("🚀 Test message from Railway Flask app!")
    return "✅ Test message sent to Telegram!"

@app.route(f"/webhook/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        logging.info(f"📩 Incoming Telegram update: {data}")

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text", "")
            reply = f"You said: {text}"
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": chat_id, "text": reply})
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logging.error(f"❌ Error in webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

# ==============================
# Run App (Railway)
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logging.info(f"🚀 Starting app on port {port}")
    app.run(host="0.0.0.0", port=port)
