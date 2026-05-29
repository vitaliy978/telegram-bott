import asyncio
import aiohttp
import os
import json
import subprocess

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

# ================= ADMIN =================
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
    await message.answer("🎧 отправь видео до 10 секунд")

# ================= AUDD =================
async def recognize(path):
    url = "https://api.audd.io/"

    async with aiohttp.ClientSession() as session:
        with open(path, "rb") as f:
            data = aiohttp.FormData()
            data.add_field("api_token", AUDD_API)
            data.add_field("file", f)

            async with session.post(url, data=data) as r:
                return await r.json()

# ================= VIDEO =================
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
            audio_path = path.replace(".mp4", ".mp3")

            print("📹 VIDEO:", path)

            # convert video → audio
            process = subprocess.run([
                "ffmpeg", "-y",
                "-i", path,
                audio_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if process.returncode != 0:
                print(process.stderr.decode())
                await message.answer("❌ ошибка конвертации видео")
                queue.task_done()
                continue

            if not os.path.exists(audio_path):
                await message.answer("❌ mp3 не создан")
                queue.task_done()
                continue

            print("🎵 AUDIO:", audio_path)

            result = await recognize(audio_path)
            print("🔎 AUDD:", result)

            os.remove(path)
            os.remove(audio_path)

            if result.get("result"):
                s = result["result"]
                await message.answer(f"🎧 {s['artist']} — {s['title']}")
            else:
                await message.answer("😕 не найдено")

        except Exception as e:
            await message.answer(f"⚠️ ошибка: {e}")

        queue.task_done()

# ================= MAIN =================
async def main():
    await bot.delete_webhook(drop_pending_updates=True)

    print("BOT STARTED 🚀")

    asyncio.create_task(worker())
    await dp.start_polling(bot)

asyncio.run(main())