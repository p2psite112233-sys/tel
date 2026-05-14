import asyncio
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ===== BOT =====
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===== DB =====
conn = sqlite3.connect("bot.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    status TEXT
)
""")
conn.commit()

# ===== FIX RENDER PORT =====
async def handle(request):
    return web.Response(text="Bot is running")

async def run_web():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ===== MENU =====
menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💳 Новая заявка")]
    ],
    resize_keyboard=True
)

# ===== START =====
@dp.message(F.text == "/start")
async def start(message: types.Message):
    await message.answer("бот запущен", reply_markup=menu)

# ===== STATE =====
waiting = {}

# ===== NEW ORDER TEXT =====
@dp.message(F.text == "💳 Новая заявка")
async def new_order(message: types.Message):
    waiting[message.from_user.id] = True

    await message.answer(
        "💳 Карта под оплату\n"
        "Введите сумму в RUB, на которую нужна карта.\n"
        "После подтверждения работник отправит реквизиты для оплаты.\n\n"
        "💸 Сумма заявки: в рублях\n"
        "Пример: 500"
    )

# ===== AMOUNT =====
@dp.message(F.text.isdigit())
async def amount(message: types.Message):

    uid = message.from_user.id

    if uid not in waiting:
        return

    waiting.pop(uid)

    cur.execute(
        "INSERT INTO orders (user_id, amount, status) VALUES (?, ?, ?)",
        (uid, float(message.text), "NEW")
    )
    conn.commit()

    order_id = cur.lastrowid

    text = f"""
📥 Доступна заявка #{order_id}
Метод: Карта под оплату
Сумма операции: {message.text} руб.
Статус: NEW
"""

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Взять в работу", callback_data=f"take_{order_id}")]
    ])

    await message.answer(text, reply_markup=keyboard)

# ===== TAKE ORDER =====
@dp.callback_query(F.data.startswith("take_"))
async def take(call: types.CallbackQuery):

    await call.answer("Взял в работу ❤️")
    await call.message.edit_text(call.message.text + "\n\n🟢 В РАБОТЕ")

# ===== MAIN =====
async def main():
    await run_web()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())