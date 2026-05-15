import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from config import TOKEN, ADMIN_IDS, WELCOME_MESSAGE
from database import db

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════
#  KEEP-ALIVE WEB SERVER (Render uchun)
# ═══════════════════════════════════════

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")
    def log_message(self, format, *args):
        pass

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    server.serve_forever()

def keep_alive():
    t = threading.Thread(target=run_server)
    t.daemon = True
    t.start()


# ═══════════════════════════════════════
#  YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_subscriptions(user_id: int, bot) -> list:
    channels = db.get_channels()
    not_subbed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["username"], user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_subbed.append(ch)
        except Exception:
            not_subbed.append(ch)
    return not_subbed


def sub_keyboard(not_subbed: list) -> InlineKeyboardMarkup:
    btns = []
    for ch in not_subbed:
        un = ch["username"].lstrip("@")
        btns.append([InlineKeyboardButton(f"📢 {ch['username']}", url=f"https://t.me/{un}")])
    btns.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(btns)


# ═══════════════════════════════════════
#  FOYDALANUVCHI QISMI
# ═══════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.add_user(user_id)
    not_subbed = await check_subscriptions(user_id, context.bot)
    if not_subbed:
        await update.message.reply_text(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            parse_mode="HTML",
            reply_markup=sub_keyboard(not_subbed)
        )
        return
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="HTML")


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    not_subbed = await check_subscriptions(user_id, context.bot)
    if not_subbed:
        await query.edit_message_text(
            "⚠️ <b>Hali obuna bo'lmagan kanallar bor!</b>",
            parse_mode="HTML",
            reply_markup=sub_keyboard(not_subbed)
        )
    else:
        await query.edit_message_text(
            "✅ <b>Rahmat! Endi kino kodini yuboring.</b>\n\n📝 Masalan: <code>AV2023</code>",
            parse_mode="HTML"
        )


async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    not_subbed = await check_subscriptions(user_id, context.bot)
    if not_subbed:
        await update.message.reply_text(
            "⚠️ <b>Avval kanallarga obuna bo'ling:</b>",
            parse_mode="HTML",
            reply_markup=sub_keyboard(not_subbed)
        )
        return
    movie = db.get_movie_by_code(text.upper())
    if movie:
        await update.message.reply_text(
            f"🎬 <b>{movie['name']}</b>\n📌 {movie.get('description','')}\n\n⬇️ Yuborilmoqda...",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_video(
                chat_id=user_id,
                video=movie["file_id"],
                caption=f"🎬 <b>{movie['name']}</b>\n{movie.get('description','')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Video xato: {e}")
            await update.message.reply_text("❌ Kinoni yuborishda xatolik. Keyinroq urinib ko'ring.")
    else:
        await update.message.reply_text(
            f"❌ <b>{text}</b> kodi topilmadi.\nKodni to'g'ri yozdingizmi?",
            parse_mode="HTML"
        )


# ═══════════════════════════════════════
#  ADMIN MENYULAR
# ═══════════════════════════════════════

def admin_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanallar", callback_data="menu_channels"),
         InlineKeyboardButton("🎬 Kinolar", callback_data="menu_movies")],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data="menu_broadcast"),
         InlineKeyboardButton("📊 Statistika", callback_data="menu_stats")],
    ])

def channels_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="ch_add")],
        [InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="ch_remove")],
        [InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="ch_list")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ])

def movies_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo'shish", callback_data="mv_add")],
        [InlineKeyboardButton("🗑 Kino o'chirish", callback_data="mv_remove")],
        [InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="mv_list")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ])

def back_keyboard(back_to: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=back_to)]])


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"🔧 <b>ADMIN PANEL</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🎬 Kinolar: <b>{s['movies']}</b>\n"
        f"📢 Kanallar: <b>{s['channels']}</b>",
        parse_mode="HTML",
        reply_markup=admin_main_keyboard()
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return
    data = query.data

    if data == "back_main":
        s = db.get_stats()
        await query.edit_message_text(
            f"🔧 <b>ADMIN PANEL</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🎬 Kinolar: <b>{s['movies']}</b>\n"
            f"📢 Kanallar: <b>{s['channels']}</b>",
            parse_mode="HTML", reply_markup=admin_main_keyboard()
        )

    elif data == "menu_channels":
        channels = db.get_channels()
        await query.edit_message_text(
            f"📢 <b>KANALLAR BOSHQARUVI</b>\n\nJami: <b>{len(channels)} ta kanal</b>",
            parse_mode="HTML", reply_markup=channels_keyboard()
        )

    elif data == "ch_list":
        channels = db.get_channels()
        if not channels:
            text = "📢 Hozircha majburiy kanallar yo'q."
        else:
            text = "📢 <b>Majburiy kanallar:</b>\n\n"
            for i, ch in enumerate(channels, 1):
                text += f"{i}. {ch['username']} — {ch['name']}\n"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=channels_keyboard())

    elif data == "ch_add":
        context.user_data["state"] = "waiting_channel"
        await query.edit_message_text(
            "📢 <b>Kanal qo'shish</b>\n\n"
            "Kanal username ni yuboring:\n"
            "<b>Misol:</b> <code>@kino_uzbek</code>\n\n"
            "⚠️ Avval botni kanalga <b>admin</b> qilib qo'shing!",
            parse_mode="HTML", reply_markup=back_keyboard("menu_channels")
        )

    elif data == "ch_remove":
        channels = db.get_channels()
        if not channels:
            await query.edit_message_text("📢 O'chirish uchun kanallar yo'q.", reply_markup=channels_keyboard())
            return
        btns = [[InlineKeyboardButton(f"🗑 {ch['username']}", callback_data=f"del_ch_{ch['username']}")] for ch in channels]
        btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_channels")])
        await query.edit_message_text("🗑 <b>O'chirish uchun kanalni tanlang:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("del_ch_"):
        username = data[7:]
        if db.remove_channel(username):
            await query.edit_message_text(f"✅ <b>{username}</b> o'chirildi!", parse_mode="HTML", reply_markup=channels_keyboard())
        else:
            await query.edit_message_text("❌ Xatolik.", reply_markup=channels_keyboard())

    elif data == "menu_movies":
        movies = db.get_all_movies()
        await query.edit_message_text(
            f"🎬 <b>KINOLAR BOSHQARUVI</b>\n\nJami: <b>{len(movies)} ta kino</b>",
            parse_mode="HTML", reply_markup=movies_keyboard()
        )

    elif data == "mv_list":
        movies = db.get_all_movies()
        if not movies:
            text = "🎬 Hozircha kinolar yo'q."
        else:
            text = "🎬 <b>Kinolar ro'yxati:</b>\n\n"
            for i, m in enumerate(movies, 1):
                text += f"{i}. <code>{m['code']}</code> — <b>{m['name']}</b>\n"
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=movies_keyboard())

    elif data == "mv_add":
        context.user_data["state"] = "waiting_video"
        await query.edit_message_text(
            "🎬 <b>Kino qo'shish</b>\n\n"
            "1️⃣ Video faylni yuboring\n"
            "2️⃣ Keyin kod va nom kiritasiz\n\n"
            "📤 Hozir videoni yuboring:",
            parse_mode="HTML", reply_markup=back_keyboard("menu_movies")
        )

    elif data == "mv_remove":
        movies = db.get_all_movies()
        if not movies:
            await query.edit_message_text("🎬 O'chirish uchun kinolar yo'q.", reply_markup=movies_keyboard())
            return
        btns = [[InlineKeyboardButton(f"🗑 {m['code']} — {m['name']}", callback_data=f"del_mv_{m['code']}")] for m in movies]
        btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_movies")])
        await query.edit_message_text("🗑 <b>O'chirish uchun kinoni tanlang:</b>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("del_mv_"):
        code = data[7:]
        if db.remove_movie(code):
            await query.edit_message_text(f"✅ <b>{code}</b> kodli kino o'chirildi!", parse_mode="HTML", reply_markup=movies_keyboard())
        else:
            await query.edit_message_text("❌ Xatolik.", reply_markup=movies_keyboard())

    elif data == "menu_stats":
        s = db.get_stats()
        await query.edit_message_text(
            f"📊 <b>STATISTIKA</b>\n\n"
            f"👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🎬 Kinolar: <b>{s['movies']}</b>\n"
            f"📢 Kanallar: <b>{s['channels']}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]])
        )

    elif data == "menu_broadcast":
        context.user_data["state"] = "waiting_broadcast"
        await query.edit_message_text(
            "📣 <b>Hammaga xabar yuborish</b>\n\nXabar matnini yuboring:",
            parse_mode="HTML", reply_markup=back_keyboard("back_main")
        )


# ═══════════════════════════════════════
#  ADMIN MATN/VIDEO XABARLAR
# ═══════════════════════════════════════

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await handle_user_message(update, context)
        return

    state = context.user_data.get("state")

    if state == "waiting_channel":
        username = update.message.text.strip()
        if not username.startswith("@"):
            username = "@" + username
        try:
            chat = await context.bot.get_chat(username)
            channel_name = chat.title or username
        except Exception:
            await update.message.reply_text(
                f"❌ <b>{username}</b> topilmadi.\nBotni kanalga admin qilib qo'shdingizmi?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_channels")]]))
            return
        if db.add_channel(username, channel_name):
            await update.message.reply_text(
                f"✅ <b>{username}</b> ({channel_name}) qo'shildi!",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Yana qo'shish", callback_data="ch_add")],
                    [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_main")]
                ])
            )
        else:
            await update.message.reply_text(f"⚠️ <b>{username}</b> allaqachon mavjud!", parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_channels")]]))
        context.user_data["state"] = None

    elif state == "waiting_movie_info":
        text = update.message.text.strip()
        parts = text.split("|")
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ <b>Noto'g'ri format!</b>\n\nTo'g'ri:\n<code>KOD|Nomi|Tavsif</code>\n\nMisol:\n<code>AV2023|Avatar|O'zbekcha, HD</code>",
                parse_mode="HTML")
            return
        code = parts[0].strip().upper()
        name = parts[1].strip()
        description = parts[2].strip() if len(parts) > 2 else ""
        file_id = context.user_data.get("pending_file_id")
        if db.add_movie(code, name, description, file_id):
            await update.message.reply_text(
                f"✅ <b>Kino qo'shildi!</b>\n\n🎬 <b>{name}</b>\n🔑 Kod: <code>{code}</code>\n📌 {description}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Yana kino qo'shish", callback_data="mv_add")],
                    [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_main")]
                ])
            )
        else:
            await update.message.reply_text(f"⚠️ <b>{code}</b> kodi allaqachon mavjud!", parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_movies")]]))
        context.user_data["state"] = None
        context.user_data["pending_file_id"] = None

    elif state == "waiting_broadcast":
        message_text = update.message.text.strip()
        users = db.get_all_users()
        sent = 0
        failed = 0
        msg = await update.message.reply_text(f"📣 {len(users)} ta foydalanuvchiga yuborilmoqda...")
        for uid in users:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📣 <b>Yangilik:</b>\n\n{message_text}", parse_mode="HTML")
                sent += 1
            except Exception:
                failed += 1
        await msg.edit_text(
            f"✅ <b>Xabar yuborildi!</b>\n\n✅ Yuborildi: <b>{sent}</b>\n❌ Xato: <b>{failed}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Asosiy menyu", callback_data="back_main")]]))
        context.user_data["state"] = None

    else:
        await handle_user_message(update, context)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if context.user_data.get("state") != "waiting_video":
        return
    video = update.message.video or update.message.document
    if not video:
        return
    file_id = video.file_id
    context.user_data["pending_file_id"] = file_id
    context.user_data["state"] = "waiting_movie_info"
    await update.message.reply_text(
        f"✅ <b>Video qabul qilindi!</b>\n\n"
        f"Endi shu formatda yuboring:\n\n"
        f"<code>KOD|Kino nomi|Tavsif</code>\n\n"
        f"<b>Misol:</b>\n<code>AV2023|Avatar: Suv yo'li|O'zbekcha dublyaj, HD</code>",
        parse_mode="HTML"
    )


# ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════

def main():
    keep_alive()  # Render uchun web server ishga tushadi

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(admin_callback))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))

    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
