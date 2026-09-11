from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from db import get_db_connection
import jwt
import datetime
import os

app = Flask(__name__)
CORS(app)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Pet Adoption Portal API is running"})

# --- USER AUTH ---

# Creates a new adopter account with a securely hashed password
@app.route("/api/users/register", methods=["POST"])
def register_user():
    data = request.get_json()
    hashed_password = generate_password_hash(data["password"])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, password, phone) VALUES (%s, %s, %s, %s)",
        (data["name"], data["email"], hashed_password, data.get("phone"))
    )
    conn.commit()
    new_user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "User registered", "user_id": new_user_id}), 201

# Verifies email/password and returns a JWT token identifying this user
@app.route("/api/users/login", methods=["POST"])
def login_user():
    data = request.get_json()
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
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)
        }, app.config["SECRET_KEY"], algorithm="HS256")
        return jsonify({"message": "Login successful", "token": token, "name": user["name"]})
    return jsonify({"error": "Invalid email or password"}), 401

# --- SHELTER/ADMIN AUTH ---

# Creates a new shelter/admin account
@app.route("/api/shelters/register", methods=["POST"])
def register_shelter():
    data = request.get_json()
    hashed_password = generate_password_hash(data["password"])
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO shelters (name, email, password, phone, address) VALUES (%s, %s, %s, %s, %s)",
        (data["name"], data["email"], hashed_password, data.get("phone"), data.get("address"))
    )
    conn.commit()
    new_shelter_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "Shelter registered", "shelter_id": new_shelter_id}), 201

# Verifies shelter email/password and returns a JWT token identifying this shelter
@app.route("/api/shelters/login", methods=["POST"])
def login_shelter():
    data = request.get_json()
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
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=6)
        }, app.config["SECRET_KEY"], algorithm="HS256")
        return jsonify({"message": "Login successful", "token": token, "name": shelter["name"]})
    return jsonify({"error": "Invalid email or password"}), 401

# --- PETS ---

# Returns all pets, or filters by species if ?species=Dog is passed in the URL
@app.route("/api/pets", methods=["GET"])
def get_pets():
    species = request.args.get("species")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if species:
        cursor.execute("SELECT * FROM pets WHERE species = %s", (species,))
    else:
        cursor.execute("SELECT * FROM pets")
    pets = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(pets)

# Returns full details of one pet by its id
@app.route("/api/pets/<int:pet_id>", methods=["GET"])
def get_pet(pet_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM pets WHERE pet_id = %s", (pet_id,))
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
    data = request.get_json()
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
    return jsonify({"message": "Pet added successfully", "pet_id": new_pet_id}), 201

# Updates a pet's status — shelter only
@app.route("/api/pets/<int:pet_id>", methods=["PUT"])
@token_required
def update_pet_status(payload, pet_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can update pet status"}), 403
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pets SET status = %s WHERE pet_id = %s", (data["status"], pet_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Pet status updated"})

# Checks the uploaded file has an allowed image extension
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# Uploads a pet's photo and saves its filename in the database — shelter only
@app.route("/api/pets/<int:pet_id>/upload-image", methods=["POST"])
@token_required
def upload_pet_image(payload, pet_id):
    if payload["role"] != "shelter":
        return jsonify({"error": "Only shelters can upload pet images"}), 403
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
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO adoption_requests (user_id, pet_id) VALUES (%s, %s)",
        (payload["user_id"], data["pet_id"])
    )
    cursor.execute("UPDATE pets SET status = 'Pending' WHERE pet_id = %s", (data["pet_id"],))
    conn.commit()
    cursor.close()
    conn.close()
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

# Shows the logged-in shelter all requests made for its own pets
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
        WHERE p.shelter_id = %s
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
    data = request.get_json()
    new_status = data["status"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT pet_id FROM adoption_requests WHERE request_id = %s", (request_id,))
    row = cursor.fetchone()
    cursor.execute("UPDATE adoption_requests SET status = %s WHERE request_id = %s", (new_status, request_id))
    pet_status = "Adopted" if new_status == "Approved" else "Available"
    cursor.execute("UPDATE pets SET status = %s WHERE pet_id = %s", (pet_status, row["pet_id"]))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": f"Request {new_status.lower()}"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)