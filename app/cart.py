from flask import Blueprint, request, jsonify, current_app

cart_bp = Blueprint('cart', __name__)

@cart_bp.route('/api/cart', methods=['GET'])
def get_cart():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    db = current_app.db
    query = """
        SELECT Products.id, Products.name, Products.price, CartItems.quantity
        FROM CartItems
        JOIN Products ON CartItems.pid = Products.id
        WHERE CartItems.uid = :user_id
    """
    items = db.execute(query, user_id=int(user_id))
    columns = ['id', 'name', 'price', 'quantity']
    return jsonify([dict(zip(columns, row)) for row in items])
