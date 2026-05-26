# plugins/join_events.py — Event-driven join request & membership tracking
#
# Uses on_chat_join_request (fires the instant a user taps "Request to Join")
# and on_chat_member_updated (fires when membership status changes) to keep
# the join-request cache accurate without any polling.
#
# This replaces the old has_pending_join_request() polling approach for real-time
# detection and ensures the "I Joined — Check Again" flow works reliably.

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatMemberUpdated, ChatJoinRequest

from miko import Bot
from database.database import record_join_req_sent, clear_join_req_cache


@Bot.on_chat_join_request()
async def handle_join_request(client: Client, join_request: ChatJoinRequest):
    """
    Fires the moment a user submits a join request to any channel/group
    where the bot is admin with Invite Users permission.
    Records the event so the membership check in check_fsub_sets /
    check_req_sets can detect it immediately without polling.
    """
    chat_id = join_request.chat.id
    user_id = join_request.from_user.id
    await record_join_req_sent(user_id, chat_id)


@Bot.on_chat_member_updated()
async def handle_member_updated(client: Client, update: ChatMemberUpdated):
    """
    Fires when a user's membership status changes in any chat the bot monitors.
    Clears the join-request cache when a user leaves or is banned so that a
    returning user is re-prompted to join rather than being waved through on a
    stale cached entry.
    """
    new = update.new_chat_member
    if not new:
        return

    if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
        user_id = new.user.id
        chat_id = update.chat.id
        await clear_join_req_cache(user_id, chat_id)
