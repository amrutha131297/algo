import os
import requests
from flask import Flask, request
import threading
import time
import datetime as dt

# ==============================
# Telegram Setup
# ==============================
TELEGRAM_TOKEN = "8428714129:AAERaYcX9fgLcQPWUwPP7z1C56EnvEf5jhQ"  # Replace with your token
CHAT_ID = "1597187434"  # Replace with your chat ID

def send_telegram_message(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("Telegram Error:", e)

# ==============================
# Trading Bot Logic
# ==============================
bot_running = False
trade_taken = False
direction = None

def get_930_levels():
    """
    Replace this with API call to get 9:25–9:30 candle high/low
    For demo: hardcoded values
    """
    return 49200, 49120  # Example: High, Low

def select_option(premium_range=(35, 45)):
    """
    Replace with API to fetch OTM options in the premium range.
    For demo: return dummy strike
    """
    return "BANKNIFTY24SEP49000CE", 40  # (symbol, premium)

def trading_loop():
    global bot_running, trade_taken, direction
    send_telegram_message("📊 Trading loop started... Waiting for breakout after 9:30 candle.")

    high, low = get_930_levels()

    while bot_running and not trade_taken:
        now = dt.datetime.now().time()
        if now >= dt.time(9, 30):  # market time check
            # DEMO: replace with live price fetch
            ltp = 49250  # Example price

            if ltp > high and direction is None:  # Breakout high → Buy CE
                option, price = select_option()
                if 35 <= price <= 45:
                    direction = "CE"
                    trade_taken = True
                    sl = price - 7
                    target = price + 10
                    send_telegram_message(f"🚀 CE Breakout! Bought {option} @ {price}\n🎯 Target: {target}, ❌ SL: {sl}")

            elif ltp < low and direction is None:  # Breakout low → Buy PE
                option, price = select_option()
                if 35 <= price <= 45:
                    direction = "PE"
                    trade_taken = True
                    sl = price - 7
                    target = price + 10
                    send_telegram_message(f"🚀 PE Breakout! Bought {option} @ {price}\n🎯 Target: {target}, ❌ SL: {sl}")

            time.sleep(5)

    send_telegram_message("🛑 Trading loop ended.")

# ==============================
# Flask App for Telegram Commands
# ==============================
app = Flask(__name__)

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    global bot_running, trade_taken, direction
    data = request.get_json()
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if str(chat_id) != str(CHAT_ID):  # Security check
            return "unauthorized"

        if text == "/start":
            if not bot_running:
                bot_running = True
                trade_taken = False
                direction = None
                send_telegram_message("🚀 Bot started! Waiting for breakout...")
                t = threading.Thread(target=trading_loop)
                t.start()
            else:
                send_telegram_message("⚠ Bot already running!")

        elif text == "/stop":
            if bot_running:
                bot_running = False
                send_telegram_message("🛑 Bot stopped by user.")
            else:
                send_telegram_message("⚠ Bot is not running.")

        elif text == "/status":
            status = "✅ Running" if bot_running else "❌ Stopped"
            send_telegram_message(f"📊 Bot status: {status}\nTrade Taken: {trade_taken}, Direction: {direction}")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Telegram Trading Bot is running!"

# ==============================
# Entry Point
# ==============================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
