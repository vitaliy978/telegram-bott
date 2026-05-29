import asyncio
import aiohttp
import os
import json

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ================= CONFIG =================
TOKEN = "8785507686:AAEV7OaolE4SK1VvFfG6IoYGLSfm3vCgycs"
AUDD_API = "e59e87c6c1d15c00d92e6652cafd3588"

ADMIN_ID = 7362066938

USERS_FILE = "users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

ads_text = "📢 реклама не настроена"
waiting_ads = False

queue = asyncio.Queue()

# ================= USERS =================
def load_users():
    if not os.path.exists(USERS_FILE):
        return set()

    try:
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_user(uid: int):
    users = load_users()
    users.add(uid)

    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

# ================= ADMIN CHECK =================
def is_admin(uid: int):
    return uid == ADMIN_ID

# ================= MENU =================
def menu(uid: int):
    kb = [
        [types.KeyboardButton(text="🎥 Видео")],
        [types.KeyboardButton(text="ℹ️ Помощь")]
    ]

    if is_admin(uid):
        kb.append([types.KeyboardButton(text="👑 Админка")])

    return types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    save_user(message.from_user.id)

    await message.answer(
        "🎧 бот запущен",
        reply_markup=menu(message.from_user.id)
    )

# ================= HELP =================
@dp.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: types.Message):
    await message.answer(
        "🎧 Отправь видео до 10 секунд\n"
        "и я попробую найти музыку"
    )

# ================= AUDIO API =================
async def recognize(path):
    url = "https://api.audd.io/recognize/"

    async with aiohttp.ClientSession() as session:
        with open(path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("api_token", AUDD_API)
            data.add_field("file", f)

            async with session.post(url, data=data) as r:
                return await r.json()

# ================= VIDEO =================
@dp.message(F.text == "🎥 Видео")
async def video_hint(message: types.Message):
    await message.answer("📹 отправь видео до 10 секунд")

@dp.message(F.video)
async def video_handler(message: types.Message):
    if message.video.duration > 10:
        await message.answer("❌ максимум 10 секунд")
        return

    file = await bot.get_file(message.video.file_id)
    path = f"video_{message.from_user.id}.mp4"

    await bot.download_file(file.file_path, path)
    await queue.put((message, path))

# ================= WORKER =================
async def worker():
    while True:
        message, path = await queue.get()

        try:
            result = await recognize(path)
            os.remove(path)

            if result.get("result"):
                s = result["result"]
                await message.answer(f"🎧 {s['artist']} — {s['title']}")
            else:
                await message.answer("😕 не найдено")

        except:
            await message.answer("⚠️ ошибка")

        queue.task_done()

# ================= ADMIN PANEL =================
@dp.message(F.text == "👑 Админка")
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="📢 Рассылка")],
            [types.KeyboardButton(text="✏️ Реклама")],
            [types.KeyboardButton(text="🔙 Назад")]
        ],
        resize_keyboard=True
    )

    await message.answer("👑 админ панель", reply_markup=kb)

# ================= BACK =================
@dp.message(F.text == "🔙 Назад")
async def back(message: types.Message):
    await message.answer(
        "↩️ меню",
        reply_markup=menu(message.from_user.id)
    )

# ================= EDIT ADS =================
@dp.message(F.text == "✏️ Реклама")
async def edit_ads(message: types.Message):
    global waiting_ads

    if not is_admin(message.from_user.id):
        return

    waiting_ads = True
    await message.answer("📝 отправь текст рекламы")

# ================= SAVE ADS =================
@dp.message()
async def save_ads(message: types.Message):
    global ads_text, waiting_ads

    if not is_admin(message.from_user.id):
        return

    if not waiting_ads:
        return

    ads_text = message.text
    waiting_ads = False

    await message.answer("✅ реклама обновлена")

# ================= BROADCAST =================
@dp.message(F.text == "📢 Рассылка")
async def broadcast(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    users = load_users()

    await message.answer("📡 рассылка запущена...")

    sent = 0

    for u in users:
        try:
            await bot.send_message(u, ads_text)
            sent += 1
        except:
            pass

    await message.answer(f"📢 готово\nотправлено: {sent}")

# ================= START BOT =================
async def main():
    print("BOT STARTED 🚀")

    asyncio.create_task(worker())

    await dp.start_polling(bot)

asyncio.run(main())