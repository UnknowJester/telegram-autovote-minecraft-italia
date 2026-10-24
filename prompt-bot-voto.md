# Prompt: bot Telegram per voto automatico server Minecraft su minecraft-italia.net

Incolla questo prompt sull'OpenCode del tuo amico. Gli servono: Python 3.12 su Windows,
Brave installato, un bot Telegram creato con BotFather (token) e un account su
minecraft-italia.net. Il bot è configurabile per qualsiasi server: l'utente imposta `VOTE_URL` (e opzionalmente `SERVER_NAME`).

---

Crea un progetto Python su Windows con due componenti:

**1. `vote.py` — automazione voto (Playwright + Brave)**

- Browser: Brave reale (`C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`
  passato come `executable_path` a Playwright), headless per il run automatico, headful
  per debug (flag `--show`). Installa con `pip install playwright`.
- Config da `.env`: `MCITALIA_EMAIL`, `MCITALIA_PASS`, `MC_USERNAME`, `VOTE_URL`
  (es. `https://minecraft-italia.net/lista/server/your-server`).
- Flusso login: vai su `https://minecraft-italia.net/login/`, clicca "Nega il consenso"
  nel popup cookie, compila `input[name="login"]` + `input[name="password"]`, clicca il
  bottone "Entra" dentro il form (mai selettori generici tipo `button[type=submit]`:
  c'è un bottone search nascosto che li fa fallire). Verifica login avvenuto (URL base,
  scritta Account in alto).
- Pagina server: clicca il `DIV.openVote` (testo "+1", non è un `<button>`).
- Nel modale "Conferma voto" clicca l'elemento `#ho-votato` (è un DIV) via JS evaluate.
- Verifica: leggi il conteggio `(\d[\d.]*) voti` prima/dopo; se aumenta → "voto registrato",
  se il modale non mostra il pulsante e il testo dice "hai già votato / cooldown /
  prossimo voto" → "già votato oggi".
- Nessun captcha osservato finora: controlla comunque iframe hcaptcha/recaptcha/turnstile
  e riportalo nell'esito.
- Salva screenshot di ogni step in `shots/`. Funzione `run_vote(show=False)` che ritorna
  la tupla `(outcome, shot_path)`.

**2. `bot.py` — bot Telegram (python-telegram-bot v21+)**

- `.env`: `TELEGRAM_TOKEN`, `ALLOWED_IDS` (solo questi ID usano il bot; con allowlist vuota
  solo `/start` deve funzionare e mostrare il chat ID per la configurazione).
- Comandi: `/start`, `/vota` (esegue `run_vote` in thread e manda la foto screenshot con
  didascalia esito), `/stato` (ultimo esito e ora). Imposta il menu comandi con
  `setMyCommands`.
- Scheduler asyncio interno: voto automatico ogni giorno alle 00:25 (una sola volta al
  giorno; se il PC era spento, recupera al primo avvio dopo quell'ora), con notifica +
  screenshot in chat.
- Single-instance via lock file `msvcrt`, log rotante su `bot.log`.

**3. Esecuzione in background su Windows**

- `watchdog.vbs`: loop che lancia `pythonw bot.py` e lo riavvia 10 secondi dopo un crash;
  collegamento `.lnk` in `shell:startup` per l'avvio al login. Nota: su Windows l'interprete
  del venv mostra sempre 2 processi `pythonw` (launcher + interprete), è normale.

---

## Istruzioni per l'amico (da fare a mano)

1. Crea il bot con BotFather e copia il token in `pc-votebot/.env` (`TELEGRAM_TOKEN`).
2. Manda `/start` al bot, copia il chat ID e mettilo in `ALLOWED_IDS`.
3. Metti email/password minecraft-italia + username Minecraft nel `.env`.
4. Prima prova con browser visibile per controllare che login e voto funzionino.
5. Doppio clic sul collegamento per l'avvio in background.
