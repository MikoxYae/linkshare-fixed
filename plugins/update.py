# plugins/update.py — /update and /cleandb commands
import asyncio
import os
import re
import sys
import subprocess

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from miko import Bot
from config import OWNER_ID
from database.database import cleanup_db


def _get_authenticated_remote() -> str | None:
    """
    Build an authenticated remote URL using GITHUB_TOKEN from env.
    Falls back to the existing origin URL (which may already have a token).
    Returns None if we can't build one.
    """
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        raw_url = result.stdout.strip()
    except Exception:
        raw_url = ""

    if not raw_url:
        return None

    # Strip any existing credentials from the URL
    clean_url = re.sub(r"https://[^@]+@", "https://", raw_url)

    if token:
        # Inject the fresh token
        return clean_url.replace("https://", f"https://{token}@")

    # No token — return the original URL as-is (works for public repos or
    # repos where the remote already contains a valid token)
    return raw_url


@Bot.on_message(filters.command("update") & filters.user(OWNER_ID))
async def cmd_update(client, message: Message):
    msg = await message.reply_text(
        "<blockquote>🔄 <b>Pulling latest changes from GitHub...</b></blockquote>",
        parse_mode=ParseMode.HTML,
    )

    remote_url = _get_authenticated_remote()
    if not remote_url:
        return await msg.edit_text(
            "<blockquote>❌ <b>Could not determine git remote URL.</b>\n\n"
            "Make sure the bot directory is a git repo with an <code>origin</code> remote.</blockquote>",
            parse_mode=ParseMode.HTML,
        )

    bot_dir = os.path.dirname(os.path.dirname(__file__))

    try:
        proc = subprocess.run(
            ["git", "pull", remote_url, "main"],
            capture_output=True, text=True, timeout=60, cwd=bot_dir,
        )
        # Scrub token from output before showing to user
        token = os.environ.get("GITHUB_TOKEN", "")
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        if token:
            stdout = stdout.replace(token, "***")
            stderr = stderr.replace(token, "***")

        output = stdout + ("\n" + stderr if stderr else "")
        output = output[:2000] if output else "(no output)"

        if proc.returncode == 0:
            await msg.edit_text(
                f"<blockquote>✅ <b>Update successful!</b>\n\n"
                f"<code>{output}</code>\n\n"
                f"♻️ Bot restarting in 3 seconds...</blockquote>",
                parse_mode=ParseMode.HTML,
            )
            await asyncio.sleep(3)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            await msg.edit_text(
                f"<blockquote>❌ <b>git pull failed!</b>\n\n<code>{output}</code></blockquote>",
                parse_mode=ParseMode.HTML,
            )
    except subprocess.TimeoutExpired:
        await msg.edit_text(
            "<blockquote>❌ <b>git pull timed out (60s)</b></blockquote>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await msg.edit_text(
            f"<blockquote>❌ <b>Error:</b> <code>{e}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )


@Bot.on_message(filters.command("cleandb") & filters.user(OWNER_ID))
async def cmd_cleandb(client, message: Message):
    msg = await message.reply_text(
        "<blockquote>🧹 <b>Cleaning MongoDB...</b></blockquote>",
        parse_mode=ParseMode.HTML,
    )
    try:
        results = await cleanup_db()
        lines = [f"• {k}: <b>{v}</b> removed" for k, v in results.items()]
        total = sum(results.values())
        text = (
            f"<blockquote>✅ <b>DB Cleanup Complete</b>\n\n"
            + "\n".join(lines)
            + f"\n\n<b>Total removed:</b> {total} documents</blockquote>"
        )
        await msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(
            f"<blockquote>❌ <b>Cleanup failed:</b> <code>{e}</code></blockquote>",
            parse_mode=ParseMode.HTML,
        )
