import os

# ─────────────────────────────────────────
#  SOZLAMALAR — config.py
#  GitHub Secrets dan o'qiydi
# ─────────────────────────────────────────

# Bot token — GitHub Secret: BOT_TOKEN
TOKEN = os.environ.get("BOT_TOKEN", "8901622532:AAGAdcAcIdC6mR1C0ebktOzm_j6BAFnxD4c")

# Admin ID lar — GitHub Secret: ADMIN_IDS (vergul bilan: 123456,789012)
_admin_env = os.environ.get("ADMIN_IDS", "")
if _admin_env:
    ADMIN_IDS = [int(x.strip()) for x in _admin_env.split(",") if x.strip().isdigit()]
else:
    ADMIN_IDS = [
        7406325328,
    ]

# Xush kelibsiz xabar
WELCOME_MESSAGE = (
    "🎬 <b>KinoBot ga xush kelibsiz!</b>\n\n"
    "Men sizga istalgan kinoni yuborishim mumkin.\n\n"
    "📌 <b>Qanday ishlaydi?</b>\n"
    "Kino kodini yuboring va men kinoni sizga yuboraman.\n\n"
    "📝 <b>Misol:</b> <code>AV2023</code>\n\n"
    "Kino kodlarini kanal adminidan oling. 👇"
)
