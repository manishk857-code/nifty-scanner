from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Nifty Scanner Running! Test: /test-buy"

@app.route("/test-buy")
def test_buy():
    import os, requests
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    CHAT_ID = os.environ.get("CHAT_ID")
    msg = "🟢 DOUBLE BUY - TEST RELIANCE 15min - Scanner Working!"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    return "✅ Telegram par message bhej diya! Check karo."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
