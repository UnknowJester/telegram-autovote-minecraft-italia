# Bot voto Minecraft Italia

Bot Telegram per votare automaticamente un server scelto dall'utente su minecraft-italia.net.

Configurazione in `.env`:
- `VOTE_URL`: URL della pagina del server da votare (es. `https://minecraft-italia.net/lista/server/nome-server`)
- `SERVER_NAME`: nome visualizzato nei messaggi (opzionale; se vuoto viene ricavato dall'URL)
- `VOTE_HOUR` / `VOTE_MINUTE`: orario del voto automatico

Comandi: `/vota` vota subito (Brave headless), `/stato` ultimo esito.
Credenziali minecraft-italia nel `.env` (solo locale). Log in `bot.log`, screenshot in `shots/`.
Avvio: `VotoPC-watchdog` in Esecuzione automatica.
