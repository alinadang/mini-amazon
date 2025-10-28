from flask import Blueprint, request, jsonify, current_app, render_template, redirect, url_for
from flask_login import current_user, login_required

sellers_bp = Blueprint('sellers', __name__)

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
    cols = ['product_id', 'name', 'base_price', 'seller_price', 'quantity', 'available']
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


@sellers_bp.route('/sellers')
def sellers_list():
    db = current_app.db
    rows = db.execute("""
        SELECT u.id, u.email, u.firstname, u.lastname, COUNT(i.product_id) AS item_count
        FROM Users u
        LEFT JOIN Inventory i ON u.id = i.seller_id
        GROUP BY u.id, u.email, u.firstname, u.lastname
        ORDER BY u.id
        LIMIT 200
    """)
    sellers = [dict(id=r[0], email=r[1], firstname=r[2], lastname=r[3], item_count=r[4]) for r in rows]
    return render_template('sellers_list.html', sellers=sellers)


@sellers_bp.route('/sellers/<int:seller_id>')
def seller_profile(seller_id):
    db = current_app.db
    row = list(db.execute("SELECT id, email, firstname, lastname FROM Users WHERE id = :id", id=seller_id))
    if not row:
        return "Seller not found", 404
    u = row[0]
    seller = {'id': u[0], 'email': u[1], 'firstname': u[2], 'lastname': u[3]}
    # The template will fetch inventory via the /api/seller_inventory endpoint
    return render_template('seller_profile.html', seller=seller)


@sellers_bp.route('/seller')
@login_required
def my_seller_dashboard():
    return redirect(url_for('.seller_profile', seller_id=current_user.id))
