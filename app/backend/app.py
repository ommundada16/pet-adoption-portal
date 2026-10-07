from flask import Flask, jsonify, request, send_from_directory, g, Response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException
from functools import wraps
from db import get_db_connection
from mysql.connector import IntegrityError
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import jwt
import datetime
import json
import logging
import os
import sys
import time
import uuid

app = Flask(__name__)
CORS(app)
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
# In production a known default secret would let anyone forge login tokens, so refuse to start
if os.environ.get("APP_ENV") == "production" and SECRET_KEY in ("dev-secret-key-change-in-production", "change-this-secret-key"):
    raise RuntimeError("SECRET_KEY must be set to a strong random value when APP_ENV=production")
app.config["SECRET_KEY"] = SECRET_KEY
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- OBSERVABILITY: structured logs + Prometheus metrics ---

# Writes each log line as one JSON object so Loki/ELK can index fields like "status" and "path"
class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "time": datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)

logger = logging.getLogger("pet_portal")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
logger.propagate = False

# The "Four Golden Signals" (traffic, errors, latency) come from these two HTTP metrics;
# the counters below them are business metrics shown on the Grafana dashboard
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency in seconds", ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
)
USERS_REGISTERED = Counter("pet_portal_registrations_total", "Accounts created", ["role"])
LOGINS = Counter("pet_portal_logins_total", "Login attempts", ["role", "outcome"])
PETS_ADDED = Counter("pet_portal_pets_added_total", "Pets listed by shelters")
ADOPTION_REQUESTS = Counter("pet_portal_adoption_requests_total", "Adoption requests by outcome", ["outcome"])

# Starts a timer and gives every request an id so its log lines can be traced
@app.before_request
def start_timer():
    g.start_time = time.perf_counter()
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]

# Records metrics and one access-log line after every request (the /metrics scrape itself is skipped)
@app.after_request
def record_request(response):
    if request.path == "/metrics":
        return response
    duration = time.perf_counter() - g.get("start_time", time.perf_counter())
    # url_rule gives "/api/pets/<int:pet_id>" instead of "/api/pets/7" - keeps label cardinality low
    endpoint = request.url_rule.rule if request.url_rule else "unmatched"
    REQUEST_COUNT.labels(request.method, endpoint, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, endpoint).observe(duration)
    logger.info("request", extra={"fields": {
        "request_id": g.get("request_id"), "method": request.method, "path": request.path,
        "status": response.status_code, "duration_ms": round(duration * 1000, 2)
    }})
    response.headers["X-Request-ID"] = g.get("request_id", "")
    return response

# Any uncaught error becomes a logged JSON 500 instead of an HTML stack trace
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    if isinstance(error, HTTPException):
        return jsonify({"error": error.description}), error.code
    logger.error("unhandled exception", exc_info=error, extra={"fields": {"request_id": g.get("request_id"), "path": request.path}})
    return jsonify({"error": "Internal server error"}), 500

# Exposes all metrics in Prometheus text format - scraped by Prometheus every 15s
@app.route("/metrics", methods=["GET"])
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

# Returns a list of required fields missing from the request body (None means the body wasn't JSON at all)
def missing_fields(data, fields):
    if not isinstance(data, dict):
        return list(fields)
    return [f for f in fields if data.get(f) in (None, "")]

# Checks a phone number is exactly 10 digits (only when one is provided - phone stays optional)
def is_valid_phone(phone):
    return phone is None or phone == "" or (phone.isdigit() and len(phone) == 10)

# Checks the Authorization header for a valid JWT before letting a route run
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Token is missing"}), 401
        try:
            token = auth_header.split(" ")[1]  # "Bearer <token>" -> take the token part
            payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except Exception:
            return jsonify({"error": "Token is invalid or expired"}), 401
        return f(payload, *args, **kwargs)
    return decorated

# Liveness check: "is the process up?" - deliberately does NOT touch the database,
# so a database outage doesn't make Kubernetes restart healthy API containers
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Pet Adoption Portal API is running"})

# Readiness check: "can this instance serve traffic?" - verifies the database answers.
# Kubernetes stops sending requests to an instance that returns 503 here
@app.route("/api/ready", methods=["GET"])
def readiness_check():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception:
        logger.error("readiness check failed: database unreachable")
        return jsonify({"status": "unavailable", "database": "down"}), 503
    return jsonify({"status": "ready", "database": "up"})

# --- USER AUTH ---

# Creates a new adopter account with a securely hashed password
@app.route("/api/users/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True)
    missing = missing_fields(data, ["name", "email", "password"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    if not is_valid_phone(data.get("phone")):
        return jsonify({"error": "Phone number must be exactly 10 digits"}), 400
    hashed_password = generate_password_hash(data["password"])
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password, phone) VALUES (%s, %s, %s, %s)",
            (data["name"], data["email"], hashed_password, data.get("phone"))
        )
        conn.commit()
    except IntegrityError:
        cursor.close()
        conn.close()
        return jsonify({"error": "An account with this email already exists"}), 409
    new_user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    USERS_REGISTERED.labels("user").inc()
    return jsonify({"message": "User registered", "user_id": new_user_id}), 201

# Verifies email/password and returns a JWT token identifying this user
@app.route("/api/users/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True)
    if missing_fields(data, ["email", "password"]):
        return jsonify({"error": "Email and password are required"}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (data["email"],))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if user and check_password_hash(user["password"], data["password"]):
        token = jwt.encode({
            "user_id": user["user_id"],
            "role": "user",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)
        }, app.config["SECRET_KEY"], algorithm="HS256")
        LOGINS.labels("user", "success").inc()
        return jsonify({"message": "Login successful", "token": token, "name": user["name"]})
    LOGINS.labels("user", "failure").inc()
    return jsonify({"error": "Invalid email or password"}), 401

# --- SHELTER/ADMIN AUTH ---

# Creates a new shelter/admin account
@app.route("/api/shelters/register", methods=["POST"])
def register_shelter():
    data = request.get_json(silent=True)
    missing = missing_fields(data, ["name", "email", "password"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    if not is_valid_phone(data.get("phone")):
        return jsonify({"error": "Phone number must be exactly 10 digits"}), 400
    hashed_password = generate_password_hash(data["password"])
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO shelters (name, email, password, phone, address) VALUES (%s, %s, %s, %s, %s)",
            (data["name"], data["email"], hashed_password, data.get("phone"), data.get("address"))
        )
        conn.commit()
    except IntegrityError:
        cursor.close()
        conn.close()
        return jsonify({"error": "An account with this email already exists"}), 409
    new_shelter_id = cursor.lastrowid
    cursor.close()
    conn.close()
    USERS_REGISTERED.labels("shelter").inc()
    return jsonify({"message": "Shelter registered", "shelter_id": new_shelter_id}), 201

# Verifies shelter email/password and returns a JWT token identifying this shelter
@app.route("/api/shelters/login", methods=["POST"])
def login_shelter():
    data = request.get_json(silent=True)
    if missing_fields(data, ["email", "password"]):
        return jsonify({"error": "Email and password are required"}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM shelters WHERE email = %s", (data["email"],))
    shelter = cursor.fetchone()
    cursor.close()
    conn.close()
    if shelter and check_password_hash(shelter["password"], data["password"]):
        token = jwt.encode({
            "shelter_id": shelter["shelter_id"],
            "role": "shelter",
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=6)
        }, app.config["SECRET_KEY"], algorithm="HS256")
        LOGINS.labels("shelter", "success").inc()
        return jsonify({"message": "Login successful", "token": token, "name": shelter["name"]})
    LOGINS.labels("shelter", "failure").inc()
    return jsonify({"error": "Invalid email or password"}), 401

# --- PETS ---

# Returns pets (with their shelter's name attached), optionally filtered by
# species (?species=Dog) and/or adoption status (?adopted=yes|no)
@app.route("/api/pets", methods=["GET"])
def get_pets():
    species = request.args.get("species")
    adopted = request.args.get("adopted")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT p.*, s.name AS shelter_name
        FROM pets p
        JOIN shelters s ON p.shelter_id = s.shelter_id
        WHERE 1=1
    """
    params = []
    if species:
        query += " AND p.species = %s"
        params.append(species)
    if adopted == "yes":
        query += " AND p.status = 'Adopted'"
    elif adopted == "no":
        query += " AND p.status != 'Adopted'"
    cursor.execute(query, tuple(params))
    pets = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(pets)

# Returns full details of one pet by its id, including its shelter's name
@app.route("/api/pets/<int:pet_id>", methods=["GET"])
def get_pet(pet_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, s.name AS shelter_name
        FROM pets p
        JOIN shelters s ON p.shelter_id = s.shelter_id
        WHERE p.pet_id = %s
    """, (pet_id,))
    pet = cursor.fetchone()
    cursor.close()
    conn.close()
    if pet is None:
        return jsonify({"error": "Pet not found"}), 404
    return jsonify(pet)

# Adds a new pet — only a logged-in shelter can do this (shelter_id comes from the token, not the request body)
@app.route("/api/pets", methods=["POST"])
@token_required
def add_pet(payload):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can add pets"}), 403
    data = request.get_json(silent=True)
    missing = missing_fields(data, ["name", "species"])
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pets (shelter_id, name, species, breed, age, description) VALUES (%s, %s, %s, %s, %s, %s)",
        (payload["shelter_id"], data["name"], data["species"], data.get("breed"), data.get("age"), data.get("description"))
    )
    conn.commit()
    new_pet_id = cursor.lastrowid
    cursor.close()
    conn.close()
    PETS_ADDED.inc()
    return jsonify({"message": "Pet added successfully", "pet_id": new_pet_id}), 201

# Returns only the pets belonging to the logged-in shelter (used by the "My Pets" page)
@app.route("/api/pets/my-pets", methods=["GET"])
@token_required
def get_my_pets(payload):
    if payload["role"] != "shelter":
        return jsonify({"error": "Shelters only"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pets WHERE shelter_id = %s", (payload["shelter_id"],))
    pets = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(pets)

# Updates any given fields of a pet (name/species/breed/age/description/status) — owning shelter only
@app.route("/api/pets/<int:pet_id>", methods=["PUT"])
@token_required
def update_pet(payload, pet_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can update pets"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT shelter_id FROM pets WHERE pet_id = %s", (pet_id,))
    pet = cursor.fetchone()
    if pet is None:
        cursor.close()
        conn.close()
        return jsonify({"error": "Pet not found"}), 404
    if pet["shelter_id"] != payload["shelter_id"]:
        cursor.close()
        conn.close()
        return jsonify({"error": "You can only update your own pets"}), 403

    data = request.get_json()
    updates = {f: data[f] for f in ["name", "species", "breed", "age", "description", "status"] if f in data}
    if not updates:
        cursor.close()
        conn.close()
        return jsonify({"error": "No fields to update"}), 400

    set_clause = ", ".join(f"{field} = %s" for field in updates)
    # Safe: column names come from the fixed whitelist above, and the values are passed as %s parameters
    cursor.execute(f"UPDATE pets SET {set_clause} WHERE pet_id = %s", (*updates.values(), pet_id))  # nosec B608
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Pet updated"})

# Deletes a pet (and its adoption request history, and its uploaded photo) — owning shelter only
@app.route("/api/pets/<int:pet_id>", methods=["DELETE"])
@token_required
def delete_pet(payload, pet_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can delete pets"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT shelter_id, image_filename FROM pets WHERE pet_id = %s", (pet_id,))
    pet = cursor.fetchone()
    if pet is None:
        cursor.close()
        conn.close()
        return jsonify({"error": "Pet not found"}), 404
    if pet["shelter_id"] != payload["shelter_id"]:
        cursor.close()
        conn.close()
        return jsonify({"error": "You can only delete your own pets"}), 403

    cursor.execute("DELETE FROM adoption_requests WHERE pet_id = %s", (pet_id,))
    cursor.execute("DELETE FROM pets WHERE pet_id = %s", (pet_id,))
    conn.commit()
    cursor.close()
    conn.close()

    if pet["image_filename"]:
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], pet["image_filename"])
        if os.path.exists(image_path):
            os.remove(image_path)

    return jsonify({"message": "Pet deleted"})

# Checks the uploaded file has an allowed image extension
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Uploads a pet's photo and saves its filename in the database — shelter only
@app.route("/api/pets/<int:pet_id>/upload-image", methods=["POST"])
@token_required
def upload_pet_image(payload, pet_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can upload pet images"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT shelter_id FROM pets WHERE pet_id = %s", (pet_id,))
    pet = cursor.fetchone()
    cursor.close()
    conn.close()
    if pet is None:
        return jsonify({"error": "Pet not found"}), 404
    if pet["shelter_id"] != payload["shelter_id"]:
        return jsonify({"error": "You can only upload photos for your own pets"}), 403
    if "image" not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400
    filename = secure_filename(f"pet_{pet_id}_{file.filename}")
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pets SET image_filename = %s WHERE pet_id = %s", (filename, pet_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Image uploaded", "filename": filename})

# Serves an uploaded pet image file back to the browser
@app.route("/uploads/<filename>", methods=["GET"])
def get_pet_image(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# --- ADOPTION REQUESTS ---

# Logged-in user requests to adopt a pet; pet flips to "Pending"
@app.route("/api/adoption-requests", methods=["POST"])
@token_required
def create_adoption_request(payload):
    if payload["role"] != "user":
        return jsonify({"error": "Only users can request adoption"}), 403
    data = request.get_json(silent=True)
    if missing_fields(data, ["pet_id"]):
        return jsonify({"error": "Missing required fields: pet_id"}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT status FROM pets WHERE pet_id = %s", (data["pet_id"],))
    pet = cursor.fetchone()
    if pet is None:
        cursor.close()
        conn.close()
        ADOPTION_REQUESTS.labels("rejected").inc()
        return jsonify({"error": "Pet not found"}), 404
    if pet["status"] == "Adopted":
        cursor.close()
        conn.close()
        ADOPTION_REQUESTS.labels("rejected").inc()
        return jsonify({"error": "This pet has already been adopted"}), 409
    cursor.execute(
        "INSERT INTO adoption_requests (user_id, pet_id) VALUES (%s, %s)",
        (payload["user_id"], data["pet_id"])
    )
    cursor.execute("UPDATE pets SET status = 'Pending' WHERE pet_id = %s", (data["pet_id"],))
    conn.commit()
    cursor.close()
    conn.close()
    ADOPTION_REQUESTS.labels("created").inc()
    return jsonify({"message": "Adoption request submitted"}), 201

# Shows the logged-in user their own requests (identity comes from the token, not the URL)
@app.route("/api/adoption-requests/my-requests", methods=["GET"])
@token_required
def get_user_requests(payload):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ar.request_id, ar.status, ar.request_date, p.name AS pet_name, p.species
        FROM adoption_requests ar
        JOIN pets p ON ar.pet_id = p.pet_id
        WHERE ar.user_id = %s
    """, (payload["user_id"],))
    requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(requests)

# Shows the logged-in shelter only the PENDING requests for its own pets
# (once approved/rejected, a request no longer needs action, so it drops off this list)
@app.route("/api/adoption-requests/shelter-requests", methods=["GET"])
@token_required
def get_shelter_requests(payload):
    if payload["role"] != "shelter":
        return jsonify({"error": "Shelters only"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ar.request_id, ar.status, u.name AS user_name, p.name AS pet_name
        FROM adoption_requests ar
        JOIN users u ON ar.user_id = u.user_id
        JOIN pets p ON ar.pet_id = p.pet_id
        WHERE p.shelter_id = %s AND ar.status = 'Pending'
    """, (payload["shelter_id"],))
    requests = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(requests)

# Shelter approves/rejects a request; pet status updates to match
@app.route("/api/adoption-requests/<int:request_id>", methods=["PUT"])
@token_required
def update_request_status(payload, request_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Shelters only"}), 403
    data = request.get_json(silent=True)
    new_status = data.get("status") if isinstance(data, dict) else None
    if new_status not in ("Approved", "Rejected"):
        return jsonify({"error": "Status must be Approved or Rejected"}), 400
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT ar.pet_id, p.shelter_id
        FROM adoption_requests ar JOIN pets p ON ar.pet_id = p.pet_id
        WHERE ar.request_id = %s
    """, (request_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return jsonify({"error": "Request not found"}), 404
    if row["shelter_id"] != payload["shelter_id"]:
        cursor.close()
        conn.close()
        return jsonify({"error": "You can only manage requests for your own pets"}), 403
    cursor.execute("UPDATE adoption_requests SET status = %s WHERE request_id = %s", (new_status, request_id))
    pet_status = "Adopted" if new_status == "Approved" else "Available"
    cursor.execute("UPDATE pets SET status = %s WHERE pet_id = %s", (pet_status, row["pet_id"]))
    conn.commit()
    cursor.close()
    conn.close()
    ADOPTION_REQUESTS.labels(new_status.lower()).inc()
    return jsonify({"message": f"Request {new_status.lower()}"})

# Lets a user withdraw their own request, as long as it's still Pending
@app.route("/api/adoption-requests/<int:request_id>", methods=["DELETE"])
@token_required
def cancel_adoption_request(payload, request_id):
    if payload["role"] != "user":
        return jsonify({"error": "Only adopters can cancel requests"}), 403
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT user_id, pet_id, status FROM adoption_requests WHERE request_id = %s", (request_id,))
    req = cursor.fetchone()
    if req is None:
        cursor.close()
        conn.close()
        return jsonify({"error": "Request not found"}), 404
    if req["user_id"] != payload["user_id"]:
        cursor.close()
        conn.close()
        return jsonify({"error": "You can only cancel your own requests"}), 403
    if req["status"] != "Pending":
        cursor.close()
        conn.close()
        return jsonify({"error": "Only pending requests can be cancelled"}), 400

    cursor.execute("DELETE FROM adoption_requests WHERE request_id = %s", (request_id,))
    cursor.execute("UPDATE pets SET status = 'Available' WHERE pet_id = %s", (req["pet_id"],))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Request cancelled"})

# Only used for quick local runs; in containers gunicorn serves the app (see Dockerfile)
if __name__ == "__main__":
    # Listening on all interfaces is required inside a container
    app.run(host="0.0.0.0", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")  # nosec B104
