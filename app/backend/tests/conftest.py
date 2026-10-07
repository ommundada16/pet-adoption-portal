import datetime
import os
import sys

import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "_uploads"))

import app as app_module  # noqa: E402


# A stand-in for a MySQL cursor: tests queue up the rows each SELECT should return,
# and every executed SQL statement is recorded so tests can assert on it
class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.lastrowid = 42

    def execute(self, sql, params=None):
        self.db.executed.append((" ".join(sql.split()), params))
        if self.db.raise_on_execute:
            raise self.db.raise_on_execute

    def fetchone(self):
        return self.db.fetchone_queue.pop(0) if self.db.fetchone_queue else None

    def fetchall(self):
        return self.db.fetchall_queue.pop(0) if self.db.fetchall_queue else []

    def close(self):
        pass


class FakeDB:
    def __init__(self):
        self.executed = []
        self.fetchone_queue = []
        self.fetchall_queue = []
        self.raise_on_execute = None
        self.committed = False

    def cursor(self, dictionary=False):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def close(self):
        pass


@pytest.fixture
def db(monkeypatch):
    fake = FakeDB()
    monkeypatch.setattr(app_module, "get_db_connection", lambda: fake)
    return fake


@pytest.fixture
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def make_token(role, ident=1, hours=6):
    key = "shelter_id" if role == "shelter" else "user_id"
    payload = {
        key: ident, "role": role,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours),
    }
    return jwt.encode(payload, app_module.app.config["SECRET_KEY"], algorithm="HS256")


@pytest.fixture
def shelter_auth():
    return {"Authorization": f"Bearer {make_token('shelter', 1)}"}


@pytest.fixture
def user_auth():
    return {"Authorization": f"Bearer {make_token('user', 7)}"}
