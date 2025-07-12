import asyncio
import logging
import os
import time
import re

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv
import pandas as pd
import pandas_ta as ta
import aiohttp

# Сопоставление полных названий с тикерами
symbol_aliases = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "dogecoin": "DOGE",
    "ripple": "XRP",
    "binancecoin": "BNB",
    "cardano": "ADA",
    "tron": "TRX",
    "polkadot": "DOT",
    "litecoin": "LTC",
    "avalanche": "AVAX",
    "shiba": "SHIB",
    "pepe": "PEPE",
    "toncoin": "TON",
    "injective": "INJ"
}

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "0"))
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Главное меню с кнопками
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Start")],
        [KeyboardButton(text="📉 Сигнал по монете"), KeyboardButton(text="💎 ТОП монеты")],
        [KeyboardButton(text="🔍 Сканировать рынок"), KeyboardButton(text="♻️ Обновить рынок")],
        [KeyboardButton(text="❓ Help")]
    ],
    resize_keyboard=True
)


# Кэш сигналов
signal_cache = {}

#Start будет всегда в меню
@dp.message(F.text.lower() == "🚀 start")
async def start_button(message: Message):
    await start(message)

# Старт
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "👋 Привет! Я Crypto Signal AI Bot.\n\n"
        "Я анализирую крипторынок по RSI, EMA и MACD 📊\n"
        "и отправляю сигналы с уверенностью более 60%.\n\n"
        "Нажми кнопку или просто напиши название монеты (например: BTC, ETH, MATIC...)\n\n"
        "Бот также каждые 5 минут сканирует рынок и отправляет сигналы в группу ✅",
        reply_markup=main_kb
    )

# Запрос тикера
@dp.message(F.text.lower() == "📉 сигнал по монете")
async def ask_symbol(message: Message):
    await message.answer("✏️ Введи тикер монеты (например: BTC, ETH, SOL...)")

# ТОП монеты
@dp.message(F.text.lower() == "💎 топ монеты")
async def show_top_coins(message: Message):
    top_list = "\n".join([f"• {v}" for v in symbol_aliases.values()])
    await message.answer(f"🔥 ТОП монеты:\n{top_list}\n\nВведи тикер одной из них!")

# Форс скан рынка
@dp.message(F.text.lower() == "♻️ обновить рынок")
async def force_scan(message: Message):
    await message.answer("⏳ Форсирую скан рынка...")
    symbols = await get_all_usdt_symbols()
    results = await analyze_many(symbols)
    if results:
        for text in results:
            await message.answer(text)
    else:
        await message.answer("❌ Сильных сигналов не найдено.")

# Скан всего рынка
@dp.message(F.text.lower() == "🔍 сканировать рынок")
async def scan_market(message: Message):
    await message.answer("⏳ Сканирую весь рынок USDT монет...")
    symbols = await get_all_usdt_symbols()
    results = await analyze_many(symbols)
    if results:
        for text in results:
            await message.answer(text)
    else:
        await message.answer("❌ Сильных сигналов не найдено.")

# HELP
@dp.message(F.text.lower() == "❓ help")
async def help_message(message: Message):
    await message.answer(
        "ℹ️ Crypto Signal AI Bot — это Telegram-бот, который помогает находить точки входа и выхода на крипторынке на основе технического анализа.\n\n"
        "Доступные функции:\n"
        "🔸 📉 Сигнал по монете — Введи тикер (например: BTC, ETH, SOL).\n"
        "🔸 💎 ТОП монеты — Быстро посмотреть список популярных монет.\n"
        "🔸 🔍 Сканировать рынок — Полный скан рынка (все пары USDT).\n"
        "🔸 ♻️ Обновить рынок — Форсировать скан прямо сейчас.\n\n"
        "🔁 Авто-скан каждые 5 минут с сигналами в группу.\n"
    )

# Если пользователь вводит тикер вручную
@dp.message(F.text.regexp(r"^[A-Za-z]{2,15}$"))
async def single_signal(message: Message):
    user_input = message.text.lower().replace(" ", "")
    base = symbol_aliases.get(user_input, user_input).upper()
    symbol = base if base.endswith("USDT") else base + "USDT"
    text = await get_signal_text(symbol)
    await message.answer(text or f"❌ Данные не найдены для {symbol}")

# Получение всех пар с USDT
async def get_all_usdt_symbols():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.binance.com/api/v3/ticker/24hr") as resp:
            data = await resp.json()
            return [
                d['symbol'] for d in data
                if d['symbol'].endswith('USDT') and not re.search(r"(BUSD|TUSD|USDC|DAI|EUR|GBP|TRY|FDUSD|USDP)", d['symbol'])
            ]

# Сигнал по монете (с кэшем)
async def get_signal_text(symbol):
    now = time.time()
    if symbol in signal_cache:
        ts, text = signal_cache[symbol]
        if now - ts < 300:  # кэш 5 минут
            return text

    klines = await get_klines(symbol)
    if klines:
        text = analyze_klines(symbol, klines)
        signal_cache[symbol] = (now, text)
        return text
    return None

# Загрузка исторических свечей
async def get_klines(symbol):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1m&limit=50"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return data if isinstance(data, list) else None
    except:
        return None

# Анализ нескольких монет
async def analyze_many(symbols):
    results = []
    sem = asyncio.Semaphore(10)

    async def limited_analyze(sym):
        async with sem:
            text = await get_signal_text(sym)
            if text and "Confidence" in text:
                conf_line = [line for line in text.splitlines() if "Confidence" in line]
                if conf_line and int(conf_line[0].split(": ")[1].replace('%', '')) >= 60:
                    results.append(text)

    tasks = [limited_analyze(s) for s in symbols]
    await asyncio.gather(*tasks)
    return results

# Технический анализ
def analyze_klines(symbol, klines):
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'qav', 'num_trades', 'taker_base_vol',
        'taker_quote_vol', 'ignore'
    ])
    df['close'] = df['close'].astype(float)
    df['RSI'] = ta.rsi(df['close'], length=14)
    df['EMA'] = ta.ema(df['close'], length=21)
    macd = ta.macd(df['close'])
    df['MACD'] = macd.iloc[:, 0]
    df['MACD_signal'] = macd.iloc[:, 1]

    last_rsi = df['RSI'].iloc[-1]
    last_close = df['close'].iloc[-1]
    last_ema = df['EMA'].iloc[-1]
    last_macd = df['MACD'].iloc[-1]
    last_macd_signal = df['MACD_signal'].iloc[-1]

    signal = "HOLD"
    confidence = 50

    if last_rsi < 35 and last_close > last_ema and last_macd > last_macd_signal:
        signal = "BUY"
        confidence = 70
    elif last_rsi > 70 and last_close < last_ema and last_macd < last_macd_signal:
        signal = "SELL"
        confidence = 70

    tp = last_close * 1.01
    sl = last_close * 0.995

    return (
        f"📈 Pair: {symbol}\n"
        f"📊 RSI: {last_rsi:.2f}\n"
        f"🔹 EMA: {last_ema:.2f}\n"
        f"💰 Close: {last_close:.2f}\n"
        f"🔗 MACD: {last_macd:.4f}\n"
        f"🔗 MACD Signal: {last_macd_signal:.4f}\n\n"
        f"✅ Signal: {signal}\n"
        f"🎯 Confidence: {confidence}%\n"
        f"🎯 Take Profit: {tp:.2f}\n"
        f"🚩 Stop Loss: {sl:.2f}"
    )

# Авто-скан каждые 5 минут
async def auto_send_signals():
    while GROUP_CHAT_ID != 0:
        symbols = await get_all_usdt_symbols()
        results = await analyze_many(symbols)
        if results:
            for text in results:
                await bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
        await asyncio.sleep(300)  # каждые 5 минут

# Запуск
async def main():
    asyncio.create_task(auto_send_signals())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
