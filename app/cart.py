from flask import Blueprint, request, jsonify, current_app, render_template
from flask_login import current_user, login_required

cart_bp = Blueprint('cart', __name__)

def get_seller_id_for_product(pid):
    db = current_app.db
    seller_row = db.execute("""
        SELECT seller_id FROM Inventory WHERE product_id = :pid AND quantity > 0 ORDER BY seller_id LIMIT 1
    """, pid=pid)
    if seller_row:
        return seller_row[0][0]
    return None

@cart_bp.route('/api/cart', methods=['GET'])
@login_required
def get_cart():
    db = current_app.db
    user_id = current_user.id
    query = """
      SELECT CartItems.pid, CartItems.seller_id, Products.name, 
             COALESCE(Inventory.seller_price, Products.price) as price, CartItems.quantity
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory ON CartItems.seller_id = Inventory.seller_id AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :user_id
    """
    items = db.execute(query, user_id=user_id)
    columns = ['pid', 'seller_id', 'name', 'price', 'quantity']
    return jsonify([dict(zip(columns, row)) for row in items])

@cart_bp.route('/api/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    data = request.get_json()
    pid = data.get("pid")
    quantity = int(data.get("quantity", 1))
    if not pid:
        return jsonify({"error": "Product ID required"}), 400
    seller_id = data.get("seller_id")
    if not seller_id:
        seller_id = get_seller_id_for_product(pid)
        if not seller_id:
            return jsonify({"error": "No seller with stock for product"}), 404
    db = current_app.db
    db.execute("""
      INSERT INTO CartItems (uid, pid, seller_id, quantity)
      VALUES (:uid, :pid, :seller_id, :quantity)
      ON CONFLICT (uid, pid, seller_id) DO UPDATE 
         SET quantity = CartItems.quantity + :quantity
    """, uid=current_user.id, pid=pid, seller_id=seller_id, quantity=quantity)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/update', methods=['POST'])
@login_required
def update_cart():
    data = request.get_json()
    pid, seller_id = data.get("pid"), data.get("seller_id")
    quantity = int(data.get("quantity") or 1)
    if not pid or not seller_id:
        return jsonify({"error": "Product ID and seller ID required"}), 400
    db = current_app.db
    db.execute("""
      UPDATE CartItems SET quantity=:quantity WHERE uid=:uid AND pid=:pid AND seller_id=:seller_id
    """, uid=current_user.id, pid=pid, seller_id=seller_id, quantity=quantity)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/remove', methods=['POST'])
@login_required
def remove_from_cart():
    data = request.get_json()
    pid, seller_id = data.get("pid"), data.get("seller_id")
    if not pid or not seller_id:
        return jsonify({"error": "Product ID and seller ID required"}), 400
    db = current_app.db
    db.execute("""
      DELETE FROM CartItems WHERE uid=:uid AND pid=:pid AND seller_id=:seller_id
    """, uid=current_user.id, pid=pid, seller_id=seller_id)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/checkout', methods=['POST'])
@login_required
def checkout():
    db = current_app.db
    cart_items = db.execute("""
      SELECT CartItems.pid, CartItems.seller_id, COALESCE(Inventory.seller_price, Products.price) as price, CartItems.quantity
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory ON CartItems.seller_id = Inventory.seller_id AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :uid
    """, uid=current_user.id)
    if not cart_items:
        return jsonify({"error": "Cart is empty"}), 400
    # Insert order and order items here (TODO)
    db.execute("DELETE FROM CartItems WHERE uid = :uid", uid=current_user.id)
    return jsonify({"success": True, "message": "Checkout successful."})

@cart_bp.route('/cart')
@login_required
def cart_page():
    return render_template('cart.html')