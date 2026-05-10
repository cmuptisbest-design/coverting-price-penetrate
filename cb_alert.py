import os
import pandas as pd
import requests
import yfinance as yf
import time
import html  # 新增：用來處理特殊符號

# ================= 設定區 =================
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
CSV_FILE_PATH = 'cb_data.csv'  
# ==========================================

def send_telegram_message(msg):
    """發送 Telegram 訊息"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Telegram 發送失敗: {response.text}")
    except Exception as e:
        print(f"Telegram 發生錯誤: {e}")

def get_stock_price(stock_code):
    """取得台股即時/最新收盤價"""
    try:
        stock = yf.Ticker(f"{stock_code}.TW")
        price = stock.fast_info['lastPrice']
        if pd.isna(price) or price == 0:
            raise ValueError("上市無報價")
        return price
    except:
        try:
            stock = yf.Ticker(f"{stock_code}.TWO")
            price = stock.fast_info['lastPrice']
            return price
        except:
            return None

def main():
    print("讀取 CB 資料中...")
    try:
        df = pd.read_csv(CSV_FILE_PATH)
    except FileNotFoundError:
        print(f"找不到檔案：{CSV_FILE_PATH}")
        return

    required_cols = ['標的債券', '轉換標的代碼', '轉換價格']
    for col in required_cols:
        if col not in df.columns:
            print(f"CSV 格式錯誤，找不到欄位：{col}")
            return

    alert_messages = []
    
    print("開始比對即時股價與轉換價...")
    for index, row in df.iterrows():
        # 【修正2】：使用 html.escape 把可能的特殊符號(如 <, >, &) 轉義，避免 Telegram 誤判
        raw_bond_name = str(row.get('標的債券', '未知標的'))
        bond_name = html.escape(raw_bond_name) 
        
        stock_code = str(row['轉換標的代碼']).strip()
        
        try:
            conv_price = float(row['轉換價格'])
        except (ValueError, TypeError):
            continue

        if not stock_code.isdigit():
            continue

        current_price = get_stock_price(stock_code)
        
        if current_price is None:
            continue

        if current_price > conv_price:
            premium_pct = ((current_price - conv_price) / conv_price) * 100
            
            msg = f"🔔 <b>{bond_name} ({stock_code})</b> 突破轉換價！\n" \
                  f"🎯 轉換價: <code>{conv_price}</code>\n" \
                  f"📈 目前市價: <code>{current_price:.2f}</code>\n" \
                  f"🔥 超出幅度: {premium_pct:.1f}%"
            alert_messages.append(msg)
            print(f"發現突破: {raw_bond_name}")
        
        time.sleep(0.5)

    # 【修正1】：安全的分批發送邏輯，避免 HTML 標籤被切斷
    if alert_messages:
        print(f"共發現 {len(alert_messages)} 檔突破，準備發送通知...")
        
        header = "<b>🚀 可轉債突破轉換價清單 🚀</b>\n\n"
        current_msg = header
        
        for alert in alert_messages:
            # Telegram 限制單篇約 4096 字元，我們抓 3800 為安全界線
            if len(current_msg) + len(alert) > 3800:
                # 達到字數上限，先發送目前累積的訊息
                send_telegram_message(current_msg)
                time.sleep(2) # 暫停 2 秒，避免被 Telegram 視為機器人洗頻而阻擋
                # 開啟新的一篇
                current_msg = alert + "\n\n"
            else:
                # 還沒達到上限，繼續疊加訊息
                current_msg += alert + "\n\n"
                
        # 迴圈結束後，把最後剩下沒發送完的送出
        if current_msg.strip() and current_msg != header:
            send_telegram_message(current_msg)
            
        print("Telegram 通知發送完成！")
    else:
        print("目前無標的突破轉換價。")

if __name__ == "__main__":
    main()
