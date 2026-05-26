# plugins/clicks.py — Click tracking: /clicks and /click {channel_id}
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from miko import Bot
from database.database import (
    get_all_channel_clicks, get_channel_clicks, get_channel_doc,
    get_channels, reset_channel_clicks,
)
from helper_func import is_owner_or_admin, cq_owner_or_admin

PAGE_SIZE = 8


@Bot.on_message(filters.command("clicks") & is_owner_or_admin)
async def cmd_clicks(client, message: Message):
    await _send_clicks_page(client, message, page=0)


async def _send_clicks_page(client, target, page=0, edit=False):
    channels   = await get_channels()
    if not channels:
        text   = "<b>📊 No channels tracked yet.</b>"
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close")]])
        fn = target.edit_text if edit else target.reply_text
        return await fn(text, reply_markup=markup, parse_mode=ParseMode.HTML)

    total_pages = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)
    start  = page * PAGE_SIZE
    chunk  = channels[start: start + PAGE_SIZE]

    # Header row
    lines = [
        "<b>╔══════════════════════════════════════╗</b>",
        "<b>║        📊 LINK CLICK ANALYTICS       ║</b>",
        "<b>╚══════════════════════════════════════╝</b>",
        f"<b>Page {page+1}/{total_pages}</b>\n",
        "<code>#   Channel           Req  Norm  Dir  FSub</code>",
        "<code>─── ─────────────── ──── ──── ──── ────</code>",
    ]

    for idx, ch_id in enumerate(chunk, start=start + 1):
        doc    = await get_channel_doc(ch_id)
        name   = (doc.get("anime_name", "Unknown") if doc else "Unknown")[:15].ljust(15)
        clicks = await get_channel_clicks(ch_id)
        req    = str(clicks.get("request", 0)).rjust(4)
        norm   = str(clicks.get("normal",  0)).rjust(4)
        direct = str(clicks.get("direct",  0)).rjust(4)
        fsub   = str(clicks.get("fsub",    0)).rjust(4)
        total  = clicks.get("request",0) + clicks.get("normal",0) + clicks.get("direct",0)
        lines.append(f"<code>{idx:<3} {name} {req} {norm} {direct} {fsub}</code>")

    lines.append(f"\n<i>Use /click [channel_id] for detailed view</i>")

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"clicks_page:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"clicks_page:{page+1}"))

    markup = InlineKeyboardMarkup([nav, [InlineKeyboardButton("✖️ Close", callback_data="close")]] if nav else
                                   [[InlineKeyboardButton("✖️ Close", callback_data="close")]])

    fn = target.edit_text if edit else target.reply_text
    await fn("\n".join(lines), reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex(r"^clicks_page:(\d+)$") & cq_owner_or_admin)
async def cb_clicks_page(client, query: CallbackQuery):
    page = int(query.data.split(":")[1])
    await _send_clicks_page(client, query.message, page=page, edit=True)
    await query.answer()


@Bot.on_message(filters.command("click") & is_owner_or_admin)
async def cmd_click_detail(client, message: Message):
    if len(message.command) < 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text(
            "Usage: <code>/click [channel_id]</code>", parse_mode=ParseMode.HTML)

    ch_id  = int(message.command[1])
    doc    = await get_channel_doc(ch_id)
    name   = doc.get("anime_name", str(ch_id)) if doc else str(ch_id)
    clicks = await get_channel_clicks(ch_id)

    req    = clicks.get("request", 0)
    norm   = clicks.get("normal",  0)
    direct = clicks.get("direct",  0)
    fsub   = clicks.get("fsub",    0)
    total  = req + norm + direct + fsub

    # Build mini bar
    def bar(n, total):
        if total == 0: return "░░░░░░░░░░"
        filled = int((n / total) * 10)
        return "█" * filled + "░" * (10 - filled)

    text = (
        f"<b>╔══════════════════════╗\n"
        f"║  📊 CHANNEL CLICKS    ║\n"
        f"╚══════════════════════╝</b>\n\n"
        f"<b>📺 Channel:</b> {name}\n"
        f"<b>🆔 ID:</b> <code>{ch_id}</code>\n"
        f"<b>🔢 Total:</b> <code>{total}</code>\n\n"
        f"<b>📨 Request:</b>  <code>{req:>5}</code>  {bar(req, total)}\n"
        f"<b>🌐 Normal:</b>   <code>{norm:>5}</code>  {bar(norm, total)}\n"
        f"<b>⚡ Direct:</b>   <code>{direct:>5}</code>  {bar(direct, total)}\n"
        f"<b>🛡 FSub:</b>     <code>{fsub:>5}</code>  {bar(fsub, total)}"
    )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑 Reset Clicks", callback_data=f"clicks_reset:{ch_id}"),
        InlineKeyboardButton("✖️ Close",        callback_data="close"),
    ]])
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex(r"^clicks_reset:(-?\d+)$") & cq_owner_or_admin)
async def cb_clicks_reset(client, query: CallbackQuery):
    ch_id = int(query.data.split(":")[1])
    await reset_channel_clicks(ch_id)
    await query.answer("✅ Clicks reset!", show_alert=True)
    try:
        await query.message.delete()
    except Exception:
        pass
