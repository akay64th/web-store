
import threading
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)

USER_SERVICE_URL = 'http://127.0.0.1:5031'
PRODUCT_SERVICE_URL = 'http://127.0.0.1:5032'
REQUEST_TIMEOUT = 5  # seconds

# Order data
orders = {}
order_id_counter = 1
order_lock = threading.Lock()


class ServiceUnavailableError(Exception):
    """Raised when a downstream service cannot be reached or misbehaves."""

    def __init__(self, service: str, message: str):
        super().__init__(message)
        self.service = service
        self.message = message


# Health endpoint
@app.route('/health', methods=['GET'])
def get_health():
    return jsonify({"status": "All good"}), 200


# The gateway forwards "POST /orders" to "POST /" here. The README describes
# the create endpoint as PUT, so both methods are accepted.
@app.route('/', methods=['POST', 'PUT'])
def create_order():
    global order_id_counter
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid data"}), 400

    user_id = data.get('user_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not _is_int(user_id) or not _is_int(product_id):
        return jsonify({"error": "user_id and product_id must be integers"}), 400
    if not _is_int(quantity) or quantity < 1:
        return jsonify({"error": "Quantity must be a positive integer"}), 400

    # Serialize order creation so concurrent orders cannot oversell stock
    with order_lock:
        try:
            # Validate user exists
            if not get_user_object(user_id):
                return jsonify({"error": "User not found"}), 404

            # Validate product exists and has stock
            product = get_product_object(product_id)
            if not product:
                return jsonify({"error": "Product not found"}), 404

            if product['stock'] < quantity:
                return jsonify({"error": "Insufficient stock"}), 400

            # Decrement stock in the product service
            update_stock(product_id, product['stock'] - quantity)
        except ServiceUnavailableError as e:
            return jsonify({"error": e.message, "service": e.service}), 503

        order = {
            "id": order_id_counter,
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "total": round(product['price'] * quantity, 2),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        orders[order_id_counter] = order
        order_id_counter += 1

    return jsonify(order), 201


@app.route('/<int:order_id>', methods=['GET'])
def get_order(order_id):
    order = orders.get(order_id)
    if order:
        return jsonify(order)
    return jsonify({"error": "Order not found"}), 404


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _call(service: str, method: str, url: str, **kwargs):
    """Make an HTTP call to another service, translating failures."""
    try:
        return requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.exceptions.Timeout:
        raise ServiceUnavailableError(service, f"{service} service timed out")
    except requests.exceptions.RequestException:
        raise ServiceUnavailableError(service, f"{service} service is unavailable")


def get_user_object(user_id: int):
    response = _call('user', 'GET', f'{USER_SERVICE_URL}/{user_id}')
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ServiceUnavailableError('user', 'user service returned an unexpected response')
    return response.json()


def get_product_object(product_id: int):
    response = _call('product', 'GET', f'{PRODUCT_SERVICE_URL}/{product_id}')
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise ServiceUnavailableError('product', 'product service returned an unexpected response')
    return response.json()


def update_stock(product_id: int, stock: int):
    response = _call('product', 'PUT', f'{PRODUCT_SERVICE_URL}/{product_id}/stock',
                     json={"stock": stock})
    if response.status_code != 200:
        raise ServiceUnavailableError('product', 'could not update product stock')
    return response.json()


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5033, debug=True)
