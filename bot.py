import asyncio
import os
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

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
    status TEXT,
    worker_id INTEGER
)
""")
conn.commit()

# ===== SIMPLE WEB SERVER (fix Render port issue) =====
async def handle(request):
    return web.Response(text="Bot is alive")

async def run_web():
    app = web.Application()
    app.router.add_get("/", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ===== KEYBOARD =====
def order_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❤️ Взять в работу",
                callback_data=f"take_{order_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⏪ Назад",
                callback_data="back"
            )
        ]
    ])

# ===== START =====
@dp.message(F.text == "/start")
async def start(message: types.Message):
    await message.answer("🚀 Бот запущен")

# ===== CREATE ORDER =====
waiting = {}

@dp.message(F.text == "💳 Новая заявка")
async def new_order(message: types.Message):
    waiting[message.from_user.id] = True
    await message.answer("💳 Введите сумму в RUB")

# ===== AMOUNT =====
@dp.message(F.text.isdigit())
async def set_amount(message: types.Message):

    uid = message.from_user.id

    if uid not in waiting:
        return

    amount = float(message.text)
    waiting.pop(uid)

    cur.execute(
        "INSERT INTO orders (user_id, amount, status, worker_id) VALUES (?, ?, ?, ?)",
        (uid, amount, "NEW", None)
    )
    conn.commit()

    order_id = cur.lastrowid

    text = f"""
📥 Доступна новая заявка #{order_id}
Метод: Карта под оплату
Сумма операции: {amount:.2f} руб.
💳 Можно выдать обычную карту
Сумма заявки: {amount:.2f} RUB
Резерв клиента: {round(amount / 63.7, 2)} USDT
⏱️ На принятие: 1500 сек
"""

    await message.answer(text, reply_markup=order_keyboard(order_id))

# ===== TAKE ORDER SAFE =====
@dp.callback_query(F.data.startswith("take_"))
async def take_order(call: types.CallbackQuery):

    order_id = int(call.data.split("_")[1])

    cur.execute("SELECT status FROM orders WHERE id=?", (order_id,))
    order = cur.fetchone()

    if not order:
        return await call.answer("Не найдено", show_alert=True)

    if order[0] != "NEW":
        return await call.answer("Уже взято", show_alert=True)

    cur.execute("""
        UPDATE orders
        SET status='IN_PROGRESS', worker_id=?
        WHERE id=?
    """, (call.from_user.id, order_id))
    conn.commit()

    await call.answer("Взял в работу ❤️")

    await call.message.edit_text(call.message.text + "\n\n🟢 В РАБОТЕ")

# ===== BACK =====
@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    await call.answer()
    await call.message.edit_text("🔙 Назад")

# ===== MAIN =====
async def main():
    await run_web()          # 👈 фикс Render
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())