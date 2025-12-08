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
def add_to_cart():
    """
    Accept either JSON (AJAX) or form-encoded submissions.
    - JSON example: {"pid": 123, "quantity": 2, "seller_id": 5}
    - Form example from product_detail: pid, qty (or quantity), seller_id

    Behavior:
      - If user not logged in:
          * AJAX/JSON => return 401 + {"error":"login_required","login_url": ...}
          * form => redirect to login page (with next)
      - On success:
          * AJAX/JSON => return {"success": True, "remaining": <inventory_qty>}
          * form => redirect back (existing flow)
    """
    db = current_app.db

    # Not logged in -> return machine-friendly or redirect for forms
    if not current_user.is_authenticated:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # return URL for login so frontend can redirect or show a login popup
            return jsonify({
                "error": "login_required",
                "login_url": url_for('users.login', _external=False)
            }), 401
        return redirect(url_for('users.login', next=request.url))

    data = request.get_json(silent=True) or request.form or request.values or {}

    pid_val = data.get('pid') or data.get('product_id')
    if pid_val is None or str(pid_val).strip() == '':
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Product ID required"}), 400
        return redirect(request.referrer or url_for('products_api.product_browser'))

    try:
        pid = int(pid_val)
    except Exception:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Invalid product id"}), 400
        return redirect(request.referrer or url_for('products_api.product_browser'))

    qty_raw = data.get('quantity') or data.get('qty') or 1
    try:
        quantity = max(1, int(qty_raw))
    except Exception:
        quantity = 1

    # seller_id (optional)
    seller_id_val = data.get('seller_id')
    seller_id = None
    if seller_id_val not in (None, '', []):
        try:
            seller_id = int(seller_id_val)
        except Exception:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "seller_id must be integer"}), 400
            return redirect(request.referrer or url_for('products_api.product_detail', pid=pid))
    else:
        seller_id = None

    if seller_id is None:
        seller_id = get_seller_id_for_product(pid)
        if seller_id is None:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({"error": "No seller with stock for product"}), 404
            return redirect(request.referrer or url_for('products_api.product_detail', pid=pid))

    try:
        db.execute("""
          INSERT INTO CartItems (uid, pid, seller_id, quantity)
          VALUES (:uid, :pid, :seller_id, :quantity)
          ON CONFLICT (uid, pid, seller_id) DO UPDATE 
             SET quantity = CartItems.quantity + :quantity
        """, uid=current_user.id, pid=pid, seller_id=seller_id, quantity=quantity)
    except Exception:
        current_app.logger.exception("Error adding to cart")
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"error": "Could not add to cart"}), 500
        return redirect(request.referrer or url_for('products_api.product_detail', pid=pid))

    inv_row = db.execute("""
        SELECT quantity FROM Inventory WHERE seller_id = :seller_id AND product_id = :pid
    """, seller_id=seller_id, pid=pid)
    remaining = inv_row[0][0] if inv_row else None

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "remaining": int(remaining) if remaining is not None else None})

    return redirect(request.referrer or url_for('cart.cart_page'))


@cart_bp.route('/api/cart/update', methods=['POST'])
@login_required
def update_cart():
    data = request.get_json(silent=True) or request.form or request.values or {}
    pid = data.get("pid")
    seller_id = data.get("seller_id")
    try:
        pid = int(pid); seller_id = int(seller_id)
    except Exception:
        return jsonify({"error": "Product ID and seller ID required and must be integers"}), 400
    try:
        quantity = max(1, int(data.get("quantity") or data.get("qty") or 1))
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
    data = request.get_json(silent=True) or request.form or request.values or {}
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

    if seller_id is None:
        seller_id = get_seller_id_for_product(pid)
        if seller_id is None:
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

            if seller_id is None:
                seller_id = get_seller_id_for_product(pid)
                if seller_id is None:
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