from flask import Flask, jsonify
import yfinance as yf
import pandas as pd
import requests
import time
import threading
from datetime import datetime
import os
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

NIFTY25 = ["RELIANCE.NS","HDFCBANK.NS","ICICIBANK.NS","INFY.NS","TCS.NS","BHARTIARTL.NS","ITC.NS","SBIN.NS","LT.NS","AXISBANK.NS","KOTAKBANK.NS","BAJFINANCE.NS","HINDUNILVR.NS","ASIANPAINT.NS","MARUTI.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","WIPRO.NS","NTPC.NS","HCLTECH.NS","POWERGRID.NS","ONGC.NS","TATAMOTORS.NS","ADANIENT.NS"]
TIMEFRAMES = {"1M":"1m","3M":"3m","5M":"5m","15M":"15m","30M":"30m","1H":"60m","2H":"120m","4H":"240m","D":"1d","W":"1wk","M":"1mo"}
TF_ORDER = ["1M","3M","5M","15M","30M","1H","2H","4H","D","W","M"]
CACHE = {"data": {}, "time": 0}

def supertrend_dir(df, p, m):
    try:
        hl2 = (df['High']+df['Low'])/2
        tr = pd.concat([(df['High']-df['Low']),(df['High']-df['Close'].shift()).abs(),(df['Low']-df['Close'].shift()).abs()],axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/p, adjust=False).mean()
        upper = hl2 + m*atr; lower = hl2 - m*atr
        fu=upper.copy(); fl=lower.copy(); direction=pd.Series(1,index=df.index)
        for i in range(1,len(df)):
            if df['Close'].iloc[i] <= fu.iloc[i-1]: fu.iloc[i]=min(upper.iloc[i],fu.iloc[i-1])
            if df['Close'].iloc[i] >= fl.iloc[i-1]: fl.iloc[i]=max(lower.iloc[i],fl.iloc[i-1])
            if df['Close'].iloc[i] > fu.iloc[i-1]: direction.iloc[i]=-1
            elif df['Close'].iloc[i] < fl.iloc[i-1]: direction.iloc[i]=1
            else: direction.iloc[i]=direction.iloc[i-1]
        return direction.iloc[-1]
    except: return 0

def get_sig(sym, interval):
    try:
        pmap={"1m":"2d","3m":"5d","5m":"5d","15m":"10d","30m":"20d","60m":"50d","120m":"100d","240m":"200d","1d":"2y","1wk":"5y","1mo":"10y"}
        df=yf.download(sym,period=pmap.get(interval,"1y"),interval=interval,progress=False,auto_adjust=True,threads=False)
        if df.empty or len(df)<20: return "N"
        if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
        df.columns=[c.capitalize() for c in df.columns]
        d1=supertrend_dir(df,10,3.0); d2=supertrend_dir(df,1,1.6)
        if d1==-1 and d2==-1: return "B"
        elif d1==1 and d2==1: return "S"
        else: return "N"
    except: return "N"

def scan(sym):
    res={}
    for tf in TF_ORDER: res[tf]=get_sig(sym,TIMEFRAMES[tf])
    return res

def scan_all_fast():
    def one(sym):
        try: return sym, scan(sym)
        except: return sym, {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(one, NIFTY25))
    data = {}
    for sym, res in results:
        clean=sym.replace(".NS","")
        b=sum(1 for v in res.values() if v=="B")
        s=sum(1 for v in res.values() if v=="S")
        data[clean]={"data":res,"b":b,"s":s,"time":datetime.now().strftime("%H:%M:%S")}
    CACHE["data"]=data
    CACHE["time"]=time.time()
    return data

# AUTO REFRESH CACHE EVERY 2 MIN
def cache_loop():
    while True:
        try: scan_all_fast()
        except: pass
        time.sleep(120)
threading.Thread(target=cache_loop, daemon=True).start()
scan_all_fast()

def create_box(results, symbol):
    tfs=TF_ORDER; cell_w,cell_h=58,48; gap=2; W=len(tfs)*cell_w+(len(tfs)-1)*gap+20; H=2*cell_h+gap+35
    img=Image.new("RGB",(W,H),"white"); draw=ImageDraw.Draw(img)
    try: f1=ImageFont.truetype("DejaVuSans-Bold.ttf",14); f2=ImageFont.truetype("DejaVuSans-Bold.ttf",18); f3=ImageFont.truetype("DejaVuSans-Bold.ttf",11)
    except: f1=f2=f3=ImageFont.load_default()
    draw.text((10,2),f"{symbol} - LIVE",fill="black",font=f3)
    x0,y0=10,18
    for i,tf in enumerate(tfs):
        x=x0+i*(cell_w+gap)
        draw.rectangle([x,y0,x+cell_w,y0+cell_h],fill=(20,40,80))
        draw.text((x+8,y0+10),tf,fill="white",font=f1)
        val=results.get(tf,"N"); col=(34,139,34) if val=="B" else (200,30,30) if val=="S" else (255,140,0)
        y1=y0+cell_h+gap; draw.rectangle([x,y1,x+cell_w,y1+cell_h],fill=col)
        draw.text((x+18,y1+12),val,fill="white",font=f2)
    path=f"/tmp/{symbol}.png"; img.save(path); return path

def send_photo(path,caption):
    try:
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(path,'rb') as f: requests.post(url,data={"chat_id":CHAT_ID,"caption":caption},files={"photo":f},timeout=20)
    except: pass

def auto_loop():
    while True:
        try:
            data=CACHE["data"]
            for sym, info in data.items():
                b=info["b"]; s=info["s"]
                if b>=7 or s>=7:
                    path=create_box(info["data"],sym)
                    cap=f"TOP25 LIVE {sym} - {b}B/{s}S Time:{info['time']}"
                    send_photo(path,cap)
                    time.sleep(2)
            time.sleep(90)
        except: time.sleep(60)
threading.Thread(target=auto_loop, daemon=True).start()

@app.route("/")
def home(): return "TOP 25 LIVE OK"

@app.route("/api/all")
def api_all():
    if not CACHE["data"] or time.time()-CACHE["time"]>180:
        threading.Thread(target=scan_all_fast).start()
    return jsonify(CACHE["data"])

@app.route("/api/scan/<symbol>")
def api_scan(symbol):
    symbol=symbol.upper()
    if ".NS" not in symbol: symbol+=".NS"
    res=scan(symbol); b=sum(1 for v in res.values() if v=="B"); s=sum(1 for v in res.values() if v=="S")
    return jsonify({"symbol":symbol.replace(".NS",""),"data":res,"b":b,"s":s,"time":datetime.now().strftime("%H:%M:%S")})

@app.route("/nifty25")
@app.route("/nifty50")
def nifty_dashboard():
    html="""<html><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>TOP 25 LIVE</title><style>body{background:#000;color:#fff;font-family:Arial;padding:5px;margin:0} .b{background:#2e7d32} .s{background:#c62828} .n{background:#ef6c00} .stock{background:#111;margin:6px;padding:8px;border-radius:10px;border:1px solid #333} .val{display:inline-block;width:28px;text-align:center;padding:4px;margin:1px;color:#fff;font-size:12px;border-radius:4px;font-weight:bold} .tf{display:inline-block;width:28px;text-align:center;background:#1e325a;margin:1px;font-size:9px;padding:2px;border-radius:3px} #head{position:sticky;top:0;background:#000;padding:10px;text-align:center;z-index:10} .live{color:#0f0;animation:blink 1s infinite} @keyframes blink{50%{opacity:0.3}}</style></head><body><div id='head'><h3 style='margin:0'><span class=live>🔴 LIVE 30 SEC</span> - TOP 25</h3><div style='color:yellow;font-size:12px' id='st'>Loading 25 Stocks...</div></div><div id='c'></div><script>
    const TF=["1M","3M","5M","15","30","1H","2H","4H","D","W","M"];
    async function load(){
      try{
        let r=await fetch('/api/all'); let all=await r.json();
        let c=document.getElementById('c'); c.innerHTML="";
        Object.keys(all).forEach(sym=>{
          let j=all[sym];
          let h=`<div class=stock style='border-left:5px solid ${j.b>=7?'#2e7d32':j.s>=7?'#c62828':'#333'}'><b>${sym} <span style='float:right'>${j.b}B/${j.s}S ${j.time}</span></b><br><div style='margin-top:5px'>`;
          TF.forEach(t=>h+=`<span class=tf>${t}</span>`); h+="<br>";
          TF.forEach(t=>{let v=(j.data && j.data[t])||"N"; let cl=v=="B"?"b":v=="S"?"s":"n"; h+=`<span class='val ${cl}'>${v}</span>`});
          h+="</div></div>"; c.innerHTML+=h;
        });
        document.getElementById('st').innerText="Updated "+new Date().toLocaleTimeString()+" - Next 30 sec (25 STOCKS LIVE)";
      }catch(e){ document.getElementById('st').innerText="Loading... 1 min wait"; }
    }
    load(); setInterval(load,30000);
    </script></body></html>"""
    return html

if __name__=="__main__": app.run(host="0.0.0.0",port=10000)
