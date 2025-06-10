...(весь предыдущий код остаётся)

# 🔧 Генерация мема
async def generate_meme(image_bytes: bytes, text: str, no_watermark: bool) -> io.BytesIO:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    font_path = "fonts/impact.ttf"  # Убедись, что шрифт существует
    font_size = int(image.height * 0.07)
    font = ImageFont.truetype(font_path, font_size)

    # Центрированный текст сверху
    text_width, text_height = draw.textsize(text, font=font)
    x = (image.width - text_width) // 2
    y = 10

    draw.text((x, y), text, font=font, fill="white", stroke_width=2, stroke_fill="black")

    if not no_watermark:
        wm_text = "@t.me/OGStickBot"
        wm_font = ImageFont.truetype(font_path, int(font_size * 0.6))
        wm_width, wm_height = draw.textsize(wm_text, font=wm_font)
        draw.text((image.width - wm_width - 10, image.height - wm_height - 10), wm_text, font=wm_font, fill="white", stroke_width=1, stroke_fill="black")

    output = io.BytesIO()
    image.save(output, format="WEBP")
    output.name = "meme.webp"
    output.seek(0)
    return output

# 👑 Панель администратора
ADMIN_ID = 1049209219  # замените на ваш Telegram ID

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM premium_users")
    premium_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM usage_count")
    user_count = cursor.fetchone()[0]

    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей всего: <b>{user_count}</b>\n"
        f"💎 Премиум пользователей: <b>{premium_count}</b>",
        parse_mode="HTML"
    )