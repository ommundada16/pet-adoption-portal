from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/api/health", methods=["GET"])
#heartbeat endpoint to check if the API is running
#before doing anythign we ahve to chekc if the server is alive or not
def health_check():
    return jsonify({"status": "ok", "message": "Pet Adoption Portal API is running"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)