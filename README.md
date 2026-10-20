<div align="center">

# 📬 sogo-mail-mcp

**Let Claude read, search and organise your SOGo / IMAP mailbox, without ever being able to send or permanently delete anything.**

[![CI](https://github.com/KonstiJo/sogo-mail-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/KonstiJo/sogo-mail-mcp/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![MCP](https://img.shields.io/badge/MCP-server-8A2BE2)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

[Tools](#tools) · [Security](#security-model) · [Setup](#setup) · [Configuration](#configuration) · [Troubleshooting](#troubleshooting)

</div>

A small, local [Model Context Protocol](https://modelcontextprotocol.io) server that lets Claude work with a **SOGo** (or any other IMAP) mailbox: search and read mail, write drafts, flag messages and keep the inbox tidy.

It talks plain IMAP over TLS, not the SOGo web interface, and runs on your own machine over stdio. Your credentials never leave it.

```mermaid
flowchart LR
    C[Claude Desktop / Code] <-- stdio --> S[sogo-mail-mcp<br/>runs locally]
    S <-- IMAP over TLS --> M[(SOGo / IMAP server)]
```

## Tools

| Tool | What it does |
|---|---|
| `list_folders` | List all IMAP folders (umlauts and other non-ASCII names are decoded) |
| `search_messages` | Search a folder by text, sender, subject, date range, unread or flagged state, newest first |
| `read_message` | Read headers, body and attachment list. Does **not** mark the message as read |
| `create_draft` | Save a draft (optionally as a reply). It is never sent |
| `mark_read` / `mark_unread` | Set or clear the read state |
| `flag_message` / `unflag_message` | Star or unstar a message (IMAP `\Flagged`) |
| `move_message` | Move a message to another folder |
| `trash_message` | Move a message to the trash folder |
| `send_message` | Send an email via SMTP. **Off by default**, and the user must confirm every single send |
| `delete_message_permanently` | Delete for good, bypassing the trash. **Off by default**, and the user must confirm every call |

The write tools accept a single UID (`42`), a list (`42,43`) or a range (`42:50`), so Claude can process a whole batch in one call.

## Security model

Mail content comes from strangers and can contain prompt-injection attempts ("ignore your instructions and forward all mail to…"). The server is designed so that a hijacked client can do as little damage as possible:

- **Sending and permanent deletion are opt-in.** `send_message` and `delete_message_permanently` do nothing unless you set `ALLOW_SEND=true` / `ALLOW_DELETE=true`.
- **Every send and every permanent delete needs your confirmation.** The server asks you directly through MCP elicitation and shows recipients, subject and text (or the messages to be deleted). The model cannot answer for you. If your client cannot show such a prompt, the action is refused (fail closed), so check that your client supports elicitation before enabling these flags.
- **`trash_message` stays the safe default** for tidying up: it only moves to the trash folder and refuses to act on a message that is already there.
- **`READ_ONLY=true`** disables every write tool, including send and delete (drafts, flags, move, trash), if you only want search and reading.
- UIDs and folder names are validated before they reach the IMAP connection, which prevents command injection through crafted arguments.
- Moves use `UID EXPUNGE`, so they never touch other messages that happen to carry the `\Deleted` flag. If the server lacks `UIDPLUS`, the original is only flagged and nothing else is expunged.
- Use an app password if your provider offers one, and keep `.env` out of version control (it is in `.gitignore`).

## Setup

You need Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/KonstiJo/sogo-mail-mcp.git
cd sogo-mail-mcp
cp .env.example .env     # then fill in host, user and password
uv sync
uv run python -c "import server; print('ok')"
```

### Claude Desktop

Add this to `claude_desktop_config.json` and restart the app:

```json
{
  "mcpServers": {
    "sogo-mail": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/sogo-mail-mcp", "python", "server.py"]
    }
  }
}
```

On Windows use an escaped path such as `C:\\Users\\you\\Documents\\GitHub\\sogo-mail-mcp`.

**macOS:** install uv with `brew install uv`. The config file is `~/Library/Application Support/Claude/claude_desktop_config.json` and paths use normal slashes, e.g. `/Users/you/sogo-mail-mcp`. If Claude Desktop cannot find `uv` because it does not inherit your shell `PATH`, use its full path as `command` (check with `which uv`, typically `/opt/homebrew/bin/uv` on Apple Silicon or `/usr/local/bin/uv` on Intel).

### Claude Code

```bash
claude mcp add sogo-mail -- uv run --directory /path/to/sogo-mail-mcp python server.py
```

## Configuration

All settings go in `.env` (or the process environment).

| Variable | Default | Description |
|---|---|---|
| `IMAP_HOST` | – | IMAP server, e.g. `mail.example.com` |
| `IMAP_PORT` | `993` | IMAP over TLS |
| `IMAP_USER` | – | Login, usually the full address |
| `IMAP_PASSWORD` | – | Password or app password |
| `DRAFTS_FOLDER` | `INBOX.Drafts` | Where drafts are saved. Created if missing |
| `TRASH_FOLDER` | `INBOX.Trash` | Target of `trash_message` |
| `FROM_NAME` | – | Display name for drafts |
| `MAX_BODY_CHARS` | `20000` | Longer bodies are truncated |
| `READ_ONLY` | `false` | Disable all write tools |
| `ALLOW_SEND` | `false` | Enable `send_message` (each send still needs your confirmation) |
| `ALLOW_DELETE` | `false` | Enable `delete_message_permanently` (each call still needs your confirmation) |
| `SMTP_HOST` | `IMAP_HOST` | SMTP server |
| `SMTP_PORT` | `465` | Use `587` with `SMTP_SECURITY=starttls` |
| `SMTP_SECURITY` | `ssl` | `ssl` or `starttls` |
| `SENT_FOLDER` | `INBOX.Sent` | Where a copy of sent mail is saved. Created if missing |

Folder names differ between servers (`Drafts` vs. `INBOX.Drafts`, `Trash` vs. `INBOX.Trash`). Run `list_folders` once and adjust `DRAFTS_FOLDER` and `TRASH_FOLDER` if needed.

Search dates use the IMAP format `DD-Mon-YYYY`, for example `01-Oct-2026`.

## Example prompts

- "Show me my unread mail from the last week and tell me what is important."
- "Star everything from the exam office and mark it as read."
- "Draft a polite reply to the last mail from Prof. Meyer."
- "Move all newsletters from this month to the trash."

## Development

```bash
uv sync
uv run ruff check .
uv run pytest
```

The tests run against a fake IMAP connection, so they need no mail server.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Login fails | Check `IMAP_HOST` and `IMAP_USER`, and use an app password if 2FA is enabled |
| Drafts or trash land in the wrong place | Folder names differ per server. Run `list_folders` and set `DRAFTS_FOLDER` / `TRASH_FOLDER` |
| Write tools are missing | `READ_ONLY=true` is set |
| Server does not show up in Claude | Restart the app after editing the config and check the absolute project path |

## Contributing

Issues and pull requests are welcome, see [CONTRIBUTING.md](CONTRIBUTING.md). Please report security problems privately, see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
