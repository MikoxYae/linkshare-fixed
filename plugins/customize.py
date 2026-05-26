# plugins/customize.py — Full settings panel via inline keyboard
import asyncio
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram import StopPropagation
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from miko import Bot
from config import DEFAULT_CAPTION, DEFAULT_BUTTON_TEXT, DEFAULT_SECOND_MSG, DEFAULT_FSUB_MSG
from database.database import (
    get_custom_caption, set_custom_caption,
    get_custom_image, set_custom_image, delete_custom_image,
    get_custom_button_text, set_custom_button_text,
    is_button_hidden, set_button_hidden,
    get_second_message, set_second_message,
    is_second_message_off, set_second_message_off,
    is_forward_enabled, set_forward_enabled,
    get_revoke_time, set_revoke_time,
    get_delete_time, set_delete_time,
    is_fsub_enabled, set_fsub_enabled,
    get_fsub_message, set_fsub_message,
    is_maintenance, set_maintenance,
    get_all_fsub_sets, get_fsub_set, save_fsub_set,
)
from helper_func import is_owner_or_admin, cq_owner_or_admin, parse_time_string

# ─── Session tracking ────────────────────────────────────────────────────────
_cust_sessions: dict = {}  # uid -> {"step": str, ...}

# Exposed so broadcast.py / other plugins can check
def has_customize_session(uid: int) -> bool:
    return uid in _cust_sessions


def _trunc(text, n=60):
    if not text:
        return "—"
    return (text[:n] + "…") if len(text) > n else text


# ═══════════════════════════════════════════════════════════════
# MAIN PANEL
# ═══════════════════════════════════════════════════════════════

async def _main_panel(client, target, edit=False):
    maint   = await is_maintenance()
    fwd     = await is_forward_enabled()
    fsub    = await is_fsub_enabled()
    btn_h   = await is_button_hidden()
    sec_off = await is_second_message_off()

    text = (
        "<b>╔══════════════════════════╗\n"
        "║   ⚙️  BOT SETTINGS PANEL  ║\n"
        "╚══════════════════════════╝</b>\n\n"
        f"🔧 <b>Maintenance:</b> {'🔴 ON' if maint else '🟢 OFF'}\n"
        f"🔒 <b>Forward Protection:</b> {'🔴 ON' if not fwd else '🟢 OFF'}\n"
        f"🛡 <b>Global FSub:</b> {'🟢 ON' if fsub else '🔴 OFF'}\n"
        f"🔘 <b>Button:</b> {'🔴 Hidden' if btn_h else '🟢 Visible'}\n"
        f"💬 <b>Second Message:</b> {'🔴 OFF' if sec_off else '🟢 ON'}\n"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Caption",          callback_data="cust:caption"),
         InlineKeyboardButton("🖼 Image",            callback_data="cust:image")],
        [InlineKeyboardButton("🔘 Button",           callback_data="cust:button"),
         InlineKeyboardButton("💬 Second Message",   callback_data="cust:secondmsg")],
        [InlineKeyboardButton("⏱ Timing",           callback_data="cust:timing"),
         InlineKeyboardButton("🛡 Global FSub",      callback_data="cust:fsub")],
        [InlineKeyboardButton(
            "🔒 Forward Protect: " + ("ON ✅" if not fwd else "OFF ❌"),
            callback_data="cust:toggle_fwd")],
        [InlineKeyboardButton(
            "🔧 Maintenance: " + ("ON 🔴" if maint else "OFF 🟢"),
            callback_data="cust:toggle_maint")],
        [InlineKeyboardButton("✖️ Close", callback_data="close")],
    ])
    fn = target.edit_text if edit else target.reply_text
    await fn(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("customize") & is_owner_or_admin)
async def cmd_customize(client, message: Message):
    await _main_panel(client, message)


@Bot.on_callback_query(filters.regex("^cust:main$") & cq_owner_or_admin)
async def cb_cust_main(client, query: CallbackQuery):
    await _main_panel(client, query.message, edit=True)
    await query.answer()


# ─── Quick toggles ───────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^cust:toggle_fwd$") & cq_owner_or_admin)
async def cb_cust_toggle_fwd(client, query: CallbackQuery):
    current = await is_forward_enabled()
    await set_forward_enabled(not current)
    await query.answer(
        f"Forward protection {'ENABLED 🔒' if not current else 'DISABLED 🔓'}!",
        show_alert=True)
    await _main_panel(client, query.message, edit=True)


@Bot.on_callback_query(filters.regex("^cust:toggle_maint$") & cq_owner_or_admin)
async def cb_cust_toggle_maint(client, query: CallbackQuery):
    current = await is_maintenance()
    await set_maintenance(not current)
    await query.answer(
        f"Maintenance {'ENABLED 🔴' if not current else 'DISABLED 🟢'}!",
        show_alert=True)
    await _main_panel(client, query.message, edit=True)


# ═══════════════════════════════════════════════════════════════
# CAPTION
# ═══════════════════════════════════════════════════════════════

@Bot.on_callback_query(filters.regex("^cust:caption$") & cq_owner_or_admin)
async def cb_cust_caption(client, query: CallbackQuery):
    current = await get_custom_caption() or DEFAULT_CAPTION
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set Caption",    callback_data="cust:set_caption"),
         InlineKeyboardButton("🔄 Reset Default",  callback_data="cust:reset_caption")],
        [InlineKeyboardButton("◀️ Back",           callback_data="cust:main")],
    ])
    await query.edit_message_text(
        f"<b>📝 Caption Settings</b>\n\n"
        f"<b>Current:</b>\n<code>{_trunc(current, 200)}</code>\n\n"
        f"<i>Use <code>[link]</code> as placeholder for the invite link.</i>",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_caption$") & cq_owner_or_admin)
async def cb_cust_set_caption_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_caption"}
    await query.edit_message_text(
        "<b>📝 Set Caption</b>\n\nSend the new caption text.\n"
        "Use <code>[link]</code> where you want the invite link to appear.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:caption")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:reset_caption$") & cq_owner_or_admin)
async def cb_cust_reset_caption(client, query: CallbackQuery):
    await set_custom_caption(DEFAULT_CAPTION)
    await query.answer("✅ Caption reset to default!", show_alert=True)
    await cb_cust_caption(client, query)


# ═══════════════════════════════════════════════════════════════
# IMAGE
# ═══════════════════════════════════════════════════════════════

@Bot.on_callback_query(filters.regex("^cust:image$") & cq_owner_or_admin)
async def cb_cust_image(client, query: CallbackQuery):
    current = await get_custom_image() or "—"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set Image URL",   callback_data="cust:set_image"),
         InlineKeyboardButton("🗑 Remove Image",    callback_data="cust:del_image")],
        [InlineKeyboardButton("◀️ Back",            callback_data="cust:main")],
    ])
    await query.edit_message_text(
        f"<b>🖼 Image Settings</b>\n\n"
        f"<b>Current URL:</b>\n<code>{_trunc(current, 150)}</code>",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_image$") & cq_owner_or_admin)
async def cb_cust_set_image_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_image"}
    await query.edit_message_text(
        "<b>🖼 Set Image</b>\n\nSend a direct image URL (must start with https://).",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:image")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:del_image$") & cq_owner_or_admin)
async def cb_cust_del_image(client, query: CallbackQuery):
    await delete_custom_image()
    await query.answer("✅ Custom image removed! Default will be used.", show_alert=True)
    await cb_cust_image(client, query)


# ═══════════════════════════════════════════════════════════════
# BUTTON
# ═══════════════════════════════════════════════════════════════

@Bot.on_callback_query(filters.regex("^cust:button$") & cq_owner_or_admin)
async def cb_cust_button(client, query: CallbackQuery):
    btn_text = await get_custom_button_text() or DEFAULT_BUTTON_TEXT
    hidden   = await is_button_hidden()
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set Button Text",   callback_data="cust:set_btn_text"),
         InlineKeyboardButton("🔄 Reset Text",        callback_data="cust:reset_btn_text")],
        [InlineKeyboardButton(
            "👁 Show Button" if hidden else "🙈 Hide Button",
            callback_data="cust:toggle_btn_hide")],
        [InlineKeyboardButton("◀️ Back", callback_data="cust:main")],
    ])
    await query.edit_message_text(
        f"<b>🔘 Button Settings</b>\n\n"
        f"<b>Text:</b> <code>{btn_text}</code>\n"
        f"<b>Visibility:</b> {'🔴 Hidden' if hidden else '🟢 Visible'}",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_btn_text$") & cq_owner_or_admin)
async def cb_cust_set_btn_text_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_btn_text"}
    await query.edit_message_text(
        "<b>🔘 Set Button Text</b>\n\nSend the new button label text.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:button")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:reset_btn_text$") & cq_owner_or_admin)
async def cb_cust_reset_btn_text(client, query: CallbackQuery):
    await set_custom_button_text(DEFAULT_BUTTON_TEXT)
    await query.answer("✅ Button text reset to default!", show_alert=True)
    await cb_cust_button(client, query)


@Bot.on_callback_query(filters.regex("^cust:toggle_btn_hide$") & cq_owner_or_admin)
async def cb_cust_toggle_btn_hide(client, query: CallbackQuery):
    current = await is_button_hidden()
    await set_button_hidden(not current)
    await query.answer(
        f"Button {'hidden 🙈' if not current else 'shown 👁'}!",
        show_alert=True)
    await cb_cust_button(client, query)


# ═══════════════════════════════════════════════════════════════
# SECOND MESSAGE
# ═══════════════════════════════════════════════════════════════

@Bot.on_callback_query(filters.regex("^cust:secondmsg$") & cq_owner_or_admin)
async def cb_cust_secondmsg(client, query: CallbackQuery):
    current = await get_second_message() or DEFAULT_SECOND_MSG
    is_off  = await is_second_message_off()
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Set Message",     callback_data="cust:set_secondmsg"),
         InlineKeyboardButton("🔄 Reset",           callback_data="cust:reset_secondmsg")],
        [InlineKeyboardButton(
            "▶️ Enable" if is_off else "⏸ Disable",
            callback_data="cust:toggle_secondmsg")],
        [InlineKeyboardButton("◀️ Back", callback_data="cust:main")],
    ])
    await query.edit_message_text(
        f"<b>💬 Second Message Settings</b>\n\n"
        f"<b>Status:</b> {'🔴 OFF' if is_off else '🟢 ON'}\n\n"
        f"<b>Current:</b>\n<code>{_trunc(current, 150)}</code>",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_secondmsg$") & cq_owner_or_admin)
async def cb_cust_set_secondmsg_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_secondmsg"}
    await query.edit_message_text(
        "<b>💬 Set Second Message</b>\n\nSend the new second message. HTML formatting is supported.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:secondmsg")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:reset_secondmsg$") & cq_owner_or_admin)
async def cb_cust_reset_secondmsg(client, query: CallbackQuery):
    await set_second_message(DEFAULT_SECOND_MSG)
    await query.answer("✅ Second message reset to default!", show_alert=True)
    await cb_cust_secondmsg(client, query)


@Bot.on_callback_query(filters.regex("^cust:toggle_secondmsg$") & cq_owner_or_admin)
async def cb_cust_toggle_secondmsg(client, query: CallbackQuery):
    current = await is_second_message_off()
    await set_second_message_off(not current)
    await query.answer(
        f"Second message {'disabled ⏸' if not current else 'enabled ▶️'}!",
        show_alert=True)
    await cb_cust_secondmsg(client, query)


# ═══════════════════════════════════════════════════════════════
# TIMING
# ═══════════════════════════════════════════════════════════════

@Bot.on_callback_query(filters.regex("^cust:timing$") & cq_owner_or_admin)
async def cb_cust_timing(client, query: CallbackQuery):
    revoke = await get_revoke_time()
    delete = await get_delete_time()
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏱ Revoke: {revoke//60}m",  callback_data="cust:set_revoke"),
         InlineKeyboardButton(f"🗑 Delete: {delete//60}m", callback_data="cust:set_delete")],
        [InlineKeyboardButton("◀️ Back", callback_data="cust:main")],
    ])
    await query.edit_message_text(
        f"<b>⏱ Timing Settings</b>\n\n"
        f"<b>Revoke Time:</b> <code>{revoke}s</code> ({revoke//60} minutes)\n"
        f"<i>How long before invite links are auto-revoked</i>\n\n"
        f"<b>Delete Time:</b> <code>{delete}s</code> ({delete//60} minutes)\n"
        f"<i>How long before link messages are auto-deleted</i>",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_revoke$") & cq_owner_or_admin)
async def cb_cust_set_revoke_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_revoke"}
    await query.edit_message_text(
        "<b>⏱ Set Revoke Time</b>\n\n"
        "Send seconds or use format: <code>30M</code>, <code>1H</code>, <code>1H 30M</code>\n\n"
        "Default: <code>1800</code> (30 min)",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:timing")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_delete$") & cq_owner_or_admin)
async def cb_cust_set_delete_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_delete"}
    await query.edit_message_text(
        "<b>🗑 Set Delete Time</b>\n\n"
        "Send seconds or use format: <code>29M</code>, <code>1H</code>\n\n"
        "Default: <code>1740</code> (29 min)",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:timing")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


# ═══════════════════════════════════════════════════════════════
# GLOBAL FSUB  (unified — channels stored in FSub Sets, Set 01)
# ═══════════════════════════════════════════════════════════════

async def _get_flat_set_channels() -> list:
    """Return all fsub channels as a flat list with set_id included."""
    sets = await get_all_fsub_sets()
    flat = []
    for s in sets:
        for ch in s.get("channels", []):
            flat.append({
                "set_id":       s["set_id"],
                "channel_id":   ch["channel_id"],
                "request_mode": ch.get("request_mode", False),
            })
    return flat


async def _fsub_panel(client, target, edit=False):
    fsub_on  = await is_fsub_enabled()
    flat_chs = await _get_flat_set_channels()

    lines = []
    for entry in flat_chs:
        ch_id = entry["channel_id"]
        req   = entry["request_mode"]
        sid   = entry["set_id"]
        try:
            chat = await client.get_chat(ch_id)
            name = chat.title[:20]
        except Exception:
            name = str(ch_id)
        lines.append(
            f"{'📨' if req else '🌐'} <b>Set{sid:02d}</b> — {name} (<code>{ch_id}</code>)")

    ch_list = "\n".join(lines) if lines else "<i>No channels set — use ➕ to add one</i>"

    btn_rows = [
        [InlineKeyboardButton(
            "🛡 Disable Global FSub" if fsub_on else "🛡 Enable Global FSub",
            callback_data="cust:toggle_fsub")],
        [InlineKeyboardButton("➕ Add to Set 01",  callback_data="cust:add_fsub_ch"),
         InlineKeyboardButton("📝 FSub Message",   callback_data="cust:set_fsub_msg")],
        [InlineKeyboardButton("📋 Manage All Sets", callback_data="fss:main")],
    ]
    for entry in flat_chs:
        ch_id = entry["channel_id"]
        req   = entry["request_mode"]
        sid   = entry["set_id"]
        try:
            chat = await client.get_chat(ch_id)
            name = chat.title[:13]
        except Exception:
            name = str(ch_id)[:13]
        btn_rows.append([
            InlineKeyboardButton(
                f"{'📨→🌐' if req else '🌐→📨'} {name}",
                callback_data=f"cust:fss_mode:{sid}:{ch_id}"),
            InlineKeyboardButton(
                f"🗑 {name}",
                callback_data=f"cust:fss_remove:{sid}:{ch_id}"),
        ])
    btn_rows.append([InlineKeyboardButton("◀️ Back", callback_data="cust:main")])

    text = (
        f"<b>🛡 Global FSub Settings</b>\n\n"
        f"<b>Status:</b> {'🟢 ENABLED' if fsub_on else '🔴 DISABLED'}\n\n"
        f"<b>Channels ({len(flat_chs)}):</b>\n{ch_list}"
    )
    fn = target.edit_text if edit else target.reply_text
    await fn(text, reply_markup=InlineKeyboardMarkup(btn_rows), parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex("^cust:fsub$") & cq_owner_or_admin)
async def cb_cust_fsub(client, query: CallbackQuery):
    await _fsub_panel(client, query.message, edit=True)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:toggle_fsub$") & cq_owner_or_admin)
async def cb_cust_toggle_fsub(client, query: CallbackQuery):
    current = await is_fsub_enabled()
    await set_fsub_enabled(not current)
    await query.answer(
        f"Global FSub {'ENABLED 🟢' if not current else 'DISABLED 🔴'}!",
        show_alert=True)
    await _fsub_panel(client, query.message, edit=True)


@Bot.on_callback_query(filters.regex("^cust:add_fsub_ch$") & cq_owner_or_admin)
async def cb_cust_add_fsub_ch_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "add_fsub_ch"}
    await query.edit_message_text(
        "<b>➕ Add FSub Channel → Set 01</b>\n\n"
        "Forward any message from the channel, OR send the channel ID / @username.\n\n"
        "<i>The channel will be added to Set 01. Use 📋 Manage All Sets to "
        "create additional sets or move channels between sets.</i>",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:fsub")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^cust:set_fsub_msg$") & cq_owner_or_admin)
async def cb_cust_set_fsub_msg_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _cust_sessions[uid] = {"step": "set_fsub_msg"}
    current = await get_fsub_message()
    await query.edit_message_text(
        f"<b>📝 Set FSub Message</b>\n\n"
        f"<b>Placeholders:</b> <code>{{first}}</code>, <code>{{mention}}</code>, <code>{{id}}</code>\n\n"
        f"<b>Current:</b>\n<code>{_trunc(current, 200)}</code>\n\nSend the new message:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cust:fsub")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^cust:fss_mode:(\d+):(-?\d+)$") & cq_owner_or_admin)
async def cb_cust_fss_mode(client, query: CallbackQuery):
    parts  = query.data.split(":")
    sid    = int(parts[2])
    ch_id  = int(parts[3])
    s_doc  = await get_fsub_set(sid)
    if not s_doc:
        await query.answer("Set not found!", show_alert=True)
        return
    channels = s_doc.get("channels", [])
    new_mode = None
    for ch in channels:
        if ch["channel_id"] == ch_id:
            new_mode = not ch.get("request_mode", False)
            ch["request_mode"] = new_mode
            break
    if new_mode is None:
        await query.answer("Channel not found in set!", show_alert=True)
        return
    await save_fsub_set(sid, channels, s_doc.get("limit", 3))
    await query.answer(
        f"Mode → {'📨 Request' if new_mode else '🌐 Normal'}!", show_alert=True)
    await _fsub_panel(client, query.message, edit=True)


@Bot.on_callback_query(filters.regex(r"^cust:fss_remove:(\d+):(-?\d+)$") & cq_owner_or_admin)
async def cb_cust_fss_remove(client, query: CallbackQuery):
    parts    = query.data.split(":")
    sid      = int(parts[2])
    ch_id    = int(parts[3])
    s_doc    = await get_fsub_set(sid)
    if not s_doc:
        await query.answer("Set not found!", show_alert=True)
        return
    channels = [c for c in s_doc.get("channels", []) if c["channel_id"] != ch_id]
    await save_fsub_set(sid, channels, s_doc.get("limit", 3))
    await query.answer("✅ Channel removed from set!", show_alert=True)
    await _fsub_panel(client, query.message, edit=True)


@Bot.on_callback_query(filters.regex(r"^cust:fss_add_mode:(req|norm):(-?\d+)$") & cq_owner_or_admin)
async def cb_cust_fss_add_mode(client, query: CallbackQuery):
    parts    = query.data.split(":")
    req_mode = (parts[2] == "req")
    ch_id    = int(parts[3])
    uid      = query.from_user.id

    s_doc    = await get_fsub_set(1)
    channels = s_doc.get("channels", []) if s_doc else []
    limit    = s_doc.get("limit", 3) if s_doc else 3

    if any(c["channel_id"] == ch_id for c in channels):
        await query.answer("⚠️ Channel already in Set 01!", show_alert=True)
        _cust_sessions.pop(uid, None)
        await _fsub_panel(client, query.message, edit=True)
        return

    channels.append({"channel_id": ch_id, "request_mode": req_mode})
    await save_fsub_set(1, channels, limit)
    _cust_sessions.pop(uid, None)
    await query.answer(
        f"✅ Added to Set 01 as {'📨 Request' if req_mode else '🌐 Normal'}!",
        show_alert=True)
    await _fsub_panel(client, query.message, edit=True)


# ═══════════════════════════════════════════════════════════════
# UNIFIED TEXT INPUT HANDLER  (group=-1 → runs before broadcast.py collect_batch)
# ═══════════════════════════════════════════════════════════════

_CUST_EXCLUDE = [
    "start", "help", "about", "info", "admins", "addadmin", "deladmin",
    "addchannel", "delchannel", "channels", "search", "customize",
    "genlink", "fsublink", "broadcast", "batchbroadcast", "done", "ddone",
    "pbroadcast", "dbroadcast", "batchdbroadcast", "delbroadcast", "cancel",
    "delallbroadcast", "allbroadcastclear", "delallpbroadcast",
    "clearpendingdbroadcast", "safebroadcasts", "deletesafebroadcast",
    "clicks", "click", "stats", "status", "ping", "cmds",
    "fsubsets", "settime", "default_limit", "approveoff", "approveon", "backup",
    "fsubchannels", "update", "cleandb",
]


@Bot.on_message(
    filters.private & is_owner_or_admin & ~filters.command(_CUST_EXCLUDE),
    group=-3
)
async def handle_customize_input(client, message: Message):
    uid     = message.from_user.id
    session = _cust_sessions.get(uid)
    if not session:
        return

    # Any command (even unknown) clears the session so the user isn't trapped
    if message.text and message.text.lstrip().startswith("/"):
        _cust_sessions.pop(uid, None)
        return

    step = session.get("step")
    text = (message.text or message.caption or "").strip()

    try:
        if step == "set_caption":
            if not text:
                await message.reply_text("❌ Please send the caption text.", parse_mode=ParseMode.HTML)
            else:
                await set_custom_caption(text)
                _cust_sessions.pop(uid, None)
                await message.reply_text("✅ Caption updated successfully!", parse_mode=ParseMode.HTML)

        elif step == "set_image":
            url = (message.text or message.caption or "").strip()
            if not url:
                await message.reply_text(
                    "❌ Please send a valid image URL (e.g. https://i.imgur.com/xyz.jpg).",
                    parse_mode=ParseMode.HTML)
            else:
                try:
                    await set_custom_image(url)
                    _cust_sessions.pop(uid, None)
                    await message.reply_text("✅ Image URL saved!", parse_mode=ParseMode.HTML)
                except Exception as _img_err:
                    await message.reply_text(
                        f"❌ Failed to save image: <code>{_img_err}</code>",
                        parse_mode=ParseMode.HTML)

        elif step == "set_btn_text":
            if not text:
                await message.reply_text("❌ Please send the button text.", parse_mode=ParseMode.HTML)
            else:
                await set_custom_button_text(text)
                _cust_sessions.pop(uid, None)
                await message.reply_text("✅ Button text updated!", parse_mode=ParseMode.HTML)

        elif step == "set_secondmsg":
            if not text:
                await message.reply_text("❌ Please send the message text.", parse_mode=ParseMode.HTML)
            else:
                await set_second_message(text)
                _cust_sessions.pop(uid, None)
                await message.reply_text("✅ Second message updated!", parse_mode=ParseMode.HTML)

        elif step == "set_revoke":
            secs = int(text) if text.isdigit() else parse_time_string(text)
            if secs <= 0:
                await message.reply_text("❌ Invalid time. Use seconds (e.g. 1800) or 30M / 1H.", parse_mode=ParseMode.HTML)
            else:
                await set_revoke_time(secs)
                _cust_sessions.pop(uid, None)
                await message.reply_text(
                    f"✅ Revoke time set to <b>{secs}s</b> ({secs//60} min).",
                    parse_mode=ParseMode.HTML)

        elif step == "set_delete":
            secs = int(text) if text.isdigit() else parse_time_string(text)
            if secs <= 0:
                await message.reply_text("❌ Invalid time. Use seconds (e.g. 1740) or 29M / 1H.", parse_mode=ParseMode.HTML)
            else:
                await set_delete_time(secs)
                _cust_sessions.pop(uid, None)
                await message.reply_text(
                    f"✅ Delete time set to <b>{secs}s</b> ({secs//60} min).",
                    parse_mode=ParseMode.HTML)

        elif step == "set_fsub_msg":
            if not text:
                await message.reply_text("❌ Please send the FSub message text.", parse_mode=ParseMode.HTML)
            else:
                await set_fsub_message(text)
                _cust_sessions.pop(uid, None)
                await message.reply_text("✅ FSub message updated!", parse_mode=ParseMode.HTML)

        elif step == "add_fsub_ch":
            ch_id = None
            # Forwarded channel message → grab the channel directly
            if message.forward_from_chat:
                ch_id = message.forward_from_chat.id
            if ch_id is None:
                raw = (message.text or message.caption or "").strip()
                if raw:
                    try:
                        ch_id = int(raw)
                    except ValueError:
                        try:
                            ref  = raw if raw.startswith("@") else f"@{raw}"
                            chat = await client.get_chat(ref)
                            ch_id = chat.id
                        except Exception:
                            pass

            if not ch_id:
                await message.reply_text(
                    "❌ Could not find that channel. Forward a message from it, or send its ID / @username.",
                    parse_mode=ParseMode.HTML)
            else:
                try:
                    chat = await client.get_chat(ch_id)
                    name = chat.title
                except Exception:
                    name = str(ch_id)
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📨 Request Mode", callback_data=f"cust:fss_add_mode:req:{ch_id}"),
                     InlineKeyboardButton("🌐 Normal Join",  callback_data=f"cust:fss_add_mode:norm:{ch_id}")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cust:fsub")],
                ])
                await message.reply_text(
                    f"<b>Channel: {name}</b> (<code>{ch_id}</code>)\n\n"
                    f"Choose the join mode for this FSub channel:\n"
                    f"📨 <b>Request</b> — user sends a join request, admin approves\n"
                    f"🌐 <b>Normal</b> — user joins directly without approval",
                    reply_markup=markup, parse_mode=ParseMode.HTML)
                raise StopPropagation  # Keep session until mode chosen

    except StopPropagation:
        raise
    except Exception as e:
        await message.reply_text(f"❌ Error: <code>{e}</code>", parse_mode=ParseMode.HTML)

    raise StopPropagation
