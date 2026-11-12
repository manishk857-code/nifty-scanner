import os
import time
import requests
import threading
from flask import Flask
from datetime import datetime

# --- Telegram Config (Render se aayega) ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

app = Flask(__name__)

@app.route('/')
def home():
    return "Nifty Scanner is Live! BUY/SELL Alerts Running"

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN or CHAT_ID missing!")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=data, timeout=10)
        print(f"Sent: {message}")
    except Exception as e:
        print(f"Telegram Error: {e}")

def scanner_loop():
    send_telegram("✅ *Nifty Scanner Started* on Render!\nYou will get BUY & SELL alerts now.")
    while True:
        try:
            # Yahan aapka original 11TF scanner logic chalega
            # Abhi ke liye har 5 min me check message
            now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            print(f"Scanning at {now}... Market check...")
            
            # TODO: Aapka Nifty 11TF BUY/SELL logic yahan aayega
            # Example:
            # if buy_condition:
            #   send_telegram(f"🟢 BUY ALERT: NIFTY at {price}")
            # if sell_condition:
            #   send_telegram(f"🔴 SELL ALERT: NIFTY at {price}")

            time.sleep(60) # 1 min me ek baar scan
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(30)

# Flask ko alag thread me chalao taaki Render ka port khula rahe
if __name__ == "__main__":
    t = threading.Thread(target=scanner_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
