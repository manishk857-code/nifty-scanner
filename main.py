import yfinance as yf
import pandas as pd
import requests
import os
import time
from datetime import datetime

# --- Telegram Config - Render me Env Variable se ayega ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")

NIFTY_50 = ["RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS","SBIN.NS","BHARTIARTL.NS","ITC.NS","LT.NS","KOTAKBANK.NS","BAJFINANCE.NS","AXISBANK.NS","ASIANPAINT.NS","MARUTI.NS","WIPRO.NS","HCLTECH.NS","SUNPHARMA.NS","TITAN.NS","ULTRACEMCO.NS","POWERGRID.NS","NTPC.NS","BAJAJFINSV.NS","ONGC.NS","M&M.NS","HINDUNILVR.NS","ADANIENT.NS","COALINDIA.NS","ADANIPORTS.NS","TECHM.NS","GRASIM.NS","JSWSTEEL.NS","HINDALCO.NS","BRITANNIA.NS","CIPLA.NS","DRREDDY.NS","EICHERMOT.NS","APOLLOHOSP.NS","TATASTEEL.NS","BPCL.NS","DIVISLAB.NS","BAJAJ-AUTO.NS","INDUSINDBK.NS","HEROMOTOCO.NS","TATAMOTORS.NS","UPL.NS","SBILIFE.NS","LTIM.NS","HDFCLIFE.NS","NESTLEIND.NS"]

def supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    atr = df['High'].sub(df['Low']).rolling(period).mean() # Simplified ATR for speed
    # Real Supertrend logic
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    df['ST_dir'] = True
    for i in range(1, len(df)):
        if df['Close'].iloc[i] > upper_band.iloc[i-1]:
            df.loc[df.index[i], 'ST_dir'] = True # BUY
        elif df['Close'].iloc[i] < lower_band.iloc[i-1]:
            df.loc[df.index[i], 'ST_dir'] = False # SELL
        else:
            df.loc[df.index[i], 'ST_dir'] = df['ST_dir'].iloc[i-1]
    return df['ST_dir'].iloc[-1]

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(e)

def scan():
    buy_list = ""
    sell_list = ""
    now = datetime.now().strftime("%d-%m %H:%M")
    
    for stock in NIFTY_50:
        try:
            df = yf.download(stock, period="10d", interval="15m", progress=False)
            if len(df) < 50: continue
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            
            st_10_3 = supertrend(df.copy(), 10, 3.0)
            st_1_16 = supertrend(df.copy(), 1, 1.6)

            price = round(df['Close'].iloc[-1],2)
            name = stock.replace(".NS","")
            
            if st_10_3 == True and st_1_16 == True: # Both BUY
                buy_list += f"{name} @ ₹{price}\n"
            elif st_10_3 == False and st_1_16 == False: # Both SELL
                sell_list += f"{name} @ ₹{price}\n"
                
        except: continue

    if buy_list:
        msg = f"🚀 *NIFTY 50 BUY ALERT (10,3 + 1,1.6)*\n\nTime: {now}\nTF: 15min\n\n{buy_list}"
        send_telegram(msg)
    if sell_list:
        msg = f"🔻 *NIFTY 50 SELL ALERT (10,3 + 1,1.6)*\n\nTime: {now}\nTF: 15min\n\n{sell_list}"
        send_telegram(msg)
    
    if not buy_list and not sell_list:
        print(f"{now} - No Signal")

# Loop for Render
if __name__ == "__main__":
    while True:
        scan()
        time.sleep(900) # 15 min
