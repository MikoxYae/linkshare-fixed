<div align="center">

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

<img src="https://i.imgur.com/Nfv1fdQ.jpeg" width="420">

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

# 🔗 Crunchyroll Link Provider Bot

<p>
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/Pyrogram-Fork-green?style=for-the-badge&logo=telegram">
  <img src="https://img.shields.io/badge/MongoDB-Database-brightgreen?style=for-the-badge&logo=mongodb">
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge">
</p>

<p><i>A powerful Telegram bot that provides anime channel invite links with advanced Force Subscribe, analytics, and admin management features.</i></p>

</div>

---

<details>
<summary><b>📌 ғᴇᴀᴛᴜʀᴇs :</b></summary>

<br>

### 🔗 Link Management
- Generate secure, time-limited invite links for Telegram channels
- Support for **Normal**, **Request**, and **Direct** link modes
- Auto-revoke links after set time (configurable)
- Auto-delete messages after delivery
- Custom captions, images, and button text
- Forward protection toggle

### 🛡 Force Subscribe — Set System
- Multi-set force subscribe system (Set 01, Set 02, ...)
- Each set supports multiple channels (default limit: 3, fully configurable)
- **Grace time** — user gets a free window after joining (default: 30 min)
- After grace expires, bot **re-checks** if user is still a member
- Users who **leave channels** are caught on next visit — no bypass
- **Request mode** & **Direct mode** per individual channel
- All unjoined channels shown at once — no channels silently skipped
- Channel names shown on join buttons (`⚡ Direct` / `📨 Request`)

### 📢 Broadcast System
- Normal broadcast to all users
- **Safe broadcast** — skips blocked/deleted accounts automatically
- Batch broadcast support
- Database broadcast (forward messages)
- Cancel any ongoing broadcast
- Delete sent broadcasts

### 📊 Analytics & Stats
- Per-link click tracking
- Top links leaderboard
- User statistics
- Graph-based analytics
- Bot uptime display

### ⚙️ Customization
- Custom start message & help message
- Custom start image / link delivery image
- Custom join button text
- Second message toggle
- Forward protection enable/disable

### 🔒 Admin System
- Owner + unlimited multi-admin support
- Add/remove admins via command
- Maintenance mode (blocks all non-admin users)
- Auto-approve join requests toggle

### 🗄 Database
- MongoDB with auto TTL index cleanup
- Backup command
- Clean DB utility
- Pending broadcast management

</details>

---

## ⚡ Commands

### 👤 User Commands
| Command | Description |
|---------|-------------|
| `/start` | Start the bot / get your link |
| `/help` | Help & support info |
| `/about` | Bot info & age |

### 🔧 Admin Commands

<details>
<summary>Link Management</summary>

| Command | Description |
|---------|-------------|
| `/addchannel` | Add a channel to the bot |
| `/delchannel` | Remove a channel |
| `/channels` | List all added channels |
| `/genlink` | Generate a shareable link |
| `/click` | Check clicks for a link |
| `/clicks` | View all link click stats |
| `/toplinks` | Top clicked links |
| `/search` | Search channels |

</details>

<details>
<summary>Force Subscribe</summary>

| Command | Description |
|---------|-------------|
| `/fsubsets` | Manage Force Sub sets (add/remove channels, set limit, grace time) |
| `/settime` | Set grace time duration |
| `/default_limit` | Set default channels per set |
| `/approveon` | Enable auto-approve join requests |
| `/approveoff` | Disable auto-approve |

</details>

<details>
<summary>Broadcast</summary>

| Command | Description |
|---------|-------------|
| `/broadcast` | Broadcast message to all users |
| `/dbroadcast` | Database broadcast |
| `/pbroadcast` | Pending broadcast |
| `/batchbroadcast` | Batch broadcast |
| `/safebroadcasts` | Safe broadcast (skip blocked users) |
| `/delbroadcast` | Delete a broadcast |
| `/delallbroadcast` | Delete all broadcasts |
| `/cancel` | Cancel ongoing broadcast |

</details>

<details>
<summary>Analytics & System</summary>

| Command | Description |
|---------|-------------|
| `/stats` | Bot statistics |
| `/userstats` | User statistics |
| `/analytics` | Detailed analytics |
| `/graph` | Graphical stats |
| `/status` | Bot status & uptime |
| `/ping` | Check bot response time |
| `/customize` | Customize bot messages & images |
| `/addadmin` / `/deladmin` | Add or remove admins |
| `/admins` | List all admins |
| `/backup` | Backup database |
| `/cleandb` | Clean stale DB entries |
| `/update` | Update bot |
| `/cmds` | Full command list |

</details>

---

## 🚀 Setup

### Requirements
- Python 3.11+
- MongoDB Atlas (or local MongoDB)
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)
- A bot token from [@BotFather](https://t.me/BotFather)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TG_BOT_TOKEN` | ✅ | Bot Token from @BotFather |
| `APP_ID` | ✅ | Telegram API ID from my.telegram.org |
| `API_HASH` | ✅ | Telegram API Hash from my.telegram.org |
| `OWNER_ID` | ✅ | Your Telegram User ID |
| `ADMINS` | ✅ | Space-separated admin user IDs |
| `DB_URI` | ✅ | MongoDB connection URI |
| `DB_NAME` | ✅ | MongoDB database name (default: `crunchyroll_bot`) |
| `DATABASE_CHANNEL` | ✅ | Telegram channel ID for DB storage |
| `CHAT_ID` | ⬜ | Force-sub channel IDs (optional) |
| `PORT` | ⬜ | Web server port (default: `8000`) |

### Installation

```bash
git clone https://github.com/MikoxYae/linkshare-fixed
cd linkshare-fixed
pip install -r requirements.txt
python main.py
```

---

## 🐛 Bug Fixes (vs original)

| # | Bug | Fix |
|---|-----|-----|
| 1 | FSub reject message never auto-deleted | `delete_after_delay` added |
| 2 | Grace expires → user permanently free (no re-check) | Full membership re-check on every grace expiry |
| 3 | User leaves channel after joining — bot doesn't detect | Re-verify membership after grace instead of skipping |
| 4 | Only 1 channel shown (others silently dropped on link fail) | Fallback `⚠️` button ensures all channels always visible |
| 5 | Slow join-request check (iterates ALL pending requests) | Replaced with fast O(1) DB cache lookup |
| 6 | DB failure silently bypasses force-sub gate | Fail-safe: enforces fsub if DB is unreachable |
| 7 | Admin session (`_set_builder`) never expires — memory leak | TTL cleanup added (10 min auto-expiry) |
| 8 | `bot.py` filename | Renamed to `miko.py` throughout |

---

## 👨‍💻 Credits

- **Original Developer:** [@World_Fastest_Bots](https://t.me/World_Fastest_Bots)
- **Bug Fixes & Maintenance:** [@MikoxYae](https://github.com/MikoxYae)
- **Anime Channel:** [@CrunchyRollChannel](https://t.me/Crunchyrollchannel)

---

<div align="center">

<img src="https://user-images.githubusercontent.com/73097560/115834477-dbab4500-a447-11eb-908a-139a6edaec5c.gif">

**⭐ Star this repo if it helped you!**

</div>
