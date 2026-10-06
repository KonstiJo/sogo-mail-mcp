# sogo-mail-mcp

Lokaler MCP-Server (stdio) für SOGo-Mail. Spricht direkt IMAP, nicht die SOGo-Weboberfläche.

Tools: `list_folders`, `search_messages`, `read_message`, `create_draft`.
Kein Senden, Löschen oder Verschieben (Schutz vor Prompt Injection über Mailinhalte).

## Setup

1. Ordner an einen festen Ort kopieren, z. B. `C:\Users\Konsti\Documents\GitHub\sogo-mail-mcp`.
2. `.env.example` nach `.env` kopieren und ausfüllen (IMAP-Host, Port, User, App-Passwort).
3. Testen:
   ```
   uv run python -c "import server; print('ok')"
   ```
4. In `claude_desktop_config.json` eintragen:
   ```json
   {
     "mcpServers": {
       "sogo-mail": {
         "command": "uv",
         "args": ["run", "--directory", "C:\\Users\\Konsti\\Documents\\GitHub\\sogo-mail-mcp", "python", "server.py"]
       }
     }
   }
   ```
   Für Claude Code: `claude mcp add sogo-mail -- uv run --directory <Pfad> python server.py`
5. Claude Desktop neu starten.

## Hinweise

- Der Drafts-Ordner heißt je nach Server `Drafts` oder `INBOX.Drafts`. Mit `list_folders` prüfen und ggf. `DRAFTS_FOLDER` in `.env` setzen.
- Suchdatum-Format: `DD-Mon-YYYY` (z. B. `01-Oct-2026`).
- `.env` nie committen (steht in `.gitignore`).
