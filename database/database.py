# database/database.py — Central MongoDB interface
import base64
import motor.motor_asyncio
from config import DB_URI, DB_NAME
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

_client  = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
_db      = _client[DB_NAME]

user_data              = _db["users"]
channels_collection    = _db["channels"]
fsub_channels_col      = _db["fsub_channels"]
admins_collection      = _db["admins"]
settings_collection    = _db["settings"]
broadcast_collection   = _db["broadcasts"]
pbroadcast_collection  = _db["pbroadcasts"]
dbroadcast_collection  = _db["dbroadcasts"]
safe_broadcast_col     = _db["safe_broadcasts"]
fsublink_config_col    = _db["fsublink_configs"]   # legacy per-token fsub overrides (deprecated)
fsublink_tokens_col    = _db["fsublink_tokens"]    # new isolated fsublink token store


# ══════════════════════════════════════════════════════
# USERS
# ══════════════════════════════════════════════════════

async def add_user(user_id: int) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    try:
        if await user_data.find_one({"_id": user_id}):
            return False
        await user_data.insert_one({"_id": user_id, "created_at": datetime.utcnow()})
        return True
    except Exception as e:
        print(f"[DB] add_user: {e}")
        return False

async def present_user(user_id: int) -> bool:
    if not isinstance(user_id, int):
        return False
    return bool(await user_data.find_one({"_id": user_id}))

async def full_userbase() -> List[int]:
    try:
        return [doc["_id"] async for doc in user_data.find()]
    except Exception as e:
        print(f"[DB] full_userbase: {e}")
        return []

async def del_user(user_id: int) -> bool:
    try:
        result = await user_data.delete_one({"_id": user_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"[DB] del_user: {e}")
        return False

async def count_users() -> int:
    try:
        return await user_data.count_documents({})
    except Exception:
        return 0


# ══════════════════════════════════════════════════════
# ADMINS
# ══════════════════════════════════════════════════════

async def is_admin(user_id: int) -> bool:
    try:
        return bool(await admins_collection.find_one({"_id": int(user_id)}))
    except Exception:
        return False

async def add_admin(user_id: int) -> bool:
    try:
        uid = int(user_id)
        await admins_collection.update_one({"_id": uid}, {"$set": {"_id": uid}}, upsert=True)
        return True
    except Exception as e:
        print(f"[DB] add_admin: {e}")
        return False

async def remove_admin(user_id: int) -> bool:
    try:
        result = await admins_collection.delete_one({"_id": int(user_id)})
        return result.deleted_count > 0
    except Exception as e:
        print(f"[DB] remove_admin: {e}")
        return False

async def list_admins() -> List[int]:
    try:
        return [doc["_id"] async for doc in admins_collection.find()]
    except Exception:
        return []


# ══════════════════════════════════════════════════════
# CHANNELS
# ══════════════════════════════════════════════════════

async def save_channel(channel_id: int, anime_name: str = "", primary_link: str = "") -> bool:
    if not isinstance(channel_id, int):
        return False
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {
                "channel_id": channel_id,
                "anime_name": anime_name,
                "primary_link": primary_link,
                "status": "active",
                "created_at": datetime.utcnow(),
            }},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_channel: {e}")
        return False

async def get_channels() -> List[int]:
    try:
        channels = await channels_collection.find({"status": "active"}).to_list(None)
        return [ch["channel_id"] for ch in channels if isinstance(ch.get("channel_id"), int)]
    except Exception as e:
        print(f"[DB] get_channels: {e}")
        return []

async def get_channel_doc(channel_id: int) -> Optional[Dict]:
    try:
        return await channels_collection.find_one({"channel_id": channel_id, "status": "active"})
    except Exception:
        return None

async def delete_channel(channel_id: int) -> bool:
    try:
        result = await channels_collection.delete_one({"channel_id": channel_id})
        return result.deleted_count > 0
    except Exception as e:
        print(f"[DB] delete_channel: {e}")
        return False

async def count_channels() -> int:
    try:
        return await channels_collection.count_documents({"status": "active"})
    except Exception:
        return 0

async def search_channels_by_name(query: str) -> List[Dict]:
    try:
        return await channels_collection.find(
            {"anime_name": {"$regex": query, "$options": "i"}, "status": "active"}
        ).to_list(None)
    except Exception as e:
        print(f"[DB] search_channels: {e}")
        return []

# ── Encoded links ─────────────────────────────────────

async def save_encoded_link(channel_id: int) -> Optional[str]:
    if not isinstance(channel_id, int):
        return None
    try:
        encoded = base64.urlsafe_b64encode(str(channel_id).encode()).decode()
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"encoded_link": encoded, "updated_at": datetime.utcnow()}},
            upsert=True)
        return encoded
    except Exception as e:
        print(f"[DB] save_encoded_link: {e}")
        return None

async def get_channel_by_encoded_link(encoded_link: str) -> Optional[int]:
    try:
        doc = await channels_collection.find_one({"encoded_link": encoded_link, "status": "active"})
        return doc["channel_id"] if doc else None
    except Exception:
        return None

async def save_encoded_link2(channel_id: int, encoded_link: str) -> Optional[str]:
    if not isinstance(channel_id, int) or not isinstance(encoded_link, str):
        return None
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"req_encoded_link": encoded_link, "updated_at": datetime.utcnow()}},
            upsert=True)
        return encoded_link
    except Exception as e:
        print(f"[DB] save_encoded_link2: {e}")
        return None

async def get_channel_by_encoded_link2(encoded_link: str) -> Optional[int]:
    try:
        doc = await channels_collection.find_one({"req_encoded_link": encoded_link, "status": "active"})
        return doc["channel_id"] if doc else None
    except Exception:
        return None

async def save_encoded_link3(channel_id: int, encoded_link: str) -> Optional[str]:
    """Save direct (no-request) encoded link."""
    if not isinstance(channel_id, int) or not isinstance(encoded_link, str):
        return None
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"dir_encoded_link": encoded_link, "updated_at": datetime.utcnow()}},
            upsert=True)
        return encoded_link
    except Exception as e:
        print(f"[DB] save_encoded_link3: {e}")
        return None

async def get_channel_by_encoded_link3(encoded_link: str) -> Optional[int]:
    """Get channel by direct encoded link."""
    try:
        doc = await channels_collection.find_one({"dir_encoded_link": encoded_link, "status": "active"})
        return doc["channel_id"] if doc else None
    except Exception:
        return None

# ── Invite link cache (per type) ──────────────────────

async def save_invite_link(channel_id: int, invite_link: str, link_type: str) -> bool:
    """link_type: 'normal', 'request', 'direct'"""
    try:
        field = f"cached_link_{link_type}"
        time_field = f"cached_link_{link_type}_at"
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {field: invite_link, time_field: datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_invite_link: {e}")
        return False

async def get_cached_invite_link(channel_id: int, link_type: str) -> Optional[Dict]:
    """Returns {'invite_link': str, 'created_at': datetime} or None"""
    try:
        field = f"cached_link_{link_type}"
        time_field = f"cached_link_{link_type}_at"
        doc = await channels_collection.find_one({"channel_id": channel_id, "status": "active"})
        if doc and doc.get(field):
            return {"invite_link": doc[field], "created_at": doc.get(time_field)}
        return None
    except Exception:
        return None

async def clear_invite_link(channel_id: int, link_type: str) -> None:
    try:
        field = f"cached_link_{link_type}"
        time_field = f"cached_link_{link_type}_at"
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$unset": {field: "", time_field: ""}})
    except Exception:
        pass

# Legacy helpers kept for compatibility
async def get_current_invite_link(channel_id: int) -> Optional[Dict]:
    return await get_cached_invite_link(channel_id, "normal")

async def get_link_creation_time(channel_id: int):
    cached = await get_cached_invite_link(channel_id, "normal")
    return cached["created_at"] if cached else None

# ── Approval ──────────────────────────────────────────

async def set_approval_off(channel_id: int, off: bool = True) -> bool:
    try:
        await channels_collection.update_one(
            {"channel_id": channel_id},
            {"$set": {"approval_off": off}},
            upsert=True)
        return True
    except Exception:
        return False

async def is_approval_off(channel_id: int) -> bool:
    try:
        doc = await channels_collection.find_one({"channel_id": channel_id})
        return bool(doc and doc.get("approval_off", False))
    except Exception:
        return False

async def get_original_link(channel_id: int) -> Optional[str]:
    try:
        doc = await channels_collection.find_one({"channel_id": channel_id, "status": "active"})
        return doc.get("original_link") if doc else None
    except Exception:
        return None


async def get_channel_fsub_override(channel_id: int):
    """Returns None (follow global), True (force fsub on), or False (bypass fsub)."""
    try:
        doc = await channels_collection.find_one({"channel_id": channel_id})
        if not doc or "fsub_override" not in doc:
            return None
        return doc["fsub_override"]
    except Exception:
        return None


async def set_channel_fsub_override(channel_id: int, override) -> bool:
    """Set fsub override: None = follow global, True = force on, False = bypass."""
    try:
        if override is None:
            await channels_collection.update_one(
                {"channel_id": channel_id},
                {"$unset": {"fsub_override": ""}})
        else:
            await channels_collection.update_one(
                {"channel_id": channel_id},
                {"$set": {"fsub_override": override}},
                upsert=True)
        return True
    except Exception as e:
        print(f"[DB] set_channel_fsub_override: {e}")
        return False


# ══════════════════════════════════════════════════════
# FSUB CHANNELS (global)
# ══════════════════════════════════════════════════════

async def add_fsub_channel(channel_id: int, request_mode: bool = False) -> bool:
    try:
        await fsub_channels_col.update_one(
            {"channel_id": channel_id},
            {"$set": {"channel_id": channel_id, "request_mode": request_mode,
                      "status": "active", "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] add_fsub_channel: {e}")
        return False

async def remove_fsub_channel(channel_id: int) -> bool:
    try:
        result = await fsub_channels_col.delete_one({"channel_id": channel_id})
        return result.deleted_count > 0
    except Exception:
        return False

async def get_fsub_channels() -> List[int]:
    try:
        docs = await fsub_channels_col.find({"status": "active"}).to_list(None)
        return [d["channel_id"] for d in docs]
    except Exception:
        return []

async def get_fsub_channels_with_mode() -> List[Dict]:
    try:
        return await fsub_channels_col.find({"status": "active"}).to_list(None)
    except Exception:
        return []

async def update_fsub_request_mode(channel_id: int, mode: bool) -> bool:
    try:
        await fsub_channels_col.update_one(
            {"channel_id": channel_id}, {"$set": {"request_mode": mode}})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# FSUBLINK CONFIGS (per-token custom fsub)
# ══════════════════════════════════════════════════════

async def save_fsublink_config(token_key: str, fsub_channels: List[Dict]) -> bool:
    """Legacy: Store custom fsub channels for a specific token set."""
    try:
        await fsublink_config_col.update_one(
            {"_id": token_key},
            {"$set": {"channels": fsub_channels, "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_fsublink_config: {e}")
        return False

async def get_fsublink_config(token_key: str) -> Optional[List[Dict]]:
    """Legacy: Get custom fsub channels for a token."""
    try:
        doc = await fsublink_config_col.find_one({"_id": token_key})
        return doc.get("channels") if doc else None
    except Exception:
        return None


# ── New isolated fsublink token store ──────────────────────────────────────────
# Each /fsublink call generates a unique fsl_{base} key stored here.
# These tokens are completely separate from regular channel tokens.

async def save_fsublink_token(base_key: str, channel_id: int, fsub_channels: List[Dict]) -> bool:
    """Save a unique fsublink token (base_key = fsl_{...}). One entry covers all 3 link types."""
    try:
        await fsublink_tokens_col.update_one(
            {"_id": base_key},
            {"$set": {
                "channel_id":   channel_id,
                "fsub_channels": fsub_channels,
                "created_at":   datetime.utcnow(),
            }},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_fsublink_token: {e}")
        return False

async def get_fsublink_token(base_key: str) -> Optional[Dict]:
    """Return the fsublink token doc for base_key (fsl_{...}), or None."""
    try:
        return await fsublink_tokens_col.find_one({"_id": base_key})
    except Exception:
        return None


async def get_all_fsublink_channel_ids() -> List[int]:
    """Returns unique channel IDs that have fsublink tokens."""
    try:
        return await fsublink_tokens_col.distinct("channel_id")
    except Exception:
        return []


async def get_latest_fsublink_token(channel_id: int) -> Optional[Dict]:
    """Returns the most recently created fsublink token doc for a channel."""
    try:
        docs = await fsublink_tokens_col.find(
            {"channel_id": channel_id}
        ).sort("created_at", -1).limit(1).to_list(1)
        return docs[0] if docs else None
    except Exception:
        return None


# ══════════════════════════════════════════════════════
# REQ CHANNELS (temporary promo force sub)
# Applied on top of fsublink tokens (/req) or all tokens (/reqall)
# ══════════════════════════════════════════════════════

req_fsub_col = _db["req_fsub_channels"]


async def add_req_channel(
    channel_id: int,
    request_mode: bool = True,
    expire_seconds: int = None,
    apply_all: bool = False,
) -> bool:
    """Add or update a promo req channel entry."""
    try:
        doc = {
            "channel_id": channel_id,
            "request_mode": request_mode,
            "apply_all": apply_all,
            "added_at": datetime.utcnow(),
            "expires_at": (
                datetime.utcnow() + timedelta(seconds=expire_seconds)
                if expire_seconds else None
            ),
        }
        await req_fsub_col.update_one(
            {"channel_id": channel_id},
            {"$set": doc},
            upsert=True,
        )
        return True
    except Exception as e:
        print(f"[DB] add_req_channel: {e}")
        return False


async def remove_req_channel(channel_id: int) -> bool:
    try:
        result = await req_fsub_col.delete_one({"channel_id": channel_id})
        return result.deleted_count > 0
    except Exception:
        return False


async def get_active_req_channels(apply_all_only: bool = False) -> List[Dict]:
    """Returns non-expired req channels. apply_all_only=True → only reqall channels."""
    try:
        query: Dict = {
            "$or": [
                {"expires_at": None},
                {"expires_at": {"$gt": datetime.utcnow()}},
            ]
        }
        if apply_all_only:
            query["apply_all"] = True
        return await req_fsub_col.find(query).to_list(None)
    except Exception:
        return []


async def get_all_req_channels() -> List[Dict]:
    """All req channels (including expired) for display."""
    try:
        return await req_fsub_col.find().to_list(None)
    except Exception:
        return []


async def clear_all_req_channels() -> bool:
    try:
        await req_fsub_col.delete_many({})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# BOT SETTINGS
# ══════════════════════════════════════════════════════

async def get_setting(key: str, default=None):
    try:
        doc = await settings_collection.find_one({"_id": key})
        return doc["value"] if doc else default
    except Exception:
        return default

async def set_setting(key: str, value) -> bool:
    try:
        await settings_collection.update_one(
            {"_id": key},
            {"$set": {"value": value, "updated_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] set_setting: {e}")
        return False

async def get_custom_caption() -> Optional[str]:
    return await get_setting("custom_caption")
async def set_custom_caption(c: str) -> bool:
    return await set_setting("custom_caption", c)
async def get_custom_image() -> Optional[str]:
    return await get_setting("custom_image")
async def set_custom_image(i: str) -> bool:
    return await set_setting("custom_image", i)
async def delete_custom_image() -> bool:
    return await set_setting("custom_image", None)
async def get_custom_button_text() -> Optional[str]:
    return await get_setting("custom_button_text")
async def set_custom_button_text(t: str) -> bool:
    return await set_setting("custom_button_text", t)
async def is_button_hidden() -> bool:
    return bool(await get_setting("button_hidden", False))
async def set_button_hidden(h: bool) -> bool:
    return await set_setting("button_hidden", h)
async def get_second_message() -> Optional[str]:
    return await get_setting("second_message")
async def set_second_message(m) -> bool:
    return await set_setting("second_message", m)
async def is_second_message_off() -> bool:
    return bool(await get_setting("second_message_off", False))
async def set_second_message_off(o: bool) -> bool:
    return await set_setting("second_message_off", o)
async def is_forward_enabled() -> bool:
    return bool(await get_setting("forward_enabled", True))
async def set_forward_enabled(e: bool) -> bool:
    return await set_setting("forward_enabled", e)
async def get_revoke_time() -> int:
    return int(await get_setting("revoke_time", 1800))
async def set_revoke_time(s: int) -> bool:
    return await set_setting("revoke_time", s)
async def get_delete_time() -> int:
    return int(await get_setting("delete_time", 1740))
async def set_delete_time(s: int) -> bool:
    return await set_setting("delete_time", s)
async def is_fsub_enabled() -> bool:
    return bool(await get_setting("fsub_enabled", False))
async def set_fsub_enabled(e: bool) -> bool:
    return await set_setting("fsub_enabled", e)
async def get_fsub_message() -> str:
    from config import DEFAULT_FSUB_MSG
    return await get_setting("fsub_message", DEFAULT_FSUB_MSG)
async def set_fsub_message(m: str) -> bool:
    return await set_setting("fsub_message", m)
async def is_maintenance() -> bool:
    return bool(await get_setting("maintenance", False))
async def set_maintenance(o: bool) -> bool:
    return await set_setting("maintenance", o)


# ══════════════════════════════════════════════════════
# BROADCAST TRACKING
# ══════════════════════════════════════════════════════

async def save_broadcast_msgs(broadcast_id: str, msg_ids: Dict, label: str = "") -> bool:
    try:
        await broadcast_collection.update_one(
            {"_id": broadcast_id},
            {"$set": {"msg_ids": msg_ids, "label": label, "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_broadcast_msgs: {e}")
        return False

async def get_broadcast_msgs(broadcast_id: str) -> Dict:
    try:
        doc = await broadcast_collection.find_one({"_id": broadcast_id})
        return doc.get("msg_ids", {}) if doc else {}
    except Exception:
        return {}

async def get_last_broadcast_id() -> Optional[str]:
    try:
        doc = await broadcast_collection.find_one({}, sort=[("created_at", -1)])
        return doc["_id"] if doc else None
    except Exception:
        return None

async def get_all_broadcast_ids() -> List[str]:
    try:
        return [doc["_id"] async for doc in broadcast_collection.find()]
    except Exception:
        return []

async def get_all_broadcast_docs() -> List[Dict]:
    try:
        return await broadcast_collection.find().sort("created_at", -1).to_list(None)
    except Exception:
        return []

async def delete_broadcast_record(broadcast_id: str) -> bool:
    try:
        result = await broadcast_collection.delete_one({"_id": broadcast_id})
        return result.deleted_count > 0
    except Exception:
        return False

async def delete_all_broadcast_records() -> bool:
    try:
        await broadcast_collection.delete_many({})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# SAFE BROADCASTS (protected from bulk delete)
# ══════════════════════════════════════════════════════

async def save_safe_broadcast(broadcast_id: str, msg_ids: Dict, label: str = "") -> bool:
    try:
        await safe_broadcast_col.update_one(
            {"_id": broadcast_id},
            {"$set": {"msg_ids": msg_ids, "label": label, "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception as e:
        print(f"[DB] save_safe_broadcast: {e}")
        return False

async def get_safe_broadcast(broadcast_id: str) -> Optional[Dict]:
    try:
        return await safe_broadcast_col.find_one({"_id": broadcast_id})
    except Exception:
        return None

async def get_all_safe_broadcasts() -> List[Dict]:
    try:
        return await safe_broadcast_col.find().sort("created_at", -1).to_list(None)
    except Exception:
        return []

async def delete_safe_broadcast(broadcast_id: str) -> bool:
    try:
        result = await safe_broadcast_col.delete_one({"_id": broadcast_id})
        return result.deleted_count > 0
    except Exception:
        return False

async def delete_all_safe_broadcasts() -> bool:
    try:
        await safe_broadcast_col.delete_many({})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# PINNED BROADCASTS
# ══════════════════════════════════════════════════════

async def save_pbroadcast_msgs(broadcast_id: str, pinned_ids: Dict) -> bool:
    try:
        await pbroadcast_collection.update_one(
            {"_id": broadcast_id},
            {"$set": {"pinned_ids": pinned_ids, "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception:
        return False

async def get_all_pbroadcast_records() -> List[Dict]:
    try:
        return await pbroadcast_collection.find().to_list(None)
    except Exception:
        return []

async def delete_all_pbroadcast_records() -> bool:
    try:
        await pbroadcast_collection.delete_many({})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# DELAYED BROADCASTS
# ══════════════════════════════════════════════════════

async def save_dbroadcast_msgs(broadcast_id: str, msg_ids: Dict, expire_at: datetime) -> bool:
    try:
        await dbroadcast_collection.update_one(
            {"_id": broadcast_id},
            {"$set": {"msg_ids": msg_ids, "expire_at": expire_at, "created_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception:
        return False

async def get_expired_dbroadcasts() -> List[Dict]:
    try:
        return await dbroadcast_collection.find({"expire_at": {"$lte": datetime.utcnow()}}).to_list(None)
    except Exception:
        return []

async def get_all_dbroadcast_records() -> List[Dict]:
    try:
        return await dbroadcast_collection.find().to_list(None)
    except Exception:
        return []

async def delete_dbroadcast_record(broadcast_id: str) -> bool:
    try:
        result = await dbroadcast_collection.delete_one({"_id": broadcast_id})
        return result.deleted_count > 0
    except Exception:
        return False

async def delete_all_dbroadcast_records() -> bool:
    try:
        await dbroadcast_collection.delete_many({})
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# CLICK TRACKING
# ══════════════════════════════════════════════════════

clicks_collection    = _db["link_clicks"]
join_req_cache_col   = _db["join_req_cache"]   # tracks when we sent a user a req-mode invite link


async def record_click(channel_id: int, link_type: str) -> None:
    """Increment click counter. link_type: 'normal', 'request', 'direct', 'fsub'"""
    try:
        await clicks_collection.update_one(
            {"channel_id": channel_id},
            {"$inc": {f"clicks.{link_type}": 1}},
            upsert=True)
    except Exception as e:
        print(f"[DB] record_click: {e}")


async def get_channel_clicks(channel_id: int) -> Dict:
    """Returns {'normal': N, 'request': N, 'direct': N, 'fsub': N}"""
    try:
        doc = await clicks_collection.find_one({"channel_id": channel_id})
        if not doc:
            return {"normal": 0, "request": 0, "direct": 0, "fsub": 0}
        return doc.get("clicks", {"normal": 0, "request": 0, "direct": 0, "fsub": 0})
    except Exception:
        return {"normal": 0, "request": 0, "direct": 0, "fsub": 0}


async def get_all_channel_clicks() -> List[Dict]:
    """Returns list of {channel_id, clicks} sorted by total clicks desc."""
    try:
        return await clicks_collection.find().to_list(None)
    except Exception:
        return []


async def reset_channel_clicks(channel_id: int) -> bool:
    try:
        result = await clicks_collection.delete_one({"channel_id": channel_id})
        return result.deleted_count > 0
    except Exception:
        return False


# ══════════════════════════════════════════════════════
# JOIN REQUEST CACHE
# Tracks when we sent a user a request-mode invite link
# so "Try Again" doesn't loop showing the same button.
# ══════════════════════════════════════════════════════

async def record_join_req_sent(user_id: int, channel_id: int) -> None:
    """Record that we sent user a join-request invite link for this channel."""
    try:
        await join_req_cache_col.update_one(
            {"user_id": user_id, "channel_id": channel_id},
            {"$set": {"user_id": user_id, "channel_id": channel_id,
                      "sent_at": datetime.utcnow()}},
            upsert=True)
    except Exception:
        pass


async def has_join_req_cache(user_id: int, channel_id: int, max_hours: int = 24) -> bool:
    """True if we sent this user a req-mode invite link for this channel within max_hours."""
    try:
        cutoff = datetime.utcnow() - timedelta(hours=max_hours)
        doc = await join_req_cache_col.find_one({
            "user_id": user_id,
            "channel_id": channel_id,
            "sent_at": {"$gte": cutoff},
        })
        return doc is not None
    except Exception:
        return False


async def clear_join_req_cache(user_id: int, channel_id: int) -> None:
    """Remove the req cache entry once user is confirmed a member (so future leave+retry works)."""
    try:
        await join_req_cache_col.delete_one({"user_id": user_id, "channel_id": channel_id})
    except Exception:
        pass


# ══════════════════════════════════════════════════════
# DB MAINTENANCE
# ══════════════════════════════════════════════════════

async def setup_ttl_indexes() -> None:
    """Create TTL indexes so MongoDB auto-purges stale docs."""
    try:
        # join_req_cache: expire after 48 hours
        await join_req_cache_col.create_index("sent_at", expireAfterSeconds=172800)
        # user_set_passes: expire after 7 days
        await user_set_pass_col.create_index("passed_at", expireAfterSeconds=604800)
    except Exception as e:
        print(f"[DB] setup_ttl_indexes: {e}")


async def cleanup_db() -> dict:
    """Delete stale documents across all collections. Returns per-collection removed counts."""
    cutoff_30d  = datetime.utcnow() - timedelta(days=30)
    cutoff_48h  = datetime.utcnow() - timedelta(hours=48)
    cutoff_7d   = datetime.utcnow() - timedelta(days=7)
    results: dict = {}
    try:
        r = await broadcast_collection.delete_many({"created_at": {"$lt": cutoff_30d}})
        results["broadcasts"] = r.deleted_count
        r = await pbroadcast_collection.delete_many({"created_at": {"$lt": cutoff_30d}})
        results["pbroadcasts"] = r.deleted_count
        r = await dbroadcast_collection.delete_many({"created_at": {"$lt": cutoff_30d}})
        results["dbroadcasts"] = r.deleted_count
        r = await join_req_cache_col.delete_many({"sent_at": {"$lt": cutoff_48h}})
        results["join_req_cache"] = r.deleted_count
        r = await user_set_pass_col.delete_many({"passed_at": {"$lt": cutoff_7d}})
        results["set_passes"] = r.deleted_count
        # Remove invite_links cache for links older than 2 days
        inv_col = _db["invite_links"]
        r = await inv_col.delete_many({"created_at": {"$lt": cutoff_48h}})
        results["invite_links"] = r.deleted_count
    except Exception as e:
        print(f"[DB] cleanup_db: {e}")
    return results


# ══════════════════════════════════════════════════════
# FSUB SETS
# ══════════════════════════════════════════════════════

fsub_sets_col    = _db["fsub_sets"]        # {"set_id": int, "channels": [...], "limit": int}
fsub_set_cfg_col = _db["fsub_set_config"]  # global config: default_limit, set_time
user_set_pass_col= _db["user_set_passes"]  # {user_id, token_key, set_id, passed_at}


async def get_fsub_set_config() -> Dict:
    try:
        doc = await fsub_set_cfg_col.find_one({"_id": "config"})
        if not doc:
            return {"default_limit": 3, "set_time": 1800}
        return {"default_limit": doc.get("default_limit", 3), "set_time": doc.get("set_time", 1800)}
    except Exception:
        return {"default_limit": 3, "set_time": 1800}


async def set_fsub_set_config(default_limit: int = None, set_time: int = None) -> bool:
    try:
        upd = {}
        if default_limit is not None: upd["default_limit"] = default_limit
        if set_time is not None:      upd["set_time"]      = set_time
        await fsub_set_cfg_col.update_one({"_id": "config"}, {"$set": upd}, upsert=True)
        return True
    except Exception:
        return False


async def get_all_fsub_sets() -> List[Dict]:
    """Returns sets sorted by set_id ascending."""
    try:
        return await fsub_sets_col.find().sort("set_id", 1).to_list(None)
    except Exception:
        return []


async def get_fsub_set(set_id: int) -> Optional[Dict]:
    try:
        return await fsub_sets_col.find_one({"set_id": set_id})
    except Exception:
        return None


async def save_fsub_set(set_id: int, channels: List[Dict], limit: int = 3) -> bool:
    try:
        await fsub_sets_col.update_one(
            {"set_id": set_id},
            {"$set": {"set_id": set_id, "channels": channels, "limit": limit}},
            upsert=True)
        return True
    except Exception:
        return False


async def delete_fsub_set(set_id: int) -> bool:
    try:
        result = await fsub_sets_col.delete_one({"set_id": set_id})
        return result.deleted_count > 0
    except Exception:
        return False


async def get_next_set_id() -> int:
    try:
        docs = await fsub_sets_col.find().sort("set_id", -1).limit(1).to_list(1)
        return (docs[0]["set_id"] + 1) if docs else 1
    except Exception:
        return 1


async def record_set_pass(user_id: int, token_key: str, set_id: int) -> bool:
    """Record that user passed a set check for a token."""
    try:
        await user_set_pass_col.update_one(
            {"user_id": user_id, "token_key": token_key, "set_id": set_id},
            {"$set": {"passed_at": datetime.utcnow()}},
            upsert=True)
        return True
    except Exception:
        return False


async def get_set_pass_time(user_id: int, token_key: str, set_id: int) -> Optional[datetime]:
    try:
        doc = await user_set_pass_col.find_one(
            {"user_id": user_id, "token_key": token_key, "set_id": set_id})
        return doc.get("passed_at") if doc else None
    except Exception:
        return None


async def is_set_pass_valid(user_id: int, token_key: str, set_id: int, grace_seconds: int = 1800) -> bool:
    """True if user passed this set within grace_seconds."""
    t = await get_set_pass_time(user_id, token_key, set_id)
    if not t:
        return False
    return (datetime.utcnow() - t).total_seconds() < grace_seconds


# ══════════════════════════════════════════════════════
# REQ SETS  (promo force-sub sets — fsublink tokens only)
# Mirror of fsub_sets but stored separately and tracked
# with namespace key "rss:{token}" in user_set_pass_col.
# ══════════════════════════════════════════════════════

req_sets_col    = _db["req_sets"]
req_set_cfg_col = _db["req_set_config"]


async def get_req_set_config() -> Dict:
    try:
        doc = await req_set_cfg_col.find_one({"_id": "config"})
        if not doc:
            return {"default_limit": 3, "set_time": 1800, "enabled": False, "scope": "fsublink"}
        return {
            "default_limit": doc.get("default_limit", 3),
            "set_time":      doc.get("set_time", 1800),
            "enabled":       doc.get("enabled", False),
            "scope":         doc.get("scope", "fsublink"),   # "fsublink" | "all"
        }
    except Exception:
        return {"default_limit": 3, "set_time": 1800, "enabled": False, "scope": "fsublink"}


async def set_req_set_config(
    default_limit: int  = None,
    set_time:      int  = None,
    enabled:       bool = None,
    scope:         str  = None,
) -> bool:
    try:
        upd = {}
        if default_limit is not None: upd["default_limit"] = default_limit
        if set_time      is not None: upd["set_time"]      = set_time
        if enabled       is not None: upd["enabled"]       = enabled
        if scope         is not None: upd["scope"]         = scope
        await req_set_cfg_col.update_one({"_id": "config"}, {"$set": upd}, upsert=True)
        return True
    except Exception:
        return False


async def get_all_req_sets() -> List[Dict]:
    try:
        return await req_sets_col.find().sort("set_id", 1).to_list(None)
    except Exception:
        return []


async def get_req_set(set_id: int) -> Optional[Dict]:
    try:
        return await req_sets_col.find_one({"set_id": set_id})
    except Exception:
        return None


async def save_req_set(set_id: int, channels: List[Dict], limit: int = 3) -> bool:
    try:
        await req_sets_col.update_one(
            {"set_id": set_id},
            {"$set": {"set_id": set_id, "channels": channels, "limit": limit}},
            upsert=True)
        return True
    except Exception:
        return False


async def delete_req_set(set_id: int) -> bool:
    try:
        result = await req_sets_col.delete_one({"set_id": set_id})
        return result.deleted_count > 0
    except Exception:
        return False


async def get_next_req_set_id() -> int:
    try:
        docs = await req_sets_col.find().sort("set_id", -1).limit(1).to_list(1)
        return (docs[0]["set_id"] + 1) if docs else 1
    except Exception:
        return 1


# ══════════════════════════════════════════════════════
# ANALYTICS HELPERS
# ══════════════════════════════════════════════════════

async def get_total_clicks_summary() -> Dict:
    """Returns aggregated {request, normal, direct, fsub} totals across all channels."""
    try:
        docs = await clicks_collection.find().to_list(None)
        summary = {"request": 0, "normal": 0, "direct": 0, "fsub": 0}
        for doc in docs:
            c = doc.get("clicks", {})
            for key in summary:
                summary[key] += c.get(key, 0)
        return summary
    except Exception:
        return {"request": 0, "normal": 0, "direct": 0, "fsub": 0}


async def get_user_growth_stats(days: int = 7) -> Dict:
    """
    Returns:
      today, yesterday, this_week, this_month counts of new users,
      plus daily_breakdown list [{"date": "Mon 19", "count": N}, ...] for `days` days.
    """
    try:
        now   = datetime.utcnow()
        today_start     = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        week_start      = today_start - timedelta(days=7)
        month_start     = today_start - timedelta(days=30)

        today_count     = await user_data.count_documents({"created_at": {"$gte": today_start}})
        yesterday_count = await user_data.count_documents({
            "created_at": {"$gte": yesterday_start, "$lt": today_start}})
        week_count      = await user_data.count_documents({"created_at": {"$gte": week_start}})
        month_count     = await user_data.count_documents({"created_at": {"$gte": month_start}})

        # Daily breakdown for the last `days` days
        breakdown = []
        for i in range(days - 1, -1, -1):
            day_start = today_start - timedelta(days=i)
            day_end   = day_start   + timedelta(days=1)
            count     = await user_data.count_documents({
                "created_at": {"$gte": day_start, "$lt": day_end}})
            label = day_start.strftime("%a %d")
            breakdown.append({"date": label, "count": count})

        return {
            "today":           today_count,
            "yesterday":       yesterday_count,
            "this_week":       week_count,
            "this_month":      month_count,
            "daily_breakdown": breakdown,
        }
    except Exception as e:
        print(f"[DB] get_user_growth_stats: {e}")
        return {
            "today": 0, "yesterday": 0,
            "this_week": 0, "this_month": 0,
            "daily_breakdown": [],
        }
