# plugins/channels.py — Channel management
import asyncio
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, FloodWait
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from miko import Bot
from config import OWNER_ID
from database.database import (
    save_channel, delete_channel, get_channels, get_channel_doc,
    save_encoded_link, save_encoded_link2, save_encoded_link3,
    search_channels_by_name, count_channels,
)
from helper_func import encode, is_owner_or_admin, cq_owner_or_admin

PAGE_SIZE = 5
_chat_cache: dict = {}


async def _get_chat(client, channel_id: int):
    if channel_id in _chat_cache:
        return _chat_cache[channel_id]
    try:
        chat = await client.get_chat(channel_id)
        _chat_cache[channel_id] = chat
        return chat
    except Exception:
        return None


async def _gen_all_tokens(client, channel_id: int) -> tuple:
    """Returns (normal_tok, req_tok, dir_tok) as full bot deep-link URLs."""
    base_n = await save_encoded_link(channel_id)
    base_r = await encode(str(channel_id) + ":req")
    base_d = await encode(str(channel_id) + ":dir")
    await save_encoded_link2(channel_id, base_r)
    await save_encoded_link3(channel_id, base_d)
    u = client.username
    return (
        f"https://t.me/{u}?start={base_n}",
        f"https://t.me/{u}?start=req_{base_r}",
        f"https://t.me/{u}?start=dir_{base_d}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# /addchannel
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("addchannel") & is_owner_or_admin)
async def cmd_addchannel(client, message: Message):
    args = message.command[1:]
    if len(args) < 2:
        return await message.reply_text(
            "<b>╔═════════════════════╗\n"
            "║  ➕ Add Channel     ║\n"
            "╚═════════════════════╝</b>\n\n"
            "Usage: <code>/addchannel [Anime Name] [Channel ID]</code>",
            parse_mode=ParseMode.HTML)

    try:
        channel_id = int(args[-1])
    except ValueError:
        return await message.reply_text(
            "❌ Channel ID must be a valid integer.", parse_mode=ParseMode.HTML)

    anime_name  = " ".join(args[:-1])
    status_msg  = await message.reply_text("⏳ Verifying channel...", parse_mode=ParseMode.HTML)

    try:
        chat = await client.get_chat(channel_id)
    except Exception as e:
        await status_msg.delete()
        return await message.reply_text(
            f"❌ Could not find channel.\n<code>{e}</code>", parse_mode=ParseMode.HTML)

    try:
        me         = await client.get_me()
        bot_member = await client.get_chat_member(channel_id, me.id)
        has_invite = getattr(bot_member.privileges, "can_invite_users", False)
        if bot_member.status.name not in ("ADMINISTRATOR", "CREATOR") or not has_invite:
            await status_msg.delete()
            return await message.reply_text(
                "❌ I need to be an admin with <b>Invite Users via Link</b> permission.",
                parse_mode=ParseMode.HTML)
    except Exception as e:
        await status_msg.delete()
        return await message.reply_text(
            f"❌ Permission check failed: <code>{e}</code>", parse_mode=ParseMode.HTML)

    try:
        primary_inv  = await client.create_chat_invite_link(chat_id=channel_id)
        primary_link = primary_inv.invite_link
    except Exception:
        primary_link = f"https://t.me/{chat.username}" if chat.username else "N/A"

    await save_channel(channel_id, anime_name, primary_link)
    normal_tok, req_tok, dir_tok = await _gen_all_tokens(client, channel_id)

    await status_msg.delete()
    await message.reply_text(
        f"<b>╔══════════════════════╗\n"
        f"║  ✅  CHANNEL ADDED!   ║\n"
        f"╚══════════════════════╝</b>\n\n"
        f"<b>📺 Anime:</b> {anime_name}\n"
        f"<b>🆔 ID:</b> <code>{channel_id}</code>\n\n"
        f"<b>🔗 Primary Link:</b>\n<code>{primary_link}</code>\n\n"
        f"<b>━━━━━━ TOKEN LINKS ━━━━━━</b>\n\n"
        f"<b>📨 Request Token:</b>\n<code>{req_tok}</code>\n\n"
        f"<b>🌐 Normal Token:</b>\n<code>{normal_tok}</code>\n\n"
        f"<b>⚡ Direct Token:</b>\n<code>{dir_tok}</code>",
        parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# /delchannel
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("delchannel") & is_owner_or_admin)
async def cmd_delchannel(client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text(
            "Usage: <code>/delchannel [Channel ID]</code>", parse_mode=ParseMode.HTML)
    channel_id = int(message.command[1])
    doc        = await get_channel_doc(channel_id)
    anime_name = doc.get("anime_name", str(channel_id)) if doc else str(channel_id)
    if await delete_channel(channel_id):
        _chat_cache.pop(channel_id, None)
        await message.reply_text(
            f"✅ <b>{anime_name}</b> (<code>{channel_id}</code>) removed.",
            parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(
            f"❌ Channel <code>{channel_id}</code> not found.", parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# /channels — paginated list with all 3 token links
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("channels") & is_owner_or_admin)
async def cmd_channels(client, message: Message):
    status_msg = await message.reply_text("⏳ Loading channels...", parse_mode=ParseMode.HTML)
    channels   = await get_channels()
    if not channels:
        await status_msg.delete()
        return await message.reply_text(
            "📭 No channels added yet.\nUse <code>/addchannel [Name] [ID]</code>",
            parse_mode=ParseMode.HTML)
    await _send_channels_page(client, message, channels, page=0, status_msg=status_msg)


async def _send_channels_page(client, message, channels, page, status_msg=None, edit=False):
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass

    total_pages = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    chunk = channels[start: start + PAGE_SIZE]

    lines = []
    for idx, ch_id in enumerate(chunk, start=start + 1):
        doc = await get_channel_doc(ch_id)
        if not doc:
            continue
        anime   = doc.get("anime_name", f"Channel {ch_id}")
        primary = doc.get("primary_link", "#")
        enc_n   = doc.get("encoded_link") or await encode(str(ch_id))
        enc_r   = doc.get("req_encoded_link") or await encode(str(ch_id) + ":req")
        enc_d   = doc.get("dir_encoded_link") or await encode(str(ch_id) + ":dir")
        req_tok  = f"https://t.me/{client.username}?start=req_{enc_r}"
        norm_tok = f"https://t.me/{client.username}?start={enc_n}"
        dir_tok  = f"https://t.me/{client.username}?start=dir_{enc_d}"
        lines.append(
            f"<b>{idx}.</b> <a href='{primary}'>{anime}</a>\n"
            f"   <a href='{req_tok}'>📨 Req</a> | "
            f"<a href='{norm_tok}'>🌐 Normal</a> | "
            f"<a href='{dir_tok}'>⚡ Direct</a>")

    text = (
        f"<b>╔══ 📋 CHANNELS LIST ══╗</b>\n"
        f"<b>Page {page+1} of {total_pages} • {len(channels)} total</b>\n\n"
        + "\n\n".join(lines))

    ch_btns = []
    for ch_id in chunk:
        doc = await get_channel_doc(ch_id)
        if doc:
            name = doc.get("anime_name", str(ch_id))[:20]
            ch_btns.append([InlineKeyboardButton(
                f"⚙️ {name}", callback_data=f"ch_settings:{ch_id}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"chpage:{page-1}"))
    nav_row.append(InlineKeyboardButton("➕ Add", callback_data="ch_add_prompt"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"chpage:{page+1}"))

    markup = InlineKeyboardMarkup(
        ch_btns + [nav_row, [InlineKeyboardButton("✖️ Close", callback_data="close")]])

    if edit:
        await message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML,
                                 disable_web_page_preview=True)
    else:
        await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML,
                                  disable_web_page_preview=True)


@Bot.on_callback_query(filters.regex(r"^chpage:(\d+)$") & cq_owner_or_admin)
async def cb_channels_page(client, query: CallbackQuery):
    page     = int(query.data.split(":")[1])
    channels = await get_channels()
    await _send_channels_page(client, query.message, channels, page=page, edit=True)
    await query.answer()


@Bot.on_callback_query(filters.regex("^ch_add_prompt$") & cq_owner_or_admin)
async def cb_ch_add_prompt(client, query: CallbackQuery):
    await query.answer()
    await query.edit_message_text(
        "<b>➕ Add Channel</b>\n\nSend:\n<code>/addchannel [Anime Name] [Channel ID]</code>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Back", callback_data="chpage:0")]]),
        parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# Channel settings panel (inline)
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^ch_settings:(-?\d+)$") & cq_owner_or_admin)
async def cb_ch_settings(client, query: CallbackQuery):
    ch_id = int(query.data.split(":")[1])
    doc   = await get_channel_doc(ch_id)
    if not doc:
        return await query.answer("Channel not found!", show_alert=True)

    anime   = doc.get("anime_name", str(ch_id))
    primary = doc.get("primary_link", "N/A")
    enc_n   = doc.get("encoded_link") or await encode(str(ch_id))
    enc_r   = doc.get("req_encoded_link") or await encode(str(ch_id) + ":req")
    enc_d   = doc.get("dir_encoded_link") or await encode(str(ch_id) + ":dir")
    req_tok  = f"https://t.me/{client.username}?start=req_{enc_r}"
    norm_tok = f"https://t.me/{client.username}?start={enc_n}"
    dir_tok  = f"https://t.me/{client.username}?start=dir_{enc_d}"

    text = (
        f"<b>⚙️ Channel Settings</b>\n\n"
        f"<b>📺 Anime:</b> {anime}\n"
        f"<b>🆔 ID:</b> <code>{ch_id}</code>\n\n"
        f"<b>🔗 Primary:</b>\n<code>{primary}</code>\n\n"
        f"<b>📨 Request Token:</b>\n<code>{req_tok}</code>\n\n"
        f"<b>🌐 Normal Token:</b>\n<code>{norm_tok}</code>\n\n"
        f"<b>⚡ Direct Token:</b>\n<code>{dir_tok}</code>")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Regenerate Links", callback_data=f"ch_regen:{ch_id}"),
         InlineKeyboardButton("🗑️ Delete Channel",  callback_data=f"ch_del_confirm:{ch_id}")],
        [InlineKeyboardButton("◀️ Back",  callback_data="chpage:0"),
         InlineKeyboardButton("✖️ Close", callback_data="close")],
    ])
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^ch_regen:(-?\d+)$") & cq_owner_or_admin)
async def cb_ch_regen(client, query: CallbackQuery):
    ch_id = int(query.data.split(":")[1])
    await _gen_all_tokens(client, ch_id)
    await query.answer("✅ Links regenerated!", show_alert=True)
    await cb_ch_settings(client, query)


@Bot.on_callback_query(filters.regex(r"^ch_del_confirm:(-?\d+)$") & cq_owner_or_admin)
async def cb_ch_del_confirm(client, query: CallbackQuery):
    ch_id = int(query.data.split(":")[1])
    doc   = await get_channel_doc(ch_id)
    anime = doc.get("anime_name", str(ch_id)) if doc else str(ch_id)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"ch_del_do:{ch_id}"),
         InlineKeyboardButton("❌ Cancel",      callback_data=f"ch_settings:{ch_id}")],
    ])
    await query.edit_message_text(
        f"<b>⚠️ Delete <code>{anime}</code>?</b>\n\nThis cannot be undone.",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^ch_del_do:(-?\d+)$") & cq_owner_or_admin)
async def cb_ch_del_do(client, query: CallbackQuery):
    ch_id = int(query.data.split(":")[1])
    _chat_cache.pop(ch_id, None)
    await delete_channel(ch_id)
    await query.answer("✅ Deleted!", show_alert=True)
    channels = await get_channels()
    await _send_channels_page(client, query.message, channels, page=0, edit=True)


# ─────────────────────────────────────────────────────────────────────────────
# /search
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("search") & is_owner_or_admin)
async def cmd_search(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: <code>/search [Anime Name]</code>", parse_mode=ParseMode.HTML)
    query_str = " ".join(message.command[1:])
    docs = await search_channels_by_name(query_str)
    if not docs:
        return await message.reply_text(
            f"🔎 No results for <b>{query_str}</b>.", parse_mode=ParseMode.HTML)
    buttons = [
        [InlineKeyboardButton(
            f"📺 {doc.get('anime_name','?')}",
            callback_data=f"ch_settings:{doc.get('channel_id')}")]
        for doc in docs[:10]
    ]
    await message.reply_text(
        f"<b>🔎 Results for:</b> <i>{query_str}</i>",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML)
