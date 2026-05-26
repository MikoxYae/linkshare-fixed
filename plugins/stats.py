# plugins/stats.py — /stats, /ping, /status
import time
import asyncio
import psutil
from datetime import datetime

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from miko import Bot
from database.database import count_users, count_channels
from helper_func import is_owner_or_admin, get_readable_time


@Bot.on_message(filters.command("stats") & is_owner_or_admin)
async def cmd_stats(client, message: Message):
    total_users    = await count_users()
    total_channels = await count_channels()
    total_links    = total_channels * 2
    now   = datetime.now()
    delta = now - client.uptime
    uptime_str = get_readable_time(int(delta.total_seconds()))
    text = (
        "<b>Bot Statistics</b>\n\n"
        f"<b>Total Users:</b> <code>{total_users}</code>\n"
        f"<b>Total Channels:</b> <code>{total_channels}</code>\n"
        f"<b>Total Links:</b> <code>{total_links}</code>\n"
        f"<b>Uptime:</b> <code>{uptime_str}</code>"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Close", callback_data="close")]])
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("ping") & is_owner_or_admin)
async def cmd_ping(client, message: Message):
    start = time.monotonic()
    temp  = await message.reply_text("Pinging...")
    ms    = (time.monotonic() - start) * 1000
    await temp.edit_text(f"<b>Pong!</b>  <code>{ms:.2f} ms</code>", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("status") & is_owner_or_admin)
async def cmd_status(client, message: Message):
    now   = datetime.now()
    delta = now - client.uptime
    total_secs = int(delta.total_seconds())
    days, rem  = divmod(total_secs, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    from database.database import dbroadcast_collection
    pending_dbc = await dbroadcast_collection.count_documents({})
    start_time_str = client.uptime.strftime("%Y-%m-%d %H:%M:%S")
    text = (
        "<b>System Status</b>\n\n"
        f"<b>CPU:</b> <code>{cpu}%</code>  |  <b>RAM:</b> <code>{ram}%</code>\n"
        f"<b>Uptime:</b> <code>{days}d {hours}h {mins}m {secs}s</code>\n"
        f"<b>Started:</b> <code>{start_time_str}</code>\n"
        f"<b>Pending dBroadcasts:</b> <code>{pending_dbc}</code>"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Close", callback_data="close")]])
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
