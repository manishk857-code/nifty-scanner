from flask import Flask
import os, requests, yfinance as yf, pandas as pd, time, threading
from datetime import datetime
import pytz

app = Flask(__name__)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Aapke Master Indicator wale 11 TimeFrames
TF_LIST = [
    ("1m","1m","2d"), ("3m","5m","5d"), ("5m","5m","5d"),
    ("15m","15m","10d"), ("30m","30m","15d"), ("1H","60m","30d"),
    ("2H","60m","60d"), ("4H","60m","60d"), ("1D","1d","1y"),
    ("1W","1wk","2y"), ("1M","1mo","5y")
]

NIFTY50 = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","ASIANPAINT.NS","LT.NS","ITC.NS","BAJFINANCE.NS","MARUTI.NS","BHARTIARTL.NS","AXISBANK.NS","KOTAKBANK.NS"]

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode":"HTML"}, timeout=20)
    except Exception as e: print(e)

def get_st_signal(symbol, yf_interval, period):
    try:
        df = yf.download(symbol, period=period, interval=yf_interval, progress=False, auto_adjust=True)
        if len(df) < 15: return "S", "🟥"
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        hl2 = (df['High'] + df['Low'])/2
        atr = df['High'].sub(df['Low']).rolling(10).mean()
        lower = hl2 - 3*atr
        # Agar Close > lower band to BUY (Green)
        if df['Close'].iloc[-1] > lower.iloc[-1]:
            return "B", "🟩"
        else:
            return "S", "🟥"
    except:
        return "?", "⬜"

def make_box_message(symbol):
    letters = []
    emojis = []
    for name, yf_tf, per in TF_LIST:
        l, e = get_st_signal(symbol, yf_tf, per)
        letters.append(l)
        emojis.append(e)
        time.sleep(0.4)
    
    clean = symbol.replace(".NS","")
    # Aapka wala format - Stock Name ke aage 11 box
    msg = f"<b>{clean}</b>  {''.join(emojis)}\n"
    msg += f"<code>{' '.join(letters)}</code>\n"
    msg += f"<code>1m 3m 5m 15 30 1H 2H 4H D  W  M</code>\n"
    msg += f"B=BUY 🟩 | S=SELL 🟥 | ST(10,3)"
    return msg, ''.join(letters)

last_sent = {}

def scanner_loop():
    ist = pytz.timezone('Asia/Kolkata')
    while True:
        try:
            now = datetime.now(ist)
            if now.weekday() < 5 and 9 <= now.hour < 16:
                for sym in NIFTY50:
                    msg, box_str = make_box_message(sym)
                    # Sirf tab bhejo jab 9+ boxes ek hi taraf ho ya TF flip ho
                    if box_str.count("B") >= 9 or box_str.count("S") >= 9:
                        if last_sent.get(sym) != box_str:
                            send_telegram(msg + f"\n\n<b>🔥 STRONG {box_str.count('B')}B / {box_str.count('S')}S</b>")
                            last_sent[sym] = box_str
                    time.sleep(2)
            time.sleep(300) # har 5 min scan
        except Exception as e:
            print(e)
            time.sleep(60)

@app.route("/")
def home(): return "✅ 11 Box Master Scanner LIVE - ST(10,3)"

@app.route("/box/<symbol>")
def box_one(symbol):
    sym = symbol.upper() + ".NS" if ".NS" not in symbol.upper() else symbol.upper()
    msg, box = make_box_message(sym)
    send_telegram(msg)
    return f"Sent {sym} : {box}"

@app.route("/test-buy")
def test():
    msg, box = make_box_message("RELIANCE.NS")
    send_telegram(msg)
    return "11 Box format sent!"

threading.Thread(target=scanner_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
