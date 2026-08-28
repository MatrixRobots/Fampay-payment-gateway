"""
FamApp AutoPay Bot — /start and /pay only.
"""

import os
import asyncio
import logging
from io import BytesIO
from datetime import datetime

import qrcode
from telethon import TelegramClient, events, Button

# ── Config ────────────────────────────────────────────────────────────────────
API_ID      = 0                           # my.telegram.org
API_HASH    = "your_api_hash"             # my.telegram.org
BOT_TOKEN   = "your_bot_token"            # @BotFather
ADMIN_ID    = 0                           # your Telegram user ID

MONGODB_URI      = "mongodb+srv://..."    # MongoDB Atlas
MONGODB_DB       = "famapp"
UPI_ID           = "yourname@fam"         # your FamApp UPI handle
PAYEE_NAME       = "Your Name"            # shown on QR
PURPOSE_PREFIX   = "FAP"
BRAND_NAME       = "FamApp Pay"
ORDER_EXPIRY_MIN = 15
GMAIL_LOOKBACK_H = 12
IMAP_HOST        = "imap.gmail.com"
IMAP_PORT        = 993
IMAP_USERNAME    = "you@gmail.com"        # Gmail that gets FamApp emails
IMAP_PASSWORD    = "xxxx xxxx xxxx xxxx"  # Google App Password
IMAP_MAILBOX     = "INBOX"
IMAP_SENDER      = "no-reply@famapp.in"

SUPPORT_CONTACT  = "@your_support_username"
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

os.makedirs("sessions", exist_ok=True)
bot = TelegramClient(f"sessions/bot_{BOT_TOKEN.split(':')[0]}", API_ID, API_HASH)
bot.parse_mode = "html"

_pm = None  # PaymentManager singleton


def get_pm():
    global _pm
    if _pm is None:
        os.environ.update({
            "MONGODB_URI":          MONGODB_URI,
            "DB_NAME":              MONGODB_DB,
            "DEFAULT_UPI_ID":       UPI_ID,
            "DEFAULT_PAYEE_NAME":   PAYEE_NAME,
            "PURPOSE_PREFIX":       PURPOSE_PREFIX,
            "BRAND_NAME":           BRAND_NAME,
            "ORDER_EXPIRY_MINUTES": str(ORDER_EXPIRY_MIN),
            "GMAIL_LOOKBACK_HOURS": str(GMAIL_LOOKBACK_H),
            "IMAP_HOST":            IMAP_HOST,
            "IMAP_PORT":            str(IMAP_PORT),
            "IMAP_USERNAME":        IMAP_USERNAME,
            "IMAP_APP_PASSWORD":    IMAP_PASSWORD,
            "IMAP_MAILBOX":         IMAP_MAILBOX,
            "IMAP_SENDER_FILTER":   IMAP_SENDER,
        })
        from payment_template import PaymentManager
        _pm = PaymentManager()
    return _pm


# uid -> amount string while keypad open
_keypad_state: dict = {}
# order_id -> {uid, amount}
_orders: dict = {}


def keypad_buttons():
    return [
        [Button.inline("1", "k1"), Button.inline("2", "k2"), Button.inline("3", "k3")],
        [Button.inline("4", "k4"), Button.inline("5", "k5"), Button.inline("6", "k6")],
        [Button.inline("7", "k7"), Button.inline("8", "k8"), Button.inline("9", "k9")],
        [Button.inline("Del", "kdel"), Button.inline("0", "k0"), Button.inline("Pay", "kdone")],
        [Button.inline("Cancel", "kcancel")],
    ]


def keypad_msg(val: str) -> str:
    return (
        f"UPI Auto Payment\n\n"
        f"Enter amount (min Rs 1)\n\n"
        f"Rs {val}"
    )


@bot.on(events.NewMessage(pattern=r"^/start$", func=lambda e: not e.is_group))
async def cmd_start(event):
    await event.respond(
        f"Welcome!\n\n"
        f"UPI Auto Payment Bot\n\n"
        f"Add money instantly via UPI.\n"
        f"Payments auto-verified via FamApp.\n\n"
        f"Use /pay to make a payment.",
        buttons=[[Button.inline("Pay Now", "open_pay")]],
    )


@bot.on(events.NewMessage(pattern=r"^/pay$", func=lambda e: not e.is_group))
async def cmd_pay(event):
    uid = event.sender_id
    _keypad_state[uid] = "0"
    await event.respond(keypad_msg("0"), buttons=keypad_buttons())


@bot.on(events.CallbackQuery())
async def on_callback(event):
    uid  = event.sender_id
    data = event.data.decode()

    if data == "open_pay":
        _keypad_state[uid] = "0"
        await event.edit(keypad_msg("0"), buttons=keypad_buttons())
        return

    if data.startswith("k"):
        key = data[1:]

        if key == "cancel":
            _keypad_state.pop(uid, None)
            try:
                await event.delete()
            except Exception:
                pass
            await bot.send_message(uid, "Payment cancelled.")
            return

        val = _keypad_state.get(uid, "0")

        if key == "del":
            val = val[:-1] or "0"
        elif key == "done":
            amount = int(val) if val.isdigit() else 0
            if amount < 1:
                await event.answer("Minimum Rs 1", alert=True)
                return
            _keypad_state.pop(uid, None)
            await generate_qr(event, uid, amount)
            return
        elif key.isdigit():
            val = ("" if val == "0" else val) + key
            if len(val) > 6:
                await event.answer("Max Rs 999999", alert=True)
                return
        else:
            return

        _keypad_state[uid] = val
        try:
            await event.edit(keypad_msg(val), buttons=keypad_buttons())
        except Exception:
            pass
        return

    if data.startswith("chk_"):
        order_id = data[4:]
        await check_payment(event, uid, order_id)
        return


async def generate_qr(event, uid: int, amount: int):
    await event.edit(f"Generating QR for Rs {amount}...")

    try:
        pm    = get_pm()
        order = await asyncio.to_thread(pm.create, user_id=uid, amount=amount)
    except Exception as exc:
        logger.error(f"create order error uid={uid}: {exc}")
        await event.edit(f"Failed to generate QR. Try again.\n\nSupport: {SUPPORT_CONTACT}")
        return

    _orders[order.id] = {"uid": uid, "amount": amount}

    buf = BytesIO()
    qrcode.make(order.upi_uri).save(buf, format="PNG")
    buf.seek(0)
    buf.name = "pay.png"

    caption = (
        f"UPI Auto Payment\n\n"
        f"Amount: Rs {amount}\n"
        f"Order: {order.id}\n"
        f"UPI ID: {UPI_ID}\n\n"
        f"1. Scan QR with GPay / PhonePe / Paytm\n"
        f"2. Pay exactly Rs {amount}\n"
        f"3. Tap Check Payment\n\n"
        f"Expires in {ORDER_EXPIRY_MIN} minutes"
    )

    try:
        await event.delete()
    except Exception:
        pass

    sent = await bot.send_file(
        uid, buf, caption=caption,
        buttons=[
            [Button.inline("Check Payment", f"chk_{order.id}")],
            [Button.inline("Cancel", "kcancel")],
        ],
    )
    asyncio.create_task(auto_verify(uid, order.id, sent))


async def auto_verify(uid: int, order_id: str, sent_msg):
    pm = get_pm()
    for _ in range(45):
        await asyncio.sleep(20)
        if order_id not in _orders:
            return
        try:
            result = await asyncio.to_thread(pm.verify, order_id)
        except Exception as exc:
            logger.error(f"auto_verify {order_id}: {exc}")
            continue
        if result.get("verified"):
            await do_credit(uid, order_id, _orders[order_id]["amount"], sent_msg)
            return
        if result.get("status") in ("expired", "cancelled"):
            break

    if order_id in _orders:
        _orders.pop(order_id, None)
        try:
            await bot.edit_message(
                uid, sent_msg.id,
                f"Payment not verified.\n\nIf you paid, contact: {SUPPORT_CONTACT}"
            )
        except Exception:
            pass


async def check_payment(event, uid: int, order_id: str):
    if order_id not in _orders:
        return await event.answer("Already processed!", alert=True)

    await event.answer("Checking...", alert=False)

    try:
        result = await asyncio.to_thread(get_pm().verify, order_id)
    except Exception as exc:
        logger.error(f"check_payment {order_id}: {exc}")
        return await event.answer("Error. Try again.", alert=True)

    if result.get("verified"):
        await do_credit(uid, order_id, _orders[order_id]["amount"], event.message)
    elif result.get("status") in ("expired", "cancelled"):
        _orders.pop(order_id, None)
        await event.answer(f"Order {result['status']}. Use /pay again.", alert=True)
    else:
        await event.answer("Not received yet. Paid? Contact support.", alert=True)


async def do_credit(uid: int, order_id: str, amount: int, msg_to_edit):
    if order_id not in _orders:
        return
    _orders.pop(order_id)

    try:
        await bot.edit_message(
            uid, msg_to_edit.id,
            f"Payment Verified!\n\nRs {amount} received.\nOrder: {order_id}\n\nThank you!"
        )
    except Exception:
        try:
            await bot.send_message(uid, f"Payment Verified! Rs {amount} received. Order: {order_id}")
        except Exception:
            pass

    try:
        t = datetime.now().strftime("%d %b %Y %H:%M")
        await bot.send_message(
            ADMIN_ID,
            f"New Payment\n\nUser: {uid}\nAmount: Rs {amount}\nOrder: {order_id}\nTime: {t}"
        )
    except Exception:
        pass


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("Bot started")
    await bot.run_until_disconnected()


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.run(main())
    except ImportError:
        asyncio.run(main())
