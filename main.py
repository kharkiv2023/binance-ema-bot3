import os
import requests
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import time

app = FastAPI()
scheduler = AsyncIOScheduler()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'LTCUSDT', 'ADAUSDT', 'LINKUSDT', 'AVAXUSDT']

TIMEFRAMES = {
    "15m": {"interval": "15m", "ema_short": 20, "ema_long": 50},
    "1h":  {"interval": "1h",  "ema_short": 20, "ema_long": 50}
}

previous_states = {}

def get_klines(symbol, interval, limit=60):
    try:
        url = 'https://api.binance.vision/api/v3/klines'
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f'Помилка {symbol} {interval}: {e}')
        return []

def calculate_ema(prices, period):
    ema = []
    k = 2 / (period + 1)
    for i, price in enumerate(prices):
        if i == 0:
            ema.append(price)
        else:
            ema.append(price * k + ema[-1] * (1 - k))
    return ema

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("ПОМИЛКА: TOKEN або CHAT_ID не встановлено!")
        return
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    try:
        response = requests.get(url, params={'chat_id': CHAT_ID, 'text': text}, timeout=10)
        if response.status_code == 200:
            print(f"Telegram OK: {text}")
        else:
            print(f"Telegram ERROR {response.status_code}: {response.text}")
    except Exception as e:
        print(f'Telegram exception: {e}')

def check_cross(symbol, tf):
    data = get_klines(symbol, tf["interval"], limit=tf["ema_long"] + 10)
    if not data or len(data) < tf["ema_long"] + 1:
        return None
    closes = [float(candle[4]) for candle in data]
    ema_short = calculate_ema(closes, tf["ema_short"])
    ema_long = calculate_ema(closes, tf["ema_long"])
    prev_diff = ema_short[-2] - ema_long[-2]
    curr_diff = ema_short[-1] - ema_long[-1]
    if prev_diff < 0 and curr_diff > 0:
        return 'UP'
    elif prev_diff > 0 and curr_diff < 0:
        return 'DOWN'
    return None

def check_all():
    print(f"Перевірка о {time.strftime('%H:%M:%S')}")
    for symbol in SYMBOLS:
        for tf_name, tf in TIMEFRAMES.items():
            key = f"{symbol}_{tf_name}"
            cross = check_cross(symbol, tf)
            if cross and previous_states.get(key) != cross:
                direction = 'Вгору ↑ (Лонг)' if cross == 'UP' else 'Вниз ↓ (Шорт)'
                msg = f"EMA 20/50 {symbol}\n{direction}\nТаймфрейм: {tf_name.upper()}"
                send_telegram(msg)
                previous_states[key] = cross
            elif cross is None:
                previous_states[key] = None

@app.on_event("startup")
async def startup():
    scheduler.add_job(check_all, "interval", minutes=15, next_run_time=datetime.now())
    scheduler.add_job(check_all, "cron", hour="*", minute=0)
    scheduler.start()
    send_telegram('Бот запущено!\nEMA 20/50 на 15m і 1h')

@app.get("/")
@app.head("/")
def home():
    return {"status": "Бот працює!"}

@app.get("/test")
def test():
    send_telegram("ТЕСТ: Бот на Render працює!")
    return {"status": "OK"}

@app.get("/id")
def get_id():
    return {"chat_id": CHAT_ID}
