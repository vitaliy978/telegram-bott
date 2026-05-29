import asyncio
import aiohttp
import os
import json
import subprocess

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart

# ================= CONFIG =================
TOKEN = "8785507686:AAEV7OaolE4SK1VvFfG6IoYGLSfm3vCgycs"
AUDD_API = "240333867bcfecfa439513e3baac2155"

ADMIN_ID = 7362066938
USERS_FILE = "users.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()

queue = asyncio.Queue()

# ================= USERS =================
def load_users():
    if not os.path.exists(USERS_FILE):
        return set()

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()

def save_user(uid: int):
    users = load_users()

    if uid not in users:
        users.add(uid)

        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users), f, ensure_ascii=False)

# ================= ADMIN =================
def is_admin(uid: int):
    return uid == ADMIN_ID

# ================= MENU =================
def menu(uid: int):
    kb = [
        [types.KeyboardButton(text="🎥 Video")],
        [types.KeyboardButton(text="ℹ️ Help")]
    ]

    if is_admin(uid):
        kb.append([types.KeyboardButton(text="👑 Admin")])

    return types.ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )

# ================= START =================
@dp.message(CommandStart())
async def start(message: types.Message):
    save_user(message.from_user.id)

    await message.answer(
        "🎧 Send a video and I will try to find the music",
        reply_markup=menu(message.from_user.id)
    )

# ================= HELP =================
@dp.message(F.text == "ℹ️ Help")
async def help_cmd(message: types.Message):
    await message.answer(
        "📌 Send a video up to 10 seconds\n"
        "🎵 I will try to recognize the music"
    )

# ================= AUDD =================
async def recognize(path):
    url = "https://api.audd.io/"

    try:
        async with aiohttp.ClientSession() as session:
            with open(path, "rb") as f:

                data = aiohttp.FormData()
                data.add_field("api_token", AUDD_API)
                data.add_field("return", "apple_music,spotify")
                data.add_field("file", f)

                async with session.post(url, data=data, timeout=60) as r:

                    if r.status != 200:
                        return {
                            "error": f"API ERROR {r.status}"
                        }

                    return await r.json()

    except asyncio.TimeoutError:
        return {
            "error": "REQUEST TIMEOUT"
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# ================= VIDEO =================
@dp.message(F.video | F.video_note)
async def video_handler(message: types.Message):

    video = message.video or message.video_note

    if video.duration > 10:
        await message.answer("❌ Maximum video length is 10 seconds")
        return

    wait_msg = await message.answer("🔎 Searching for music...")

    file = await bot.get_file(video.file_id)

    path = f"video_{message.from_user.id}.mp4"

    await bot.download_file(file.file_path, path)

    await queue.put((message, wait_msg, path))

# ================= WORKER =================
async def worker():
    while True:

        message, wait_msg, path = await queue.get()

        audio_path = path.replace(".mp4", ".mp3")

        try:
            print(f"📹 VIDEO: {path}")

            # VIDEO -> MP3
            process = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    path,
                    "-vn",
                    "-acodec",
                    "mp3",
                    audio_path
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            if process.returncode != 0:
                print(process.stderr.decode())

                await wait_msg.edit_text(
                    "❌ Video processing error"
                )

                continue

            if not os.path.exists(audio_path):

                await wait_msg.edit_text(
                    "❌ Failed to create audio file"
                )

                continue

            print(f"🎵 AUDIO: {audio_path}")

            result = await recognize(audio_path)

            print("🔎 AUDD:", result)

            if result.get("error"):

                await wait_msg.edit_text(
                    f"⚠️ {result['error']}"
                )

                continue

            if result.get("result"):

                song = result["result"]

                text = (
                    f"🎵 <b>{song.get('artist', 'Unknown')}</b>\n"
                    f"🎧 {song.get('title', 'Unknown')}"
                )

                if song.get("album"):
                    text += f"\n💿 {song['album']}"

                await wait_msg.edit_text(
                    text,
                    parse_mode="HTML"
                )

            else:
                await wait_msg.edit_text(
                    "😕 Music not found"
                )

        except Exception as e:

            await wait_msg.edit_text(
                f"⚠️ Error:\n{e}"
            )

        finally:

            try:
                if os.path.exists(path):
                    os.remove(path)

                if os.path.exists(audio_path):
                    os.remove(audio_path)

            except:
                pass

            queue.task_done()

# ================= MAIN =================
async def main():

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    print("🚀 BOT STARTED")

    asyncio.create_task(worker())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())