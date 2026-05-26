# plugins/misc.py — /genlink, /backup, /approveoff, /approveon
import asyncio
import json
import zipfile
import io
from datetime import datetime

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from miko import Bot
from config import OWNER_ID
from database.database import (
    save_channel, save_encoded_link, save_encoded_link2, save_encoded_link3,
    set_approval_off,
    user_data, channels_collection, admins_collection, settings_collection,
    fsub_channels_col,
)
from helper_func import encode, is_owner_or_admin


# ── /genlink [URL] ────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("genlink") & is_owner_or_admin)
async def cmd_genlink(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "<b>Usage:</b> <code>/genlink [URL]</code>\n\n"
            "Wraps an external URL as a bot deep-link with all 3 token types.",
            parse_mode=ParseMode.HTML)

    url = message.command[1]
    if not url.startswith("http"):
        return await message.reply_text(
            "❌ Please provide a valid URL (must start with http/https).",
            parse_mode=ParseMode.HTML)

    fake_id = abs(hash(url)) % (10**9) + int(datetime.utcnow().timestamp())
    await save_channel(fake_id, "External Link", url)
    await channels_collection.update_one(
        {"channel_id": fake_id}, {"$set": {"original_link": url}})

    base_n = await save_encoded_link(fake_id)
    base_r = await encode(str(fake_id) + ":req")
    base_d = await encode(str(fake_id) + ":dir")
    await save_encoded_link2(fake_id, base_r)
    await save_encoded_link3(fake_id, base_d)

    u = client.username
    norm_tok = f"https://t.me/{u}?start={base_n}"
    req_tok  = f"https://t.me/{u}?start=req_{base_r}"
    dir_tok  = f"https://t.me/{u}?start=dir_{base_d}"

    await message.reply_text(
        f"<b>╔══════════════════╗\n"
        f"║  🔗  LINK TOKENS  ║\n"
        f"╚══════════════════╝</b>\n\n"
        f"<b>URL:</b> <code>{url}</code>\n\n"
        f"<b>📨 Request Token:</b>\n<code>{req_tok}</code>\n\n"
        f"<b>🌐 Normal Token:</b>\n<code>{norm_tok}</code>\n\n"
        f"<b>⚡ Direct Token:</b>\n<code>{dir_tok}</code>",
        parse_mode=ParseMode.HTML)


# ── /approveoff / /approveon ──────────────────────────────────────────────────

@Bot.on_message(filters.command("approveoff") & is_owner_or_admin)
async def cmd_approveoff(client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text(
            "Usage: <code>/approveoff [channel_id]</code>", parse_mode=ParseMode.HTML)
    cid = int(message.command[1])
    await set_approval_off(cid, True)
    await message.reply_text(
        f"✅ Auto-approve <b>disabled</b> for <code>{cid}</code>.", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("approveon") & is_owner_or_admin)
async def cmd_approveon(client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text(
            "Usage: <code>/approveon [channel_id]</code>", parse_mode=ParseMode.HTML)
    cid = int(message.command[1])
    await set_approval_off(cid, False)
    await message.reply_text(
        f"✅ Auto-approve <b>enabled</b> for <code>{cid}</code>.", parse_mode=ParseMode.HTML)


# ── /backup ───────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("backup") & filters.user(OWNER_ID))
async def cmd_backup(client, message: Message):
    p = await message.reply_text("⏳ Creating backup, please wait...", parse_mode=ParseMode.HTML)
    try:
        users    = [doc async for doc in user_data.find()]
        channels = [doc async for doc in channels_collection.find()]
        admins   = [doc async for doc in admins_collection.find()]
        settings = [doc async for doc in settings_collection.find()]
        fsub     = [doc async for doc in fsub_channels_col.find()]

        def _clean(docs):
            return [{k: v for k, v in d.items() if k != "_id"} for d in docs]

        data = {
            "users":          _clean(users),
            "channels":       _clean(channels),
            "admins":         _clean(admins),
            "settings":       _clean(settings),
            "fsub":           _clean(fsub),
            "exported_at":    datetime.utcnow().isoformat(),
            "total_users":    len(users),
            "total_channels": len(channels),
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("backup.json", json.dumps(data, indent=2, default=str))
        buf.seek(0)
        buf.name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"

        await p.delete()
        await client.send_document(
            message.chat.id, buf,
            caption=(
                f"<b>📦 Bot Database Backup</b>\n\n"
                f"<b>Users:</b> {len(users)}\n"
                f"<b>Channels:</b> {len(channels)}\n"
                f"<b>Admins:</b> {len(admins)}\n"
                f"<b>Date:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            ),
            parse_mode=ParseMode.HTML)
    except Exception as e:
        await p.edit_text(
            f"❌ Backup failed: <code>{e}</code>", parse_mode=ParseMode.HTML)
