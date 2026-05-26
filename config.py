import os
import re
import logging
from logging.handlers import RotatingFileHandler
from os import environ

# ─── Core Credentials ───────────────────────────────────────────────
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
APP_ID       = int(os.environ.get("APP_ID", ""))
API_HASH     = os.environ.get("API_HASH", "")

# ─── Owner & Admins ─────────────────────────────────────────────────
OWNER_ID = int(os.environ.get("OWNER_ID", ""))

try:
    ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split() if x]
except ValueError:
    raise Exception("ADMINS list must contain valid integers only.")

if OWNER_ID not in ADMINS:
    ADMINS.append(OWNER_ID)

# ─── Database ────────────────────────────────────────────────────────
DB_URI  = os.environ.get("DB_URI",  "")
DB_NAME = os.environ.get("DB_NAME", "crunchyroll_bot")

# ─── Web Server ──────────────────────────────────────────────────────
PORT = os.environ.get("PORT", "4231")
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "40"))

# ─── Auto-Approve ────────────────────────────────────────────────────
id_pattern = re.compile(r"^-?\d+$")
CHAT_ID = [
    int(cid) if id_pattern.search(cid) else cid
    for cid in environ.get("CHAT_ID", "").split()
]
APPROVED    = environ.get("APPROVED_WELCOME", "off").lower()

# ─── Timing Defaults (seconds) ──────────────────────────────────────
REVOKE_TIME       = int(os.environ.get("REVOKE_TIME",   "1800"))   # 30 min
DELETE_TIME       = int(os.environ.get("DELETE_TIME",   "1740"))   # 29 min
FSUB_LINK_EXPIRY  = int(os.environ.get("FSUB_LINK_EXPIRY", "300")) # 5 min
START_DELETE_TIME = 120   # 2 min
HELP_DELETE_TIME  = 120   # 2 min
ABOUT_DELETE_TIME = 60    # 1 min

# ─── Media / Text Defaults ──────────────────────────────────────────
START_PIC = os.environ.get(
    "START_PIC",
    "https://i.ibb.co/zV9rq4Jf/x.jpg"
)

# Image used in link delivery messages
LINK_IMAGE = "https://i.ibb.co/zV9rq4Jf/x.jpg"

START_MSG = os.environ.get("START_MESSAGE", (
    "<b>Konnichiwa! 🤗\n"
    "Mera Naam <b>Crunchyroll Link Provider</b> hai.\n"
    "Main aapko <b>anime channels</b> ki links provide karta hu.\n"
    "<blockquote>"
    "🔹 Agar aapko kisi anime ki link chahiye,\n"
    "🔹 Ya channel ki link nahi mil rahi hai,\n"
    "🔹 Ya link expired ho gayi hai"
    "</blockquote>\n"
    "Toh aap <b>@CrunchyRollChannel.</b> se New aur working links le sakte hain.\n\n"
    "Shukriya! ❤️</b>"
))

HELP_MSG = os.environ.get("HELP_MESSAGE", (
    "<blockquote expandable>"
    "<b>\U0001f198 Help &amp; Support</b>\n\n"
    "Agar aapko kisi bhi help ki zaroorat hai, toh humse yahan sampark karein:\n"
    "<b>@CrunchyRollHelper</b></blockquote>\n\n"
    "<blockquote><b>\U0001f3ac More Anime</b>\n"
    "Agar aap aur anime dekna chahte hain, toh yahan se dekh sakte hain:\n"
    "<b>@CrunchyRollChannel</b></blockquote>\n\n"
    "<blockquote expandable><b>\U0001f916 Bot Info</b>\n"
    "Bot ki jaankari ke liye /about ya /info ka istemal karein."
    "</blockquote>"
))

# Bot birth date for age calculation
BOT_BIRTH_DATE = "11/04/2026"

ABOUT_TXT = (
    "<b>About The Bot</b>\n\n"
    "🤖 <b>My Name :-</b> <a href='https://telegra.ph/Crunchyroll-Link-Provider-03-15'>Crunchyroll Link Provider</a>\n"
    "📅 <b>Bot Age :-</b> {age}\n"
    "📺 <b>Anime Channel :-</b> <a href='https://t.me/Crunchyrollchannel'>Crunchy Roll Channel</a>\n"
    "💻 <b>Language :-</b> <a href='https://t.me/Crunchyrollchannel'>Python</a>\n"
    "👨‍💻 <b>Developer :-</b> <a href='https://t.me/World_Fastest_Bots'>World Fastest Bots</a>\n\n"
    "<i>This Is a Private/Paid Bot Provided By @World_Fastest_Bots.</i>"
)

# Default image post caption (use [link] placeholder for invite link position)
DEFAULT_CAPTION = "Channel link 🔗 👇👇\n\n[link]\n[link]"

# Default join button text
DEFAULT_BUTTON_TEXT = "⛩️ 𝗖𝗟𝗜𝗖𝗞 𝗛𝗘𝗥𝗘 𝗧𝗢 𝗝𝗢𝗜𝗡 ⛩️"

# Default second message
DEFAULT_SECOND_MSG = (
    "<u><b>👆Uper Diye Gaye Link Ya Button Pe Click Karke Channel Mein Join Ho Jayenge."
    "Note: Please Join The Channel By Clicking The Link Or Button.</b></u>"
)

# Default Force Sub Message
DEFAULT_FSUB_MSG = (
    "<b>ʀᴏᴋᴏ {first}!</b>\n\n"
    "<b>ᴛᴜᴍɴᴇ ᴀʙʜɪ ᴛᴀᴋ ʜᴀᴍᴀʀᴀ ᴀɴɪᴍᴇ ᴄʜᴀɴɴᴇʟ ᴊᴏɪɴ ɴᴀʜɪɴ ᴋɪʏᴀ ʜᴀɪ!</b>\n"
    "<b><blockquote>ᴀɴɪᴍᴇ ᴋᴇ ᴇᴘɪꜱᴏᴅᴇꜱ ᴀᴜʀ ᴘᴜʀᴇ ᴀɴɪᴍᴇꜱ ʜɪɴᴅɪ ᴍᴇɪɴ ᴅᴇᴋʜɴᴇ ᴋᴇ ʟɪʏᴇ, "
    "ᴘᴇʜʟᴇ ʜᴀᴍᴀʀᴇ ᴄʜᴀɴɴᴇʟꜱ ᴊᴏɪɴ ᴋᴀʀɴᴀ ʜᴏɢᴀ।</blockquote></b>\n"
    "<b>ꜱᴀʙ ᴄʜᴀɴɴᴇʟꜱ ᴊᴏɪɴ ᴋᴀʀɴᴇ ᴋᴇ ʙᴀᴀᴅ ᴛʀʏ ᴀɢᴀɪɴ ᴘᴇ ᴄʟɪᴄᴋ ᴋᴀʀᴏ ᴀᴜʀ ᴍᴀᴢᴀ ʟᴜᴛᴏ!</b>"
)

# Maintenance mode message
MAINTENANCE_MSG = (
    "<b>🔧 The Bot Is Under Maintenance.</b>\n\n"
    "After a while the bot will be back to work as before.\n"
    "For now you can watch anime from <b>@CrunchyRollChannel</b> "
    "or contact them for support."
)

# Stats / status
BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"
USER_REPLY_TEXT = ""

DATABASE_CHANNEL = int(os.environ.get("DATABASE_CHANNEL", "-1003180409625"))  # Set this to your DB channel ID

# ─── Logging ─────────────────────────────────────────────────────────
LOG_FILE_NAME = "crunchyroll_bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler(LOG_FILE_NAME, maxBytes=50_000_000, backupCount=10),
        logging.StreamHandler(),
    ],
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
