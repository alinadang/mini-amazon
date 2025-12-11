from flask import (
    Blueprint, request, jsonify, current_app,
    render_template, redirect, url_for, flash
)
from flask_login import current_user, login_required
from .users import get_seller_statistics, get_seller_reviews

sellers_bp = Blueprint('sellers', __name__)


# ============================================================================
# Helper: has this user ever bought from this seller?
# ============================================================================
def user_has_purchased_from_seller(user_id, seller_id):
    """
    Return True if this user has at least one order that includes
    an item sold by seller_id.
    """
    rows = current_app.db.execute("""
        SELECT COUNT(*)
        FROM Orders o
        JOIN OrderItems oi ON o.id = oi.order_id
        WHERE o.user_id = :uid
          AND oi.seller_id = :sid
    """, uid=user_id, sid=seller_id)

    return rows[0][0] > 0



# ============================================================================
# Inventory API (used by seller_profile.js)
# ============================================================================
@sellers_bp.route('/api/seller_inventory', methods=['GET'])
def seller_inventory():
    seller_id = request.args.get('seller_id', type=int)
    if seller_id is None:
        return jsonify({"error": "seller_id required"}), 400

    db = current_app.db
    query = """
        SELECT p.id AS product_id,
               p.name,
               p.price AS base_price,
               i.seller_price,
               i.quantity,
               p.available
        FROM Inventory i
        JOIN Products p ON i.product_id = p.id
        WHERE i.seller_id = :seller_id
        ORDER BY p.id
    """
    rows = db.execute(query, seller_id=seller_id)
    cols = ['product_id', 'name', 'base_price', 'seller_price',
            'quantity', 'available']
    results = [dict(zip(cols, row)) for row in rows]

    # normalize/serialize for JSON
    for r in results:
        r['id'] = r.pop('product_id')
        av = r.get('available')
        if isinstance(av, bool):
            r['available'] = av
        else:
            r['available'] = str(av).lower() in ('t', 'true', '1', 'yes')

        if r.get('base_price') is not None:
            try:
                r['base_price'] = float(r['base_price'])
            except Exception:
                pass

        if r.get('seller_price') is not None:
            try:
                r['seller_price'] = float(r['seller_price'])
            except Exception:
                pass

    return jsonify(results)


# ============================================================================
# Sellers list
# ============================================================================
@sellers_bp.route('/sellers')
def sellers_list():
    db = current_app.db
    rows = db.execute("""
        SELECT u.id, u.email, u.firstname, u.lastname,
               COUNT(i.product_id) AS item_count
        FROM Users u
        LEFT JOIN Inventory i ON u.id = i.seller_id
        GROUP BY u.id, u.email, u.firstname, u.lastname
        ORDER BY u.id
        LIMIT 200
    """)
    sellers = [
        dict(
            id=r[0],
            email=r[1],
            firstname=r[2],
            lastname=r[3],
            item_count=r[4],
        )
        for r in rows
    ]
    return render_template('sellers_list.html', sellers=sellers)


# ============================================================================
# Seller profile: inventory + stats + review eligibility
# ============================================================================
from .users import get_seller_statistics, get_seller_reviews
# ^ make sure this import is at the top of sellers.py

@sellers_bp.route('/sellers/<int:seller_id>')
def seller_profile(seller_id):
    db = current_app.db

    # basic seller info
    rows = db.execute("""
        SELECT id, email, firstname, lastname
        FROM Users
        WHERE id = :id
    """, id=seller_id)
    if not rows:
        return "Seller not found", 404

    u = rows[0]
    seller = {
        'id': u[0],
        'email': u[1],
        'firstname': u[2],
        'lastname': u[3],
    }

    # summary stats (products, orders, revenue, etc.)
    seller_stats = get_seller_statistics(seller_id)

    # ---------- get SELLER reviews via helper (uses SellerReviews) ----------
    reviews = get_seller_reviews(seller_id)

    # compute seller_avg_rating and seller_review_count for template
    if reviews:
        seller_review_count = len(reviews)
        seller_avg_rating = sum(r['rating'] for r in reviews) / seller_review_count
    else:
        seller_review_count = 0
        seller_avg_rating = None

    # ---- seller-review eligibility + existing seller-review for THIS viewer ----
    can_review_seller = False
    existing_seller_review = None

    if current_user.is_authenticated and current_user.id != seller_id:
        # only allow review if user has purchased from this seller
        can_review_seller = user_has_purchased_from_seller(
            current_user.id,
            seller_id
        )

        if can_review_seller:
            existing_rows = db.execute("""
                SELECT id, rating, comment
                FROM SellerReviews
                WHERE seller_id = :sid AND user_id = :uid
                LIMIT 1
            """, sid=seller_id, uid=current_user.id)

            if existing_rows:
                r = existing_rows[0]
                existing_seller_review = {
                    "id": r[0],
                    "rating": r[1],
                    "comment": r[2],
                }

    return render_template(
        'seller_profile.html',
        seller=seller,
        seller_stats=seller_stats,
        reviews=reviews,                         # <-- used by {% if reviews %}
        can_review_seller=can_review_seller,
        existing_seller_review=existing_seller_review,
        seller_avg_rating=seller_avg_rating,     # <-- Avg Rating tile
        seller_review_count=seller_review_count  # <-- # of Reviews tile
    )






# quick link "My seller dashboard"
@sellers_bp.route('/seller')
@login_required
def my_seller_dashboard():
    return redirect(url_for('.seller_profile', seller_id=current_user.id))


# ============================================================================
# Inventory mutations
# ============================================================================
@sellers_bp.route('/api/seller_inventory/add', methods=['POST'])
@login_required
def add_to_inventory():
    """Add a product to seller's inventory"""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 0)
    seller_price = data.get('seller_price')

    if not product_id:
        return jsonify({"error": "product_id required"}), 400

    if quantity < 0:
        return jsonify({"error": "quantity cannot be negative"}), 400

    if seller_price is not None and seller_price < 0:
        return jsonify({"error": "price cannot be negative"}), 400

    db = current_app.db
    try:
        # Check if product exists and is available
        product_check = list(db.execute(
            "SELECT id, available FROM Products WHERE id = :pid",
            pid=product_id
        ))
        if not product_check:
            return jsonify({"error": "Product does not exist"}), 404

        if not product_check[0][1]:
            return jsonify({"error": "Product is not available for sale"}), 400

        # Check if seller already has this product
        existing = list(db.execute("""
            SELECT seller_id FROM Inventory
            WHERE seller_id = :seller_id AND product_id = :product_id
        """, seller_id=current_user.id, product_id=product_id))

        if existing:
            return jsonify({
                "error": "Product already in your inventory. Use update to modify quantity or price."
            }), 409

        db.execute("""
            INSERT INTO Inventory (seller_id, product_id, quantity, seller_price)
            VALUES (:seller_id, :product_id, :quantity, :seller_price)
            ON CONFLICT (seller_id, product_id)
            DO UPDATE SET quantity = :quantity, seller_price = :seller_price
        """, seller_id=current_user.id, product_id=product_id,
           quantity=quantity, seller_price=seller_price)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sellers_bp.route('/api/seller_inventory/update', methods=['POST'])
@login_required
def update_inventory():
    """Update quantity or price for existing inventory item"""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    seller_price = data.get('seller_price')

    if not product_id:
        return jsonify({"error": "product_id required"}), 400

    if quantity is not None and quantity < 0:
        return jsonify({"error": "quantity cannot be negative"}), 400

    if seller_price is not None and seller_price < 0:
        return jsonify({"error": "price cannot be negative"}), 400

    db = current_app.db
    try:
        db.execute("""
            UPDATE Inventory
            SET quantity = :quantity, seller_price = :seller_price
            WHERE seller_id = :seller_id AND product_id = :product_id
        """, seller_id=current_user.id, product_id=product_id,
           quantity=quantity, seller_price=seller_price)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sellers_bp.route('/api/seller_inventory/remove', methods=['POST'])
@login_required
def remove_from_inventory():
    """Remove a product from seller's inventory"""
    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({"error": "product_id required"}), 400

    db = current_app.db
    try:
        db.execute("""
            DELETE FROM Inventory
            WHERE seller_id = :seller_id AND product_id = :product_id
        """, seller_id=current_user.id, product_id=product_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# Seller REVIEWS: add / edit / delete
# ============================================================================
@sellers_bp.route('/sellers/<int:seller_id>/review/new', methods=['GET', 'POST'])
@login_required
def add_seller_review(seller_id):
    db = current_app.db

    # can't review yourself
    if current_user.id == seller_id:
        flash("You cannot review yourself as a seller.", "error")
        return redirect(url_for('sellers.seller_profile', seller_id=seller_id))

    # must have purchased from this seller
    if not user_has_purchased_from_seller(current_user.id, seller_id):
        flash("You can only review sellers you've purchased from.", "error")
        return redirect(url_for('sellers.seller_profile', seller_id=seller_id))

    # if a review already exists, send them to edit instead
    existing = list(db.execute("""
        SELECT id, rating, comment
        FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
        LIMIT 1
    """, sid=seller_id, uid=current_user.id))
    if existing:
        return redirect(url_for('sellers.edit_seller_review', seller_id=seller_id))

    if request.method == 'POST':
        rating = int(request.form.get('rating', 0))
        comment = request.form.get('comment', '').strip() or None

        if rating < 1 or rating > 5:
            flash("Rating must be between 1 and 5.", "error")
            return redirect(url_for('sellers.add_seller_review', seller_id=seller_id))

        db.execute("""
            INSERT INTO SellerReviews (seller_id, user_id, rating, comment)
            VALUES (:sid, :uid, :rating, :comment)
        """, sid=seller_id, uid=current_user.id,
           rating=rating, comment=comment)
        flash("Your review has been submitted.", "success")
        return redirect(url_for('sellers.seller_profile', seller_id=seller_id))

    # GET -> show blank form
    return render_template(
        'seller_review_form.html',
        seller_id=seller_id,
        mode='create',
        review=None
    )


@sellers_bp.route('/sellers/<int:seller_id>/review/edit', methods=['GET', 'POST'])
@login_required
def edit_seller_review(seller_id):
    db = current_app.db

    existing = list(db.execute("""
        SELECT id, rating, comment
        FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
        LIMIT 1
    """, sid=seller_id, uid=current_user.id))

    if not existing:
        flash("You don't have a review for this seller yet.", "error")
        return redirect(url_for('sellers.add_seller_review', seller_id=seller_id))

    review_row = existing[0]
    review = {
        'id': review_row[0],
        'rating': review_row[1],
        'comment': review_row[2] or ''
    }

    if request.method == 'POST':
        rating = int(request.form.get('rating', 0))
        comment = request.form.get('comment', '').strip() or None

        if rating < 1 or rating > 5:
            flash("Rating must be between 1 and 5.", "error")
            return redirect(url_for('sellers.edit_seller_review', seller_id=seller_id))

        db.execute("""
            UPDATE SellerReviews
            SET rating = :rating,
                comment = :comment,
                date_reviewed = NOW()
            WHERE id = :id AND seller_id = :sid AND user_id = :uid
        """, id=review['id'], sid=seller_id, uid=current_user.id,
           rating=rating, comment=comment)
        flash("Your review has been updated.", "success")
        return redirect(url_for('sellers.seller_profile', seller_id=seller_id))

    # GET -> render form with existing values
    return render_template(
        'seller_review_form.html',
        seller_id=seller_id,
        mode='edit',
        review=review
    )


@sellers_bp.route('/sellers/<int:seller_id>/review/delete', methods=['POST'])
@login_required
def delete_seller_review(seller_id):
    db = current_app.db
    db.execute("""
        DELETE FROM SellerReviews
        WHERE seller_id = :sid AND user_id = :uid
    """, sid=seller_id, uid=current_user.id)
    flash("Your review has been deleted.", "success")
    return redirect(url_for('sellers.seller_profile', seller_id=seller_id))


# ============================================================================
# Seller orders + fulfill + analytics
# ============================================================================
@sellers_bp.route('/api/seller_orders', methods=['GET'])
@login_required
def seller_orders_api():
    """Get all orders for this seller"""
    status_filter = request.args.get('status', 'all')

    db = current_app.db

    query = """
        WITH seller_order_items AS (
            SELECT oi.order_id,
                   COUNT(*) as seller_item_count,
                   SUM(CASE WHEN oi.fulfillment_status = 'fulfilled'
                            THEN 1 ELSE 0 END) as fulfilled_count
            FROM orderitems oi
            WHERE oi.seller_id = :seller_id
            GROUP BY oi.order_id
        )
        SELECT o.id AS order_id,
               o.order_date,
               o.total_amount,
               u.firstname || ' ' || u.lastname AS buyer_name,
               u.email AS buyer_email,
               COALESCE(u.address, 'No address provided') AS buyer_address,
               soi.seller_item_count,
               CASE
                   WHEN soi.fulfilled_count = soi.seller_item_count THEN 'fulfilled'
                   WHEN soi.fulfilled_count = 0 THEN 'pending'
                   ELSE 'partial'
               END as fulfillment_status
        FROM orders o
        JOIN seller_order_items soi ON o.id = soi.order_id
        JOIN users u ON o.user_id = u.id
        WHERE o.status != 'cancelled'
    """

    if status_filter == 'pending':
        query += " AND soi.fulfilled_count < soi.seller_item_count"
    elif status_filter == 'fulfilled':
        query += " AND soi.fulfilled_count = soi.seller_item_count"

    query += " ORDER BY o.order_date DESC"

    rows = db.execute(query, seller_id=current_user.id)

    orders = []
    for row in rows:
        orders.append({
            'order_id': row[0],
            'order_date': str(row[1]),
            'total_amount': float(row[2]) if row[2] else 0,
            'buyer_name': row[3],
            'buyer_email': row[4],
            'buyer_address': row[5],
            'item_count': row[6],
            'status': row[7]
        })

    return jsonify(orders)


@sellers_bp.route('/api/order_items/<int:order_id>', methods=['GET'])
@login_required
def get_order_items(order_id):
    """Get line items for a specific order (only this seller's items)"""
    db = current_app.db
    rows = db.execute("""
        SELECT oi.id, oi.product_id, p.name, oi.quantity, oi.price,
               oi.fulfillment_status, oi.fulfilled_date
        FROM OrderItems oi
        JOIN Products p ON oi.product_id = p.id
        WHERE oi.order_id = :order_id AND oi.seller_id = :seller_id
        ORDER BY oi.id
    """, order_id=order_id, seller_id=current_user.id)

    items = []
    for row in rows:
        items.append({
            'id': row[0],
            'product_id': row[1],
            'name': row[2],
            'quantity': row[3],
            'price': float(row[4]) if row[4] else 0,
            'fulfillment_status': row[5],
            'fulfilled_date': str(row[6]) if row[6] else None
        })

    return jsonify(items)


@sellers_bp.route('/api/fulfill_item', methods=['POST'])
@login_required
def fulfill_item():
    """Mark an order item as fulfilled"""
    data = request.get_json()
    item_id = data.get('item_id')

    if not item_id:
        return jsonify({"error": "item_id required"}), 400

    db = current_app.db
    try:
        # First verify this item belongs to this seller
        check = list(db.execute("""
            SELECT id FROM OrderItems
            WHERE id = :item_id AND seller_id = :seller_id
        """, item_id=item_id, seller_id=current_user.id))

        if not check:
            return jsonify({"error": "Item not found or unauthorized"}), 404

        db.execute("""
            UPDATE OrderItems
            SET fulfillment_status = 'fulfilled',
                fulfilled_date = CURRENT_TIMESTAMP
            WHERE id = :item_id AND seller_id = :seller_id
        """, item_id=item_id, seller_id=current_user.id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sellers_bp.route('/seller/orders')
@login_required
def seller_orders_page():
    """Page for sellers to view and fulfill orders"""
    return render_template('seller_orders.html')


@sellers_bp.route('/api/seller_analytics', methods=['GET'])
@login_required
def seller_analytics():
    """Get analytics data for seller's products"""
    db = current_app.db

    try:
        # 1. Top selling products by quantity
        top_products = list(db.execute("""
            SELECT p.id, p.name,
                   SUM(oi.quantity) as total_sold,
                   COUNT(DISTINCT oi.order_id) as order_count,
                   SUM(oi.quantity * oi.price) as revenue
            FROM orderitems oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.seller_id = :seller_id
            GROUP BY p.id, p.name
            ORDER BY total_sold DESC
            LIMIT 10
        """, seller_id=current_user.id))

        # 2. Sales over time (last 30 days)
        sales_timeline = list(db.execute("""
            SELECT DATE(o.order_date) as sale_date,
                   COUNT(DISTINCT oi.order_id) as order_count,
                   SUM(oi.quantity) as items_sold,
                   SUM(oi.quantity * oi.price) as daily_revenue
            FROM orderitems oi
            JOIN orders o ON oi.order_id = o.id
            WHERE oi.seller_id = :seller_id
              AND o.order_date >= CURRENT_DATE - 30
            GROUP BY DATE(o.order_date)
            ORDER BY sale_date ASC
        """, seller_id=current_user.id))

        # 3. Fulfillment status breakdown
        fulfillment_stats = list(db.execute("""
            SELECT oi.fulfillment_status,
                   COUNT(*) as count,
                   SUM(oi.quantity * oi.price) as total_value
            FROM orderitems oi
            WHERE oi.seller_id = :seller_id
            GROUP BY oi.fulfillment_status
        """, seller_id=current_user.id))

        # 4. Inventory status
        inventory_stats = list(db.execute("""
            SELECT
                COUNT(*) as total_products,
                SUM(quantity) as total_inventory,
                AVG(quantity) as avg_quantity,
                COUNT(CASE WHEN quantity = 0 THEN 1 END) as out_of_stock
            FROM inventory
            WHERE seller_id = :seller_id
        """, seller_id=current_user.id))

        return jsonify({
            'top_products': [
                {
                    'id': row[0],
                    'name': row[1],
                    'total_sold': int(row[2]) if row[2] else 0,
                    'order_count': int(row[3]) if row[3] else 0,
                    'revenue': float(row[4]) if row[4] else 0
                }
                for row in top_products
            ],
            'sales_timeline': [
                {
                    'date': str(row[0]),
                    'order_count': int(row[1]) if row[1] else 0,
                    'items_sold': int(row[2]) if row[2] else 0,
                    'revenue': float(row[3]) if row[3] else 0
                }
                for row in sales_timeline
            ],
            'fulfillment_stats': [
                {
                    'status': row[0],
                    'count': int(row[1]) if row[1] else 0,
                    'value': float(row[2]) if row[2] else 0
                }
                for row in fulfillment_stats
            ],
            'inventory_stats': {
                'total_products': int(inventory_stats[0][0]) if inventory_stats and inventory_stats[0][0] else 0,
                'total_inventory': int(inventory_stats[0][1]) if inventory_stats and inventory_stats[0][1] else 0,
                'avg_quantity': float(inventory_stats[0][2]) if inventory_stats and inventory_stats[0][2] else 0,
                'out_of_stock': int(inventory_stats[0][3]) if inventory_stats and inventory_stats[0][3] else 0
            }
        })
    except Exception as e:
        print(f"Analytics error: {e}")
        return jsonify({"error": str(e)}), 500


@sellers_bp.route('/seller/analytics')
@login_required
def seller_analytics_page():
    """Analytics dashboard for sellers"""
    return render_template('seller_analytics.html')
