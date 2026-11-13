from flask import Flask, jsonify
import yfinance as yf
import pandas as pd
import requests
import time
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

NIFTY50 = ["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","BHARTIARTL.NS","ITC.NS","SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","BAJFINANCE.NS","HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","NTPC.NS","HCLTECH.NS","POWERGRID.NS","ONGC.NS","TATAMOTORS.NS","ADANIENT.NS","ADANIPORTS.NS","BAJAJFINSV.NS","COALINDIA.NS","GRASIM.NS","JSWSTEEL.NS","TATASTEEL.NS","TECHM.NS","M&M.NS","BAJAJ-AUTO.NS","INDUSINDBK.NS","CIPLA.NS","DRREDDY.NS","EICHERMOT.NS","APOLLOHOSP.NS","BRITANNIA.NS","BEL.NS","DIVISLAB.NS","HEROMOTOCO.NS","HINDALCO.NS","LTIM.NS","SBILIFE.NS","SHRIRAMFIN.NS","TRENT.NS","HDFCLIFE.NS"]

TIMEFRAMES = {"1M":"1m","3M":"3m","5M":"5m","15M":"15m","30M":"30m","1H":"60m","2H":"120m","4H":"240m","D":"1d","W":"1wk","M":"1mo"}
TF_ORDER = ["1M","3M","5M","15M","30M","1H","2H","4H","D","W","M"]

# Cache taaki Yahoo block na kare
CACHE = {}
CACHE_TIME = {}

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
        df = yf.download(symbol, period=pmap.get(yf_interval,"1y"), interval=yf_interval, progress=False, auto_adjust=True, threads=False)
        if df.empty or len(df)<20:
            return "N"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.capitalize() for c in df.columns]
        d1 = supertrend_dir(df, 10, 3.0)
        d2 = supertrend_dir(df, 1, 1.6)
        if d1==-1 and d2==-1: return "B"
        elif d1==1 and d2==1: return "S"
        else: return "N"
    except:
        return "N"

def scan_symbol(symbol):
    # 30 sec cache check
    now = time.time()
    if symbol in CACHE and now - CACHE_TIME.get(symbol,0) < 30:
        return CACHE[symbol]
    
    res = {}
    for label in TF_ORDER:
        res[label] = get_dual_signal(symbol, TIMEFRAMES[label])
    
    CACHE[symbol] = res
    CACHE_TIME[symbol] = now
    return res

def create_box_image(results, symbol):
    tfs = TF_ORDER
    cell_w, cell_h = 58, 48
    gap = 2
    W = len(tfs)*cell_w + (len(tfs)-1)*gap + 20
    H = 2*cell_h + gap + 35
    img = Image.new("RGB", (W,H), "white")
    draw = ImageDraw.Draw(img)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 14)
        f2 = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        f3 = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
    except:
        f1 = f2 = f3 = ImageFont.load_default()
    draw.text((10,2), f"{symbol} - DUAL ST LIVE", fill="black", font=f3)
    x0,y0=10,18
    for i,tf in enumerate(tfs):
        x = x0 + i*(cell_w+gap)
        draw.rectangle([x,y0,x+cell_w,y0+cell_h], fill=(20,40,80))
        bbox = draw.textbbox((0,0), tf, font=f1)
        tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
        draw.text((x+(cell_w-tw)//2, y0+(cell_h-th)//2 -2), tf, fill="white", font=f1)
        val = results[tf]
        col = (34,139,34) if val=="B" else (200,30,30) if val=="S" else (255,140,0)
        y1 = y0+cell_h+gap
        draw.rectangle([x,y1,x+cell_w,y1+cell_h], fill=col)
        bbox2 = draw.textbbox((0,0), val, font=f2)
        tw2 = bbox2[2]-bbox2[0]; th2 = bbox2[3]-bbox2[1]
        draw.text((x+(cell_w-tw2)//2, y1+(cell_h-th2)//2 -2), val, fill="white", font=f2)
    path = f"/tmp/{symbol.replace('.','_')}.png"
    img.save(path)
    return path

def send_photo(path, caption):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(path,'rb') as f:
            r = requests.post(url, data={"chat_id":CHAT_ID, "caption":caption}, files={"photo":f}, timeout=20)
            return r.text
    except Exception as e:
        return str(e)

@app.route("/")
def home():
    return "✅ LIVE 30-SEC PAL-PAL | /nifty50 = LIVE Dashboard | /box/RELIANCE = Photo Box"

@app.route("/box/<symbol>")
def box_test(symbol):
    symbol = symbol.upper()
    if ".NS" not in symbol:
        symbol += ".NS"
    res = scan_symbol(symbol)
    clean = symbol.replace(".NS","")
    path = create_box_image(res, clean)
    b = sum(1 for v in res.values() if v=="B")
    s = sum(1 for v in res.values() if v=="S")
    caption = f"{clean} - {b}B / {s}S - DUAL ST(10,3)+(1,1.6) | LIVE {datetime.now().strftime('%H:%M:%S')}"
    send_photo(path, caption)
    return f"LIVE Photo Sent: {clean} - {b}B/{s}S at {datetime.now().strftime('%H:%M:%S')}"

@app.route("/api/scan/<symbol>")
def api_scan(symbol):
    symbol = symbol.upper()
    if ".NS" not in symbol:
        symbol += ".NS"
    res = scan_symbol(symbol)
    b = sum(1 for v in res.values() if v=="B")
    s = sum(1 for v in res.values() if v=="S")
    return jsonify({"symbol":symbol.replace(".NS",""), "data":res, "b":b, "s":s, "time":datetime.now().strftime("%H:%M:%S")})

@app.route("/nifty50")
def nifty_dashboard():
    html = """
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
    body{background:#0f0f0f;color:white;font-family:Arial;padding:8px;margin:0}
    h3{color:#00ff88;text-align:center;margin:5px}
    #status{text-align:center;color:yellow;font-size:13px;margin:5px;padding:5px;background:#222;border-radius:5px}
    .stock{margin-bottom:8px;border:1px solid #333;padding:6px;border-radius:8px;background:#1c1c1c}
    .name{font-weight:bold;font-size:14px;margin-bottom:4px;display:flex;justify-content:space-between}
    .row{display:flex;gap:2px;flex-wrap:wrap}
    .tf{background:#1e325a;color:white;width:31px;text-align:center;padding:2px 0;font-size:10px;font-weight:bold}
    .val{width:31px;text-align:center;padding:4px 0;font-size:12px;font-weight:bold;color:white}
    .B{background:#2e7d32} .S{background:#c62828} .N{background:#ef6c00}
    .fire{color:#ff4444;animation:blink 1s infinite}
    @keyframes blink{50%{opacity:0}}
    </style></head><body>
    <h3>🔴 LIVE NIFTY 50 - 30 SEC PAL-PAL</h3>
    <div id="status">⏳ LIVE Loading... Har 30 sec me Auto-Update Hoga...</div>
    <div id="container"></div>
    <script>
    const NIFTY = ["RELIANCE","HDFCBANK","ICICIBANK","INFY","TCS","BHARTIARTL","ITC","SBIN","LT","AXISBANK","KOTAKBANK","BAJFINANCE","HINDUNILVR","ASIANPAINT","MARUTI","SUNPHARMA","TITAN","ULTRACEMCO","WIPRO","NTPC","HCLTECH","POWERGRID","ONGC","TATAMOTORS","ADANIENT","ADANIPORTS","BAJAJFINSV","COALINDIA","GRASIM","JSWSTEEL","TATASTEEL","TECHM","M&M","BAJAJ-AUTO","INDUSINDBK","CIPLA","DRREDDY","EICHERMOT","APOLLOHOSP","BRITANNIA","BEL","DIVISLAB","HEROMOTOCO","HINDALCO","LTIM","SBILIFE","SHRIRAMFIN","TRENT","HDFCLIFE"];
    const TF = ["1M","3M","5M","15M","30M","1H","2H","4H","D","W","M"];
    async function scanOne(sym){
        try{
            let r = await fetch('/api/scan/'+sym);
            let j = await r.json();
            return j;
        }catch(e){ return {symbol:sym, data:{}, b:0,s:0, time:""}; }
    }
    async function render(){
        let cont = document.getElementById('container');
        cont.innerHTML = "";
        for(let i=0;i<NIFTY.length;i+=5){
            let batch = NIFTY.slice(i,i+5);
            let results = await Promise.all(batch.map(s=>scanOne(s)));
            results.forEach(j=>{
                let clean = j.symbol;
                let res = j.data;
                let b = j.b; let s = j.s;
                let strong = (b>=9||s>=9) ? " <span class='fire'>🔥 LIVE STRONG</span>" : "";
                let html = `<div class="stock"><div class="name"><span>${clean} - ${b}B/${s}S ${j.time}</span><span>${strong}</span></div><div class="row">`;
                TF.forEach(tf=>{ html+= `<div class="tf">${tf}</div>`; });
                html+=`</div><div class="row">`;
                TF.forEach(tf=>{ let v=res[tf]||"N"; html+= `<div class="val ${v}">${v}</div>`; });
                html+=`</div></div>`;
                cont.innerHTML += html;
            });
            document.getElementById('status').innerText = `🔴 LIVE - ${new Date().toLocaleTimeString()} - Scanned ${Math.min(i+5,NIFTY.length)}/50 - Agla update 30 sec me...`;
        }
        document.getElementById('status').innerText = `✅ LIVE Updated: ${new Date().toLocaleTimeString()} - Agla PAL-PAL Update 30 sec me...`;
    }
    render();
    setInterval(render, 30000);
    </script></body></html>
    """
    return html

if __name__=="__main__":
    app.run(host="0.0.0.0", port=10000)
