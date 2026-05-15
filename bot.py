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
#  KEEP-ALIVE (Render uchun)
# ═══════════════════════════════════════

class KeepAlive(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot ishlayapti!")
    def log_message(self, format, *args):
        pass

def keep_alive():
    server = HTTPServer(("0.0.0.0", 8080), KeepAlive)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()


# ═══════════════════════════════════════
#  YORDAMCHI
# ═══════════════════════════════════════

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def check_subscriptions(user_id, bot):
    not_subbed = []
    for ch in db.get_channels():
        try:
            m = await bot.get_chat_member(ch["username"], user_id)
            if m.status in ["left", "kicked", "banned"]:
                not_subbed.append(ch)
        except:
            not_subbed.append(ch)
    return not_subbed

def sub_keyboard(not_subbed):
    btns = [[InlineKeyboardButton(f"📢 {ch['username']}", url=f"https://t.me/{ch['username'].lstrip('@')}")] for ch in not_subbed]
    btns.append([InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(btns)

def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Kanallar", callback_data="menu_channels"),
         InlineKeyboardButton("🎬 Kinolar", callback_data="menu_movies")],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data="menu_broadcast"),
         InlineKeyboardButton("📊 Statistika", callback_data="menu_stats")],
    ])

def channels_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo'shish", callback_data="ch_add")],
        [InlineKeyboardButton("🗑 Kanal o'chirish", callback_data="ch_remove")],
        [InlineKeyboardButton("📋 Ro'yxat", callback_data="ch_list")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ])

def movies_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kino qo'shish", callback_data="mv_add")],
        [InlineKeyboardButton("🗑 Kino o'chirish", callback_data="mv_remove")],
        [InlineKeyboardButton("📋 Ro'yxat", callback_data="mv_list")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
    ])

def back_kb(to):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data=to)]])


# ═══════════════════════════════════════
#  FOYDALANUVCHI
# ═══════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db.add_user(user_id)
    not_subbed = await check_subscriptions(user_id, context.bot)
    if not_subbed:
        await update.message.reply_text(
            "⚠️ <b>Botdan foydalanish uchun obuna bo'ling:</b>",
            parse_mode="HTML", reply_markup=sub_keyboard(not_subbed))
        return
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode="HTML")

async def check_sub_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    not_subbed = await check_subscriptions(q.from_user.id, context.bot)
    if not_subbed:
        await q.edit_message_text("⚠️ <b>Hali obuna bo'lmagan kanallar bor!</b>",
            parse_mode="HTML", reply_markup=sub_keyboard(not_subbed))
    else:
        await q.edit_message_text(
            "✅ <b>Rahmat! Endi kino kodini yuboring.</b>\n\n📝 Masalan: <code>AV2023</code>",
            parse_mode="HTML")

async def user_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    not_subbed = await check_subscriptions(user_id, context.bot)
    if not_subbed:
        await update.message.reply_text("⚠️ <b>Avval kanallarga obuna bo'ling:</b>",
            parse_mode="HTML", reply_markup=sub_keyboard(not_subbed))
        return
    movie = db.get_movie_by_code(text.upper())
    if movie:
        await update.message.reply_text(
            f"🎬 <b>{movie['name']}</b>\n📌 {movie.get('description','')}\n\n⬇️ Yuborilmoqda...",
            parse_mode="HTML")
        try:
            await context.bot.send_video(chat_id=user_id, video=movie["file_id"],
                caption=f"🎬 <b>{movie['name']}</b>", parse_mode="HTML")
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("❌ Xatolik yuz berdi.")
    else:
        await update.message.reply_text(f"❌ <b>{text}</b> kodi topilmadi.", parse_mode="HTML")


# ═══════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Siz admin emassiz.")
        return
    s = db.get_stats()
    await update.message.reply_text(
        f"🔧 <b>ADMIN PANEL</b>\n\n👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
        f"🎬 Kinolar: <b>{s['movies']}</b>\n📢 Kanallar: <b>{s['channels']}</b>",
        parse_mode="HTML", reply_markup=admin_main_kb())

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    d = q.data
    s = db.get_stats()

    if d == "back_main":
        await q.edit_message_text(
            f"🔧 <b>ADMIN PANEL</b>\n\n👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🎬 Kinolar: <b>{s['movies']}</b>\n📢 Kanallar: <b>{s['channels']}</b>",
            parse_mode="HTML", reply_markup=admin_main_kb())
    elif d == "menu_channels":
        chs = db.get_channels()
        await q.edit_message_text(f"📢 <b>KANALLAR</b>\n\nJami: <b>{len(chs)} ta</b>",
            parse_mode="HTML", reply_markup=channels_kb())
    elif d == "ch_list":
        chs = db.get_channels()
        txt = "📢 <b>Kanallar:</b>\n\n" + "\n".join(f"{i+1}. {c['username']}" for i,c in enumerate(chs)) if chs else "📢 Kanallar yo'q."
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=channels_kb())
    elif d == "ch_add":
        context.user_data["state"] = "waiting_channel"
        await q.edit_message_text(
            "📢 <b>Kanal username yuboring:</b>\n\nMisol: <code>@kino_uzbek</code>\n\n"
            "⚠️ Botni kanalga admin qilib qo'shing!",
            parse_mode="HTML", reply_markup=back_kb("menu_channels"))
    elif d == "ch_remove":
        chs = db.get_channels()
        if not chs:
            await q.edit_message_text("Kanallar yo'q.", reply_markup=channels_kb())
            return
        btns = [[InlineKeyboardButton(f"🗑 {c['username']}", callback_data=f"del_ch_{c['username']}")] for c in chs]
        btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_channels")])
        await q.edit_message_text("🗑 <b>O'chirish uchun tanlang:</b>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("del_ch_"):
        username = d[7:]
        db.remove_channel(username)
        await q.edit_message_text(f"✅ <b>{username}</b> o'chirildi!", parse_mode="HTML", reply_markup=channels_kb())
    elif d == "menu_movies":
        mvs = db.get_all_movies()
        await q.edit_message_text(f"🎬 <b>KINOLAR</b>\n\nJami: <b>{len(mvs)} ta</b>",
            parse_mode="HTML", reply_markup=movies_kb())
    elif d == "mv_list":
        mvs = db.get_all_movies()
        txt = "🎬 <b>Kinolar:</b>\n\n" + "\n".join(f"{i+1}. <code>{m['code']}</code> — {m['name']}" for i,m in enumerate(mvs)) if mvs else "🎬 Kinolar yo'q."
        await q.edit_message_text(txt, parse_mode="HTML", reply_markup=movies_kb())
    elif d == "mv_add":
        context.user_data["state"] = "waiting_video"
        await q.edit_message_text(
            "🎬 <b>Kino qo'shish</b>\n\n📤 Video faylni yuboring:",
            parse_mode="HTML", reply_markup=back_kb("menu_movies"))
    elif d == "mv_remove":
        mvs = db.get_all_movies()
        if not mvs:
            await q.edit_message_text("Kinolar yo'q.", reply_markup=movies_kb())
            return
        btns = [[InlineKeyboardButton(f"🗑 {m['code']} — {m['name']}", callback_data=f"del_mv_{m['code']}")] for m in mvs]
        btns.append([InlineKeyboardButton("🔙 Orqaga", callback_data="menu_movies")])
        await q.edit_message_text("🗑 <b>O'chirish uchun tanlang:</b>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("del_mv_"):
        code = d[7:]
        db.remove_movie(code)
        await q.edit_message_text(f"✅ <b>{code}</b> o'chirildi!", parse_mode="HTML", reply_markup=movies_kb())
    elif d == "menu_stats":
        await q.edit_message_text(
            f"📊 <b>STATISTIKA</b>\n\n👥 Foydalanuvchilar: <b>{s['users']}</b>\n"
            f"🎬 Kinolar: <b>{s['movies']}</b>\n📢 Kanallar: <b>{s['channels']}</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]]))
    elif d == "menu_broadcast":
        context.user_data["state"] = "waiting_broadcast"
        await q.edit_message_text("📣 <b>Xabar matnini yuboring:</b>",
            parse_mode="HTML", reply_markup=back_kb("back_main"))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await user_msg(update, context)
        return
    state = context.user_data.get("state")
    text = update.message.text.strip()

    if state == "waiting_channel":
        username = text if text.startswith("@") else "@" + text
        try:
            chat = await context.bot.get_chat(username)
            name = chat.title or username
        except:
            await update.message.reply_text(f"❌ <b>{username}</b> topilmadi!", parse_mode="HTML",
                reply_markup=back_kb("menu_channels"))
            return
        db.add_channel(username, name)
        await update.message.reply_text(f"✅ <b>{username}</b> qo'shildi!", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yana qo'shish", callback_data="ch_add")],
                [InlineKeyboardButton("🏠 Menyu", callback_data="back_main")]]))
        context.user_data["state"] = None

    elif state == "waiting_movie_info":
        parts = text.split("|")
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Format: <code>KOD|Nomi|Tavsif</code>\n\nMisol: <code>AV2023|Avatar|O'zbekcha</code>",
                parse_mode="HTML")
            return
        code = parts[0].strip().upper()
        name = parts[1].strip()
        desc = parts[2].strip() if len(parts) > 2 else ""
        file_id = context.user_data.get("pending_file_id")
        db.add_movie(code, name, desc, file_id)
        await update.message.reply_text(
            f"✅ <b>Kino qo'shildi!</b>\n\n🎬 {name}\n🔑 <code>{code}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Yana qo'shish", callback_data="mv_add")],
                [InlineKeyboardButton("🏠 Menyu", callback_data="back_main")]]))
        context.user_data["state"] = None
        context.user_data["pending_file_id"] = None

    elif state == "waiting_broadcast":
        users = db.get_all_users()
        sent = 0
        msg = await update.message.reply_text(f"📣 {len(users)} ta foydalanuvchiga yuborilmoqda...")
        for uid in users:
            try:
                await context.bot.send_message(uid, f"📣 <b>Yangilik:</b>\n\n{text}", parse_mode="HTML")
                sent += 1
            except:
                pass
        await msg.edit_text(f"✅ Yuborildi: <b>{sent}</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menyu", callback_data="back_main")]]))
        context.user_data["state"] = None

    else:
        await user_msg(update, context)


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if context.user_data.get("state") != "waiting_video":
        return
    video = update.message.video or update.message.document
    if not video:
        return
    context.user_data["pending_file_id"] = video.file_id
    context.user_data["state"] = "waiting_movie_info"
    await update.message.reply_text(
        "✅ <b>Video qabul qilindi!</b>\n\nEndi yuboring:\n<code>KOD|Nomi|Tavsif</code>\n\nMisol:\n<code>AV2023|Avatar|O'zbekcha, HD</code>",
        parse_mode="HTML")


# ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════

def main():
    keep_alive()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(check_sub_cb, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(admin_cb))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
