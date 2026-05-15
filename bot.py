import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from config import TOKEN, ADMIN_IDS, WELCOME_MESSAGE
from database import db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────

async def check_subscriptions(user_id: int, bot) -> list:
    """Foydalanuvchi obuna bo'lmagan kanallarni qaytaradi."""
    channels = db.get_channels()
    not_subscribed = []
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch["username"], user_id)
            if member.status in ["left", "kicked", "banned"]:
                not_subscribed.append(ch)
        except Exception:
            not_subscribed.append(ch)
    return not_subscribed


def subscription_keyboard(not_subscribed: list) -> InlineKeyboardMarkup:
    """Obuna bo'lmagan kanallar uchun tugmalar."""
    buttons = []
    for ch in not_subscribed:
        username = ch["username"].lstrip("@")
        buttons.append([InlineKeyboardButton(
            f"📢 {ch['username']} ga obuna bo'lish",
            url=f"https://t.me/{username}"
        )])
    buttons.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(buttons)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─────────────────────────────────────────
#  FOYDALANUVCHI HANDLERLARI
# ─────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    not_subscribed = await check_subscriptions(user_id, context.bot)

    if not_subscribed:
        await update.message.reply_text(
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard(not_subscribed)
        )
        return

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="HTML"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Admin panel komandalarini o'tkazib yuborish
    if text.startswith("/"):
        return

    # Obuna tekshirish
    not_subscribed = await check_subscriptions(user_id, context.bot)
    if not_subscribed:
        await update.message.reply_text(
            "⚠️ <b>Botdan foydalanish uchun avval kanallarga obuna bo'ling:</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard(not_subscribed)
        )
        return

    # Kino qidirish
    movie = db.get_movie_by_code(text.upper())
    if movie:
        await update.message.reply_text(
            f"🎬 <b>{movie['name']}</b>\n"
            f"📌 {movie.get('description', '')}\n\n"
            f"⬇️ Kino yuborilmoqda...",
            parse_mode="HTML"
        )
        try:
            await context.bot.send_video(
                chat_id=user_id,
                video=movie["file_id"],
                caption=f"🎬 <b>{movie['name']}</b>\n{movie.get('description', '')}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Video yuborishda xato: {e}")
            await update.message.reply_text(
                "❌ Kinoni yuborishda xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."
            )
    else:
        await update.message.reply_text(
            f"❌ <b>{text}</b> kodi bo'yicha kino topilmadi.\n"
            f"Kodni to'g'ri kiritdingizmi? Harflar katta/kichik bo'lishi muhim emas.",
            parse_mode="HTML"
        )


async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    not_subscribed = await check_subscriptions(user_id, context.bot)

    if not_subscribed:
        await query.edit_message_text(
            "⚠️ <b>Hali obuna bo'lmagan kanallar bor:</b>",
            parse_mode="HTML",
            reply_markup=subscription_keyboard(not_subscribed)
        )
    else:
        await query.edit_message_text(
            "✅ <b>Barcha kanallarga obuna bo'ldingiz!</b>\n\n"
            "🎬 Endi kino kodini yuboring va men sizga kinoni yuboraman.",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────
#  ADMIN HANDLERLARI
# ─────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return

    channels = db.get_channels()
    movies = db.get_all_movies()

    text = (
        "🔧 <b>ADMIN PANEL</b>\n\n"
        f"📢 Majburiy kanallar: <b>{len(channels)} ta</b>\n"
        f"🎬 Kinolar: <b>{len(movies)} ta</b>\n\n"
        "<b>Kanallar boshqaruvi:</b>\n"
        "/addchannel @username — kanal qo'shish\n"
        "/removechannel @username — kanalni o'chirish\n"
        "/listchannels — kanallar ro'yxati\n\n"
        "<b>Kino boshqaruvi:</b>\n"
        "/addmovie — kino qo'shish (video yuboring)\n"
        "/removemovie KOD — kinoni o'chirish\n"
        "/listmovies — kinolar ro'yxati\n\n"
        "<b>Boshqa:</b>\n"
        "/broadcast — hammaga xabar yuborish\n"
        "/stats — statistika"
    )

    await update.message.reply_text(text, parse_mode="HTML")


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>Ishlatilishi:</b> /addchannel @kanalusername\n\n"
            "<b>Misol:</b> /addchannel @kino_uzbek",
            parse_mode="HTML"
        )
        return

    username = context.args[0]
    if not username.startswith("@"):
        username = "@" + username

    # Kanal mavjudligini tekshirish
    try:
        chat = await context.bot.get_chat(username)
        channel_name = chat.title or username
    except Exception:
        await update.message.reply_text(
            f"❌ <b>{username}</b> kanali topilmadi.\n"
            "Bot kanalga admin qilib qo'shilganmi?",
            parse_mode="HTML"
        )
        return

    if db.add_channel(username, channel_name):
        await update.message.reply_text(
            f"✅ <b>{username}</b> ({channel_name}) majburiy kanallar ro'yxatiga qo'shildi!",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"⚠️ <b>{username}</b> allaqachon ro'yxatda mavjud.",
            parse_mode="HTML"
        )


async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>Ishlatilishi:</b> /removechannel @kanalusername",
            parse_mode="HTML"
        )
        return

    username = context.args[0]
    if not username.startswith("@"):
        username = "@" + username

    if db.remove_channel(username):
        await update.message.reply_text(f"✅ <b>{username}</b> o'chirildi.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ <b>{username}</b> topilmadi.", parse_mode="HTML")


async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    channels = db.get_channels()
    if not channels:
        await update.message.reply_text("📢 Hozircha majburiy kanallar yo'q.")
        return

    text = "📢 <b>Majburiy kanallar ro'yxati:</b>\n\n"
    for i, ch in enumerate(channels, 1):
        text += f"{i}. {ch['username']} — {ch['name']}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    await update.message.reply_text(
        "🎬 <b>Kino qo'shish</b>\n\n"
        "Iltimos, video faylni yuboring.\n"
        "Video yuborilgandan keyin kod va nom so'raladi.",
        parse_mode="HTML"
    )
    context.user_data["awaiting_video"] = True


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.user_data.get("awaiting_video"):
        return

    video = update.message.video or update.message.document
    if not video:
        return

    file_id = video.file_id
    context.user_data["pending_movie_file_id"] = file_id
    context.user_data["awaiting_video"] = False
    context.user_data["awaiting_movie_info"] = True

    await update.message.reply_text(
        f"✅ Video qabul qilindi!\n"
        f"📁 <code>File ID: {file_id}</code>\n\n"
        "Endi quyidagi formatda ma'lumot yuboring:\n\n"
        "<b>KOD|Kino nomi|Tavsif</b>\n\n"
        "<b>Misol:</b>\n"
        "<code>AV2023|Avatar: Suv yo'li|O'zbekcha dublyaj, 2022, HD</code>",
        parse_mode="HTML"
    )


async def handle_movie_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.user_data.get("awaiting_movie_info"):
        return

    text = update.message.text.strip()
    parts = text.split("|")

    if len(parts) < 2:
        await update.message.reply_text(
            "❌ Noto'g'ri format!\n\n"
            "To'g'ri format:\n"
            "<code>KOD|Kino nomi|Tavsif</code>",
            parse_mode="HTML"
        )
        return

    code = parts[0].strip().upper()
    name = parts[1].strip()
    description = parts[2].strip() if len(parts) > 2 else ""
    file_id = context.user_data.get("pending_movie_file_id")

    if db.add_movie(code, name, description, file_id):
        await update.message.reply_text(
            f"✅ <b>Kino qo'shildi!</b>\n\n"
            f"🎬 Nomi: <b>{name}</b>\n"
            f"🔑 Kod: <code>{code}</code>\n"
            f"📌 Tavsif: {description}\n\n"
            f"Foydalanuvchi <code>{code}</code> kodini yuborganda ushbu kinoni oladi.",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"⚠️ <b>{code}</b> kodi allaqachon mavjud!\n"
            "Avval /removemovie buyrug'i bilan o'chiring.",
            parse_mode="HTML"
        )

    context.user_data["awaiting_movie_info"] = False
    context.user_data["pending_movie_file_id"] = None


async def remove_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "🎬 <b>Ishlatilishi:</b> /removemovie KOD\n\n"
            "<b>Misol:</b> /removemovie AV2023",
            parse_mode="HTML"
        )
        return

    code = context.args[0].upper()
    if db.remove_movie(code):
        await update.message.reply_text(f"✅ <b>{code}</b> kodli kino o'chirildi.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ <b>{code}</b> kodli kino topilmadi.", parse_mode="HTML")


async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    movies = db.get_all_movies()
    if not movies:
        await update.message.reply_text("🎬 Hozircha kinolar yo'q.")
        return

    text = "🎬 <b>Kinolar ro'yxati:</b>\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. <code>{m['code']}</code> — <b>{m['name']}</b>\n"
        if m.get("description"):
            text += f"   📌 {m['description']}\n"

    await update.message.reply_text(text, parse_mode="HTML")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    s = db.get_stats()
    await update.message.reply_text(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🎬 Kinolar: <b>{s['movies']}</b>\n"
        f"📢 Kanallar: <b>{s['channels']}</b>",
        parse_mode="HTML"
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    if not context.args:
        await update.message.reply_text(
            "📣 <b>Ishlatilishi:</b> /broadcast Xabar matni\n\n"
            "<b>Misol:</b> /broadcast Yangi kinolar qo'shildi!",
            parse_mode="HTML"
        )
        return

    message = " ".join(context.args)
    users = db.get_all_users()
    sent = 0
    failed = 0

    await update.message.reply_text(f"📣 Xabar {len(users)} ta foydalanuvchiga yuborilmoqda...")

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📣 <b>Yangilik:</b>\n\n{message}",
                parse_mode="HTML"
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato: <b>{failed}</b>",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────
#  FOYDALANUVCHINI RO'YXATGA OLISH
# ─────────────────────────────────────────

async def register_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Har bir xabarda foydalanuvchini ro'yxatga olish."""
    if update.effective_user:
        db.add_user(update.effective_user.id)


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()

    # Ro'yxatga olish middleware
    app.add_handler(MessageHandler(filters.ALL, register_user), group=-1)

    # Foydalanuvchi handlerlari
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))

    # Admin handlerlari
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("addchannel", add_channel))
    app.add_handler(CommandHandler("removechannel", remove_channel))
    app.add_handler(CommandHandler("listchannels", list_channels))
    app.add_handler(CommandHandler("addmovie", add_movie_start))
    app.add_handler(CommandHandler("removemovie", remove_movie))
    app.add_handler(CommandHandler("listmovies", list_movies))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Video/document handler (admin uchun)
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))

    # Matn handlerlari
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_movie_info))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
