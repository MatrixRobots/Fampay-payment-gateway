# 🤖 FamApp AutoPay Bot

A Telegram bot that generates branded UPI QR codes and **auto-verifies payments** by scanning FamApp notification emails via IMAP — no payment gateway API needed.

Built on the `payment_template` SDK (included), powered by **Telethon**, **MongoDB**, and **Gmail IMAP**.

---

## ✨ Features

- 🔢 In-chat numeric keypad to enter any amount
- 🖼️ Branded UPI QR code generated instantly (PNG, 1400×1700)
- ✅ Auto-verification every 20 s for up to 15 minutes via IMAP
- 🔁 Manual **Check Payment** button for instant re-check
- 🗄️ MongoDB persists all orders and verification logs
- 🚫 Duplicate-email guard — same email can't verify two orders
- 📬 Admin gets a DM on every successful payment
- 🧩 Clean SDK (`payment_template`) — drop it into any Python project

---

## 📁 Project Structure

```
.
├── bot.py                  # Telegram bot (Telethon) — entry point
├── payment_template/
│   ├── __init__.py         # Exports PaymentManager
│   ├── config.py           # AppConfig — loads env vars
│   ├── database.py         # MongoRepository — orders + logs
│   ├── exceptions.py       # All custom exceptions
│   ├── gmail.py            # IMAP email scanner
│   ├── manager.py          # PaymentManager (public API)
│   ├── models.py           # Order, VerificationResult dataclasses
│   ├── purpose.py          # Secure purpose-string generator
│   ├── qr.py               # Branded QR PNG generator (Pillow)
│   └── utils.py            # Shared helpers
├── .env                    # ← you create this (see below)
├── requirements.txt
└── README.md
```

---

## ⚙️ Prerequisites

| Requirement | Where to get it |
|---|---|
| Python 3.11+ | [python.org](https://www.python.org/downloads/) |
| Telegram API ID & Hash | [my.telegram.org](https://my.telegram.org) → API development tools |
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) → `/newbot` |
| Your Telegram User ID | [@userinfobot](https://t.me/userinfobot) |
| MongoDB Atlas URI | [cloud.mongodb.com](https://cloud.mongodb.com) → free M0 cluster |
| FamApp UPI ID | FamApp (Federal Bank) app → your `yourname@fam` handle |
| Gmail App Password | See [Gmail setup](#-gmail-imap-setup) below |

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/your-username/famapp-autopay-bot.git
cd famapp-autopay-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in all values (see [Environment Variables](#-environment-variables)).

### 4. Run the bot

```bash
python bot.py
```

---

## 🔑 Environment Variables

Create a `.env` file in the project root. **All fields are required unless marked optional.**

```env
# ── Telegram ──────────────────────────────────────────────
API_ID=12345678
API_HASH=your_api_hash_from_my_telegram_org
BOT_TOKEN=123456789:AAFxxxxxxxxxxxxxxxxxxxxxxx
ADMIN_ID=987654321

# ── MongoDB ───────────────────────────────────────────────
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
DB_NAME=famapp

# ── UPI / Payment ─────────────────────────────────────────
DEFAULT_UPI_ID=yourname@fam
DEFAULT_PAYEE_NAME=Your Name
PURPOSE_PREFIX=FAP
BRAND_NAME=FamApp Pay
ORDER_EXPIRY_MINUTES=15      # optional, default 15

# ── Gmail IMAP ────────────────────────────────────────────
IMAP_USERNAME=you@gmail.com
IMAP_APP_PASSWORD=xxxx xxxx xxxx xxxx
IMAP_HOST=imap.gmail.com     # optional, default imap.gmail.com
IMAP_PORT=993                # optional, default 993
IMAP_MAILBOX=INBOX           # optional, default INBOX
IMAP_SENDER_FILTER=no-reply@famapp.in   # optional
GMAIL_LOOKBACK_HOURS=12      # optional, default 12

# ── Support ───────────────────────────────────────────────
SUPPORT_CONTACT=@your_support_username
```

> ⚠️ **Never commit your `.env` file.** Add it to `.gitignore`.

---

## 📬 Gmail IMAP Setup

FamApp sends a payment-received email to your linked Gmail when someone pays your UPI ID. The bot reads these emails to verify payments.

1. Go to your [Google Account](https://myaccount.google.com) → **Security**
2. Enable **2-Step Verification** (required for App Passwords)
3. Go to **Security → App Passwords**
4. Select app: **Mail** | Select device: **Other** → name it `famapp-bot`
5. Copy the 16-character password → paste into `IMAP_APP_PASSWORD` in `.env`
6. Make sure your FamApp account is linked to this Gmail

> 💡 FamApp notification emails come from `no-reply@famapp.in`. The bot searches for the **unique purpose string** (e.g. `FAP-20240828-A3X9KZ`) inside these emails to match the payment.

---

## 🍃 MongoDB Atlas Setup

1. Sign up at [cloud.mongodb.com](https://cloud.mongodb.com) (free M0 tier works)
2. Create a cluster → **Connect** → **Drivers** → copy the connection string
3. Replace `<password>` in the URI with your DB user password
4. Paste the full URI into `MONGODB_URI` in `.env`
5. In **Network Access**, add `0.0.0.0/0` (allow from anywhere) or your server's IP

The bot creates these collections automatically on first run:

| Collection | Purpose |
|---|---|
| `orders` | Every payment order (pending / verified / expired / cancelled) |
| `verification_logs` | One log per successful verification, keyed by Gmail message ID |

---

## 🤖 Telegram Bot Setup

1. Open [@BotFather](https://t.me/BotFather) → `/newbot`
2. Follow prompts → copy the bot token → paste into `BOT_TOKEN`
3. Go to [my.telegram.org](https://my.telegram.org) → **API development tools**
4. Copy **App api_id** and **App api_hash** → paste into `API_ID` and `API_HASH`
5. Get your own Telegram user ID from [@userinfobot](https://t.me/userinfobot) → paste into `ADMIN_ID`

---

## 🛠️ Using the `payment_template` SDK Standalone

The SDK is fully independent and can be used in any Python project:

```python
from payment_template import PaymentManager

pm = PaymentManager()  # reads config from env vars / .env

# 1. Create a payment order
order = pm.create(user_id=123456, amount=499)
print(order.id)          # ORD-20240828-A3B4C5D6
print(order.upi_uri)     # upi://pay?pa=...
# order.qr_image is the branded PNG as bytes

# 2. Check verification status
result = pm.verify(order.id)
print(result["verified"])  # True / False
print(result["status"])    # "pending" | "verified" | "expired" | "cancelled"

# 3. Get current status
status = pm.status(order.id)   # string

# 4. Cancel an order
pm.cancel(order.id)
```

### Order statuses

| Status | Meaning |
|---|---|
| `pending` | Created, awaiting payment |
| `verified` | Payment email found and matched |
| `expired` | Not verified within `ORDER_EXPIRY_MINUTES` |
| `cancelled` | Cancelled via `pm.cancel()` |

### Exceptions

| Exception | When raised |
|---|---|
| `ConfigurationError` | Missing / invalid env var |
| `DatabaseError` | MongoDB operation failed |
| `GmailError` | IMAP connection / search failed |
| `OrderNotFoundError` | `order_id` doesn't exist |
| `OrderStateError` | Invalid state transition (e.g. cancel a verified order) |
| `VerificationError` | Bad `user_id` or unverifiable input |

```python
from payment_template import PaymentManager
from payment_template.exceptions import OrderNotFoundError, OrderStateError

try:
    pm.cancel("ORD-XXXX")
except OrderNotFoundError:
    print("Order doesn't exist")
except OrderStateError:
    print("Can only cancel pending orders")
```

---

## 📦 requirements.txt

```txt
telethon
pymongo[srv]
python-dotenv
qrcode[pil]
Pillow
```

Save this as `requirements.txt` and install with:

```bash
pip install -r requirements.txt
```

---

## 🖥️ Deployment

### Local / VPS

```bash
# Keep running with nohup
nohup python bot.py &

# Or with screen
screen -S fambot
python bot.py
# Ctrl+A, D to detach
```

### Termux (Android)

```bash
pkg install python
pip install -r requirements.txt
python bot.py
```

### Railway / Render

1. Push the repo to GitHub
2. Create a new service → connect the repo
3. Set all environment variables in the dashboard (Settings → Environment)
4. Set the start command to `python bot.py`

### systemd (Linux VPS)

```ini
[Unit]
Description=FamApp AutoPay Bot
After=network.target

[Service]
WorkingDirectory=/home/ubuntu/famapp-autopay-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/famapp-autopay-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable famapp-bot
sudo systemctl start famapp-bot
sudo systemctl status famapp-bot
```

---

## 🔒 Security Notes

- Keep `.env` out of version control — add it to `.gitignore`
- Use a **Gmail App Password**, not your real Gmail password
- Restrict MongoDB network access to your server IP in production
- The purpose string is cryptographically random — collision probability is negligible
- Each Gmail message ID can only verify one order (duplicate guard in DB)

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `ConfigurationError: IMAP_USERNAME is required` | Check your `.env` — make sure IMAP fields are set |
| `Unable to connect to MongoDB` | Check your Atlas URI, password, and network access |
| Bot doesn't respond | Confirm `BOT_TOKEN`, `API_ID`, `API_HASH` are correct |
| Payment not auto-verified | Make sure the Gmail account receives FamApp emails; check `IMAP_SENDER_FILTER` |
| QR generated but scan fails | Confirm `DEFAULT_UPI_ID` is your exact FamApp UPI handle |
| Font not found (QR text) | Install `fonts-dejavu` or `fonts-liberation` on your Linux server |

---

## 📄 License

MIT — free to use, modify, and distribute.

---

## 🙏 Credits

[Matrix Robots channel](https://t.me/Matrix_Robots) 
[chat group](https://t.me/UseMasterUpdate) 

