from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for
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
    """
    JSON API: { pid: int, quantity: int (opt), seller_id: int (opt) }
    """
    data = request.get_json() or {}
    try:
        pid = int(data.get("pid"))
    except Exception:
        return jsonify({"error": "Product ID required and must be integer"}), 400

    try:
        quantity = max(1, int(data.get("quantity", 1)))
    except Exception:
        quantity = 1

    seller_id = data.get("seller_id")
    if seller_id is not None and seller_id != '':
        try:
            seller_id = int(seller_id)
        except Exception:
            return jsonify({"error": "seller_id must be integer"}), 400
    else:
        seller_id = None

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
    data = request.get_json() or {}
    pid = data.get("pid")
    seller_id = data.get("seller_id")
    try:
        pid = int(pid); seller_id = int(seller_id)
    except Exception:
        return jsonify({"error": "Product ID and seller ID required and must be integers"}), 400
    try:
        quantity = max(1, int(data.get("quantity") or 1))
    except Exception:
        quantity = 1

    db = current_app.db
    db.execute("""
      UPDATE CartItems SET quantity=:quantity WHERE uid=:uid AND pid=:pid AND seller_id=:seller_id
    """, uid=current_user.id, pid=pid, seller_id=seller_id, quantity=quantity)
    return jsonify({"success": True})

@cart_bp.route('/api/cart/remove', methods=['POST'])
@login_required
def remove_from_cart():
    data = request.get_json() or {}
    pid = data.get("pid"); seller_id = data.get("seller_id")
    try:
        pid = int(pid); seller_id = int(seller_id)
    except Exception:
        return jsonify({"error": "Product ID and seller ID required and must be integers"}), 400
    db = current_app.db
    db.execute("""
      DELETE FROM CartItems WHERE uid=:uid AND pid=:pid AND seller_id=:seller_id
    """, uid=current_user.id, pid=pid, seller_id=seller_id)
    return jsonify({"success": True})

# Form-friendly add endpoint (for product_detail HTML form)
@cart_bp.route('/add', methods=['POST'])
@login_required
def add_to_cart_form():
    """
    Accepts form POSTs from product detail pages (pid, seller_id optional, qty optional)
    and redirects back to referrer or product page.
    """
    try:
        pid = int(request.form.get('pid'))
    except Exception:
        return redirect(request.referrer or url_for('products_api.product_browser'))

    qty = 1
    try:
        qty = max(1, int(request.form.get('qty', 1)))
    except Exception:
        qty = 1

    seller_id = request.form.get('seller_id')
    if seller_id:
        try:
            seller_id = int(seller_id)
        except Exception:
            seller_id = None
    else:
        seller_id = None

    if not seller_id:
        seller_id = get_seller_id_for_product(pid)
        if not seller_id:
            # no seller with stock
            return redirect(request.referrer or url_for('products_api.product_detail', pid=pid))

    db = current_app.db
    try:
        db.execute("""
          INSERT INTO CartItems (uid, pid, seller_id, quantity)
          VALUES (:uid, :pid, :seller_id, :quantity)
          ON CONFLICT (uid, pid, seller_id) DO UPDATE 
             SET quantity = CartItems.quantity + :quantity
        """, uid=current_user.id, pid=pid, seller_id=seller_id, quantity=qty)
    except Exception:
        current_app.logger.exception("Error adding to cart (form)")
        return redirect(request.referrer or url_for('products_api.product_detail', pid=pid))

    return redirect(request.referrer or url_for('cart.cart_page'))

# Transactional checkout
@cart_bp.route('/api/cart/checkout', methods=['POST'])
@login_required
def checkout_api():
    """
    Transactional checkout:
      - locks and decrements inventory rows (ensures enough stock)
      - creates Orders row
      - creates OrderItems rows
      - deletes CartItems for the user
    """
    db = current_app.db
    uid = current_user.id

    cart_items = db.execute("""
      SELECT CartItems.pid, CartItems.seller_id, COALESCE(Inventory.seller_price, Products.price) as price, CartItems.quantity
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory ON CartItems.seller_id = Inventory.seller_id AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :uid
    """, uid=uid)

    if not cart_items:
        return jsonify({"error": "Cart is empty"}), 400

    try:
        # Start transaction
        db.execute("BEGIN;")

        total_amount = 0.0
        order_rows = []
        for row in cart_items:
            pid, seller_id, price, qty = row
            qty = int(qty)
            price = float(price) if price is not None else 0.0

            if not seller_id:
                seller_id = get_seller_id_for_product(pid)
                if not seller_id:
                    db.execute("ROLLBACK;")
                    return jsonify({"error": f"No seller available for product {pid}"}), 400

            update_res = db.execute("""
UPDATE Inventory
SET quantity = quantity - :qty
WHERE seller_id = :seller_id AND product_id = :pid AND quantity >= :qty
RETURNING quantity;
""", seller_id=seller_id, pid=pid, qty=qty)

            if not update_res:
                db.execute("ROLLBACK;")
                return jsonify({"error": f"Insufficient stock for product {pid} from seller {seller_id}"}), 400

            total_amount += price * qty
            order_rows.append({'product_id': pid, 'seller_id': seller_id, 'quantity': qty, 'price': price})

        # Create order
        order_res = db.execute("""
INSERT INTO Orders (user_id, total_amount)
VALUES (:uid, :total)
RETURNING id;
""", uid=uid, total=round(total_amount, 2))
        order_id = order_res[0][0]

        # Insert order items
        for item in order_rows:
            db.execute("""
INSERT INTO OrderItems (order_id, product_id, seller_id, quantity, price)
VALUES (:order_id, :product_id, :seller_id, :quantity, :price)
""", order_id=order_id, product_id=item['product_id'], seller_id=item['seller_id'], quantity=item['quantity'], price=item['price'])

        # Remove items from cart
        db.execute("DELETE FROM CartItems WHERE uid = :uid", uid=uid)

        # Commit
        db.execute("COMMIT;")

        return jsonify({"success": True, "order_id": order_id, "total": round(total_amount, 2)})
    except Exception:
        current_app.logger.exception("Checkout transaction failed")
        try:
            db.execute("ROLLBACK;")
        except Exception:
            pass
        return jsonify({"error": "Checkout failed"}), 500

@cart_bp.route('/cart')
@login_required
def cart_page():
    return render_template('cart.html')