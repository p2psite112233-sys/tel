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
    status TEXT,
    worker_id INTEGER
)
""")
conn.commit()

# ===== WEB (Render fix) =====
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

# ===== ROLES =====
users_role = {}
workers = set()

def set_role(user_id: int, role: str):
    users_role[user_id] = role

def get_role(user_id: int):
    return users_role.get(user_id, "user")

ADMIN_ID = 8538723496

# ===== MENU =====
menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💳 Новая заявка")]],
    resize_keyboard=True
)

# ===== START =====
@dp.message(F.text == "/start")
async def start(message: types.Message):

    role = get_role(message.from_user.id)

    if role == "worker":
        await message.answer("🛠 Вы вошли как WORKER", reply_markup=menu)
    elif role == "admin":
        await message.answer("👑 Вы вошли как ADMIN", reply_markup=menu)
    else:
        await message.answer("👤 Вы вошли как USER", reply_markup=menu)

# ===== SET WORKER =====
@dp.message(F.text.startswith("/setworker"))
async def set_worker(message: types.Message):

    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()

    if len(parts) < 2:
        await message.answer("Формат: /setworker 123456789")
        return

    try:
        user_id = int(parts[1])
        workers.add(user_id)
        set_role(user_id, "worker")

        await message.answer(f"✅ Worker назначен: {user_id}")
    except:
        await message.answer("Ошибка ID")

# ===== STATE =====
waiting = {}

# ===== NEW ORDER =====
@dp.message(F.text == "💳 Новая заявка")
async def new_order(message: types.Message):

    waiting[message.from_user.id] = True

    await message.answer(
        "💳 Карта под оплату\n"
        "Введите сумму в RUB\n"
        "Пример: 500"
    )

# ===== AMOUNT (ВАЖНО: БЕЗ FILTERОВ) =====
@dp.message()
async def amount(message: types.Message):

    uid = message.from_user.id

    if not waiting.get(uid):
        return

    text = message.text.strip()

    try:
        rub = float(text)
    except:
        await message.answer("❌ Введите число, например 500")
        return

    waiting[uid] = False

    usdt = round(rub / 63.7, 2)
    total = round(rub * 1.2, 2)

    cur.execute(
        "INSERT INTO orders (user_id, amount, status, worker_id) VALUES (?, ?, ?, ?)",
        (uid, rub, "NEW", None)
    )
    conn.commit()

    order_id = cur.lastrowid

    text_order = (
        f"📥 Доступна новая заявка #{order_id}\n"
        f"Метод: Карта под оплату\n"
        f"Сумма операции: {rub:.2f} руб.\n"
        f"💳 Можно выдать обычную карту\n"
        f"Сумма заявки: {total:.2f} RUB\n"
        f"Резерв клиента: {usdt} USDT\n"
        f"⏱️ На принятие: 1500 сек"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Взять в работу", callback_data=f"take_{order_id}")]
    ])

    # рассылка воркерам
    for w in workers:
        try:
            await bot.send_message(w, text_order, reply_markup=keyboard)
        except:
            pass

    await message.answer("✅ Заявка создана")

# ===== TAKE ORDER =====
@dp.callback_query(F.data.startswith("take_"))
async def take(call: types.CallbackQuery):

    role = get_role(call.from_user.id)

    if role not in ["worker", "admin"]:
        return await call.answer("Нет доступа", show_alert=True)

    order_id = int(call.data.split("_")[1])

    cur.execute(
        "UPDATE orders SET status='IN_PROGRESS', worker_id=? WHERE id=?",
        (call.from_user.id, order_id)
    )
    conn.commit()

    await call.answer("Взял в работу ❤️")
    await call.message.edit_text(call.message.text + "\n\n🟢 В РАБОТЕ")

# ===== MAIN =====
async def main():
    await run_web()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())