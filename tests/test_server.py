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
