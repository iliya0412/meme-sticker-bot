import openai
import sqlite3
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice
from aiogram.dispatcher.filters import Command
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import os
import logging

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
openai.api_key = OPENAI_API_KEY

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

DB_NAME = "users.db"
FREE_LIMIT = 3
FONT_PATH = "fonts/impact.ttf"
WATERMARK = "@t.me/OGStickBot"
PRICE_RUB = 9900  # 99.00₽

# Инициализация базы данных
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                premium INTEGER DEFAULT 0,
                used INTEGER DEFAULT 0
            )
        """)

init_db()

# Хранилище пользовательских состояний
user_states = {}

def is_premium(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT premium FROM users WHERE id = ?", (user_id,)).fetchone()
        return row and row[0] == 1

def increment_usage(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT used FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            conn.execute("UPDATE users SET used = used + 1 WHERE id = ?", (user_id,))
        else:
            conn.execute("INSERT INTO users (id, used) VALUES (?, 1)", (user_id,))

def can_generate(user_id):
    if is_premium(user_id):
        return True
    with sqlite3.connect(DB_NAME) as conn:
        row = conn.execute("SELECT used FROM users WHERE id = ?", (user_id,)).fetchone()
        return not row or row[0] < FREE_LIMIT

async def generate_meme(image_bytes, text, no_watermark):
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype(FONT_PATH, size=36)
    except:
        font = ImageFont.load_default()

    w, h = image.size
    text_w, text_h = draw.textsize(text, font=font)
    x = (w - text_w) // 2
    y = h - text_h - 20

    draw.text((x, y), text, font=font, fill="white", stroke_fill="black", stroke_width=2)

    if not no_watermark:
        draw.text((10, h - 40), WATERMARK, font=font, fill="gray")

    output = BytesIO()
    output.name = "sticker.webp"
    image.save(output, format="WEBP")
    output.seek(0)
    return output

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("👋 Отправь мне изображение, и я сделаю мем-стикер! Бесплатно доступно 3 стикера.")

@dp.message_handler(commands=["premium"])
async def premium(message: types.Message):
    prices = [LabeledPrice(label="Подписка без ограничений", amount=PRICE_RUB)]
    await bot.send_invoice(
        message.chat.id,
        title="Премиум-доступ",
        description="Создавайте неограниченно мем-стикеров и без водяного знака",
        provider_token=PAYMENT_PROVIDER_TOKEN,
        currency="RUB",
        prices=prices,
        start_parameter="premium-subscription",
        payload="premium_user"
    )

@dp.pre_checkout_query_handler(lambda q: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    user_id = message.from_user.id
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("UPDATE users SET premium = 1 WHERE id = ?", (user_id,))
    await message.answer("🎉 Вы получили премиум-доступ! Теперь можно создавать неограниченно мемов без водяного знака.")

@dp.message_handler(content_types=[types.ContentType.PHOTO])
async def handle_photo(message: types.Message):
    user_id = message.from_user.id
    if not can_generate(user_id):
        await message.answer("🚫 Лимит бесплатных стикеров исчерпан. Оформи подписку за 99₽: /premium")
        return

    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_data = await bot.download_file(file.file_path)

    user_states[user_id] = {"image_bytes": file_data.read()}

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✍️ Ввести текст", callback_data="manual_text"),
        InlineKeyboardButton("🤖 Сгенерировать нейросетью", callback_data="ai_text")
    )
    await message.answer("Выбери способ добавления текста:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data in ["manual_text", "ai_text"])
async def handle_text_choice(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    choice = callback_query.data

    if user_id not in user_states or "image_bytes" not in user_states[user_id]:
        await callback_query.message.answer("⚠️ Сначала отправьте изображение.")
        return

    if choice == "manual_text":
        await callback_query.message.answer("✍️ Введите текст, который хотите добавить к изображению.")
        user_states[user_id]["awaiting_text"] = True
    elif choice == "ai_text":
        await callback_query.message.answer("🤖 Генерирую текст через нейросеть...")
        try:
            prompt = "Придумай короткую, смешную подпись на русском языке для изображения мем-стикера."
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.9
            )
            text = response.choices[0].message.content.strip()

            image_bytes = user_states[user_id].get("image_bytes")
            if not image_bytes:
                await callback_query.message.answer("⚠️ Ошибка: изображение не найдено.")
                return

            no_watermark = is_premium(user_id)
            increment_usage(user_id)
            output = await generate_meme(image_bytes, text, no_watermark)

            await bot.send_sticker(callback_query.message.chat.id, output)
            del user_states[user_id]
        except Exception as e:
            await callback_query.message.answer("⚠️ Ошибка генерации текста: " + str(e))

@dp.message_handler()
async def handle_text(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_states and user_states[user_id].get("awaiting_text"):
        text = message.text
        image_bytes = user_states[user_id].get("image_bytes")
        if not image_bytes:
            await message.answer("⚠️ Ошибка: изображение не найдено.")
            return

        no_watermark = is_premium(user_id)
        increment_usage(user_id)
        output = await generate_meme(image_bytes, text, no_watermark)

        await bot.send_sticker(message.chat.id, output)
        del user_states[user_id]
    else:
        await message.answer("📸 Отправьте изображение для создания стикера.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
