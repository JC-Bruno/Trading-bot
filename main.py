import requests
import pandas as pd
import asyncio
from telegram import Bot

# Configuración del bot de Telegram
TELEGRAM_BOT_TOKEN = "8100006867:AAGg5h_MAFexUwTcJ2BZRCI02wCjSDM9_5E"
TELEGRAM_CHAT_ID = "1528276156"
ENDPOINT_SIMBOLS = "https://fapi.binance.com/fapi/v1/exchangeInfo"

bot = Bot(token=TELEGRAM_BOT_TOKEN)

response = requests.get(ENDPOINT_SIMBOLS)
data = response.json()
SYMBOLS = [symbol["symbol"] for symbol in data["symbols"] if 
           symbol["contractType"]== "PERPETUAL" and 
           symbol["status"] == "TRADING" and 
           symbol["marginAsset"] =="USDC"]

# Parámetros de EMA
EMA_PERIOD = 200
THRESHOLD_PERCENT = 1  # Umbral de proximidad a la EMA (0.5% del precio)

# Función para obtener datos de velas de Binance
async def get_klines(symbol, interval, limit=200):
    url = f"https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame(data, columns=[
            "timestamp", "open", "high", "low", "close",
            "volume", "close_time", "quote_asset_volume",
            "trades", "taker_buy_base", "taker_buy_quote", "ignore"
        ])
        df["close"] = df["close"].astype(float)
        return df
    else:
        print(f"Error al obtener datos para {symbol} ({interval}): {response.text}")
        return None

# Función para calcular la EMA de 200
def calculate_ema(df):
    df["EMA_200"] = df["close"].ewm(span=EMA_PERIOD, adjust=False).mean()
    return df

# Función para obtener el precio actual de un símbolo
async def get_current_price(symbol):
    url = f"https://fapi.binance.com/fapi/v1/ticker/price"
    params = {"symbol": symbol}
    
    response = requests.get(url, params=params)
    if response.status_code == 200:
        return float(response.json()["price"])
    else:
        print(f"Error al obtener el precio actual de {symbol}")
        return None

# Función para verificar si el precio está cerca de la EMA en todos los períodos
async def check_ema_proximity(symbol):
    timeframes = ["4h", "2h", "1h", "30m"]
    intervals = {"4h": "4h", "2h": "2h", "1h": "1h", "30m": "30m"}
    
    results = {}
    
    for tf in timeframes:
        df = await get_klines(symbol, intervals[tf])
        if df is not None:
            df = calculate_ema(df)
            last_ema = df["EMA_200"].iloc[-1]
            results[tf] = last_ema
    
    # Obtener precio actual
    current_price = await get_current_price(symbol)
    if current_price is None:
        return False

    # Verificar si el precio está cerca de la EMA en todos los períodos
    near_ema = all(
        abs(current_price - results[tf]) / current_price * 100 <= THRESHOLD_PERCENT
        for tf in timeframes
    )
    
    return near_ema

# Función asíncrona para enviar alerta por Telegram
async def send_alert(symbol):
    message = f"Alerta de Trading\nEl precio de {symbol} está cerca de la EMA 200 en 4H, 2H, 1H y 30M."
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

# Bucle principal del bot
async def main():
    while True:
        for symbol in SYMBOLS:
            if await check_ema_proximity(symbol):
                await send_alert(symbol)
                print(f"✅ Alerta enviada para {symbol}")
            else:
                print(f"⏳ {symbol}: No cumple con la condición")
        
        print("🔄 Esperando 1 hora para la próxima verificación...\n")
        await asyncio.sleep(3600)  # Espera 5 minutos antes de la siguiente ejecución

if __name__ == "__main__":
    asyncio.run(main())
