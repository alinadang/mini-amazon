from flask import Blueprint, request, jsonify, current_app

sellers_bp = Blueprint('sellers', __name__)

@sellers_bp.route('/api/seller_inventory', methods=['GET'])
def get_seller_inventory():
    seller_id = request.args.get('seller_id')
    if not seller_id:
        return jsonify({"error": "seller_id required"}), 400

    db = current_app.db
    # returns product id, name, base price, seller price, quantity, and whether product is available
    # shows only in-stock items currently
    query = """
        SELECT p.id, p.name, p.price AS base_price, i.seller_price, i.quantity, p.available
        FROM Inventory i
        JOIN Products p ON i.product_id = p.id
        WHERE i.seller_id = :seller_id AND i.quantity > 0
        ORDER BY p.name
    """
    try:
        items = db.execute(query, seller_id=int(seller_id))
    except Exception as e:
        current_app.logger.exception("DB error fetching seller inventory")
        return jsonify({"error": "database_error", "detail": str(e)}), 500

    columns = ['id', 'name', 'base_price', 'seller_price', 'quantity', 'available']
    return jsonify([dict(zip(columns, row)) for row in items])