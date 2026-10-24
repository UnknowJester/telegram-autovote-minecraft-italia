"""Bot voto Minecraft Italia: /vota ora + voto automatico giornaliero (Brave headless)."""
import asyncio
import datetime
import logging
import os
import sys
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    _base = os.path.dirname(sys.executable)
else:
    _base = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_base, ".env"))
load_dotenv()
sys.path.insert(0, _base)

VOTE_URL = os.getenv("VOTE_URL", "").strip()
SERVER_NAME = os.getenv("SERVER_NAME", "").strip()
if not SERVER_NAME:
    _slug = VOTE_URL.rstrip("/").split("/")[-1] if VOTE_URL else ""
    SERVER_NAME = _slug.replace("-", " ").replace("_", " ").strip().title() or "il server scelto"

TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
ALLOWED_IDS = set(x.strip() for x in os.getenv("ALLOWED_IDS", "").split(",") if x.strip())
def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)) or default)
    except (ValueError, TypeError):
        return default


VOTE_HOUR = _env_int("VOTE_HOUR", 13)
VOTE_MINUTE = _env_int("VOTE_MINUTE", 0)

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
try:
    from logging.handlers import RotatingFileHandler
    _fh = RotatingFileHandler(os.path.join(_base, "bot.log"), maxBytes=500_000, backupCount=2, encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logging.getLogger().addHandler(_fh)
except Exception:
    pass
log = logging.getLogger("voto")

LAST = {"outcome": "mai eseguito", "at": "-"}
_voting = False


def authorized(update: Update) -> bool:
    return bool(ALLOWED_IDS) and str(update.effective_user.id) in ALLOWED_IDS


async def deny(update: Update):
    uid = update.effective_user.id
    if not ALLOWED_IDS:
        await update.message.reply_text(f"👋 Il tuo chat ID è: `{uid}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⛔ Non autorizzato (ID `{uid}`).", parse_mode="Markdown")


def targets():
    return [int(x) for x in ALLOWED_IDS]


async def do_vote(app, origin: str = "manuale"):
    global _voting
    if _voting:
        return "voto già in corso..."
    _voting = True
    try:
        from vote import run_vote, kill_playwright_braves
        try:
            outcome, shot = await asyncio.wait_for(asyncio.to_thread(run_vote, False), timeout=300)
        except asyncio.TimeoutError:
            kill_playwright_braves()
            outcome, shot = "timeout dopo 5 minuti (browser killato, riprovo domani)", None
    except Exception as e:
        log.exception("voto")
        outcome, shot = f"errore: {e}", None
    finally:
        _voting = False
    LAST["outcome"] = outcome
    LAST["at"] = datetime.datetime.now().strftime("%d/%m %H:%M")
    text = f"🗳️ Voto {SERVER_NAME} ({origin}): {outcome}"
    if len(text) > 900:
        text = text[:900] + "… (troncato, vedi bot.log)"
    for cid in targets():
        try:
            if shot and os.path.exists(shot):
                with open(shot, "rb") as f:
                    await app.bot.send_photo(cid, photo=f, caption=text)
            else:
                await app.bot.send_message(cid, text)
        except Exception:
            log.exception("invio esito")
    return outcome


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await deny(update)
        return
    await update.message.reply_text(
        f"🗳️ Bot voto {SERVER_NAME}.\n"
        f"• server: {VOTE_URL or 'non configurato'}\n"
        f"• /vota → vota subito\n• /stato → ultimo esito\n"
        f"• automatico ogni giorno alle {VOTE_HOUR:02d}:{VOTE_MINUTE:02d} (se PC acceso)")


async def vota(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await deny(update)
        return
    status = await update.message.reply_text("🗳️ Voto in corso (Brave headless, ~1 min)...")
    outcome = await do_vote(ctx.application, "manuale")
    await status.edit_text(f"🗳️ Esito: {outcome}")


async def stato(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        await deny(update)
        return
    await update.message.reply_text(f"🗳️ Ultimo voto: {LAST['at']}\nEsito: {LAST['outcome']}")


async def scheduler(app):
    fired_today = None
    while True:
        try:
            now = datetime.datetime.now()
            due = (now.hour, now.minute) >= (VOTE_HOUR, VOTE_MINUTE)
            if due and fired_today != now.date():
                fired_today = now.date()
                log.info("voto automatico giornaliero")
                await do_vote(app, "automatico")
        except Exception:
            log.exception("scheduler")
        await asyncio.sleep(300)


async def post_init(app):
    app.create_task(scheduler(app), name="scheduler")
    for cid in targets():
        try:
            await app.bot.send_message(cid, "🗳️ Bot voto online.")
        except Exception:
            log.exception("invio online")


def single_instance_lock():
    import msvcrt
    global _lock_fh
    try:
        _lock_fh = open(os.path.join(_base, "bot.lock"), "w")
        msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
        _lock_fh.write(str(os.getpid()))
        _lock_fh.flush()
        return True
    except (OSError, IOError):
        return False


def main():
    if not TOKEN or TOKEN == "INCOLLA_QUI_IL_TOKEN":
        print("ERRORE: metti il token nel file .env.")
        raise SystemExit(1)
    if not single_instance_lock():
        print("Un'altra istanza è già in esecuzione, esco.")
        raise SystemExit(0)
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("vota", vota))
    app.add_handler(CommandHandler("stato", stato))
    print("Bot voto avviato.")
    app.run_polling()


if __name__ == "__main__":
    main()
