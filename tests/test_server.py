from contextlib import contextmanager

import pytest

import server


class FakeConn:
    def __init__(self, capabilities=("IMAP4REV1", "UIDPLUS")):
        self.capabilities = capabilities
        self.calls = []

    def select(self, folder, readonly=True):
        self.calls.append(("select", folder, readonly))
        return "OK", [b"1"]

    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        return "OK", [None]


@pytest.fixture
def conn(monkeypatch):
    fake = FakeConn()

    @contextmanager
    def fake_imap():
        yield fake

    monkeypatch.setattr(server, "imap", fake_imap)
    monkeypatch.setattr(server, "READ_ONLY", False)
    return fake


def test_utf7_roundtrip():
    assert server._utf7_encode("Entwürfe") == "Entw&APw-rfe"
    assert server._utf7_encode("R&D") == "R&-D"
    assert server._utf7_encode("日本語") == "&ZeVnLIqe-"
    for name in ("INBOX.Gesendet", "Entwürfe", "R&D", "日本語", "a/b ü"):
        assert server._utf7_decode(server._utf7_encode(name)) == name


def test_quote_rejects_control_characters():
    with pytest.raises(ValueError):
        server._q("INBOX\r\nA1 LOGOUT")


@pytest.mark.parametrize("value", ["42", "42,43", "42:50", "1,5:7,9", " 42 , 43 "])
def test_uid_set_accepts(value):
    assert server._uid_set(value) == value.replace(" ", "")


@pytest.mark.parametrize("value", ["", "abc", "1;2", "1\r\nA1 LOGOUT", "*", "1:", ":1", "1,,2"])
def test_uid_set_rejects(value):
    with pytest.raises(ValueError):
        server._uid_set(value)


def test_mark_read_sets_seen(conn):
    server.mark_read("42")
    assert ("select", '"INBOX"', False) in conn.calls
    assert ("uid", "STORE", "42", "+FLAGS.SILENT", r"(\Seen)") in conn.calls


def test_mark_unread_removes_seen(conn):
    server.mark_unread("42,43")
    assert ("uid", "STORE", "42,43", "-FLAGS.SILENT", r"(\Seen)") in conn.calls


def test_flag_and_unflag(conn):
    server.flag_message("7")
    server.unflag_message("7")
    assert ("uid", "STORE", "7", "+FLAGS.SILENT", r"(\Flagged)") in conn.calls
    assert ("uid", "STORE", "7", "-FLAGS.SILENT", r"(\Flagged)") in conn.calls


def test_move_uses_uid_expunge_when_available(conn):
    server.move_message("5", "Archive")
    commands = [c[1] for c in conn.calls if c[0] == "uid"]
    assert commands == ["COPY", "STORE", "EXPUNGE"]
    assert ("uid", "EXPUNGE", "5") in conn.calls


def test_move_never_blanket_expunges_without_uidplus(conn):
    conn.capabilities = ("IMAP4REV1",)
    result = server.move_message("5", "Archive")
    assert [c[1] for c in conn.calls if c[0] == "uid"] == ["COPY", "STORE"]
    assert "UIDPLUS" in result


def test_trash_moves_to_trash_folder(conn):
    server.trash_message("9")
    assert ("uid", "COPY", "9", server._q(server.TRASH)) in conn.calls


def test_trash_refuses_permanent_delete(conn):
    with pytest.raises(ValueError):
        server.trash_message("9", folder=server.TRASH)


def test_read_only_blocks_every_write_tool(conn, monkeypatch):
    monkeypatch.setattr(server, "READ_ONLY", True)
    for call in (
        lambda: server.mark_read("1"),
        lambda: server.mark_unread("1"),
        lambda: server.flag_message("1"),
        lambda: server.unflag_message("1"),
        lambda: server.move_message("1", "Archive"),
        lambda: server.trash_message("1"),
        lambda: server.create_draft("a@b.c", "s", "b"),
    ):
        with pytest.raises(PermissionError):
            call()
    assert conn.calls == []


def test_invalid_uid_never_reaches_server(conn):
    with pytest.raises(ValueError):
        server.mark_read("1\r\nA1 DELETE")
    with pytest.raises(ValueError):
        server.read_message("1; x")
    assert conn.calls == []


# --- send / permanent delete: opt-in and always confirmed by the user ------- #

class FakeCtx:
    def __init__(self, action="accept", confirm=True, raises=None):
        self.action, self.confirm, self.raises = action, confirm, raises
        self.asked = []

    async def elicit(self, message, schema):
        self.asked.append(message)
        if self.raises:
            raise self.raises
        data = schema(confirm=self.confirm) if self.action == "accept" else None
        return type("R", (), {"action": self.action, "data": data})()


@pytest.fixture
def smtp(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "ALLOW_SEND", True)
    monkeypatch.setattr(server, "_smtp_send", sent.append)
    monkeypatch.setattr(server, "_append", lambda *a: None)
    return sent


def _send(ctx, **kw):
    import asyncio
    return asyncio.run(server.send_message("a@b.c", "Hi", "Body", ctx, **kw))


def test_send_disabled_by_default(conn, smtp, monkeypatch):
    monkeypatch.setattr(server, "ALLOW_SEND", False)
    ctx = FakeCtx()
    with pytest.raises(PermissionError):
        _send(ctx)
    assert smtp == [] and ctx.asked == []


def test_send_blocked_in_read_only(conn, smtp, monkeypatch):
    monkeypatch.setattr(server, "READ_ONLY", True)
    with pytest.raises(PermissionError):
        _send(FakeCtx())
    assert smtp == []


def test_send_after_confirmation(conn, smtp):
    ctx = FakeCtx()
    assert "Sent" in _send(ctx)
    assert len(smtp) == 1 and "a@b.c" in ctx.asked[0] and "Body" in ctx.asked[0]


@pytest.mark.parametrize("ctx", [
    FakeCtx(action="decline"), FakeCtx(action="cancel"), FakeCtx(confirm=False),
    FakeCtx(raises=RuntimeError("elicitation unsupported")),
])
def test_send_refused_without_confirmation(conn, smtp, ctx):
    with pytest.raises(PermissionError):
        _send(ctx)
    assert smtp == []


def test_send_rejects_header_injection(conn, smtp):
    with pytest.raises(ValueError):
        _send(FakeCtx(), cc="x@y.z\r\nBcc: evil@e.vil")
    assert smtp == []


def _delete(ctx, uid="5"):
    import asyncio
    return asyncio.run(server.delete_message_permanently(uid, ctx))


class DeleteConn(FakeConn):
    def uid(self, command, *args):
        self.calls.append(("uid", command, *args))
        if command == "FETCH":
            return "OK", [(b"1 (BODY[HEADER.FIELDS])", b"Subject: Old\r\nFrom: x@y.z\r\n\r\n"), b")"]
        return "OK", [None]


@pytest.fixture
def dconn(monkeypatch):
    fake = DeleteConn()

    @contextmanager
    def fake_imap():
        yield fake

    monkeypatch.setattr(server, "imap", fake_imap)
    monkeypatch.setattr(server, "READ_ONLY", False)
    monkeypatch.setattr(server, "ALLOW_DELETE", True)
    return fake


def test_delete_disabled_by_default(dconn, monkeypatch):
    monkeypatch.setattr(server, "ALLOW_DELETE", False)
    with pytest.raises(PermissionError):
        _delete(FakeCtx())
    assert dconn.calls == []


def test_delete_after_confirmation_expunges_only_given_uid(dconn):
    ctx = FakeCtx()
    assert "Permanently deleted 1" in _delete(ctx)
    assert "Old" in ctx.asked[0]
    assert ("uid", "EXPUNGE", "5") in dconn.calls


def test_delete_refused_without_confirmation(dconn):
    for ctx in (FakeCtx(action="decline"), FakeCtx(raises=RuntimeError("no elicit"))):
        with pytest.raises(PermissionError):
            _delete(ctx)
    assert not any(c[1] in ("STORE", "EXPUNGE") for c in dconn.calls if c[0] == "uid")


def test_delete_requires_uidplus(dconn):
    dconn.capabilities = ("IMAP4REV1",)
    with pytest.raises(RuntimeError):
        _delete(FakeCtx())
