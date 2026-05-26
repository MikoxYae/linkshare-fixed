# plugins/broadcast.py — Full broadcast suite with safe broadcasts (FIXED)
import asyncio
import uuid
from datetime import datetime, timedelta

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated

from miko import Bot
from config import DATABASE_CHANNEL
from database.database import (
    full_userbase, del_user,
    save_broadcast_msgs, get_broadcast_msgs, get_last_broadcast_id,
    get_all_broadcast_ids, get_all_broadcast_docs, delete_broadcast_record,
    delete_all_broadcast_records,
    save_pbroadcast_msgs, get_all_pbroadcast_records, delete_all_pbroadcast_records,
    save_dbroadcast_msgs, get_expired_dbroadcasts, get_all_dbroadcast_records,
    delete_dbroadcast_record, delete_all_dbroadcast_records,
    save_safe_broadcast, get_all_safe_broadcasts, get_safe_broadcast,
    delete_safe_broadcast, delete_all_safe_broadcasts,
)
from helper_func import is_owner_or_admin, cq_owner_or_admin, parse_time_string


# ── Auto-delete 'pinned a message' service notifications in private chats ───

@Bot.on_message(filters.private & filters.service, group=2)
async def auto_delete_pin_service(client, message: Message):
    if message.pinned_message:
        try:
            await message.delete()
        except Exception:
            pass

_is_canceled = False
_cancel_lock = asyncio.Lock()
_batch_states:  dict = {}
_batch_dstates: dict = {}
_batch_dtimes:  dict = {}

BAR       = 20
DONE_CHR  = "●"
EMPTY_CHR = "○"


def _progress_bar(pct):
    n = int(pct * BAR)
    return DONE_CHR * n + EMPTY_CHR * (BAR - n)


def _status_text(label, total, ok, blocked, deleted, fail, pct, done=False):
    icon = "✅" if done else "⏳"
    bar  = _progress_bar(pct)
    word = "COMPLETED" if done else "IN PROGRESS"
    return (
        f"<b>{icon} BROADCAST {word}</b>\n"
        f"<b>Mode: {label}</b>\n\n"
        f"<b>[{bar}] {pct:.0%}</b>\n\n"
        f"<blockquote>"
        f"• <b>Total Users</b>:    <code>{total}</code>\n"
        f"• <b>Delivered</b>:      <code>{ok}</code>\n"
        f"• <b>Blocked</b>:        <code>{blocked}</code>\n"
        f"• <b>Deactivated</b>:    <code>{deleted}</code>\n"
        f"• <b>Failed</b>:         <code>{fail}</code>"
        f"</blockquote>"
        + ("" if done else "\n\n<i>Send /cancel to stop.</i>")
    )


async def _broadcast_to_all(client, source_msg, progress_msg, label="NORMAL",
                             do_pin=False, do_delete=False,
                             delete_delay=0, silent=False):
    global _is_canceled
    users = await full_userbase()
    total = len(users)
    ok = blocked = deleted = fail = 0
    sent_map = {}
    last_pct = 0

    for i, chat_id in enumerate(users, start=1):
        async with _cancel_lock:
            if _is_canceled:
                break
        try:
            sent = await source_msg.copy(chat_id, disable_notification=silent)
            if do_pin:
                try:
                    await client.pin_chat_message(chat_id, sent.id, both_sides=True)
                except Exception:
                    pass
            if do_delete and delete_delay > 0:
                asyncio.create_task(_auto_delete_msg(sent, delete_delay))
            sent_map[str(chat_id)] = sent.id
            ok += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                sent = await source_msg.copy(chat_id, disable_notification=silent)
                sent_map[str(chat_id)] = sent.id
                ok += 1
            except Exception:
                fail += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except InputUserDeactivated:
            await del_user(chat_id)
            deleted += 1
        except Exception:
            fail += 1

        pct = i / total
        if pct - last_pct >= 0.05 or i == total:
            try:
                await progress_msg.edit_text(
                    _status_text(label, total, ok, blocked, deleted, fail, pct),
                    parse_mode=ParseMode.HTML)
            except Exception:
                pass
            last_pct = pct

    async with _cancel_lock:
        canceled = _is_canceled

    return {
        "canceled": canceled, "total": total, "ok": ok,
        "blocked": blocked, "deleted": deleted, "fail": fail,
        "sent_map": sent_map,
    }


async def _auto_delete_msg(msg, delay):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def _log_to_db_channel(client, bc_id: str, source_msg, label: str, result: dict):
    if not DATABASE_CHANNEL:
        return
    try:
        await source_msg.forward(DATABASE_CHANNEL)
        stats = (
            f"<b>📦 Broadcast Record</b>\n"
            f"<b>ID:</b> <code>{bc_id}</code>\n"
            f"<b>Mode:</b> {label}\n"
            f"<b>Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"<b>Sent:</b> {result['ok']} / {result['total']}\n"
            f"<b>Blocked:</b> {result['blocked']}\n"
            f"<b>Failed:</b> {result['fail']}"
        )
        await client.send_message(DATABASE_CHANNEL, stats, parse_mode=ParseMode.HTML)
    except Exception as e:
        print(f"[BC] db channel log failed: {e}")


@Bot.on_message(filters.command("cancel") & is_owner_or_admin)
async def cmd_cancel(client, message: Message):
    global _is_canceled
    async with _cancel_lock:
        _is_canceled = True
    await message.reply_text("⛔ Broadcast cancellation requested.", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("broadcast") & is_owner_or_admin)
async def cmd_broadcast(client, message: Message):
    global _is_canceled
    if not message.reply_to_message:
        return await message.reply_text(
            "<b>Reply to a message, then use:</b>\n"
            "<code>/broadcast</code>\n"
            "<code>/broadcast pin</code>\n"
            "<code>/broadcast delete 3600</code>\n"
            "<code>/broadcast pin delete 3600 silent</code>",
            parse_mode=ParseMode.HTML)

    args      = message.command[1:]
    do_pin    = "pin" in args
    silent    = "silent" in args
    do_delete = "delete" in args
    delete_delay = 0
    if do_delete:
        try:
            idx = args.index("delete")
            delete_delay = int(args[idx + 1])
        except (IndexError, ValueError):
            return await message.reply_text(
                "❌ Provide seconds after 'delete': <code>/broadcast delete 3600</code>",
                parse_mode=ParseMode.HTML)

    label_parts = []
    if do_pin:    label_parts.append("PIN")
    if silent:    label_parts.append("SILENT")
    if do_delete: label_parts.append(f"DELETE({delete_delay}s)")
    if not label_parts: label_parts.append("NORMAL")
    label = " + ".join(label_parts)

    async with _cancel_lock:
        _is_canceled = False

    progress_msg = await message.reply_text("⏳ Preparing broadcast...", parse_mode=ParseMode.HTML)
    result = await _broadcast_to_all(
        client, message.reply_to_message, progress_msg,
        label=label, do_pin=do_pin,
        do_delete=do_delete, delete_delay=delete_delay, silent=silent)

    bc_id = f"bc_{uuid.uuid4().hex[:8]}"
    await save_broadcast_msgs(bc_id, result["sent_map"], label)
    await _log_to_db_channel(client, bc_id, message.reply_to_message, label, result)

    final = _status_text(
        label, result['total'], result['ok'], result['blocked'],
        result['deleted'], result['fail'], 1.0, done=True)
    final += f"\n\n<b>Broadcast ID:</b> <code>{bc_id}</code>"
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔒 Mark Safe", callback_data=f"bc_marksafe:{bc_id}"),
        InlineKeyboardButton("🗑 Delete",    callback_data=f"bc_delete:{bc_id}"),
        InlineKeyboardButton("✖️ Close",     callback_data="close"),
    ]])
    await progress_msg.edit_text(final, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex(r"^bc_marksafe:(.+)$") & cq_owner_or_admin)
async def cb_bc_marksafe(client, query: CallbackQuery):
    bc_id = query.data.split(":", 1)[1]
    sent_map = await get_broadcast_msgs(bc_id)
    if not sent_map:
        return await query.answer("Broadcast not found!", show_alert=True)
    await save_safe_broadcast(bc_id, sent_map, f"Safe BC {bc_id}")
    await delete_broadcast_record(bc_id)
    await query.answer("🔒 Marked as Safe Broadcast!", show_alert=True)
    await query.edit_message_reply_markup(reply_markup=None)


@Bot.on_callback_query(filters.regex(r"^bc_delete:(.+)$") & cq_owner_or_admin)
async def cb_bc_delete(client, query: CallbackQuery):
    bc_id    = query.data.split(":", 1)[1]
    sent_map = await get_broadcast_msgs(bc_id)
    if not sent_map:
        return await query.answer("❌ Broadcast not found or already deleted!", show_alert=True)
    await query.answer("🗑 Deleting from all users...", show_alert=True)
    await query.edit_message_reply_markup(reply_markup=None)
    n = 0
    for cid, mid in sent_map.items():
        try:
            await client.delete_messages(int(cid), mid)
            n += 1
        except Exception:
            pass
    await delete_broadcast_record(bc_id)
    await query.message.reply_text(
        f"✅ Broadcast <code>{bc_id}</code> deleted from <b>{n}</b> users.",
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("batchbroadcast") & is_owner_or_admin)
async def cmd_batchbroadcast_start(client, message: Message):
    uid = message.from_user.id
    _batch_states[uid] = []
    await message.reply_text(
        "<b>📦 Batch Broadcast</b>\n\nSend all messages you want to broadcast, then send /done to start.",
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("done") & is_owner_or_admin)
async def cmd_batchbroadcast_done(client, message: Message):
    global _is_canceled
    uid = message.from_user.id
    if uid not in _batch_states:
        return await message.reply_text(
            "❌ No active batch broadcast session. Start one with /batchbroadcast",
            parse_mode=ParseMode.HTML)
    msgs = _batch_states.pop(uid)
    if not msgs:
        return await message.reply_text("❌ No messages collected.", parse_mode=ParseMode.HTML)

    async with _cancel_lock:
        _is_canceled = False
    users        = await full_userbase()
    progress_msg = await message.reply_text(
        f"<b>📦 Batch broadcasting {len(msgs)} message(s) to {len(users)} users...</b>",
        parse_mode=ParseMode.HTML)

    bc_id    = f"bc_{uuid.uuid4().hex[:8]}"
    all_sent = {}
    total_ok = 0
    for source in msgs:
        result = await _broadcast_to_all(client, source, progress_msg, label="BATCH")
        for k, v in result.get("sent_map", {}).items():
            all_sent[k] = v
        total_ok += result["ok"]
        if result.get("canceled"):
            break

    await save_broadcast_msgs(bc_id, all_sent, "BATCH")
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔒 Mark Safe", callback_data=f"bc_marksafe:{bc_id}"),
        InlineKeyboardButton("🗑 Delete",    callback_data=f"bc_delete:{bc_id}"),
        InlineKeyboardButton("✖️ Close",     callback_data="close"),
    ]])
    await progress_msg.edit_text(
        f"<b>✅ Batch Broadcast Done!</b>\n\n"
        f"<b>Messages:</b> {len(msgs)}\n"
        f"<b>Delivered:</b> {total_ok} / {len(users)}\n"
        f"<b>BC ID:</b> <code>{bc_id}</code>",
        reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("pbroadcast") & is_owner_or_admin)
async def cmd_pbroadcast(client, message: Message):
    global _is_canceled
    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to a message to broadcast with pin.", parse_mode=ParseMode.HTML)
    async with _cancel_lock:
        _is_canceled = False
    progress_msg = await message.reply_text(
        "📌 Starting pinned broadcast...", parse_mode=ParseMode.HTML)
    result = await _broadcast_to_all(
        client, message.reply_to_message, progress_msg, label="PINNED", do_pin=True)
    bc_id = f"pbc_{uuid.uuid4().hex[:8]}"
    await save_pbroadcast_msgs(bc_id, result["sent_map"])
    await _log_to_db_channel(client, bc_id, message.reply_to_message, "PINNED", result)
    final = _status_text(
        "PINNED", result['total'], result['ok'],
        result['blocked'], result['deleted'], result['fail'], 1.0, done=True)
    await progress_msg.edit_text(final, parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("delallpbroadcast") & is_owner_or_admin)
async def cmd_delallpbroadcast(client, message: Message):
    records = await get_all_pbroadcast_records()
    p = await message.reply_text("🗑️ Deleting all pinned broadcasts...", parse_mode=ParseMode.HTML)
    n = 0
    for rec in records:
        for cid, mid in rec.get("pinned_ids", {}).items():
            try:
                await client.unpin_chat_message(int(cid), mid)
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_pbroadcast_records()
    await p.edit_text(f"✅ Deleted and unpinned {n} message(s).", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("dbroadcast") & is_owner_or_admin)
async def cmd_dbroadcast(client, message: Message):
    global _is_canceled
    if not message.reply_to_message:
        return await message.reply_text(
            "Reply to a message: <code>/dbroadcast 1H 30M</code>", parse_mode=ParseMode.HTML)
    args = message.command[1:]
    if not args:
        return await message.reply_text(
            "Provide time e.g. <code>1H 30M</code>", parse_mode=ParseMode.HTML)
    duration = parse_time_string(" ".join(args))
    if duration <= 0:
        return await message.reply_text(
            "Invalid time. Use <code>1D</code>, <code>1H</code>, <code>30M</code>, <code>45S</code>",
            parse_mode=ParseMode.HTML)

    async with _cancel_lock:
        _is_canceled = False
    progress_msg = await message.reply_text(
        f"<b>⏱ Timed Broadcast ({duration}s / {duration//60}min)</b>", parse_mode=ParseMode.HTML)
    result = await _broadcast_to_all(
        client, message.reply_to_message, progress_msg, label=f"TIMED({duration}s)")
    bc_id     = f"dbc_{uuid.uuid4().hex[:8]}"
    expire_at = datetime.utcnow() + timedelta(seconds=duration)
    await save_dbroadcast_msgs(bc_id, result["sent_map"], expire_at)
    asyncio.create_task(_schedule_dbc_delete(client, bc_id, duration))
    await _log_to_db_channel(
        client, bc_id, message.reply_to_message, f"TIMED({duration}s)", result)
    final = _status_text(
        f"TIMED({duration}s)", result['total'], result['ok'],
        result['blocked'], result['deleted'], result['fail'], 1.0, done=True)
    final += f"\n\n<b>⏱ Auto-deletes in {duration//60} minutes</b>"
    await progress_msg.edit_text(final, parse_mode=ParseMode.HTML)


async def _schedule_dbc_delete(client, bc_id, delay):
    await asyncio.sleep(delay)
    from database.database import dbroadcast_collection
    doc = await dbroadcast_collection.find_one({"_id": bc_id})
    if doc:
        for cid, mid in doc.get("msg_ids", {}).items():
            try:
                await client.delete_messages(int(cid), mid)
            except Exception:
                pass
        await delete_dbroadcast_record(bc_id)


@Bot.on_message(filters.command("batchdbroadcast") & is_owner_or_admin)
async def cmd_batchdbroadcast_start(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: <code>/batchdbroadcast 1H 30M</code>", parse_mode=ParseMode.HTML)
    duration = parse_time_string(" ".join(message.command[1:]))
    if duration <= 0:
        return await message.reply_text(
            "Invalid time format. Example: <code>1H 30M</code>", parse_mode=ParseMode.HTML)
    uid = message.from_user.id
    _batch_dstates[uid] = []
    _batch_dtimes[uid]  = duration
    await message.reply_text(
        f"<b>⏱ Batch Timed Broadcast ({duration//60} min)</b>\n\n"
        "Send all messages you want to broadcast, then send /ddone.",
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("ddone") & is_owner_or_admin)
async def cmd_batchdbroadcast_done(client, message: Message):
    uid = message.from_user.id
    if uid not in _batch_dstates:
        return await message.reply_text(
            "❌ No active batch timed broadcast session. Start one with /batchdbroadcast",
            parse_mode=ParseMode.HTML)
    msgs     = _batch_dstates.pop(uid)
    duration = _batch_dtimes.pop(uid, 1800)
    if not msgs:
        return await message.reply_text("❌ No messages collected.", parse_mode=ParseMode.HTML)

    users = await full_userbase()
    p     = await message.reply_text("⏳ Broadcasting...", parse_mode=ParseMode.HTML)
    bc_id    = f"dbc_{uuid.uuid4().hex[:8]}"
    all_sent = {}
    for source in msgs:
        result = await _broadcast_to_all(client, source, p, label=f"TIMED({duration}s)")
        for k, v in result.get("sent_map", {}).items():
            all_sent[k] = v
    expire_at = datetime.utcnow() + timedelta(seconds=duration)
    await save_dbroadcast_msgs(bc_id, all_sent, expire_at)
    asyncio.create_task(_schedule_dbc_delete(client, bc_id, duration))
    await p.edit_text(
        f"✅ <b>Batch Timed Broadcast Done!</b>\n"
        f"Auto-deletes in {duration//60} minutes.\n"
        f"Delivered: {len(all_sent)} / {len(users)}\n"
        f"BC ID: <code>{bc_id}</code>",
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("delbroadcast") & is_owner_or_admin)
async def cmd_delbroadcast(client, message: Message):
    bc_id = await get_last_broadcast_id()
    if not bc_id:
        return await message.reply_text(
            "❌ No broadcast records found.", parse_mode=ParseMode.HTML)
    sent_map = await get_broadcast_msgs(bc_id)
    p = await message.reply_text("🗑️ Deleting last broadcast...", parse_mode=ParseMode.HTML)
    n = 0
    for cid, mid in sent_map.items():
        try:
            await client.delete_messages(int(cid), mid)
            n += 1
        except Exception:
            pass
    await delete_broadcast_record(bc_id)
    await p.edit_text(f"✅ Deleted {n} message(s). (ID: <code>{bc_id}</code>)", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("delallbroadcast") & is_owner_or_admin)
async def cmd_delallbroadcast(client, message: Message):
    ids = await get_all_broadcast_ids()
    if not ids:
        return await message.reply_text("❌ No broadcasts found.", parse_mode=ParseMode.HTML)
    p   = await message.reply_text(
        f"🗑️ Deleting {len(ids)} broadcast(s)...", parse_mode=ParseMode.HTML)
    n   = 0
    for bc_id in ids:
        for cid, mid in (await get_broadcast_msgs(bc_id)).items():
            try:
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_broadcast_records()
    await p.edit_text(f"✅ Deleted {n} message(s) from {len(ids)} broadcast(s).", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("allbroadcastclear") & is_owner_or_admin)
async def cmd_allbroadcastclear(client, message: Message):
    p = await message.reply_text("💥 Clearing ALL broadcasts...", parse_mode=ParseMode.HTML)
    n = 0
    for bc_id in await get_all_broadcast_ids():
        for cid, mid in (await get_broadcast_msgs(bc_id)).items():
            try:
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_broadcast_records()
    for rec in await get_all_pbroadcast_records():
        for cid, mid in rec.get("pinned_ids", {}).items():
            try:
                await client.unpin_chat_message(int(cid), mid)
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_pbroadcast_records()
    for rec in await get_all_dbroadcast_records():
        for cid, mid in rec.get("msg_ids", {}).items():
            try:
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_dbroadcast_records()
    await p.edit_text(
        f"<b>✅ All broadcasts cleared!</b> ({n} total messages deleted)",
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("clearpendingdbroadcast") & is_owner_or_admin)
async def cmd_clearpending(client, message: Message):
    expired = await get_expired_dbroadcasts()
    if not expired:
        return await message.reply_text("✅ No expired timed broadcasts.", parse_mode=ParseMode.HTML)
    p = await message.reply_text(
        f"🗑️ Clearing {len(expired)} expired timed broadcast(s)...", parse_mode=ParseMode.HTML)
    n = 0
    for rec in expired:
        for cid, mid in rec.get("msg_ids", {}).items():
            try:
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
        await delete_dbroadcast_record(rec["_id"])
    await p.edit_text(f"✅ Cleared {n} expired message(s).", parse_mode=ParseMode.HTML)


# ── Safe Broadcasts ───────────────────────────────────────────────────────────

@Bot.on_message(filters.command("safebroadcasts") & is_owner_or_admin)
async def cmd_safebroadcasts(client, message: Message):
    await _send_safe_bc_page(client, message, page=0)


async def _send_safe_bc_page(client, target, page=0, edit=False):
    PAGE = 5
    docs = await get_all_safe_broadcasts()
    if not docs:
        text   = "<b>🔒 Safe Broadcasts</b>\n\nNo safe broadcasts found."
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✖️ Close", callback_data="close")
        ]])
    else:
        total_pages = max(1, (len(docs) + PAGE - 1) // PAGE)
        start = page * PAGE
        chunk = docs[start: start + PAGE]
        lines = []
        for doc in chunk:
            created = doc.get("created_at", datetime.utcnow()).strftime("%d/%m %H:%M")
            label   = doc.get("label", doc["_id"])
            count   = len(doc.get("msg_ids", {}))
            lines.append(f"🔒 <code>{doc['_id']}</code>\n   {label} — {created} ({count} users)")
        text = (
            f"<b>🔒 Safe Broadcasts</b>\n"
            f"<b>Page {page+1}/{total_pages}</b>\n\n"
            + "\n\n".join(lines))
        btn_rows = [
            [InlineKeyboardButton(f"🗑 Delete {doc['_id'][:10]}", callback_data=f"sbc_del:{doc['_id']}")]
            for doc in chunk
        ]
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"sbc_page:{page-1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"sbc_page:{page+1}"))
        if nav:
            btn_rows.append(nav)
        btn_rows.append([
            InlineKeyboardButton("🧹 Delete All Safe", callback_data="sbc_delall"),
            InlineKeyboardButton("✖️ Close",           callback_data="close"),
        ])
        markup = InlineKeyboardMarkup(btn_rows)

    if edit:
        await target.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await target.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex(r"^sbc_page:(\d+)$") & cq_owner_or_admin)
async def cb_sbc_page(client, query: CallbackQuery):
    page = int(query.data.split(":")[1])
    await _send_safe_bc_page(client, query.message, page=page, edit=True)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^sbc_del:(.+)$") & cq_owner_or_admin)
async def cb_sbc_del(client, query: CallbackQuery):
    bc_id = query.data.split(":", 1)[1]
    doc   = await get_safe_broadcast(bc_id)
    if not doc:
        return await query.answer("Not found!", show_alert=True)
    await query.edit_message_text(
        f"<b>⚠️ Delete safe broadcast <code>{bc_id}</code>?</b>\n\n"
        f"This will delete the message from <b>{len(doc.get('msg_ids', {}))} users</b>.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"sbc_del_do:{bc_id}"),
             InlineKeyboardButton("❌ Cancel",      callback_data="sbc_page:0")],
        ]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^sbc_del_do:(.+)$") & cq_owner_or_admin)
async def cb_sbc_del_do(client, query: CallbackQuery):
    bc_id = query.data.split(":", 1)[1]
    doc   = await get_safe_broadcast(bc_id)
    if not doc:
        return await query.answer("Not found!", show_alert=True)
    n = 0
    for cid, mid in doc.get("msg_ids", {}).items():
        try:
            await client.delete_messages(int(cid), mid)
            n += 1
        except Exception:
            pass
    await delete_safe_broadcast(bc_id)
    await query.answer(f"✅ Deleted {n} messages!", show_alert=True)
    await _send_safe_bc_page(client, query.message, page=0, edit=True)


@Bot.on_callback_query(filters.regex("^sbc_delall$") & cq_owner_or_admin)
async def cb_sbc_delall_confirm(client, query: CallbackQuery):
    docs = await get_all_safe_broadcasts()
    total_msgs = sum(len(d.get("msg_ids", {})) for d in docs)
    await query.edit_message_text(
        f"<b>⚠️ Delete ALL {len(docs)} safe broadcasts?</b>\n\n"
        f"This will delete messages from approximately <b>{total_msgs} users</b>.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete All", callback_data="sbc_delall_do"),
             InlineKeyboardButton("❌ Cancel",          callback_data="sbc_page:0")],
        ]),
        parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex("^sbc_delall_do$") & cq_owner_or_admin)
async def cb_sbc_delall_do(client, query: CallbackQuery):
    docs = await get_all_safe_broadcasts()
    n = 0
    for doc in docs:
        for cid, mid in doc.get("msg_ids", {}).items():
            try:
                await client.delete_messages(int(cid), mid)
                n += 1
            except Exception:
                pass
    await delete_all_safe_broadcasts()
    await query.answer(f"✅ Deleted {n} messages!", show_alert=True)
    await _send_safe_bc_page(client, query.message, page=0, edit=True)


@Bot.on_message(filters.command("deletesafebroadcast") & is_owner_or_admin)
async def cmd_deletesafebroadcast(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "Usage: <code>/deletesafebroadcast [broadcast_id]</code>", parse_mode=ParseMode.HTML)
    bc_id = message.command[1]
    doc   = await get_safe_broadcast(bc_id)
    if not doc:
        return await message.reply_text(
            f"❌ Safe broadcast <code>{bc_id}</code> not found.", parse_mode=ParseMode.HTML)
    n = 0
    for cid, mid in doc.get("msg_ids", {}).items():
        try:
            await client.delete_messages(int(cid), mid)
            n += 1
        except Exception:
            pass
    await delete_safe_broadcast(bc_id)
    await message.reply_text(
        f"✅ Safe broadcast <code>{bc_id}</code> deleted from {n} chats.",
        parse_mode=ParseMode.HTML)


# ── Batch message collector (group=0, runs after session handlers in group=-1) ──

_BATCH_EXCLUDE = [
    "done", "ddone", "cancel", "broadcast", "batchbroadcast",
    "pbroadcast", "dbroadcast", "batchdbroadcast", "delbroadcast",
    "delallbroadcast", "allbroadcastclear", "clearpendingdbroadcast",
    "delallpbroadcast", "safebroadcasts", "deletesafebroadcast",
    "start", "help", "about", "info", "admins", "addadmin", "deladmin",
    "addchannel", "delchannel", "channels", "search", "customize",
    "genlink", "fsublink", "backup", "clicks", "click",
    "stats", "status", "ping", "cmds", "fsubsets",
    "settime", "default_limit", "approveoff", "approveon",
]


@Bot.on_message(
    filters.private & is_owner_or_admin & ~filters.command(_BATCH_EXCLUDE),
    group=0
)
async def collect_batch(client, message: Message):
    uid = message.from_user.id
    if uid in _batch_states:
        _batch_states[uid].append(message)
        await message.reply_text(
            f"✅ Message #{len(_batch_states[uid])} added to batch.",
            parse_mode=ParseMode.HTML)
    elif uid in _batch_dstates:
        _batch_dstates[uid].append(message)
        await message.reply_text(
            f"✅ Message #{len(_batch_dstates[uid])} added to timed batch.",
            parse_mode=ParseMode.HTML)
