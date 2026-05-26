import asyncio
import logging
import traceback
from datetime import datetime
from pyrogram import Client
from pyrogram.enums import ParseMode
from config import API_HASH, APP_ID, LOGGER, TG_BOT_TOKEN, TG_BOT_WORKERS, PORT, OWNER_ID
from plugins import web_server
from aiohttp import web
import pyrogram.utils

pyrogram.utils.MIN_CHANNEL_ID = -1009147483647


class _OwnerDMHandler(logging.Handler):
    """Forwards ERROR+ log records to the owner's DM as blockquote messages."""

    def __init__(self, bot):
        super().__init__(level=logging.ERROR)
        self._bot = bot

    def emit(self, record):
        try:
            msg = self.format(record)
            asyncio.create_task(self._send(msg))
        except Exception:
            pass

    async def _send(self, text: str):
        try:
            safe = text[:3500]
            await self._bot.send_message(
                chat_id=OWNER_ID,
                text=f"<blockquote>⚠️ <b>Bot Error / Log</b>\n\n<code>{safe}</code></blockquote>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="CrunchyrollLinkBot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={"root": "plugins"},
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN,
        )
        self.LOGGER = LOGGER
        self._owner_log_handler: _OwnerDMHandler | None = None

    async def start(self, *args, **kwargs):
        await super().start()
        me = await self.get_me()
        self.uptime = datetime.now()
        self.username = me.username

        # Set up owner-DM error logging
        self._owner_log_handler = _OwnerDMHandler(self)
        fmt = logging.Formatter("%(levelname)s [%(name)s]: %(message)s")
        self._owner_log_handler.setFormatter(fmt)
        logging.getLogger().addHandler(self._owner_log_handler)

        # Set up TTL indexes for automatic MongoDB cleanup
        try:
            from database.database import setup_ttl_indexes
            await setup_ttl_indexes()
        except Exception as e:
            self.LOGGER(__name__).warning(f"TTL index setup failed: {e}")

        try:
            await self.send_message(
                chat_id=OWNER_ID,
                text="<b><blockquote>🤖 Crunchyroll Link Provider Bot Restarted ♻️</blockquote></b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            self.LOGGER(__name__).warning(f"Failed to notify owner: {e}")

        self.set_parse_mode(ParseMode.HTML)
        self.LOGGER(__name__).info("✅ Bot is running!")

        # Start web keep-alive server
        try:
            app = web.AppRunner(await web_server())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", PORT).start()
            self.LOGGER(__name__).info(f"🌐 Web server started on port {PORT}")
        except Exception as e:
            self.LOGGER(__name__).error(f"Web server failed: {e}")

    async def stop(self, *args):
        if self._owner_log_handler:
            logging.getLogger().removeHandler(self._owner_log_handler)
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")


if __name__ == "__main__":
    Bot().run()
