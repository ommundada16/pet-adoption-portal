from flask import Flask, jsonify, request
from flask_cors import CORS
from db import get_db_connection

app = Flask(__name__)
CORS(app)

@app.route("/api/health", methods=["GET"])
#heartbeat endpoint to check if the API is running
#before doing anythign we ahve to chekc if the server is alive or not
def health_check():
    return jsonify({"status": "ok", "message": "Pet Adoption Portal API is running"})

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

# Adds a new pet to the database (used by the shelter/admin)
@app.route("/api/pets", methods=["POST"])
def add_pet():
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pets (shelter_id, name, species, breed, age, description) VALUES (%s, %s, %s, %s, %s, %s)",
        (data["shelter_id"], data["name"], data["species"], data.get("breed"), data.get("age"), data.get("description"))
    )
    conn.commit()
    new_pet_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"message": "Pet added successfully", "pet_id": new_pet_id}), 201

# Updates a pet's status (Available / Pending / Adopted)
@app.route("/api/pets/<int:pet_id>", methods=["PUT"])
def update_pet_status(pet_id):
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE pets SET status = %s WHERE pet_id = %s", (data["status"], pet_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"message": "Pet status updated"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)