import db as db_module


def test_connection_reads_settings_from_environment(monkeypatch):
    captured = {}
    monkeypatch.setattr(db_module.mysql.connector, "connect", lambda **kw: captured.update(kw) or "conn")
    monkeypatch.setenv("DB_HOST", "db")
    monkeypatch.setenv("DB_USER", "app")
    monkeypatch.setenv("DB_PASSWORD", "pw")
    monkeypatch.setenv("DB_NAME", "pets")
    assert db_module.get_db_connection() == "conn"
    assert captured == {"host": "db", "user": "app", "password": "pw", "database": "pets"}
