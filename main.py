from flask import Flask
import yfinance as yf
import pandas as pd
import requests
import threading
import time
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# NIFTY 50 LIST
NIFTY50 = ["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","BHARTIARTL.NS","ITC.NS","SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","BAJFINANCE.NS","HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","NTPC.NS","HCLTECH.NS","POWERGRID.NS","ONGC.NS","TATAMOTORS.NS","ADANIENT.NS","ADANIPORTS.NS","BAJAJFINSV.NS","COALINDIA.NS","GRASIM.NS","JSWSTEEL.NS","TATASTEEL.NS","TECHM.NS","M&M.NS","BAJAJ-AUTO.NS","INDUSINDBK.NS","CIPLA.NS","DRREDDY.NS","EICHERMOT.NS","APOLLOHOSP.NS","BRITANNIA.NS","BEL.NS","DIVISLAB.NS","HEROMOTOCO.NS","HINDALCO.NS","LTIM.NS","SBILIFE.NS","SHRIRAMFIN.NS","TRENT.NS","HDFCLIFE.NS"]

TIMEFRAMES = {"1M":"1m","3M":"3m","5M":"5m","15M":"15m","30M":"30m","1H":"60m","2H":"120m","4H":"240m","D":"1d","W":"1wk","M":"1mo"}
TF_ORDER = ["1M","3M","5M","15M","30M","1H","2H","4H","D","W","M"]

def supertrend_dir(df, period, mult):
    try:
        hl2 = (df['High'] + df['Low']) / 2
        tr1 = df['High'] - df['Low']
        tr2 = (df['High'] - df['Close'].shift()).abs()
        tr3 = (df['Low'] - df['Close'].shift()).abs()
        tr = pd.concat([tr1,tr2,tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        upper = hl2 + mult*atr
        lower = hl2 - mult*atr
        fu = upper.copy()
        fl = lower.copy()
        direction = pd.Series(1, index=df.index)
        for i in range(1,len(df)):
            if df['Close'].iloc[i] <= fu.iloc[i-1]:
                fu.iloc[i] = min(upper.iloc[i], fu.iloc[i-1])
            if df['Close'].iloc[i] >= fl.iloc[i-1]:
                fl.iloc[i] = max(lower.iloc[i], fl.iloc[i-1])
            if df['Close'].iloc[i] > fu.iloc[i-1]:
                direction.iloc[i] = -1
            elif df['Close'].iloc[i] < fl.iloc[i-1]:
                direction.iloc[i] = 1
            else:
                direction.iloc[i] = direction.iloc[i-1]
        return direction.iloc[-1]
    except:
        return 0

def get_dual_signal(symbol, yf_interval):
    try:
        pmap = {"1m":"2d","3m":"5d","5m":"5d","15m":"10d","30m":"20d","60m":"50d","120m":"100d","240m":"200d","1d":"2y","1wk":"5y","1mo":"10y"}
        df = yf.download(symbol, period=pmap.get(yf_interval,"1y"), interval=yf_interval, progress=False, auto_adjust=True)
        if df.empty or len(df)<20:
            return "N"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        d1 = supertrend_dir(df, 10, 3.0)
        d2 = supertrend_dir(df, 1, 1.6)
        if d1==-1 and d2==-1:
            return "B"
        elif d1==1 and d2==1:
            return "S"
        else:
            return "N"
    except:
        return "N"

def scan_symbol(symbol):
    res = {}
    for label in TF_ORDER:
        res[label] = get_dual_signal(symbol, TIMEFRAMES[label])
    return res

def create_box_image(results, symbol):
    tfs = TF_ORDER
    cell_w, cell_h = 70, 46
    gap = 3
    W = len(tfs)*cell_w + (len(tfs)-1)*gap + 20
    H = 2*cell_h + gap + 20
    img = Image.new("RGB", (W,H), "white")
    draw = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        f2 = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except:
        f1 = f2 = ImageFont.load_default()
    x0,y0=10,10
    for i,tf in enumerate(tfs):
        x = x0 + i*(cell_w+gap)
        draw.rectangle([x,y0,x+cell_w,y0+cell_h], fill=(20,40,80))
        bbox = draw.textbbox((0,0), tf, font=f1)
        tw = bbox[2]-bbox[0]
        draw.text((x+(cell_w-tw)//2, y0+10), tf, fill="white", font=f1)
        val = results[tf]
        col = (34,139,34) if val=="B" else (200,30,30) if val=="S" else (255,140,0)
        y1 = y0+cell_h+gap
        draw.rectangle([x,y1,x+cell_w,y1+cell_h], fill=col)
        bbox2 = draw.textbbox((0,0), val, font=f2)
        tw2 = bbox2[2]-bbox2[0]
        draw.text((x+(cell_w-tw2)//2, y1+9), val, fill="white", font=f2)
    path = f"/tmp/{symbol.replace('.','_')}.png"
    img.save(path)
    return path

def send_photo(path, caption):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(path,'rb') as f:
            requests.post(url, data={"chat_id":CHAT_ID, "caption":caption}, files={"photo":f}, timeout=15)
    except Exception as e:
        print(e)

@app.route("/")
def home():
    return "✅ LIVE: /nifty50 for ALL 50 BOXES | /box/RELIANCE for Photo BOX"

@app.route("/box/<symbol>")
def box_test(symbol):
    symbol = symbol.upper()
    if ".NS" not in symbol and "BTC" not in symbol and "USD" not in symbol:
        symbol += ".NS"
    res = scan_symbol(symbol)
    clean = symbol.replace(".NS","")
    path = create_box_image(res, clean)
    b = sum(1 for v in res.values() if v=="B")
    s = sum(1 for v in res.values() if v=="S")
    caption = f"{clean} - {b}B / {s}S - {datetime.now().strftime('%d %b %I:%M %p')}"
    send_photo(path, caption)
    return f"Photo Sent {clean} - {res}"

@app.route("/nifty50")
def nifty_dashboard():
    html = """
    <html><head><meta http-equiv="refresh" content="120">
    <style>
    body{background:#0f0f0f;color:white;font-family:Arial;padding:10px}
    .stock{margin-bottom:12px;border:1px solid #333;padding:8px;border-radius:8px;background:#1c1c1c}
    .name{font-weight:bold;font-size:17px;margin-bottom:6px}
    .row{display:flex;gap:2px;flex-wrap:wrap}
    .tf{background:#1e325a;color:white;width:42px;text-align:center;padding:4px 0;font-size:12px;font-weight:bold}
    .val{width:42px;text-align:center;padding:6px 0;font-size:14px;font-weight:bold;color:white}
    .B{background:#2e7d32} .S{background:#c62828} .N{background:#ef6c00}
    </style></head><body>
    <h2>📊 NIFTY 50 - 11 TF BOX (All 50 Stocks Ek Sath) - Auto Refresh 2 min</h2>
    """
    for sym in NIFTY50:
        res = scan_symbol(sym)
        clean = sym.replace(".NS","")
        b = sum(1 for v in res.values() if v=="B")
        s = sum(1 for v in res.values() if v=="S")
        strong = "🔥 STRONG" if b>=9 or s>=9 else ""
        html += f'<div class="stock"><div class="name">{clean} - {b}B / {s}S {strong}</div>'
        html += '<div class="row">'
        for tf in TF_ORDER:
            html += f'<div class="tf">{tf}</div>'
        html += '</div><div class="row">'
        for tf in TF_ORDER:
            html += f'<div class="val {res[tf]}">{res[tf]}</div>'
        html += '</div></div>'
    html += "</body></html>"
    return html

def scanner_loop():
    while True:
        try:
            now = datetime.now()
            if now.weekday()<5 and 9 <= now.hour <= 15:
                for sym in NIFTY50[:15]: # Telegram spam se bachne ke liye 15 hi strong wale
                    res = scan_symbol(sym)
                    b = sum(1 for v in res.values() if v=="B")
                    s = sum(1 for v in res.values() if v=="S")
                    if b>=10 or s>=10:
                        clean = sym.replace(".NS","")
                        path = create_box_image(res, clean)
                        caption = f"{clean} - STRONG {b}B {s}S - 11 TF BOX"
                        send_photo(path, caption)
                    time.sleep(2)
            time.sleep(300)
        except Exception as e:
            print(e)
            time.sleep(60)

threading.Thread(target=scanner_loop, daemon=True).start()

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
