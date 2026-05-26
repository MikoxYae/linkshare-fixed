# plugins/fsubsets.py — FSub Sets management (FIXED: consolidated handlers, StopPropagation)
import asyncio
import time as _time
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram import StopPropagation
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from miko import Bot
from database.database import (
    get_all_fsub_sets, get_fsub_set, save_fsub_set, delete_fsub_set,
    get_next_set_id, get_fsub_set_config, set_fsub_set_config,
    record_set_pass, is_set_pass_valid, get_set_pass_time,
)
from helper_func import is_owner_or_admin, cq_owner_or_admin, parse_time_string

MAX_CHANNELS_PER_SET = 15
_set_builder: dict = {}          # uid -> {session data, "created_at": float}
_SET_BUILDER_TTL = 600             # 10-minute session expiry
_fsub_invite_cache: dict = {}    # (ch_id, req_mode) -> {"link": str, "expires_at": float}
_FSUB_LINK_TTL = 600             # 10-minute invite links for force-sub checks

# Exposed for cross-plugin session checks
def has_fsubset_session(uid: int) -> bool:
    _cleanup_expired_sessions()
    return uid in _set_builder


def _cleanup_expired_sessions():
    """Remove stale _set_builder sessions older than _SET_BUILDER_TTL."""
    now = _time.time()
    expired = [uid for uid, s in _set_builder.items() if now - s.get("created_at", now) > _SET_BUILDER_TTL]
    for uid in expired:
        _set_builder.pop(uid, None)


# ── Helper: build set menu ────────────────────────────────────────────────────

async def _set_main_menu(client, target, edit=False):
    sets = await get_all_fsub_sets()
    cfg  = await get_fsub_set_config()

    btn_rows = []
    for s in sets:
        sid   = s["set_id"]
        limit = s.get("limit", cfg["default_limit"])
        count = len(s.get("channels", []))
        btn_rows.append([InlineKeyboardButton(
            f"Set {sid:02d}  [{count}/{limit} ch]",
            callback_data=f"fss:set:{sid}")])

    btn_rows.append([
        InlineKeyboardButton("➕ Add New Set",   callback_data="fss:addset"),
        InlineKeyboardButton("⚙️ Default Limit", callback_data="fss:setlimit"),
    ])
    btn_rows.append([
        InlineKeyboardButton(f"⏱ Grace Time: {cfg['set_time']//60}m", callback_data="fss:settime"),
        InlineKeyboardButton("✖️ Close", callback_data="close"),
    ])

    text = (
        "<b>╔══════════════════════╗\n"
        "║  🛡 FORCE SUB SETS   ║\n"
        "╚══════════════════════╝</b>\n\n"
        f"<b>Sets:</b> {len(sets)}\n"
        f"<b>Default channels/set:</b> {cfg['default_limit']}\n"
        f"<b>Pass grace time:</b> {cfg['set_time']//60} minutes\n\n"
        "Tap a set to manage its channels."
    )
    markup = InlineKeyboardMarkup(btn_rows)
    fn = target.edit_text if edit else target.reply_text
    await fn(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("fsubsets") & is_owner_or_admin)
async def cmd_fsubsets(client, message: Message):
    await _set_main_menu(client, message)


@Bot.on_callback_query(filters.regex("^fss:main$") & cq_owner_or_admin)
async def cb_fss_main(client, query: CallbackQuery):
    await _set_main_menu(client, query.message, edit=True)
    await query.answer()


# ── Add new set ───────────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^fss:addset$") & cq_owner_or_admin)
async def cb_fss_addset(client, query: CallbackQuery):
    cfg    = await get_fsub_set_config()
    new_id = await get_next_set_id()
    await save_fsub_set(new_id, [], cfg["default_limit"])
    await query.answer(f"✅ Set {new_id:02d} created!", show_alert=True)
    await _set_main_menu(client, query.message, edit=True)


# ── View/manage a set ─────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^fss:set:(\d+)$") & cq_owner_or_admin)
async def cb_fss_set(client, query: CallbackQuery):
    set_id  = int(query.data.split(":")[2])
    set_doc = await get_fsub_set(set_id)
    if not set_doc:
        return await query.answer("Set not found!", show_alert=True)
    cfg      = await get_fsub_set_config()
    limit    = set_doc.get("limit", cfg["default_limit"])
    channels = set_doc.get("channels", [])

    lines    = [f"<b>Set {set_id:02d}</b>  ({len(channels)}/{limit} channels)\n"]
    btn_rows = []

    for ch in channels:
        ch_id    = ch["channel_id"]
        req_mode = ch.get("request_mode", False)
        mode_icon = "📨" if req_mode else "⚡"
        try:
            chat = await client.get_chat(ch_id)
            name = chat.title[:22]
        except Exception:
            name = str(ch_id)
        btn_rows.append([InlineKeyboardButton(
            f"{mode_icon} {name}", callback_data=f"fss:ch:{set_id}:{ch_id}")])

    if len(channels) < limit:
        btn_rows.append([InlineKeyboardButton("➕ Add Channel", callback_data=f"fss:addch:{set_id}")])

    btn_rows.append([
        InlineKeyboardButton(f"📏 Limit: {limit}", callback_data=f"fss:chlimit:{set_id}"),
        InlineKeyboardButton("🗑 Delete Set",       callback_data=f"fss:delset:{set_id}"),
    ])
    btn_rows.append([InlineKeyboardButton("◀️ Back", callback_data="fss:main")])

    await query.edit_message_text(
        "<b>╔═══════════════════╗\n"
        "║  🛡 SET SETTINGS  ║\n"
        "╚═══════════════════╝</b>\n\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(btn_rows),
        parse_mode=ParseMode.HTML)
    await query.answer()


# ── Add channel to set ────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^fss:addch:(\d+)$") & cq_owner_or_admin)
async def cb_fss_addch(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    uid    = query.from_user.id
    _set_builder[uid] = {"set_id": set_id, "step": "waiting_channel", "created_at": _time.time()}
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"fss:set:{set_id}")]])
    await query.edit_message_text(
        f"<b>➕ Add Channel to Set {set_id:02d}</b>\n\n"
        "• Forward any message from the channel, OR\n"
        "• Send the channel ID directly (e.g. <code>-1001234567890</code>)",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^fss:mode:(req|dir):(\d+)$") & cq_owner_or_admin)
async def cb_fss_mode(client, query: CallbackQuery):
    parts    = query.data.split(":")
    mode_str = parts[2]
    uid      = int(parts[3])
    session  = _set_builder.pop(uid, None)
    if not session:
        return await query.answer("Session expired. Please try again.", show_alert=True)

    ch_id    = session.get("pending_ch_id")
    req_mode = (mode_str == "req")
    set_id   = session["set_id"]

    if not ch_id:
        return await query.answer("No channel pending. Please try again.", show_alert=True)

    set_doc  = await get_fsub_set(set_id) or {"set_id": set_id, "channels": [], "limit": 3}
    channels = set_doc.get("channels", [])
    if any(c["channel_id"] == ch_id for c in channels):
        return await query.answer("Channel already in this set!", show_alert=True)
    if len(channels) >= MAX_CHANNELS_PER_SET:
        return await query.answer("Maximum 15 channels per set reached!", show_alert=True)

    channels.append({"channel_id": ch_id, "request_mode": req_mode})
    await save_fsub_set(set_id, channels, set_doc.get("limit", 3))

    mode_label = "📨 Request" if req_mode else "⚡ Direct"
    await query.answer(f"✅ Channel added! [{mode_label}]", show_alert=True)
    query.data = f"fss:set:{set_id}"
    await cb_fss_set(client, query)


# ── Channel settings in set ───────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^fss:ch:(\d+):(-?\d+)$") & cq_owner_or_admin)
async def cb_fss_ch(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    ch_id  = int(query.data.split(":")[3])
    set_doc= await get_fsub_set(set_id)
    if not set_doc:
        return await query.answer("Set not found!", show_alert=True)
    ch_cfg = next((c for c in set_doc["channels"] if c["channel_id"] == ch_id), None)
    if not ch_cfg:
        return await query.answer("Channel not found in set!", show_alert=True)

    req_mode   = ch_cfg.get("request_mode", False)
    try:
        chat = await client.get_chat(ch_id)
        name = chat.title
    except Exception:
        name = str(ch_id)

    mode_icon  = "📨 Request" if req_mode else "⚡ Direct"
    toggle_lbl = "Switch to ⚡ Direct" if req_mode else "Switch to 📨 Request"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_lbl, callback_data=f"fss:chtoggle:{set_id}:{ch_id}")],
        [InlineKeyboardButton("🗑 Remove Channel", callback_data=f"fss:chremove:{set_id}:{ch_id}")],
        [InlineKeyboardButton("◀️ Back", callback_data=f"fss:set:{set_id}")],
    ])
    await query.edit_message_text(
        f"<b>Channel:</b> {name}\n"
        f"<b>ID:</b> <code>{ch_id}</code>\n"
        f"<b>Mode:</b> {mode_icon}",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^fss:chtoggle:(\d+):(-?\d+)$") & cq_owner_or_admin)
async def cb_fss_chtoggle(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    ch_id  = int(query.data.split(":")[3])
    set_doc= await get_fsub_set(set_id)
    if not set_doc:
        return await query.answer("Set not found!", show_alert=True)
    channels = set_doc["channels"]
    for c in channels:
        if c["channel_id"] == ch_id:
            c["request_mode"] = not c.get("request_mode", False)
            break
    await save_fsub_set(set_id, channels, set_doc.get("limit", 3))
    await query.answer("✅ Mode toggled!", show_alert=True)
    query.data = f"fss:ch:{set_id}:{ch_id}"
    await cb_fss_ch(client, query)


@Bot.on_callback_query(filters.regex(r"^fss:chremove:(\d+):(-?\d+)$") & cq_owner_or_admin)
async def cb_fss_chremove(client, query: CallbackQuery):
    set_id   = int(query.data.split(":")[2])
    ch_id    = int(query.data.split(":")[3])
    set_doc  = await get_fsub_set(set_id)
    if not set_doc:
        return await query.answer("Set not found!", show_alert=True)
    channels = [c for c in set_doc["channels"] if c["channel_id"] != ch_id]
    await save_fsub_set(set_id, channels, set_doc.get("limit", 3))
    await query.answer("✅ Channel removed!", show_alert=True)
    query.data = f"fss:set:{set_id}"
    await cb_fss_set(client, query)


# ── Delete set ────────────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^fss:delset:(\d+)$") & cq_owner_or_admin)
async def cb_fss_delset(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"fss:delset_do:{set_id}"),
         InlineKeyboardButton("❌ Cancel",      callback_data=f"fss:set:{set_id}")],
    ])
    await query.edit_message_text(
        f"<b>⚠️ Delete Set {set_id:02d}?</b>\n\nThis cannot be undone.",
        reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^fss:delset_do:(\d+)$") & cq_owner_or_admin)
async def cb_fss_delset_do(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    await delete_fsub_set(set_id)
    await query.answer("✅ Set deleted!", show_alert=True)
    await _set_main_menu(client, query.message, edit=True)


# ── Per-set channel limit ─────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex(r"^fss:chlimit:(\d+)$") & cq_owner_or_admin)
async def cb_fss_chlimit(client, query: CallbackQuery):
    set_id  = int(query.data.split(":")[2])
    set_doc = await get_fsub_set(set_id)
    cur     = set_doc.get("limit", 3) if set_doc else 3
    btns    = []
    row     = []
    for n in range(1, 8):
        icon = "🟢" if n == cur else ""
        row.append(InlineKeyboardButton(f"{icon}{n}", callback_data=f"fss:setlim_do:{set_id}:{n}"))
        if len(row) == 4:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([
        InlineKeyboardButton("✏️ Custom",  callback_data=f"fss:setlim_custom:{set_id}"),
        InlineKeyboardButton("◀️ Back",    callback_data=f"fss:set:{set_id}"),
    ])
    await query.edit_message_text(
        f"<b>📏 Channel limit for Set {set_id:02d}</b>\nCurrent: {cur}",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^fss:setlim_do:(\d+):(\d+)$") & cq_owner_or_admin)
async def cb_fss_setlim_do(client, query: CallbackQuery):
    set_id = int(query.data.split(":")[2])
    limit  = int(query.data.split(":")[3])
    set_doc= await get_fsub_set(set_id)
    if set_doc:
        await save_fsub_set(set_id, set_doc.get("channels", []), limit)
    await query.answer(f"✅ Limit set to {limit}!", show_alert=True)
    query.data = f"fss:set:{set_id}"
    await cb_fss_set(client, query)


@Bot.on_callback_query(filters.regex(r"^fss:setlim_custom:(\d+)$") & cq_owner_or_admin)
async def cb_fss_setlim_custom(client, query: CallbackQuery):
    uid    = query.from_user.id
    set_id = int(query.data.split(":")[2])
    _set_builder[uid] = {"step": "waiting_limit", "set_id": set_id, "created_at": _time.time()}
    await query.edit_message_text(
        f"<b>✏️ Custom limit for Set {set_id:02d}</b>\n\nSend a number (1–{MAX_CHANNELS_PER_SET}):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data=f"fss:chlimit:{set_id}")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


# ── Global default limit ──────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^fss:setlimit$") & cq_owner_or_admin)
async def cb_fss_global_limit(client, query: CallbackQuery):
    cfg  = await get_fsub_set_config()
    cur  = cfg["default_limit"]
    btns = []
    row  = []
    for n in range(1, 8):
        icon = "🟢" if n == cur else ""
        row.append(InlineKeyboardButton(f"{icon}{n}", callback_data=f"fss:glim_do:{n}"))
        if len(row) == 4:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton("◀️ Back", callback_data="fss:main")])
    await query.edit_message_text(
        f"<b>📏 Default Channels Per Set</b>\nCurrent: {cur}",
        reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^fss:glim_do:(\d+)$") & cq_owner_or_admin)
async def cb_fss_glim_do(client, query: CallbackQuery):
    n = int(query.data.split(":")[2])
    await set_fsub_set_config(default_limit=n)
    await query.answer(f"✅ Default limit set to {n}!", show_alert=True)
    await _set_main_menu(client, query.message, edit=True)


@Bot.on_message(filters.command("default_limit") & is_owner_or_admin)
async def cmd_default_limit(client, message: Message):
    if len(message.command) < 2 or not message.command[1].isdigit():
        return await message.reply_text(
            "Usage: <code>/default_limit [number]</code>", parse_mode=ParseMode.HTML)
    n = int(message.command[1])
    if n < 1 or n > MAX_CHANNELS_PER_SET:
        return await message.reply_text(
            f"❌ Must be between 1 and {MAX_CHANNELS_PER_SET}.", parse_mode=ParseMode.HTML)
    await set_fsub_set_config(default_limit=n)
    await message.reply_text(f"✅ Default set limit updated to {n}.", parse_mode=ParseMode.HTML)


# ── /settime ──────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("settime") & is_owner_or_admin)
async def cmd_settime(client, message: Message):
    if len(message.command) < 2:
        cfg = await get_fsub_set_config()
        return await message.reply_text(
            f"<b>Current set grace time:</b> {cfg['set_time']//60} minutes\n\n"
            "Usage: <code>/settime 30M</code>  or  <code>/settime 1H</code>",
            parse_mode=ParseMode.HTML)
    secs = parse_time_string(" ".join(message.command[1:]))
    if secs <= 0:
        return await message.reply_text(
            "❌ Invalid time. Example: <code>30M</code>, <code>1H</code>", parse_mode=ParseMode.HTML)
    await set_fsub_set_config(set_time=secs)
    await message.reply_text(
        f"✅ Set grace time updated to <b>{secs//60} minutes</b>.", parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex("^fss:settime$") & cq_owner_or_admin)
async def cb_fss_settime_prompt(client, query: CallbackQuery):
    uid = query.from_user.id
    _set_builder[uid] = {"step": "waiting_settime"}
    await query.edit_message_text(
        "<b>⏱ Set Grace Time</b>\n\n"
        "Send the time (e.g. <code>30M</code>, <code>1H</code>).\n"
        "After a user passes all channels in a set, they won't be checked again for this duration.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Cancel", callback_data="fss:main")
        ]]),
        parse_mode=ParseMode.HTML)
    await query.answer()


# ═══════════════════════════════════════════════════════════════
# UNIFIED TEXT/MESSAGE INPUT HANDLER
# group=-1 → runs before broadcast.py collect_batch (group=0)
# Handles: waiting_channel, waiting_limit, waiting_settime
# ═══════════════════════════════════════════════════════════════

_FSS_EXCLUDE = [
    "start", "help", "about", "info", "admins", "addadmin", "deladmin",
    "addchannel", "delchannel", "channels", "search", "customize",
    "genlink", "fsublink", "broadcast", "batchbroadcast", "done", "ddone",
    "pbroadcast", "dbroadcast", "batchdbroadcast", "delbroadcast", "cancel",
    "delallbroadcast", "allbroadcastclear", "delallpbroadcast",
    "clearpendingdbroadcast", "safebroadcasts", "deletesafebroadcast",
    "clicks", "click", "stats", "status", "ping", "cmds",
    "fsubsets", "settime", "default_limit", "approveoff", "approveon", "backup",
    "fsubchannels", "fsublinkchannels", "update", "cleandb",
    "req", "unreq", "reqall", "unreqall", "reqs",
]


@Bot.on_message(
    filters.private & is_owner_or_admin & ~filters.command(_FSS_EXCLUDE),
    group=-2
)
async def handle_fss_messages(client, message: Message):
    uid     = message.from_user.id
    session = _set_builder.get(uid)
    if not session:
        return  # Not in a session, let other handlers run

    step = session.get("step")

    try:
        if step == "waiting_channel":
            await _process_fss_channel(client, message, uid, session)

        elif step == "waiting_limit":
            await _process_fss_limit(client, message, uid)

        elif step == "waiting_settime":
            await _process_fss_settime(client, message, uid)

    except StopPropagation:
        raise
    except Exception as e:
        await message.reply_text(f"❌ Error: <code>{e}</code>", parse_mode=ParseMode.HTML)

    raise StopPropagation


async def _process_fss_channel(client, message: Message, uid: int, session: dict):
    """Handle channel ID input for fsubset channel addition."""
    ch_id = None
    # Try forwarded message first
    if message.forward_from_chat:
        ch_id = message.forward_from_chat.id
    elif message.text:
        txt = message.text.strip()
        # Silently ignore messages that don't look like a channel identifier.
        # This prevents spam when admin accidentally sends a regular message
        # while an fsubset session is still open.
        looks_like_channel = (
            txt.lstrip("-").isdigit() or
            txt.startswith("@") or
            txt.startswith("https://t.me/")
        )
        if not looks_like_channel:
            return  # Keep session alive, don't send an error
        try:
            ch_id = int(txt)
        except ValueError:
            try:
                ref  = txt if txt.startswith("@") else f"@{txt}"
                chat = await client.get_chat(ref)
                ch_id = chat.id
            except Exception:
                pass

    if not ch_id:
        await message.reply_text(
            "❌ Could not resolve that channel.\n"
            "Forward a message from the channel, or send its ID (e.g. <code>-1001234567890</code>).",
            parse_mode=ParseMode.HTML)
        return  # Keep session alive

    # Verify bot admin status
    try:
        me  = await client.get_me()
        mem = await client.get_chat_member(ch_id, me.id)
        has_invite = getattr(mem.privileges, "can_invite_users", False)
        if mem.status.name not in ("ADMINISTRATOR", "CREATOR") or not has_invite:
            await message.reply_text(
                "❌ I need to be an <b>admin</b> with <b>Invite Users</b> permission in that channel.",
                parse_mode=ParseMode.HTML)
            return
        chat = await client.get_chat(ch_id)
        name = chat.title
    except Exception as e:
        await message.reply_text(
            f"❌ Could not verify permissions: <code>{e}</code>", parse_mode=ParseMode.HTML)
        return

    # Store pending channel and ask for mode
    session["pending_ch_id"]   = ch_id
    session["pending_ch_name"] = name
    session["step"]            = "waiting_mode"

    set_id = session["set_id"]
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 Request Mode (admin approves)", callback_data=f"fss:mode:req:{uid}"),
         InlineKeyboardButton("⚡ Direct Join (instant)",         callback_data=f"fss:mode:dir:{uid}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"fss:set:{set_id}")],
    ])
    await message.reply_text(
        f"<b>Channel: {name}</b> (<code>{ch_id}</code>)\n\nChoose the join mode:",
        reply_markup=markup, parse_mode=ParseMode.HTML)


async def _process_fss_limit(client, message: Message, uid: int):
    """Handle numeric limit input for per-set channel limit."""
    session = _set_builder.pop(uid, None)
    if not session:
        return
    txt = (message.text or "").strip()
    if not txt.isdigit():
        _set_builder[uid] = session  # Restore session
        await message.reply_text("❌ Please send a valid number.", parse_mode=ParseMode.HTML)
        return
    n = int(txt)
    if n < 1 or n > MAX_CHANNELS_PER_SET:
        _set_builder[uid] = session  # Restore session
        await message.reply_text(
            f"❌ Number must be between 1 and {MAX_CHANNELS_PER_SET}.", parse_mode=ParseMode.HTML)
        return
    set_id  = session["set_id"]
    set_doc = await get_fsub_set(set_id)
    if set_doc:
        await save_fsub_set(set_id, set_doc.get("channels", []), n)
    await message.reply_text(
        f"✅ Channel limit for Set {set_id:02d} set to <b>{n}</b>.", parse_mode=ParseMode.HTML)


async def _process_fss_settime(client, message: Message, uid: int):
    """Handle time input for set grace period."""
    _set_builder.pop(uid, None)
    txt  = (message.text or "").strip()
    secs = parse_time_string(txt)
    if secs <= 0:
        await message.reply_text(
            "❌ Invalid time format. Use e.g. <code>30M</code>, <code>1H</code>",
            parse_mode=ParseMode.HTML)
        return
    await set_fsub_set_config(set_time=secs)
    await message.reply_text(
        f"✅ Grace time updated to <b>{secs//60} minutes</b>.", parse_mode=ParseMode.HTML)


# ═══════════════════════════════════════════════════════════════
# Invite-link cache helper for force-sub set channels
# ═══════════════════════════════════════════════════════════════

async def _get_fsub_invite_link(client, ch_id: int, req_mode: bool):
    """
    Returns a valid Telegram invite link string, or None on failure.

    Caches links for _FSUB_LINK_TTL seconds.  If the cached link has
    less than 60 seconds left it is treated as expired and a fresh one
    is created.  Public (@username) channels are returned directly and
    are not cached (they never expire).
    """
    now = _time.time()
    cache_key = (ch_id, req_mode)

    cached = _fsub_invite_cache.get(cache_key)
    if cached and cached["expires_at"] - now > 60:
        return cached["link"]

    try:
        chat = await client.get_chat(ch_id)
        if not req_mode and chat.username:
            # Public channel — @username link never expires, no cache needed
            return f"https://t.me/{chat.username}"

        inv = await client.create_chat_invite_link(
            chat_id=ch_id,
            creates_join_request=req_mode,
            # ↓ Must be a datetime object; plain int causes BadRequest
            expire_date=datetime.now(tz=timezone.utc) + timedelta(seconds=_FSUB_LINK_TTL),
        )
        link = inv.invite_link or None      # coerce empty string → None
        if link:
            _fsub_invite_cache[cache_key] = {
                "link": link,
                "expires_at": now + _FSUB_LINK_TTL,
            }
        return link
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# RUNTIME: check_fsub_sets (called from start.py)
# ═══════════════════════════════════════════════════════════════

async def check_fsub_sets(client, user_id: int, token_key: str) -> tuple:
    """
    Returns (all_passed: bool, buttons: list, completed_set_id: int).

    Cascade rules (sets processed in order — Set 01, Set 02, …):

      1. Grace active for this set
         → PASS immediately. Deliver link.

      2. Grace expired OR never completed
         → RE-CHECK membership for ALL channels in this set right now.

         2a. Some channels unjoined / no pending request
             → Show ALL unjoined channels as join buttons. Return False.

         2b. All channels joined, pass_time = None (first time completing)
             → Return (True, [], set_id) — caller records pass + starts grace.

         2c. All channels joined, pass_time already recorded (re-verified)
             → Advance to next set silently.

    When all sets exhausted → Return (True, [], 0).

    KEY FIXES vs old version:
      - leave detection: after grace expires we always re-check membership
        so users who left get caught and must re-join (old code just skipped).
      - all channels shown: fallback button added even when invite link
        generation fails so no channel silently disappears.
      - no slow API iteration: removed has_pending_join_request() call
        (iterates ALL pending requests — hits Telegram limits on big channels).
        We rely only on the fast DB cache.
    """
    sets  = await get_all_fsub_sets()
    cfg   = await get_fsub_set_config()
    grace = cfg["set_time"]

    if not sets:
        return True, [], 0

    from helper_func import is_sub
    from database.database import has_join_req_cache, record_join_req_sent, clear_join_req_cache
    import asyncio as _aio

    async def _build_buttons(unjoined_channels: list) -> list:
        """Build join buttons for all unjoined channels with fallback."""
        buttons: list = []
        for ch in unjoined_channels:
            ch_id    = ch["channel_id"]
            req_mode = ch.get("request_mode", False)

            # Get channel name
            try:
                _chat    = await client.get_chat(ch_id)
                ch_title = _chat.title[:22]
            except Exception:
                ch_title = "Channel"

            icon     = "📨" if req_mode else "⚡"
            btn_text = f"{icon} Join {ch_title}"

            join_link = await _get_fsub_invite_link(client, ch_id, req_mode)
            if join_link:
                if req_mode:
                    await record_join_req_sent(user_id, ch_id)
                buttons.append([InlineKeyboardButton(btn_text, url=join_link)])
            else:
                # Link generation failed (bot not admin?) — still show button
                # so user knows which channel is required
                buttons.append([InlineKeyboardButton(f"⚠️ {btn_text}", url="https://t.me")])
        return buttons

    # ── Cascade through sets ─────────────────────────────────────────────────
    for set_doc in sets:
        set_id   = set_doc["set_id"]
        channels = set_doc.get("channels", [])

        # Rule 1 — grace is still active → pass immediately
        grace_valid = await is_set_pass_valid(user_id, "global", set_id, grace)
        if grace_valid:
            return True, [], 0

        # ── Re-check membership NOW (grace expired or first visit) ────────────
        # FIX: old code skipped sets with pass_time without re-checking,
        # allowing users who left channels to bypass force-sub after grace.
        unjoined: list = []
        for ch in channels:
            ch_id    = ch["channel_id"]
            req_mode = ch.get("request_mode", False)

            is_member = await is_sub(client, user_id, ch_id)

            if is_member:
                # Full member — clear stale request cache if any
                if req_mode:
                    _aio.create_task(clear_join_req_cache(user_id, ch_id))
                continue  # this channel is fine

            # Not a full member — for request-mode channels check DB cache
            # (cache records that WE sent them a join-request link; fast O(1) lookup)
            if req_mode and await has_join_req_cache(user_id, ch_id):
                continue  # request was sent — treat as pending/OK

            # Neither member nor pending request → must join
            unjoined.append(ch)

        if unjoined:
            # Rule 2a — some channels still unjoined → show ALL of them
            buttons = await _build_buttons(unjoined)
            return False, buttons, set_id

        # All channels in this set are joined / have pending request
        pass_time = await get_set_pass_time(user_id, "global", set_id)

        if pass_time is None:
            # Rule 2b — first time completing this set → deliver link
            return True, [], set_id
        else:
            # Rule 2c — re-verified after grace expiry → advance to next set
            continue

    # All sets exhausted (all verified) → deliver link
    return True, [], 0
