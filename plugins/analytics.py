# plugins/analytics.py — /analytics, /toplinks, /graph, /userstats (admin)
import asyncio
from datetime import datetime, timedelta, timezone

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from miko import Bot
from database.database import (
    count_users, count_channels, get_all_channel_clicks,
    get_channel_doc, get_channels,
    get_user_growth_stats, get_total_clicks_summary,
)
from helper_func import is_owner_or_admin, get_readable_time


# ─── /analytics ───────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("analytics") & is_owner_or_admin)
async def cmd_analytics(client, message: Message):
    loading = await message.reply_text("📊 Gathering analytics...", parse_mode=ParseMode.HTML)

    total_users    = await count_users()
    total_channels = await count_channels()
    clicks_summary = await get_total_clicks_summary()
    growth         = await get_user_growth_stats()

    total_clicks   = (
        clicks_summary.get("request", 0)
        + clicks_summary.get("normal", 0)
        + clicks_summary.get("direct", 0)
    )

    now = datetime.now()
    delta = now - client.uptime
    uptime_str = get_readable_time(int(delta.total_seconds()))

    text = (
        "<b>╔══════════════════════════════╗\n"
        "║      📊 BOT ANALYTICS        ║\n"
        "╚══════════════════════════════╝</b>\n\n"
        "<b>👥 Users</b>\n"
        f"┣ Total:      <code>{total_users:,}</code>\n"
        f"┣ Today:      <code>{growth.get('today', 0):,}</code>\n"
        f"┣ This Week:  <code>{growth.get('this_week', 0):,}</code>\n"
        f"┗ This Month: <code>{growth.get('this_month', 0):,}</code>\n\n"
        "<b>📺 Channels</b>\n"
        f"┗ Total: <code>{total_channels:,}</code>\n\n"
        "<b>🔗 Link Clicks (All Time)</b>\n"
        f"┣ 📨 Request: <code>{clicks_summary.get('request', 0):,}</code>\n"
        f"┣ 🌐 Normal:  <code>{clicks_summary.get('normal', 0):,}</code>\n"
        f"┣ ⚡ Direct:  <code>{clicks_summary.get('direct', 0):,}</code>\n"
        f"┗ 🔢 Total:   <code>{total_clicks:,}</code>\n\n"
        f"<b>⏱ Uptime:</b> <code>{uptime_str}</code>"
    )

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close")]])
    await loading.delete()
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


# ─── /toplinks ────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("toplinks") & is_owner_or_admin)
async def cmd_toplinks(client, message: Message):
    loading = await message.reply_text("🔝 Loading top links...", parse_mode=ParseMode.HTML)

    all_clicks = await get_all_channel_clicks()
    if not all_clicks:
        await loading.delete()
        return await message.reply_text(
            "<b>📊 No click data yet.</b>", parse_mode=ParseMode.HTML)

    # Sort by total clicks descending
    def total(doc):
        c = doc.get("clicks", {})
        return c.get("request", 0) + c.get("normal", 0) + c.get("direct", 0)

    ranked = sorted(all_clicks, key=total, reverse=True)[:10]

    lines = [
        "<b>╔══════════════════════════════════╗</b>",
        "<b>║       🔝 TOP USED LINKS          ║</b>",
        "<b>╚══════════════════════════════════╝</b>\n",
    ]

    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7

    for rank, doc in enumerate(ranked):
        ch_id  = doc.get("channel_id")
        ch_doc = await get_channel_doc(ch_id) if ch_id else None
        name   = (ch_doc.get("anime_name", str(ch_id)) if ch_doc else str(ch_id))[:20]
        c      = doc.get("clicks", {})
        req    = c.get("request", 0)
        norm   = c.get("normal", 0)
        direct = c.get("direct", 0)
        ttl    = req + norm + direct

        lines.append(
            f"{medals[rank]} <b>{rank+1}.</b> {name}\n"
            f"   📨<code>{req}</code> 🌐<code>{norm}</code> ⚡<code>{direct}</code>  "
            f"[Total: <b>{ttl}</b>]"
        )

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close")]])
    await loading.delete()
    await message.reply_text(
        "\n".join(lines), reply_markup=markup, parse_mode=ParseMode.HTML)


# ─── /graph ───────────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("graph") & is_owner_or_admin)
async def cmd_graph(client, message: Message):
    loading = await message.reply_text("📈 Building usage graph...", parse_mode=ParseMode.HTML)

    growth = await get_user_growth_stats(days=7)
    daily  = growth.get("daily_breakdown", [])

    if not daily:
        await loading.delete()
        return await message.reply_text(
            "<b>📈 Not enough data yet.</b>", parse_mode=ParseMode.HTML)

    max_val = max((d["count"] for d in daily), default=1) or 1
    bar_w   = 12

    lines = [
        "<b>╔══════════════════════════════╗</b>",
        "<b>║    📈 USER GROWTH (7 DAYS)   ║</b>",
        "<b>╚══════════════════════════════╝</b>\n",
    ]

    for d in daily:
        label  = d["date"]           # "Mon 19"
        count  = d["count"]
        filled = round((count / max_val) * bar_w)
        bar    = "█" * filled + "░" * (bar_w - filled)
        lines.append(f"<code>{label:6s} │{bar}│ {count}</code>")

    all_clicks  = await get_all_channel_clicks()
    total_req   = sum(d.get("clicks", {}).get("request", 0) for d in all_clicks)
    total_norm  = sum(d.get("clicks", {}).get("normal",  0) for d in all_clicks)
    total_dir   = sum(d.get("clicks", {}).get("direct",  0) for d in all_clicks)
    grand_total = total_req + total_norm + total_dir

    if grand_total:
        lines += [
            "\n<b>🔗 Click Distribution</b>",
            f"<code>📨 Req  │{'█' * round((total_req  / grand_total) * bar_w)}{'░' * (bar_w - round((total_req  / grand_total) * bar_w))}│ {total_req}</code>",
            f"<code>🌐 Norm │{'█' * round((total_norm / grand_total) * bar_w)}{'░' * (bar_w - round((total_norm / grand_total) * bar_w))}│ {total_norm}</code>",
            f"<code>⚡ Dir  │{'█' * round((total_dir  / grand_total) * bar_w)}{'░' * (bar_w - round((total_dir  / grand_total) * bar_w))}│ {total_dir}</code>",
        ]

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close")]])
    await loading.delete()
    await message.reply_text(
        "\n".join(lines), reply_markup=markup, parse_mode=ParseMode.HTML)


# ─── /userstats ───────────────────────────────────────────────────────────────

@Bot.on_message(filters.command("userstats") & is_owner_or_admin)
async def cmd_userstats(client, message: Message):
    loading = await message.reply_text("👥 Fetching user stats...", parse_mode=ParseMode.HTML)

    total  = await count_users()
    growth = await get_user_growth_stats(days=30)

    today       = growth.get("today",      0)
    this_week   = growth.get("this_week",  0)
    this_month  = growth.get("this_month", 0)
    yesterday   = growth.get("yesterday",  0)
    daily_avg   = round(this_month / 30, 1) if this_month else 0.0

    # Growth trend arrow
    trend = "📈" if today >= yesterday else ("📉" if today < yesterday else "➡️")

    # Retention bar: % who joined in last 7 days out of last 30
    weekly_of_monthly = f"{round(this_week / this_month * 100)}%" if this_month else "N/A"

    text = (
        "<b>╔══════════════════════════════╗\n"
        "║    👥 USER STATISTICS        ║\n"
        "╚══════════════════════════════╝</b>\n\n"
        f"<b>📌 Total Users:</b> <code>{total:,}</code>\n\n"
        "<b>📅 New Users</b>\n"
        f"┣ Today:      <code>{today:,}</code>  {trend}\n"
        f"┣ Yesterday:  <code>{yesterday:,}</code>\n"
        f"┣ This Week:  <code>{this_week:,}</code>\n"
        f"┣ This Month: <code>{this_month:,}</code>\n"
        f"┗ Daily Avg (30d): <code>{daily_avg}</code>\n\n"
        f"<b>📊 7-Day Share of 30-Day:</b> <code>{weekly_of_monthly}</code>\n\n"
        "<b>📋 Daily Breakdown (Last 7 Days)</b>"
    )

    daily = growth.get("daily_breakdown", [])
    for d in daily:
        text += f"\n  <code>{d['date']:6s}  {d['count']:>4}</code>"

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Close", callback_data="close")]])
    await loading.delete()
    await message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)
