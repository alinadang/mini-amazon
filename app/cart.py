from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for
from flask_login import current_user, login_required

cart_bp = Blueprint('cart', __name__)

def get_seller_id_for_product(pid):
    db = current_app.db
    seller_row = db.execute("""
        SELECT seller_id FROM Inventory
        WHERE product_id = :pid AND quantity > 0
        ORDER BY seller_id LIMIT 1
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
      SELECT
          CartItems.pid,
          CartItems.seller_id,
          Products.name,
          COALESCE(Inventory.seller_price, Products.price) AS price,
          CartItems.quantity,
          Products.image_url
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory
             ON CartItems.seller_id = Inventory.seller_id
            AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :user_id
        AND CartItems.saved = FALSE
    """
    items = db.execute(query, user_id=user_id)
    columns = ['pid', 'seller_id', 'name', 'price', 'quantity', 'image_url']
    return jsonify([dict(zip(columns, row)) for row in items])

@cart_bp.route('/api/cart/saved', methods=['GET'])
@login_required
def get_saved_cart():
    db = current_app.db
    user_id = current_user.id
    query = """
      SELECT
          CartItems.pid,
          CartItems.seller_id,
          Products.name,
          COALESCE(Inventory.seller_price, Products.price) AS price,
          CartItems.quantity,
          Products.image_url
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory
             ON CartItems.seller_id = Inventory.seller_id
            AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :user_id
        AND CartItems.saved = TRUE
    """
    items = db.execute(query, user_id=user_id)
    columns = ['pid', 'seller_id', 'name', 'price', 'quantity', 'image_url']
    return jsonify([dict(zip(columns, row)) for row in items])


@cart_bp.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    db = current_app.db

    if not current_user.is_authenticated:
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
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

@cart_bp.route('/api/cart/save', methods=['POST'])
@login_required
def save_for_later():
    db = current_app.db
    data = request.get_json(silent=True) or {}
    pid = data.get("pid")
    seller_id = data.get("seller_id")
    saved = bool(data.get("saved", True))

    try:
        pid = int(pid)
        seller_id = int(seller_id)
    except Exception:
        return jsonify({"error": "Product ID and seller ID required and must be integers"}), 400

    db.execute("""
        UPDATE CartItems
        SET saved = :saved
        WHERE uid = :uid AND pid = :pid AND seller_id = :seller_id
    """, uid=current_user.id, pid=pid, seller_id=seller_id, saved=saved)

    return jsonify({"success": True})


@cart_bp.route('/add', methods=['POST'])
@login_required
def add_to_cart_form():
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


@cart_bp.route('/api/cart/checkout', methods=['POST'])
@login_required
def checkout_api():
    db = current_app.db
    uid = current_user.id

    data = request.get_json(silent=True) or {}
    coupon = (data.get("coupon") or "").strip().upper()

    # 1. Load current cart items
    cart_items = db.execute("""
      SELECT CartItems.pid,
             CartItems.seller_id,
             COALESCE(Inventory.seller_price, Products.price) AS price,
             CartItems.quantity
      FROM CartItems
      JOIN Products ON CartItems.pid = Products.id
      LEFT JOIN Inventory
             ON CartItems.seller_id = Inventory.seller_id
            AND CartItems.pid = Inventory.product_id
      WHERE CartItems.uid = :uid
    """, uid=uid)

    if not cart_items:
        current_app.logger.debug(f"checkout: user {uid} attempted checkout with empty cart")
        return jsonify({"error": "Cart is empty"}), 400

    # 2. Rough total for early insufficient-balance check
    try:
        total_estimate = 0.0
        for row in cart_items:
            _pid, _seller_id, price, qty = row
            price = float(price) if price is not None else 0.0
            qty = int(qty)
            total_estimate += price * qty
        total_estimate = round(total_estimate, 2)
    except Exception:
        current_app.logger.exception("Failed to compute cart total")
        return jsonify({"error": "Could not compute cart total"}), 500

    # 3. Check current balance
    try:
        bal_row = db.execute(
            "SELECT COALESCE(balance,0)::numeric FROM Users WHERE id = :uid",
            uid=uid
        )
        balance = float(bal_row[0][0]) if bal_row and bal_row[0][0] is not None else 0.0
    except Exception:
        current_app.logger.exception("Could not fetch user balance")
        return jsonify({"error": "Could not fetch account balance"}), 500

    if balance < total_estimate:
        msg = (
            f"Not able to checkout: insufficient account balance "
            f"(${balance:.2f}) for cart total (${total_estimate:.2f})."
        )
        current_app.logger.debug(
            f"checkout_insufficient_balance uid={uid} balance={balance} "
            f"estimated_total={total_estimate}"
        )
        return jsonify({
            "error": "insufficient_balance",
            "message": msg,
            "balance": round(balance, 2),
            "total": round(total_estimate, 2)
        }), 400

    # 4. Transaction: lock inventory & balances, create order, update balances
    try:
        db.execute("BEGIN;")
        total_amount = 0.0
        order_rows = []
        seller_totals = {}  # seller_id -> amount to credit

        for row in cart_items:
            pid, preferred_seller_id, price, qty = row
            qty = int(qty)
            price = float(price) if price is not None else 0.0
            chosen_seller = preferred_seller_id

            # Choose seller if none stored
            if chosen_seller is None:
                alt = db.execute("""
                    SELECT seller_id,
                           COALESCE(seller_price, p.price) AS seller_price
                    FROM Inventory
                    LEFT JOIN Products p ON p.id = Inventory.product_id
                    WHERE product_id = :pid AND quantity >= :qty
                    ORDER BY seller_id
                    LIMIT 1
                """, pid=pid, qty=qty)
                if not alt:
                    db.execute("ROLLBACK;")
                    current_app.logger.debug(
                        f"checkout_no_seller pid={pid} uid={uid}"
                    )
                    return jsonify({
                        "error": "no_seller",
                        "message": f"No seller available with sufficient stock for product {pid}."
                    }), 400
                chosen_seller = alt[0][0]
                price = float(alt[0][1]) if alt[0][1] is not None else price

            # Decrement inventory for chosen seller
            update_res = db.execute("""
                UPDATE Inventory
                SET quantity = quantity - :qty
                WHERE seller_id = :seller_id
                  AND product_id = :pid
                  AND quantity >= :qty
                RETURNING quantity,
                          COALESCE(seller_price,
                                   (SELECT price FROM Products WHERE id = :pid)) AS actual_price;
            """, seller_id=chosen_seller, pid=pid, qty=qty)

            # If preferred seller fails, try alternatives
            if not update_res:
                alt_rows = db.execute("""
                    SELECT seller_id,
                           COALESCE(seller_price, p.price) AS seller_price
                    FROM Inventory
                    LEFT JOIN Products p ON p.id = Inventory.product_id
                    WHERE product_id = :pid AND quantity >= :qty
                    ORDER BY seller_id
                """, pid=pid, qty=qty)

                alt_chosen = None
                if alt_rows:
                    for ar in alt_rows:
                        try_sid = ar[0]
                        try_price = float(ar[1]) if ar[1] is not None else price
                        upd = db.execute("""
                            UPDATE Inventory
                            SET quantity = quantity - :qty
                            WHERE seller_id = :seller_id
                              AND product_id = :pid
                              AND quantity >= :qty
                            RETURNING quantity;
                        """, seller_id=try_sid, pid=pid, qty=qty)
                        if upd:
                            alt_chosen = (try_sid, try_price)
                            break

                if not alt_chosen:
                    db.execute("ROLLBACK;")
                    current_app.logger.debug(
                        f"checkout_insufficient_stock pid={pid} preferred={preferred_seller_id} uid={uid}"
                    )
                    return jsonify({
                        "error": "insufficient_stock",
                        "message": f"Insufficient stock for product {pid}."
                    }), 400

                chosen_seller, price = alt_chosen[0], alt_chosen[1]
            else:
                # Use price actually stored in inventory if present
                try:
                    db_price = update_res[0][1] if len(update_res[0]) > 1 else None
                    if db_price is not None:
                        price = float(db_price)
                except Exception:
                    pass

            # Accumulate totals
            line_total = price * qty
            total_amount += line_total
            order_rows.append({
                'product_id': pid,
                'seller_id': chosen_seller,
                'quantity': qty,
                'price': price
            })
            seller_totals[chosen_seller] = seller_totals.get(chosen_seller, 0.0) + line_total

        total_amount = round(total_amount, 2)

        # Simple coupon: SAVE10 = 10% off entire cart
        discount = 0.0
        if coupon == "SAVE10":
            discount = round(total_amount * 0.10, 2)

        total_amount = round(total_amount - discount, 2)
        if total_amount < 0:
            total_amount = 0.0

        # Lock user row and re-check balance
        bal_row_after = db.execute(
            "SELECT COALESCE(balance,0)::numeric FROM Users WHERE id = :uid FOR UPDATE",
            uid=uid
        )
        balance_after = float(bal_row_after[0][0]) if bal_row_after and bal_row_after[0][0] is not None else 0.0
        if balance_after < total_amount:
            db.execute("ROLLBACK;")
            current_app.logger.debug(
                f"checkout_balance_changed uid={uid} balance={balance_after} total_required={total_amount}"
            )
            return jsonify({
                "error": "insufficient_balance_after_select",
                "message": (
                    f"Not able to checkout: balance ${balance_after:.2f} "
                    f"is insufficient for final total ${total_amount:.2f}."
                )
            }), 400

        # Insert order
        order_res = db.execute("""
            INSERT INTO Orders (user_id, total_amount)
            VALUES (:uid, :total)
            RETURNING id;
        """, uid=uid, total=total_amount)
        order_id = order_res[0][0]

        # Insert order items
        for item in order_rows:
            db.execute("""
                INSERT INTO OrderItems (order_id, product_id, seller_id, quantity, price)
                VALUES (:order_id, :product_id, :seller_id, :quantity, :price)
            """, order_id=order_id,
                 product_id=item['product_id'],
                 seller_id=item['seller_id'],
                 quantity=item['quantity'],
                 price=item['price'])

        # Debit buyer balance
        db.execute("""
            UPDATE Users
            SET balance = balance - :amount
            WHERE id = :uid
        """, uid=uid, amount=total_amount)

        # Credit each seller
        for seller_id, seller_amount in seller_totals.items():
            db.execute("""
                UPDATE Users
                SET balance = balance + :amount
                WHERE id = :sid
            """, sid=seller_id, amount=seller_amount)

        # Empty cart
        db.execute("DELETE FROM CartItems WHERE uid = :uid", uid=uid)

        db.execute("COMMIT;")

        current_app.logger.debug(
            f"checkout_success uid={uid} order_id={order_id} total={total_amount}"
        )
        # Optional: return the buyer's new balance so frontend can show it
        new_balance = balance_after - total_amount
        return jsonify({
            "success": True,
            "order_id": order_id,
            "total": total_amount,
            "discount": discount,
            "new_balance": round(new_balance, 2)
        })
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