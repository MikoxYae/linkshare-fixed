# plugins/start.py
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from miko import Bot
from config import (
    OWNER_ID, LINK_IMAGE, START_MSG, HELP_MSG, ABOUT_TXT,
    BOT_BIRTH_DATE, START_DELETE_TIME, HELP_DELETE_TIME, ABOUT_DELETE_TIME,
    DEFAULT_BUTTON_TEXT, DEFAULT_SECOND_MSG, DEFAULT_CAPTION, MAINTENANCE_MSG,
)
from database.database import (
    record_click,
    add_user, get_channel_by_encoded_link, get_channel_by_encoded_link2,
    get_channel_by_encoded_link3, get_cached_invite_link, save_invite_link,
    clear_invite_link, get_revoke_time, get_delete_time, get_fsub_message,
    is_maintenance, get_custom_caption, get_custom_image, get_custom_button_text,
    is_button_hidden, get_second_message, is_second_message_off,
    is_forward_enabled, get_original_link, is_admin,
    record_set_pass, is_fsub_enabled,
)
from plugins.fsubsets import check_fsub_sets
from helper_func import (
    decode, encode, delete_after_delay, delete_messages_after_delay,
    is_owner_or_admin, cq_owner_or_admin, get_bot_age, is_sub,
    is_owner_or_admin_check,
)

_channel_locks: dict = defaultdict(asyncio.Lock)

LINK_NORMAL  = "normal"
LINK_REQUEST = "request"
LINK_DIRECT  = "direct"


# ─────────────────────────────────────────────────────────────────────────────
# Invite link factory
# ─────────────────────────────────────────────────────────────────────────────

async def _get_or_create_invite(client, channel_id: int, link_type: str) -> tuple:
    """
    Returns (invite_link: str, remaining_seconds: int).
    remaining_seconds < 60  →  show "Get Again" button.

    LINK_DIRECT:  creates_join_request=False — user joins instantly even if
                  the channel has request-mode enabled.
    LINK_NORMAL:  creates_join_request=False (or @username for public channels).
    LINK_REQUEST: creates_join_request=True  — admin must approve.
    """
    async with _channel_locks[channel_id]:
        revoke_time = await get_revoke_time()
        cached      = await get_cached_invite_link(channel_id, link_type)
        remaining   = 0

        if cached and cached.get("created_at"):
            age       = (datetime.utcnow() - cached["created_at"]).total_seconds()
            remaining = max(0, revoke_time - age)
            if remaining > 60:
                return cached["invite_link"], int(remaining)

        expire_dt = datetime.now(tz=timezone.utc) + timedelta(seconds=revoke_time)

        if link_type == LINK_DIRECT:
            inv  = await client.create_chat_invite_link(
                chat_id=channel_id,
                creates_join_request=False,
                expire_date=expire_dt,
            )
            link = inv.invite_link

        elif link_type == LINK_REQUEST:
            inv  = await client.create_chat_invite_link(
                chat_id=channel_id,
                creates_join_request=True,
                expire_date=expire_dt,
            )
            link = inv.invite_link

        else:  # LINK_NORMAL
            try:
                chat = await client.get_chat(channel_id)
                if chat.username:
                    return f"https://t.me/{chat.username}", revoke_time
            except Exception:
                pass
            inv  = await client.create_chat_invite_link(
                chat_id=channel_id,
                creates_join_request=False,
                expire_date=expire_dt,
            )
            link = inv.invite_link

        await save_invite_link(channel_id, link, link_type)
        return link, revoke_time


# ─────────────────────────────────────────────────────────────────────────────
# Send link message
# ─────────────────────────────────────────────────────────────────────────────

async def _send_link_messages(client, message: Message, channel_id: int,
                               link_type: str, original_token: str = ""):
    invite_link, remaining = await _get_or_create_invite(client, channel_id, link_type)

    caption_tmpl = (await get_custom_caption()) or DEFAULT_CAPTION
    image        = (await get_custom_image()) or LINK_IMAGE
    btn_text     = (await get_custom_button_text()) or DEFAULT_BUTTON_TEXT
    hide_button  = await is_button_hidden()
    second_txt   = (await get_second_message()) or DEFAULT_SECOND_MSG
    second_off   = await is_second_message_off()
    forward_ok   = await is_forward_enabled()
    delete_time  = await get_delete_time()
    revoke_time  = await get_revoke_time()

    caption = caption_tmpl.replace("[link]", invite_link)
    protect = not forward_ok

    btn_row = []
    if not hide_button and invite_link:
        btn_row.append(InlineKeyboardButton(btn_text, url=invite_link))

    if remaining > 0 and remaining < 120 and original_token:
        me    = await client.get_me()
        uname = getattr(me, "username", None)
        if uname:
            btn_row.append(InlineKeyboardButton(
                "🔄 Get Again",
                url=f"https://t.me/{uname}?start={original_token}",
            ))

    markup = InlineKeyboardMarkup([btn_row]) if btn_row else None

    try:
        img_msg = await client.send_photo(
            chat_id=message.chat.id,
            photo=image,
            caption=caption,
            reply_markup=markup,
            protect_content=protect,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        img_msg = await message.reply_text(
            caption,
            reply_markup=markup,
            protect_content=protect,
            parse_mode=ParseMode.HTML,
        )

    msgs = [img_msg]
    if not second_off and second_txt:
        note = await img_msg.reply_text(
            second_txt,
            protect_content=protect,
            parse_mode=ParseMode.HTML,
        )
        msgs.append(note)

    asyncio.create_task(delete_messages_after_delay(msgs, delete_time))
    asyncio.create_task(_revoke_link(client, channel_id, invite_link, link_type, revoke_time))


async def _revoke_link(client, channel_id: int, invite_link: str, link_type: str, delay: int):
    await asyncio.sleep(delay)
    try:
        await client.revoke_chat_invite_link(channel_id, invite_link)
    except Exception:
        pass
    await clear_invite_link(channel_id, link_type)


# ─────────────────────────────────────────────────────────────────────────────
# Token resolver
# ─────────────────────────────────────────────────────────────────────────────

async def _resolve_token(token: str):
    """
    Returns (channel_id: int|None, link_type: str, original_token: str).

    Token formats:
      req_{b64}  →  LINK_REQUEST
      dir_{b64}  →  LINK_DIRECT
      {b64}      →  LINK_NORMAL
    """
    if token.startswith("req_"):
        enc = token[4:]
        ch  = await get_channel_by_encoded_link2(enc)
        if ch is None:
            try:
                raw = await decode(enc)
                ch  = int(raw.split(":")[0])
            except Exception:
                ch = None
        return ch, LINK_REQUEST, token

    elif token.startswith("dir_"):
        enc = token[4:]
        ch  = await get_channel_by_encoded_link3(enc)
        if ch is None:
            try:
                raw = await decode(enc)
                ch  = int(raw.split(":")[0])
            except Exception:
                ch = None
        return ch, LINK_DIRECT, token

    else:
        ch = await get_channel_by_encoded_link(token)
        if ch is None:
            try:
                ch = int(await decode(token))
            except Exception:
                ch = None
        return ch, LINK_NORMAL, token


# ─────────────────────────────────────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Bot, message: Message):
    user_id = message.from_user.id
    await add_user(user_id)

    if await is_maintenance():
        if user_id != OWNER_ID and not await is_admin(user_id):
            return await message.reply_text(MAINTENANCE_MSG, parse_mode=ParseMode.HTML)

    args  = message.command
    token = args[1].strip() if len(args) > 1 else ""

    if not token:
        msg = await message.reply_text(START_MSG, parse_mode=ParseMode.HTML)
        asyncio.create_task(delete_after_delay(msg, START_DELETE_TIME))
        return

    channel_id, link_type, original_token = await _resolve_token(token)

    if not channel_id:
        return await message.reply_text(
            "<b>❌ Invalid or expired link.</b>", parse_mode=ParseMode.HTML)

    # External URL token (genlink)
    original = await get_original_link(channel_id)
    if original:
        dt       = await get_delete_time()
        btn_text = (await get_custom_button_text()) or DEFAULT_BUTTON_TEXT
        markup   = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=original)]])
        m1 = await message.reply_text(
            f"<b>🔗 Your Link:</b>\n{original}",
            reply_markup=markup, parse_mode=ParseMode.HTML,
        )
        m2 = await m1.reply_text(
            "<u><b>Note: Click the post link again if this link expires.</b></u>",
            parse_mode=ParseMode.HTML,
        )
        asyncio.create_task(delete_messages_after_delay([m1, m2], dt))
        return

    # ── Global Force Sub — Set System ────────────────────────────────────────
    # All 3 link types (normal, request, direct) go through the fsub gate.
    # Direct links give instant join access WITHOUT a join-request prompt,
    # but they still require the user to pass force-sub checks.
    try:
        fsub_on = await is_fsub_enabled()
    except Exception:
        fsub_on = True  # Fail-safe: if DB is down, enforce fsub
    if fsub_on:
        all_sets_passed, sets_btns, completed_set_id = await check_fsub_sets(
            client, user_id, original_token)
        if not all_sets_passed:
            tmpl = await get_fsub_message()
            try:
                fsub_text = tmpl.format(
                    first=message.from_user.first_name or "User",
                    mention=message.from_user.mention,
                    id=user_id,
                )
            except Exception:
                fsub_text = tmpl
            me    = await client.get_me()
            uname = getattr(me, "username", None)
            if uname:
                sets_btns.append([InlineKeyboardButton(
                    "♻️ I Joined — Try Again",
                    url=f"https://t.me/{uname}?start={original_token}")])
            fsub_msg = await message.reply_text(
                fsub_text,
                reply_markup=InlineKeyboardMarkup(sets_btns) if sets_btns else None,
                parse_mode=ParseMode.HTML,
            )
            asyncio.create_task(delete_after_delay(fsub_msg, START_DELETE_TIME))
            return
        completed_set_id_val = completed_set_id
    else:
        completed_set_id_val = 0

    # All checks passed — deliver link
    asyncio.create_task(record_click(channel_id, link_type))
    if completed_set_id_val:
        asyncio.create_task(record_set_pass(user_id, "global", completed_set_id_val))
    await _send_link_messages(client, message, channel_id, link_type, original_token)


# ─────────────────────────────────────────────────────────────────────────────
# /help  /about  /info
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("help") & filters.private)
async def help_command(client: Bot, message: Message):
    msg = await message.reply_text(HELP_MSG, parse_mode=ParseMode.HTML)
    asyncio.create_task(delete_after_delay(msg, HELP_DELETE_TIME))


@Bot.on_message((filters.command("about") | filters.command("info")) & filters.private)
async def about_command(client: Bot, message: Message):
    age_str = get_bot_age(BOT_BIRTH_DATE)
    text    = ABOUT_TXT.format(age=age_str)
    markup  = InlineKeyboardMarkup([[
        InlineKeyboardButton("📡 Powered By", url="https://t.me/World_Fastest_Bots"),
        InlineKeyboardButton("World Fastest Bots", url="https://t.me/World_Fastest_Bots"),
    ]])
    msg = await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    asyncio.create_task(delete_after_delay(msg, ABOUT_DELETE_TIME))


# ─────────────────────────────────────────────────────────────────────────────
# /cmds
# ─────────────────────────────────────────────────────────────────────────────

CMDS_PAGE_1 = (
    "<b>╔══════════════════════╗\n"
    "║  📋  BOT COMMANDS   ║\n"
    "╚══════════════════════╝</b>\n\n"
    "<b>👤 Public</b>\n"
    "┣ /start — Get invite link or welcome\n"
    "┣ /help  — Help &amp; support\n"
    "┣ /about — Bot info\n"
    "┗ /info  — Same as /about\n\n"
    "<b>🛡 Admin: General</b>\n"
    "┣ /cmds    — This command list\n"
    "┣ /stats   — Users / channels / links\n"
    "┣ /ping    — Server latency\n"
    "┣ /status  — CPU, RAM, uptime\n"
    "┣ /update  — Pull latest update &amp; restart\n"
    "┗ /cleandb — Remove stale DB data\n\n"
    "<b>👥 Admin Management</b>\n"
    "┣ /admins          — Admin list\n"
    "┣ /addadmin [id]   — Add admin\n"
    "┗ /deladmin [id]   — Remove admin\n\n"
    "<b>📺 Channel Management</b>\n"
    "┣ /addchannel [Name] [ID]  — Add channel &amp; generate all tokens\n"
    "┣ /delchannel [ID]         — Remove channel\n"
    "┣ /channels                — List channels with all 3 token links\n"
    "┗ /search [Name]           — Search channel"
)

CMDS_PAGE_2 = (
    "<b>🔗 Token Link Types (per channel)</b>\n"
    "┣ 📨 <b>Request</b>  — User sends join request; admin approves\n"
    "┣ 🌐 <b>Normal</b>   — Direct join (no approval needed)\n"
    "┗ ⚡ <b>Direct</b>   — Instant join link, no join-request prompt\n\n"
    "All 3 tokens are shown in /channels and generated on /addchannel.\n\n"
    "<b>🔗 Extra Link Tools</b>\n"
    "┗ /genlink [URL]  — Wrap an external URL as a bot deep-link\n\n"
    "<b>📊 Analytics</b>\n"
    "┣ /clicks              — All channel click stats\n"
    "┣ /click [channel_id]  — Detailed stats + chart\n"
    "┣ /analytics           — Full bot analytics overview\n"
    "┣ /toplinks            — Top used links ranking\n"
    "┣ /graph               — Usage graph (text-based)\n"
    "┗ /userstats           — Detailed user statistics\n\n"
    "<b>📡 Broadcast</b>\n"
    "┣ /broadcast               — Broadcast to all users\n"
    "┣ /batchbroadcast          — Batch mode → /done\n"
    "┣ /pbroadcast              — Pinned broadcast\n"
    "┣ /dbroadcast [time]       — Timed (e.g. 1H 30M)\n"
    "┣ /batchdbroadcast [time]  — Batch timed → /ddone\n"
    "┣ /delbroadcast            — Delete last broadcast\n"
    "┣ /delallbroadcast         — Delete all broadcasts\n"
    "┣ /allbroadcastclear       — Nuke everything\n"
    "┣ /clearpendingdbroadcast  — Clear expired timed\n"
    "┣ /safebroadcasts          — Manage safe broadcasts\n"
    "┣ /deletesafebroadcast [id]\n"
    "┗ /cancel                  — Stop active broadcast\n\n"
    "<b>🛡 Force Sub — Set System</b>\n"
    "┣ /fsubsets        — Manage force-sub sets\n"
    "┃   • Each set holds up to 15 channels\n"
    "┃   • Cascading: user must pass Set 01 before Set 02\n"
    "┃   • Grace time: passed set isn't re-checked for N minutes\n"
    "┣ /settime [time]  — Grace time (e.g. 1H, 30M)\n"
    "┗ /default_limit [n]  — Default channels shown per set\n\n"
    "<b>⚙️ Settings &amp; Tools</b>\n"
    "┣ /customize               — Full settings panel\n"
    "┣ /approveoff [id]         — Disable auto-approve for channel\n"
    "┣ /approveon [id]          — Enable auto-approve for channel\n"
    "┗ /backup                  — Export DB as ZIP"
)


@Bot.on_message(filters.command("cmds") & filters.private)
async def cmd_cmds(client: Bot, message: Message):
    uid = message.from_user.id
    if not await is_owner_or_admin_check(uid):
        return
    await message.reply_text(CMDS_PAGE_1, parse_mode=ParseMode.HTML)
    await message.reply_text(CMDS_PAGE_2, parse_mode=ParseMode.HTML)


# ─────────────────────────────────────────────────────────────────────────────
# close callback — global
# ─────────────────────────────────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^close$"))
async def cb_close(client: Bot, query: CallbackQuery):
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass
