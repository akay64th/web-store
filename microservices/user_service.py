from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# In-memory "database"
users = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com"},
    2: {"id": 2, "name": "Bob", "email": "bob@example.com"}
}
user_id_counter = 3


# Health endpoint
@app.route('/health', methods=['GET'])
def get_health():
    return jsonify({"status": "All good"}), 200


# The API gateway strips the "/users" prefix before forwarding, so each route
# is also registered under "/users" to support direct calls (curl, README).
@app.route('/<int:user_id>', methods=['GET'])
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = users.get(user_id)
    if user:
        return jsonify(user)
    return jsonify({"error": "User not found"}), 404


@app.route('/', methods=['GET'])
@app.route('/users', methods=['GET'])
def get_users():
    return jsonify(list(users.values()))


@app.route('/', methods=['POST'])
@app.route('/users', methods=['POST'])
def create_user():
    global user_id_counter
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid data"}), 400

    name = data.get('name')
    email = data.get('email')
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Name is required"}), 400
    if not isinstance(email, str) or '@' not in email:
        return jsonify({"error": "A valid email is required"}), 400

    user = {"id": user_id_counter, "name": name.strip(), "email": email.strip()}
    users[user_id_counter] = user
    user_id_counter += 1
    return jsonify(user), 201


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5031, debug=True)
