import os, time, requests, threading, pandas as pd
import yfinance as yf
from flask import Flask
from datetime import datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

app = Flask(__name__)
@app.route('/')
def home():
    return "Nifty DOUBLE Supertrend Scanner LIVE - ST(10,3) + ST(1,1.6)"

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(e)

def supertrend_direction(df, atr_period, atr_mult):
    try:
        hl2 = (df['High'] + df['Low']) / 2
        atr = (df['High'] - df['Low']).rolling(atr_period).mean()
        upper = hl2 + (atr_mult * atr)
        lower = hl2 - (atr_mult * atr)
        close = df['Close']
        # Last candle close > lower band = GREEN (-1), else RED (1)
        if close.iloc[-1] > lower.iloc[-1]:
            return -1  # GREEN / BUY
        else:
            return 1   # RED / SELL
    except:
        return 0

TF_MAP = {
    "1": ("1m", "1d"), "3": ("1m", "1d"), "5": ("5m", "5d"),
    "15": ("15m", "5d"), "30": ("30m", "5d"), "45": ("30m", "5d"),
    "60": ("60m", "10d"), "120": ("60m", "10d"), "240": ("60m", "10d"),
    "D": ("1d", "3mo"), "W": ("1wk", "1y")
}

NIFTY_50 = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","LT.NS","AXISBANK.NS","BAJFINANCE.NS","MARUTI.NS","TATAMOTORS.NS","SUNPHARMA.NS","WIPRO.NS","ASIANPAINT.NS","HCLTECH.NS","KOTAKBANK.NS","M&M.NS","BAJAJFINSV.NS","TITAN.NS","ULTRACEMCO.NS","NTPC.NS","POWERGRID.NS","ONGC.NS"]

def check_stock_dual_st(symbol):
    buy_tf_count = 0
    sell_tf_count = 0
    details = {}
    try:
        for tf, (interval, period) in TF_MAP.items():
            df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
            if len(df) < 12:
                continue
            
            st1 = supertrend_direction(df, 10, 3)      # Aapka pehla ST
            st2 = supertrend_direction(df, 1, 1.6)     # Aapka dusra ST
            
            # Dono Green to hi BUY, Dono Red to hi SELL
            if st1 == -1 and st2 == -1:
                details[tf] = "B"
                buy_tf_count += 1
            elif st1 == 1 and st2 == 1:
                details[tf] = "S"
                sell_tf_count += 1
            else:
                details[tf] = "N" # Neutral - dono match nahi

        return buy_tf_count, sell_tf_count, details
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return 0,0,{}

def scanner_loop():
    send_telegram("✅ *DOUBLE Supertrend Scanner LIVE!*\nST1(10,3) + ST2(1,1.6)\nRule: Dono Green=BUY, Dono Red=SELL\nScanning 11 TFs...")
    sent = {}
    while True:
        try:
            for sym in NIFTY_50:
                buy_c, sell_c, det = check_stock_dual_st(sym)
                clean = sym.replace(".NS","")
                price = "0"
                try: price = f"{yf.Ticker(sym).fast_info.last_price:.2f}"
                except: pass

                # Agar 9+ TF me Dono Green hai to Strong BUY
                if buy_c >= 9 and sent.get(clean) != "BUY":
                    send_telegram(f"🟢 *DOUBLE ST BUY*\n*{clean}* ₹{price}\nDono ST GREEN in {buy_c}/11 TFs\n{det}")
                    sent[clean] = "BUY"
                elif sell_c >= 9 and sent.get(clean) != "SELL":
                    send_telegram(f"🔴 *DOUBLE ST SELL*\n*{clean}* ₹{price}\nDono ST RED in {sell_c}/11 TFs\n{det}")
                    sent[clean] = "SELL"
                time.sleep(4)
            print(f"Full scan done {datetime.now()}")
            time.sleep(120)
        except Exception as e:
            print(e)
            time.sleep(30)

if __name__ == "__main__":
    t = threading.Thread(target=scanner_loop, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
