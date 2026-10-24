"""Voto automatico minecraft-italia.net (test guidato + run giornaliero).
Uso: vote.py [--show] [--notify]
  --show   : browser visibile (per vedere captcha/login la prima volta)
  --notify : manda esito su Telegram via bot telecomando
"""
import os
import re
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def load_env(path):
    d = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


ENV = load_env(os.path.join(BASE, ".env"))
EMAIL = ENV.get("MCITALIA_EMAIL", "")
PASSWORD = ENV.get("MCITALIA_PASS", "")
MCUSER = ENV.get("MC_USERNAME", "")
VOTE_URL = ENV.get("VOTE_URL", "").strip()
SERVER_NAME = ENV.get("SERVER_NAME", "").strip()
if not SERVER_NAME:
    _slug = VOTE_URL.rstrip("/").split("/")[-1] if VOTE_URL else ""
    SERVER_NAME = _slug.replace("-", " ").replace("_", " ").strip().title() or "il server scelto"
SHOW = "--show" in sys.argv
NOTIFY = "--notify" in sys.argv
BRAVE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"


def notify_telegram(text: str):
    try:
        renv = {}
        for line in open(os.path.join(BASE, ".env"), encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                renv[k.strip()] = v.strip()
        if not renv.get("TELEGRAM_TOKEN") or not renv.get("ALLOWED_IDS"):
            return
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"chat_id": list(renv["ALLOWED_IDS"].split(","))[0], "text": text}).encode()
        urllib.request.urlopen(f'https://api.telegram.org/bot{renv["TELEGRAM_TOKEN"]}/sendMessage', data=data, timeout=20)
    except Exception as e:
        print("notify fallita:", e)


def kill_playwright_braves():
    """Killa solo i Brave lanciati da Playwright (profilo temp), mai quello dell'utente."""
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if (proc.info["name"] or "").lower() in ("brave.exe", "chrome.exe"):
                    cmd = " ".join(proc.info["cmdline"] or [])
                    if "playwright" in cmd.lower():
                        proc.kill()
            except Exception:
                continue
    except Exception:
        pass


def _latest_shot(shots: str):
    try:
        pngs = [os.path.join(shots, f) for f in os.listdir(shots) if f.endswith(".png")]
        return max(pngs, key=os.path.getmtime) if pngs else None
    except OSError:
        return None


def _dismiss_consent(pg):
    """Chiude popup consenso in tutte le varianti (semplice + preferenze dettagliate)."""
    for _ in range(3):
        handled = False
        for name in ("Nega il consenso", "Rifiuta tutto", "Reject all"):
            try:
                b = pg.get_by_role("button", name=re.compile(f"^{name}$", re.I))
                if b.count():
                    b.first.click(timeout=4000)
                    handled = True
                    break
            except Exception:
                continue
        if handled:
            pg.wait_for_timeout(1200)
            continue
        # preferenze dettagliate aperte? chiudi con X o conferma scelte (toggle già off)
        try:
            x = pg.locator("[aria-label='Chiudi'], .modal-close, button.close").first
            if x.count():
                x.click(timeout=3000)
                pg.wait_for_timeout(1000)
                continue
        except Exception:
            pass
        try:
            b = pg.get_by_role("button", name=re.compile(r"conferma le scelte", re.I))
            if b.count():
                b.first.click(timeout=4000)
                pg.wait_for_timeout(1200)
                continue
        except Exception:
            pass
        break


def _cleanup_shots(shots: str, keep_days: float = 7.0):
    import time as _t
    try:
        now = _t.time()
        for f in os.listdir(shots):
            p = os.path.join(shots, f)
            if f.endswith(".png") and now - os.path.getmtime(p) > keep_days * 86400:
                os.remove(p)
    except OSError:
        pass


def _launch_browser(p, show: bool):
    errs = []
    candidates = [
        {"executable_path": BRAVE},
        {"channel": "chrome"},
        {},
    ]
    for kw in candidates:
        try:
            return p.chromium.launch(headless=not show,
                                     args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception as e:
            errs.append(f"{kw}: {e}")
    raise RuntimeError("nessun browser avviabile: " + " | ".join(errs))


def run_vote(show: bool = False):
    """Esegue login+voto con Brave, ritorna stringa esito."""
    from playwright.sync_api import sync_playwright
    shots = os.path.join(BASE, "shots")
    os.makedirs(shots, exist_ok=True)
    _cleanup_shots(shots)
    if not (EMAIL and PASSWORD and MCUSER and VOTE_URL):
        return "credenziali/URL mancanti nel .env (MCITALIA_EMAIL, MCITALIA_PASS, MC_USERNAME, VOTE_URL)", _latest_shot(shots)
    if not VOTE_URL.startswith("https://minecraft-italia.net/lista/server/"):
        return "VOTE_URL non valido: usa https://minecraft-italia.net/lista/server/<slug-del-server>", _latest_shot(shots)
    outcome = "sconosciuto"
    with sync_playwright() as p:
        browser = _launch_browser(p, show)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            viewport={"width": 1366, "height": 900}, locale="it-IT")
        ctx.set_default_timeout(20000)
        pg = ctx.new_page()
        try:
            # 1. login
            pg.goto("https://minecraft-italia.net/login/", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(4000)
            _dismiss_consent(pg)
            pg.screenshot(path=os.path.join(shots, "1-login.png"))
            email_sel = 'input[name="login"], input[name="username"], input[type="email"]'
            pass_sel = 'input[name="password"], input[type="password"]'
            if pg.locator(email_sel).count() and pg.locator(pass_sel).count():
                pg.locator(email_sel).first.fill(EMAIL)
                pg.locator(pass_sel).first.fill(PASSWORD)
                pg.screenshot(path=os.path.join(shots, "2-compilato.png"))
                btn = pg.locator("form").locator("button:has-text('Entra'), button[type=submit]").last
                try:
                    btn.scroll_into_view_if_needed(timeout=5000)
                    btn.click(timeout=10000)
                except Exception:
                    pg.locator(pass_sel).first.press("Enter")
                pg.wait_for_timeout(5000)
            pg.screenshot(path=os.path.join(shots, "3-dopo-login.png"))
            print("URL dopo login:", pg.url)
            if "/login" in pg.url:
                try:
                    pg.screenshot(path=os.path.join(shots, "errore.png"))
                except Exception:
                    pass
                return "login fallito (ancora su /login, vedi shots)", _latest_shot(shots)
            # captcha presente?
            frames = [f.url for f in pg.frames]
            cap = [u for u in frames if re.search(r"(hcaptcha|recaptcha|turnstile|cloudflare)", u, re.I)]
            print("captcha iframe:", cap if cap else "nessuno rilevato")
            # 2. pagina voto
            pg.goto(VOTE_URL, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(5000)
            pg.screenshot(path=os.path.join(shots, "4-server.png"))
            txt = pg.locator("body").inner_text()[:1500]
            print("--- testo pagina ---")
            print(txt[:800])
            # cerca bottone voto (è un DIV.openVote con testo "+1")
            voted = re.search(r"(hai già votato|già votato|potrai votare|prossimo voto|cooldown|attendi)", txt, re.I)
            vote_btn = None
            try:
                if pg.locator(".openVote").count():
                    vote_btn = pg.locator(".openVote").first
            except Exception:
                pass
            if vote_btn is None:
                btns = pg.locator("button, a").all()
                for b in btns:
                    try:
                        t = (b.inner_text() or "").strip()
                    except Exception:
                        continue
                    if re.match(r"(?i)^vota", t) or t in ("+1", "+ 1"):
                        vote_btn = b
                        break
            if voted and not vote_btn:
                outcome = "già votato (cooldown attivo)"
                print(outcome)
            elif vote_btn:
                print("clicco:", vote_btn.inner_text().strip()[:40])
                try:
                    vote_btn.scroll_into_view_if_needed(timeout=8000)
                    vote_btn.click(timeout=12000)
                except Exception:
                    pg.evaluate("""(() => {
                      const el = document.querySelector('.openVote');
                      if (el) { el.scrollIntoView(); el.click(); }
                    })()""")
                pg.wait_for_timeout(5000)
                pg.screenshot(path=os.path.join(shots, "5-dopo-voto.png"))
                # eventuale campo username
                for sel in ("input[name*=user i]", "input[name*=nick i]", "input[placeholder*=minecraft i]"):
                    try:
                        if pg.locator(sel).count():
                            pg.locator(sel).first.fill(MCUSER)
                            print("username inserito")
                            break
                    except Exception:
                        pass
                # secondo click di conferma ("Vota!" nel modale)
                def vote_count():
                    try:
                        t = pg.locator("body").inner_text()
                        m = re.search(r"(\d[\d.]*)\s*voti", t)
                        return m.group(1) if m else "?"
                    except Exception:
                        return "?"
                before = vote_count()
                try:
                    clicked = pg.evaluate("""(() => {
                      let el = document.getElementById('ho-votato');
                      if (!el) {
                        const els = [...document.querySelectorAll('*')];
                        el = els.find(x => /^vota!?$/i.test((x.innerText||'').trim()) && x.children.length === 0);
                      }
                      if (!el) {
                        const m = document.body.innerText.match(/.{0,80}(già votato|cooldown|prossimo voto|attendi[^.]{0,80})/i);
                        return 'nobtn:' + (m ? m[0].trim().slice(0,120) : document.body.innerText.slice(0,120));
                      }
                      el.scrollIntoView(); el.click();
                      return 'clicked';
                    })()""")
                    print("click modale:", clicked[:150])
                    if clicked.startswith("nobtn:") and re.search(r"(già votato|cooldown|prossimo voto)", clicked, re.I):
                        outcome = "già votato oggi (cooldown)"
                        print("ESITO:", outcome)
                        return outcome, _latest_shot(shots)
                    pg.wait_for_timeout(6000)
                except Exception as e:
                    print("conferma fallita:", e)
                after = vote_count()
                print(f"voti prima={before} dopo={after}")
                if before != after and after != "?":
                    outcome = f"voto registrato ({before} -> {after})"
                else:
                    outcome = "click fatto ma conteggio invariato (forse già votato oggi)"
                pg.screenshot(path=os.path.join(shots, "6-finale.png"))
                final = pg.locator("body").inner_text()[:1000]
                print("--- dopo voto ---")
                print(final[:500])
            else:
                outcome = "bottone voto non trovato"
                print(outcome)
        except Exception as e:
            outcome = f"errore: {e}"
            print(outcome)
            try:
                pg.screenshot(path=os.path.join(shots, "errore.png"))
            except Exception:
                pass
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            kill_playwright_braves()
    print("ESITO:", outcome)
    final = os.path.join(shots, "6-finale.png")
    return outcome, final if os.path.exists(final) else _latest_shot(shots)


def main():
    outcome, _shot = run_vote(show=SHOW)
    if NOTIFY:
        notify_telegram(f"🗳️ Voto {SERVER_NAME}: {outcome}")


if __name__ == "__main__":
    main()
