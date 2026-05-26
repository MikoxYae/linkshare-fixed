# helper_func.py
import base64
import re
import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ParseMode
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from config import OWNER_ID
from database.database import is_admin


# ─── Custom Filters ───────────────────────────────────────────────────────────
# These use filters.create() for Pyrogram v2 compatibility.
# The function signature is (flt_obj, client, update).

async def _is_owner_or_admin_func(flt, client, message):
    try:
        if not message.from_user:
            return False
        uid = message.from_user.id
        if uid == OWNER_ID:            # owner always passes
            return True
        result = await is_admin(uid)   # check DB
        return bool(result)
    except Exception:
        return False


async def _cq_is_owner_or_admin(flt, client, query):
    try:
        if not query.from_user:
            return False
        uid = query.from_user.id
        if uid == OWNER_ID:
            return True
        return bool(await is_admin(uid))
    except Exception:
        return False


is_owner_or_admin = filters.create(_is_owner_or_admin_func)
cq_owner_or_admin = filters.create(_cq_is_owner_or_admin)


# ─── Quick sync owner check (no DB, use inside handlers as fallback) ──────────

def is_owner(uid: int) -> bool:
    return int(uid) == int(OWNER_ID)


async def is_owner_or_admin_check(uid: int) -> bool:
    """Use inside handler body when filter-level check is insufficient."""
    try:
        if int(uid) == int(OWNER_ID):
            return True
        return bool(await is_admin(uid))
    except Exception:
        return is_owner(uid)


# ─── Encoding ─────────────────────────────────────────────────────────────────

async def encode(string: str) -> str:
    return base64.urlsafe_b64encode(string.encode("ascii")).decode("ascii").strip("=")


async def decode(b64_string: str) -> str:
    b64_string = b64_string.strip("=")
    padded = b64_string + "=" * (-len(b64_string) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")


# ─── Time Helpers ─────────────────────────────────────────────────────────────

def parse_time_string(time_str: str) -> int:
    total   = 0
    pattern = re.compile(r"(\d+)\s*([DdHhMmSs])")
    matches = pattern.findall(time_str)
    if not matches:
        return -1
    multipliers = {"d": 86400, "h": 3600, "m": 60, "s": 1}
    for value, unit in matches:
        total += int(value) * multipliers.get(unit.lower(), 0)
    return total


def get_readable_time(seconds: int) -> str:
    count = 0
    up_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", "days"]
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        up_time += f"{time_list.pop()}, "
    time_list.reverse()
    up_time += ":".join(time_list)
    return up_time


def get_bot_age(birth_str: str) -> str:
    from datetime import datetime
    try:
        birth = datetime.strptime(birth_str, "%d/%m/%Y")
        delta = datetime.now() - birth
        days  = delta.days
        years,  rem       = divmod(days, 365)
        months, rem_days  = divmod(rem, 30)
        parts = []
        if years:  parts.append(f"{years} Year{'s' if years > 1 else ''}")
        if months: parts.append(f"{months} Month{'s' if months > 1 else ''}")
        parts.append(f"{rem_days} Day{'s' if rem_days != 1 else ''}")
        return " | ".join(parts) + f" (Since {birth_str})"
    except Exception:
        return f"1 Day ({birth_str})"


# ─── Subscription Check ───────────────────────────────────────────────────────

async def is_sub(client, user_id: int, channel_id: int) -> bool:
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status not in [
            ChatMemberStatus.BANNED,
            ChatMemberStatus.LEFT,
            ChatMemberStatus.RESTRICTED,
        ]
    except UserNotParticipant:
        return False
    except Exception:
        return False


async def has_pending_join_request(client, channel_id: int, user_id: int) -> bool:
    """
    Returns True if the user has a PENDING join request in the channel
    (sent a request but not yet approved/declined).
    Used for request-mode force-sub channels so users who have already
    sent a request are not blocked again.
    """
    try:
        async for joiner in client.get_chat_join_requests(channel_id):
            if joiner.user and joiner.user.id == user_id:
                return True
        return False
    except Exception:
        return False


# ─── Delayed deletion helpers ─────────────────────────────────────────────────

async def delete_after_delay(msg, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def delete_messages_after_delay(msgs: list, delay: int):
    await asyncio.sleep(delay)
    for msg in msgs:
        try:
            await msg.delete()
        except Exception:
            pass
