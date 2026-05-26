<div align="center">

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

<img src="https://i.imgur.com/Nfv1fdQ.jpeg" width="420">

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

# 🔗 ᴄʀᴜɴᴄʜʏʀᴏʟʟ ʟɪɴᴋ ᴘʀᴏᴠɪᴅᴇʀ ʙᴏᴛ

<p>
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Pyrogram-Fork-0088CC?style=for-the-badge&logo=telegram&logoColor=white">
  <img src="https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white">
  <img src="https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge">
  <img src="https://img.shields.io/badge/Status-Active-00C853?style=for-the-badge">
</p>

**A feature-rich Telegram bot for sharing anime channel invite links with advanced Force Subscribe, broadcast, analytics, and admin management.**

</div>

---

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

## 📌 ғᴇᴀᴛᴜʀᴇs

<details>
<summary><b>🔗 Link Management & Delivery</b></summary>
<br>

> Generate and deliver secure, time-limited Telegram invite links with full control over format, expiry, and style.

| Feature | Detail |
|---------|--------|
| **3 Link Modes** | Normal · Request · Direct |
| **Auto-Revoke** | Links expire after configurable time (default 30 min) |
| **Auto-Delete** | Messages auto-deleted after delivery timer |
| **Forward Lock** | Protect messages from being forwarded |
| **Custom Caption** | Use `[link]` placeholder anywhere in caption |
| **Custom Image** | Set your own thumbnail for link messages |
| **Custom Button** | Fully customizable join button text |
| **Second Message** | Optional follow-up note after link delivery |
| **Get Again Button** | Auto-appears when link is about to expire |
| **URL Encoding** | Links encoded with base64 — safe & clean |

**Commands:**
```
/addchannel   — Add a channel to the bot
/delchannel   — Remove a channel
/channels     — List all added channels
/genlink      — Generate a shareable bot link
/search       — Search channels by name
```

</details>

---

<details>
<summary><b>🛡️ Force Subscribe — Set System</b></summary>
<br>

> A multi-set cascade force-subscribe system. Users must join all channels in a set before receiving their link. Sets process in order with per-set grace timers.

**How it works:**

```
User clicks link
      │
      ▼
Check Set 01 channels ──► Not all joined? ──► Show join buttons for ALL unjoined channels
      │
      ▼ (all joined)
Grace timer starts (default 30 min)
      │
      ▼ (grace active = next visit)
Link delivered directly ✅
      │
      ▼ (grace expired)
Re-check Set 01 membership ──► Left? ──► Must rejoin
      │
      ▼ (still joined)
Check Set 02 ──► and so on...
```

| Feature | Detail |
|---------|--------|
| **Multiple Sets** | Unlimited sets (Set 01, Set 02, Set 03...) |
| **Per-Set Channels** | Default 3 channels/set, configurable up to 15 |
| **Grace Timer** | Configurable per bot (default 30 min) |
| **Leave Detection** | Users who leave get caught on next visit after grace |
| **Request Mode** | `📨` Channel join requires admin approval |
| **Direct Mode** | `⚡` Channel join is instant |
| **All Channels Shown** | All unjoined channels shown at once — none hidden |
| **Named Buttons** | Buttons show actual channel name |
| **Request Cache** | Fast DB cache for pending requests (no slow API scan) |
| **Fail-safe** | If DB is unreachable, force-sub stays ON |

**Commands:**
```
/fsubsets     — Open force sub manager (add sets, channels, configure)
/settime      — Change global grace time duration
/default_limit — Change default channels per set
/approveon    — Enable auto-approve for request-mode channels
/approveoff   — Disable auto-approve
```

</details>

---

<details>
<summary><b>📢 Broadcast System</b></summary>
<br>

> Send messages to all bot users with multiple broadcast modes — safe, batch, database, and pending broadcasts with full control.

| Mode | Description |
|------|-------------|
| **Normal Broadcast** | Send any message to all users |
| **Safe Broadcast** | Skips blocked/deleted accounts automatically |
| **Database Broadcast** | Forward a stored message to all users |
| **Batch Broadcast** | Send multiple messages in sequence |
| **Pending Broadcast** | Schedule & manage queued broadcasts |

**Smart Features:**
- ✅ Real-time progress tracking
- ✅ Cancel any ongoing broadcast mid-way
- ✅ Delete all sent broadcast messages at once
- ✅ Blocked user auto-detection & skip
- ✅ Batch management with done/cancel controls

**Commands:**
```
/broadcast         — Broadcast to all users
/safebroadcasts    — Safe broadcast (auto-skips blocked users)
/dbroadcast        — Database/forward broadcast
/batchbroadcast    — Multi-message batch broadcast
/pbroadcast        — View pending broadcasts
/delbroadcast      — Delete a specific broadcast
/delallbroadcast   — Delete all broadcast messages
/cancel            — Cancel ongoing broadcast
/done              — Mark broadcast as done
```

</details>

---

<details>
<summary><b>📊 Analytics & Statistics</b></summary>
<br>

> Track every click, user, and link with detailed analytics and visual graphs.

| Metric | Description |
|--------|-------------|
| **Click Tracking** | Every link click recorded with timestamp |
| **Per-Link Stats** | Individual click count per channel link |
| **Top Links** | Leaderboard of most-clicked links |
| **User Stats** | Total users, active users, growth |
| **Bot Uptime** | Live uptime since last restart |
| **Graph View** | Visual bar/line graph of activity |
| **Detailed Analytics** | Full breakdown by time period |

**Commands:**
```
/stats        — Bot overview (users, uptime, clicks)
/userstats    — Detailed user statistics
/analytics    — Full analytics report
/graph        — Visual activity graph
/clicks       — All link click counts
/click        — Click count for a specific link
/toplinks     — Top clicked links leaderboard
```

</details>

---

<details>
<summary><b>⚙️ Customization</b></summary>
<br>

> Customize every message, image, and button the bot sends — no code editing required.

| Setting | Default | Changeable |
|---------|---------|------------|
| Start Message | Bot intro text | ✅ |
| Help Message | Support info | ✅ |
| Start Image | Bot banner | ✅ |
| Link Image | Link delivery photo | ✅ |
| Button Text | Join button label | ✅ |
| Caption | Link message text | ✅ |
| Second Message | Follow-up note | ✅ |
| Forward Lock | Protect content | ✅ |
| Second Message Toggle | Show/hide | ✅ |
| Button Visibility | Show/hide button | ✅ |

**Commands:**
```
/customize    — Open customization panel (interactive buttons)
```

> All settings changed live — no restart needed.

</details>

---

<details>
<summary><b>👑 Admin Management</b></summary>
<br>

> Multi-level admin system with owner and admin roles. Full control over who can manage the bot.

| Role | Permissions |
|------|------------|
| **Owner** | Full access — all commands, cannot be removed |
| **Admin** | All management commands except owner-only |

**Features:**
- ✅ Add unlimited admins
- ✅ Remove admins instantly
- ✅ List all current admins
- ✅ Maintenance mode — block all regular users
- ✅ Owner gets error logs in DM automatically
- ✅ Admin check on all sensitive commands

**Commands:**
```
/addadmin     — Add a new admin (reply to user or send ID)
/deladmin     — Remove an admin
/admins       — List all current admins
/maintenance  — Toggle maintenance mode on/off
/ping         — Check bot response time
/status       — Full bot status & uptime
/cmds         — Show all available commands
```

</details>

---

<details>
<summary><b>🗄️ Database & System</b></summary>
<br>

> MongoDB-powered database with auto-cleanup, TTL indexes, backup support, and health monitoring.

| Feature | Detail |
|---------|--------|
| **Auto TTL Cleanup** | Join req cache: 48h · Set passes: 7 days |
| **Backup** | Export DB snapshot on demand |
| **Clean DB** | Remove stale/orphan entries |
| **Web Keep-Alive** | Built-in aiohttp server for uptime monitoring |
| **Error DM** | Bot errors forwarded to owner DM automatically |
| **Multi-Worker** | Configurable Pyrogram workers (default 40) |

**Commands:**
```
/backup       — Backup database
/cleandb      — Remove stale database entries
/update       — Pull latest bot update
```

</details>

---

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

## 🚀 Setup

### Requirements
- Python 3.11+
- MongoDB Atlas (or local MongoDB)
- Telegram API credentials → [my.telegram.org](https://my.telegram.org)
- Bot token → [@BotFather](https://t.me/BotFather)

### Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `TG_BOT_TOKEN` | ✅ | Bot Token from @BotFather |
| `APP_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `OWNER_ID` | ✅ | Your Telegram User ID |
| `ADMINS` | ✅ | Space-separated admin IDs |
| `DB_URI` | ✅ | MongoDB connection URI |
| `DB_NAME` | ✅ | Database name (default: `crunchyroll_bot`) |
| `DATABASE_CHANNEL` | ✅ | Telegram channel ID for DB storage |
| `CHAT_ID` | ⬜ | Force-sub channel IDs |
| `PORT` | ⬜ | Web server port (default: `8000`) |
| `REVOKE_TIME` | ⬜ | Link expiry in seconds (default: `1800`) |
| `DELETE_TIME` | ⬜ | Message delete delay in seconds (default: `1740`) |
| `TG_BOT_WORKERS` | ⬜ | Pyrogram workers (default: `40`) |

### Installation

```bash
git clone https://github.com/MikoxYae/linkshare-fixed
cd linkshare-fixed
pip install -r requirements.txt
python main.py
```

### Requirements File
```
pyrofork
TgCrypto
pyromod
python-dotenv
pymongo
dnspython
motor
aiohttp
asyncio
aiofiles
psutil
```

---

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

## 🐛 Bug Fixes (vs Original)

| # | Bug | Status | Fix Applied |
|---|-----|:------:|-------------|
| 1 | FSub reject message never auto-deleted | ✅ Fixed | `delete_after_delay` added to fsub rejection |
| 2 | Grace expires → user permanently free | ✅ Fixed | Full re-check on every grace expiry |
| 3 | User leaves channel — bot doesn't detect | ✅ Fixed | Membership re-verified after grace instead of skipping |
| 4 | Only 1 channel shown (others silently dropped) | ✅ Fixed | `⚠️` fallback button — all channels always visible |
| 5 | Slow join-request check (iterates ALL requests) | ✅ Fixed | Replaced with fast O(1) DB cache lookup |
| 6 | DB failure silently bypasses force-sub | ✅ Fixed | Fail-safe: fsub enforced if DB unreachable |
| 7 | Admin sessions never expire — memory leak | ✅ Fixed | TTL cleanup added (10 min auto-expiry) |
| 8 | Misleading `failed_set_id` variable name | ✅ Fixed | Renamed to `completed_set_id` |
| 9 | `bot.py` filename | ✅ Fixed | Renamed to `miko.py` throughout |

---

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

## 👨‍💻 Credits

<div align="center">

| Role | Contact |
|------|---------|
| 🔨 Original Developer | [@World_Fastest_Bots](https://t.me/World_Fastest_Bots) |
| 🛠️ Bug Fixes & Maintenance | [@MikoxYae](https://github.com/MikoxYae) |
| 📺 Anime Channel | [@CrunchyRollChannel](https://t.me/Crunchyrollchannel) |
| 💬 Support | [@CrunchyRollHelper](https://t.me/CrunchyRollHelper) |

<br>

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

**⭐ Star this repo if it helped you!**

<img src="https://img.shields.io/github/stars/MikoxYae/linkshare-fixed?style=social">

</div>
