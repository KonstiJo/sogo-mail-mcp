# Contributing

Thanks for helping out!

```bash
uv sync
uv run ruff check .
uv run pytest
```

- Tests use a fake IMAP connection, so no mail server is needed.
- New write tools must respect `READ_ONLY` and validate UIDs and folder names.
- Keep the security model intact: no sending mail and no permanent deletion.
- Open an issue first for larger changes.
