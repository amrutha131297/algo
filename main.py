import os
import time
import requests
import threading
import datetime as dt
from zoneinfo import ZoneInfo

# ================== CONFIG ==================
FYERS_BASE = "https://api.fyers.in"
FYERS_DATA_BASE = "https://api.fyers.in/data-rest/v2"
FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
FYERS_APP_ID = os.getenv("FYERS_APP_ID", "YOUR_APP_ID")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

MARKET = "NSE:NIFTYBANK-INDEX"
TIMEZONE = ZoneInfo("Asia/Kolkata")

RUN_STRATEGY = False  # start/stop flag controlled by Telegram

# ================== TELEGRAM ==================
def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        r = requests.post(url, data=payload)
        if r.status_code != 200:
            print("⚠ Telegram send failed:", r.text)
    except Exception as e:
        print("❌ Telegram error:", str(e))


def listen_telegram_commands():
    """ Continuously listen for Telegram bot commands """
    global RUN_STRATEGY
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": offset}
            resp = requests.get(url, params=params).json()

            if "result" in resp:
                for update in resp["result"]:
                    offset = update["update_id"] + 1
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip().lower()

                        if text == "/start":
                            RUN_STRATEGY = True
                            send_telegram_message("🚀 9:30 Breakout Strategy Started!")
                        elif text == "/stop":
                            RUN_STRATEGY = False
                            send_telegram_message("🛑 Strategy Stopped!")
                        elif text == "/status":
                            status = "✅ Running" if RUN_STRATEGY else "⏸ Stopped"
                            send_telegram_message(f"📊 Current Status: {status}")
        except Exception as e:
            print("⚠ Command Listener Error:", str(e))
        time.sleep(2)

# ================== FYERS DATA FETCH ==================
def get_history(symbol, resolution="5", start=None, end=None):
    url = f"{FYERS_DATA_BASE}/history/"
    headers = {"Authorization": f"Bearer {FYERS_ACCESS_TOKEN}"}
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "date_format": "1",
        "range_from": start,
        "range_to": end,
        "cont_flag": "1"
    }
    try:
        resp = requests.get(url, headers=headers, params=params)
        return resp.json()
    except Exception as e:
        print("⚠ History fetch failed:", str(e))
        return None

# ================== STRATEGY ==================
def breakout_strategy():
    global RUN_STRATEGY
    traded = False  # allow only one trade per day

    while True:
        if RUN_STRATEGY:
            now = dt.datetime.now(TIMEZONE)

            # Run only after 9:30 AM
            if now.hour == 9 and now.minute >= 30 and not traded:
                today = now.date().strftime("%Y-%m-%d")
                data = get_history(MARKET, resolution="5", start=today, end=today)

                if not data or "candles" not in data:
                    time.sleep(5)
                    continue

                candles = data["candles"]
                if len(candles) < 2:
                    time.sleep(5)
                    continue

                # Take 9:25-9:30 candle
                breakout_candle = candles[-2]
                high = breakout_candle[2]
                low = breakout_candle[3]

                msg = f"📊 9:30 Breakout Levels:\nHigh: {high}\nLow: {low}"
                send_telegram_message(msg)

                # Example logic: Place trade if high breaks
                # (Replace this with your CE/PE order placement logic)
                send_telegram_message("🚀 Simulated Trade Entry: Buy CE at breakout high")

                traded = True

            time.sleep(10)
        else:
            time.sleep(3)

# ================== MAIN ==================
if __name__ == "__main__":
    # Start Telegram listener in background
    threading.Thread(target=listen_telegram_commands, daemon=True).start()

    # Start breakout strategy loop
    breakout_strategy()
