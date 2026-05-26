# plugins/admin.py — Admin management
import asyncio
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from miko import Bot
from config import OWNER_ID
from database.database import add_admin, remove_admin, list_admins
from helper_func import is_owner_or_admin, cq_owner_or_admin

PAGE_SIZE = 8


@Bot.on_message(filters.command("admins") & filters.user(OWNER_ID))
async def cmd_admins(client, message: Message):
    admins = await list_admins()
    await _send_admins_page(client, message, admins, page=0)


async def _send_admins_page(client, message, admins, page, edit=False):
    total_pages = max(1, (len(admins) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    chunk = admins[start: start + PAGE_SIZE]
    buttons = []
    for uid in chunk:
        try:
            user = await client.get_users(uid)
            label = user.first_name or str(uid)
        except Exception:
            label = str(uid)
        buttons.append([InlineKeyboardButton(label, callback_data=f"admin_info:{uid}:{page}")])
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("Prev", callback_data=f"admin_page:{page-1}"))
    nav_row.append(InlineKeyboardButton("+ Add Admin", callback_data="admin_add"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next", callback_data=f"admin_page:{page+1}"))
    buttons.append(nav_row)
    markup = InlineKeyboardMarkup(buttons)
    header = f"<b>Admin List</b> — Page {page+1}/{total_pages}"
    if edit:
        await message.edit_text(header, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(header, reply_markup=markup, parse_mode=ParseMode.HTML)


@Bot.on_callback_query(filters.regex(r"^admin_page:(\d+)$") & cq_owner_or_admin)
async def cb_admin_page(client, query: CallbackQuery):
    page = int(query.data.split(":")[1])
    admins = await list_admins()
    await _send_admins_page(client, query.message, admins, page=page, edit=True)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^admin_info:(-?\d+):(\d+)$") & cq_owner_or_admin)
async def cb_admin_info(client, query: CallbackQuery):
    parts = query.data.split(":")
    uid = int(parts[1])
    page = int(parts[2])
    try:
        user = await client.get_users(uid)
        name = user.first_name or "N/A"
        username = f"@{user.username}" if user.username else "N/A"
    except Exception:
        name = "Unknown"
        username = "N/A"
    text = f"<b>Admin Info</b>\n\n<b>Name:</b> {name}\n<b>ID:</b> <code>{uid}</code>\n<b>Username:</b> {username}"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Remove Admin", callback_data=f"admin_remove:{uid}:{page}")],
        [InlineKeyboardButton("Back", callback_data=f"admin_page:{page}")],
    ])
    await query.edit_message_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
    await query.answer()


@Bot.on_callback_query(filters.regex(r"^admin_remove:(-?\d+):(\d+)$") & cq_owner_or_admin)
async def cb_admin_remove(client, query: CallbackQuery):
    parts = query.data.split(":")
    uid = int(parts[1])
    page = int(parts[2])
    success = await remove_admin(uid)
    await query.answer("Removed!" if success else "Failed.", show_alert=True)
    admins = await list_admins()
    page = min(page, max(0, (len(admins) - 1) // PAGE_SIZE))
    await _send_admins_page(client, query.message, admins, page=page, edit=True)


@Bot.on_callback_query(filters.regex("^admin_add$") & cq_owner_or_admin)
async def cb_admin_add_prompt(client, query: CallbackQuery):
    await query.answer()
    client._pending_add_admin = query.from_user.id
    await query.edit_message_text(
        "<b>Add Admin</b>\n\nSend the User ID of the new admin.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="admin_page:0")]]),
        parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("addadmin") & filters.user(OWNER_ID))
async def cmd_addadmin(client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/addadmin user_id</code>", parse_mode=ParseMode.HTML)
    uid = int(message.command[1])
    if await add_admin(uid):
        await message.reply_text(f"User <code>{uid}</code> added as admin.", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"Failed to add <code>{uid}</code>.", parse_mode=ParseMode.HTML)


@Bot.on_message(filters.command("deladmin") & filters.user(OWNER_ID))
async def cmd_deladmin(client, message: Message):
    if len(message.command) != 2 or not message.command[1].lstrip("-").isdigit():
        return await message.reply_text("Usage: <code>/deladmin user_id</code>", parse_mode=ParseMode.HTML)
    uid = int(message.command[1])
    if await remove_admin(uid):
        await message.reply_text(f"User <code>{uid}</code> removed from admins.", parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(f"Admin <code>{uid}</code> not found.", parse_mode=ParseMode.HTML)
