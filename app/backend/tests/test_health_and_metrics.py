import os
import subprocess
import sys

from mysql.connector import Error as MySQLError

import app as app_module


def test_health_does_not_need_database(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_ready_ok_when_db_answers(client, db):
    r = client.get("/api/ready")
    assert r.status_code == 200 and r.get_json()["database"] == "up"


def test_ready_503_when_db_down(client, monkeypatch):
    def boom():
        raise MySQLError("db down")
    monkeypatch.setattr(app_module, "get_db_connection", boom)
    r = client.get("/api/ready")
    assert r.status_code == 503 and r.get_json()["database"] == "down"


def test_metrics_exposes_request_counters_with_route_template(client, db):
    db.fetchone_queue.append({"pet_id": 5, "name": "Rex", "shelter_name": "S"})
    client.get("/api/pets/5")
    body = client.get("/metrics").get_data(as_text=True)
    assert "http_requests_total" in body
    # label uses the route template, not the concrete id, to keep cardinality low
    assert 'endpoint="/api/pets/<int:pet_id>"' in body
    assert "http_request_duration_seconds_bucket" in body


def test_metrics_endpoint_is_not_self_counted(client):
    client.get("/metrics")
    body = client.get("/metrics").get_data(as_text=True)
    assert 'endpoint="/metrics"' not in body


def test_response_carries_request_id(client):
    r = client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"
    assert client.get("/api/health").headers["X-Request-ID"]


def test_unknown_route_returns_json_404(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and "error" in r.get_json()


def test_unhandled_exception_returns_json_500(client, monkeypatch):
    def boom():
        raise RuntimeError("kaboom")
    monkeypatch.setattr(app_module, "get_db_connection", boom)
    r = client.get("/api/pets")
    assert r.status_code == 500 and r.get_json() == {"error": "Internal server error"}


def test_production_refuses_default_secret():
    # run in a subprocess: a failed re-import would otherwise leave this test process with a broken app module
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "APP_ENV": "production"}
    env.pop("SECRET_KEY", None)
    result = subprocess.run([sys.executable, "-c", "import app"], cwd=backend_dir, env=env, capture_output=True, text=True)
    assert result.returncode != 0 and "SECRET_KEY must be set" in result.stderr
    env["SECRET_KEY"] = "a-long-random-production-secret"
    assert subprocess.run([sys.executable, "-c", "import app"], cwd=backend_dir, env=env).returncode == 0
